#!/usr/bin/env python3
"""Rename the application package name stored in a compiled resources.arsc.

Only the fixed 128-code-unit UTF-16 name in the unique 0x7f
ResTable_package chunk is changed. This module does not rewrite an APK; the
caller can extract resources.arsc, call :func:`rename_resource_package`, and
put the returned bytes into its normal build pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from typing import Any


OLD_PACKAGE = "com.xingin.xhs"
NEW_PACKAGE = "com.kirikira.rednote.fold"

RES_TABLE_TYPE = 0x0002
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
PACKAGE_NAME_UNITS = 128
PACKAGE_NAME_BYTES = PACKAGE_NAME_UNITS * 2
UINT16_MAX = 0xFFFF
UINT32_MAX = 0xFFFFFFFF


class ResourceTableError(ValueError):
    """The resource table is malformed or does not match the expected APK."""


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _chunk(data: bytes, offset: int, limit: int, label: str) -> tuple[int, int, int]:
    if offset < 0 or offset + 8 > limit:
        raise ResourceTableError(f"Truncated {label} chunk header at 0x{offset:x}")
    chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
    if header_size < 8 or chunk_size < header_size:
        raise ResourceTableError(
            f"Invalid {label} chunk sizes at 0x{offset:x}: "
            f"header={header_size}, size={chunk_size}"
        )
    if offset + chunk_size > limit:
        raise ResourceTableError(
            f"{label} chunk at 0x{offset:x} ends beyond its container"
        )
    return chunk_type, header_size, chunk_size


def _decode_package_name(field: bytes, offset: int) -> str:
    if len(field) != PACKAGE_NAME_BYTES:
        raise ResourceTableError("ResTable_package name field is not 128 UTF-16 units")
    try:
        value = field.decode("utf-16le")
    except UnicodeDecodeError as exc:
        raise ResourceTableError(
            f"Invalid UTF-16 package name at 0x{offset:x}: {exc}"
        ) from exc
    terminator = value.find("\0")
    if terminator < 0:
        raise ResourceTableError(f"Unterminated package name at 0x{offset:x}")
    if any(char != "\0" for char in value[terminator + 1 :]):
        raise ResourceTableError(
            f"Nonzero data follows the package-name terminator at 0x{offset:x}"
        )
    return value[:terminator]


def _resource_id(package_id: int, type_id: int, entry_id: int) -> int:
    if not 0 <= package_id <= 0xFF:
        raise ResourceTableError(f"Package ID out of range: {package_id}")
    if not 1 <= type_id <= 0xFF:
        raise ResourceTableError(f"Effective resource type ID out of range: {type_id}")
    if not 0 <= entry_id <= 0xFFFF:
        raise ResourceTableError(f"Resource entry ID out of range: {entry_id}")
    return (package_id << 24) | (type_id << 16) | entry_id


def _entry_indexes(
    data: bytes,
    offset: int,
    header_size: int,
    chunk_size: int,
    flags: int,
    entry_count: int,
    entries_start: int,
) -> list[int]:
    """Return populated entry indexes, checking the type chunk's offset table."""
    if entries_start < header_size or entries_start > chunk_size:
        raise ResourceTableError(
            f"Invalid entriesStart={entries_start} for type chunk at 0x{offset:x}"
        )
    table_start = offset + header_size
    chunk_end = offset + chunk_size

    if flags & 0x01:  # ResTable_type::FLAG_SPARSE
        if flags & 0x02:
            raise ResourceTableError("A type chunk cannot be both sparse and offset16")
        table_bytes = entry_count * 4
        if header_size + table_bytes > entries_start:
            raise ResourceTableError("Sparse type-entry index exceeds entriesStart")
        indexes: list[int] = []
        for item in range(entry_count):
            pair = table_start + item * 4
            index, offset_units = struct.unpack_from("<HH", data, pair)
            indexes.append(index)
            relative_offset = offset_units * 4
            _validate_entry(data, offset, chunk_end, entries_start, relative_offset)
        if len(set(indexes)) != len(indexes) or indexes != sorted(indexes):
            raise ResourceTableError("Sparse type-entry indexes are duplicated or unordered")
        return indexes

    if flags & 0x02:  # ResTable_type::FLAG_OFFSET16
        table_bytes = entry_count * 2
        if header_size + table_bytes > entries_start:
            raise ResourceTableError("Offset16 type-entry index exceeds entriesStart")
        indexes = []
        for item in range(entry_count):
            entry_offset = _u16(data, table_start + item * 2)
            if entry_offset == UINT16_MAX:
                continue
            indexes.append(item)
            _validate_entry(data, offset, chunk_end, entries_start, entry_offset * 4)
        return indexes

    table_bytes = entry_count * 4
    if header_size + table_bytes > entries_start:
        raise ResourceTableError("Type-entry offset table exceeds entriesStart")
    indexes = []
    for item in range(entry_count):
        entry_offset = _u32(data, table_start + item * 4)
        if entry_offset == UINT32_MAX:
            continue
        indexes.append(item)
        _validate_entry(data, offset, chunk_end, entries_start, entry_offset)
    return indexes


def _validate_entry(
    data: bytes,
    chunk_offset: int,
    chunk_end: int,
    entries_start: int,
    relative_offset: int,
) -> None:
    entry_offset = chunk_offset + entries_start + relative_offset
    if entry_offset + 8 > chunk_end:
        raise ResourceTableError(
            f"Resource entry at 0x{entry_offset:x} exceeds its type chunk"
        )
    entry_size = _u16(data, entry_offset)
    if entry_size < 8 or entry_offset + entry_size > chunk_end:
        raise ResourceTableError(
            f"Invalid resource entry size {entry_size} at 0x{entry_offset:x}"
        )


def _parse_package_children(
    data: bytes,
    package_offset: int,
    package_header_size: int,
    package_size: int,
    package_id: int,
    type_id_offset: int,
) -> tuple[list[int], list[int], int]:
    """Parse type-spec slots and configured entry IDs in a package chunk."""
    cursor = package_offset + package_header_size
    package_end = package_offset + package_size
    spec_ids: set[int] = set()
    entry_ids: set[int] = set()
    child_count = 0

    while cursor < package_end:
        chunk_type, header_size, chunk_size = _chunk(
            data, cursor, package_end, "package child"
        )
        child_count += 1

        if chunk_type == RES_TABLE_TYPE_SPEC_TYPE:
            if header_size < 16:
                raise ResourceTableError(
                    f"Short ResTable_typeSpec header at 0x{cursor:x}"
                )
            type_id = data[cursor + 8]
            count = _u32(data, cursor + 12)
            if (
                1 <= type_id + type_id_offset <= 0xFF
                and header_size + count * 4 <= chunk_size
            ):
                effective_type_id = type_id + type_id_offset
                spec_ids.update(
                    _resource_id(package_id, effective_type_id, item)
                    for item in range(count)
                )
            else:
                raise ResourceTableError(
                    f"Invalid type-spec type/count at 0x{cursor:x}: "
                    f"type={type_id}, offset={type_id_offset}, entries={count}"
                )

        elif chunk_type == RES_TABLE_TYPE_TYPE:
            if header_size < 20:
                raise ResourceTableError(f"Short ResTable_type header at 0x{cursor:x}")
            type_id = data[cursor + 8]
            flags = data[cursor + 9]
            count = _u32(data, cursor + 12)
            entries_start = _u32(data, cursor + 16)
            effective_type_id = type_id + type_id_offset
            if not 1 <= effective_type_id <= 0xFF:
                raise ResourceTableError(
                    f"Invalid type ID {type_id} + offset {type_id_offset} "
                    f"at 0x{cursor:x}"
                )
            indexes = _entry_indexes(
                data,
                cursor,
                header_size,
                chunk_size,
                flags,
                count,
                entries_start,
            )
            entry_ids.update(
                _resource_id(package_id, effective_type_id, index)
                for index in indexes
            )

        cursor += chunk_size

    if cursor != package_end:
        raise ResourceTableError("Package child chunks do not end at package boundary")
    return sorted(spec_ids), sorted(entry_ids), child_count


def package_records(data: bytes) -> list[dict[str, Any]]:
    """Parse top-level ResTable_package chunks and their numeric resource IDs."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("resources.arsc data must be bytes-like")
    raw = bytes(data)
    if len(raw) < 12:
        raise ResourceTableError("resources.arsc is shorter than a ResTable_header")

    table_type, table_header_size, table_size = struct.unpack_from("<HHI", raw, 0)
    if table_type != RES_TABLE_TYPE:
        raise ResourceTableError(f"Expected ResTable chunk type 0x0002, got 0x{table_type:04x}")
    if table_header_size < 12 or table_size != len(raw):
        raise ResourceTableError(
            f"Invalid ResTable header size={table_header_size}, chunk size={table_size}, "
            f"file size={len(raw)}"
        )
    declared_package_count = _u32(raw, 8)

    packages: list[dict[str, Any]] = []
    cursor = table_header_size
    while cursor < table_size:
        chunk_type, header_size, chunk_size = _chunk(raw, cursor, table_size, "table child")
        if chunk_type == RES_TABLE_PACKAGE_TYPE:
            if header_size < 284:
                raise ResourceTableError(
                    f"Short ResTable_package header at 0x{cursor:x}: {header_size}"
                )
            package_id = _u32(raw, cursor + 8)
            name_offset = cursor + 12
            package_name = _decode_package_name(
                raw[name_offset : name_offset + PACKAGE_NAME_BYTES], name_offset
            )
            type_id_offset = _u32(raw, cursor + 284) if header_size >= 288 else 0
            spec_ids, entry_ids, child_count = _parse_package_children(
                raw,
                cursor,
                header_size,
                chunk_size,
                package_id,
                type_id_offset,
            )
            combined = sorted(set(spec_ids) | set(entry_ids))
            packages.append(
                {
                    "id": package_id,
                    "name": package_name,
                    "offset": cursor,
                    "size": chunk_size,
                    "header_size": header_size,
                    "name_offset": name_offset,
                    "name_size": PACKAGE_NAME_BYTES,
                    "type_id_offset": type_id_offset,
                    "child_chunk_count": child_count,
                    "type_spec_id_count": len(spec_ids),
                    "configured_entry_id_count": len(entry_ids),
                    "numeric_resource_ids": combined,
                    "numeric_resource_id_sha256": _id_digest(combined),
                }
            )
        cursor += chunk_size

    if cursor != table_size:
        raise ResourceTableError("Top-level chunks do not end at ResTable boundary")
    if len(packages) != declared_package_count:
        raise ResourceTableError(
            f"ResTable declares {declared_package_count} packages, found {len(packages)}"
        )
    return packages


def _id_digest(resource_ids: list[int]) -> str:
    digest = hashlib.sha256()
    for resource_id in resource_ids:
        digest.update(struct.pack("<I", resource_id))
    return digest.hexdigest()


def _verify_target(records: list[dict[str, Any]], package_name: str) -> dict[str, Any]:
    target_packages = [record for record in records if record["id"] == 0x7F]
    if len(target_packages) != 1:
        raise ResourceTableError(
            f"Expected exactly one package ID 0x7f, found {len(target_packages)}"
        )
    target = target_packages[0]
    if target["name"] != package_name:
        raise ResourceTableError(
            f"Expected package ID 0x7f to be {package_name!r}, found {target['name']!r}"
        )
    return target


def rename_resource_package(
    data: bytes,
    old_package: str = OLD_PACKAGE,
    new_package: str = NEW_PACKAGE,
) -> tuple[bytes, dict[str, Any]]:
    """Rename the unique application package name and verify the binary diff.

    The function requires the sole package ID 0x7f to contain ``old_package``.
    It returns patched bytes and a JSON-serializable audit record. Package IDs,
    type/entry resource IDs, chunk sizes, offsets, and all bytes outside the
    fixed package-name field are verified unchanged.
    """
    if not old_package or not new_package:
        raise ValueError("Package names must be nonempty")
    if old_package == new_package:
        raise ValueError("Old and new package names must differ")
    try:
        encoded_new = new_package.encode("utf-16le")
    except UnicodeEncodeError as exc:
        raise ValueError(f"New package name is not valid UTF-16: {exc}") from exc
    new_name_units = len(encoded_new) // 2
    if "\0" in new_package:
        raise ValueError("Package names cannot contain a NUL character")
    if new_name_units + 1 > PACKAGE_NAME_UNITS:
        raise ValueError("New package name exceeds the 128-code-unit package field")

    original = bytes(data)
    before_records = package_records(original)
    target = _verify_target(before_records, old_package)
    start = target["name_offset"]
    end = start + PACKAGE_NAME_BYTES
    replacement = encoded_new + b"\0\0" * (PACKAGE_NAME_UNITS - new_name_units)
    patched_mutable = bytearray(original)
    patched_mutable[start:end] = replacement
    patched = bytes(patched_mutable)

    if len(patched) != len(original):
        raise AssertionError("Package name edit changed resources.arsc length")
    if patched[:start] != original[:start] or patched[end:] != original[end:]:
        raise AssertionError("Package name edit changed bytes outside the fixed name field")

    after_records = package_records(patched)
    after_target = _verify_target(after_records, new_package)
    if target["id"] != after_target["id"]:
        raise AssertionError("Package ID changed during name replacement")
    if target["numeric_resource_ids"] != after_target["numeric_resource_ids"]:
        raise AssertionError("Numeric resource IDs changed during name replacement")
    if target["numeric_resource_id_sha256"] != after_target["numeric_resource_id_sha256"]:
        raise AssertionError("Numeric resource ID digest changed during name replacement")
    if (target["offset"], target["size"], target["header_size"]) != (
        after_target["offset"],
        after_target["size"],
        after_target["header_size"],
    ):
        raise AssertionError("ResTable_package layout changed during name replacement")

    changed = [index for index, (old, new) in enumerate(zip(original, patched)) if old != new]
    if changed and (changed[0] < start or changed[-1] >= end):
        raise AssertionError("Binary diff escaped the package-name field")

    audit = {
        "package_id": target["id"],
        "old_package": old_package,
        "new_package": new_package,
        "package_count": len(before_records),
        "package_chunk_offset": target["offset"],
        "package_chunk_size": target["size"],
        "package_header_size": target["header_size"],
        "name_field_offset": start,
        "name_field_size": PACKAGE_NAME_BYTES,
        "changed_byte_count": len(changed),
        "changed_byte_range": [min(changed), max(changed)] if changed else None,
        "resources_arsc_size_before": len(original),
        "resources_arsc_size_after": len(patched),
        "sha256_before": hashlib.sha256(original).hexdigest(),
        "sha256_after": hashlib.sha256(patched).hexdigest(),
        "numeric_resource_ids_unchanged": True,
        "numeric_resource_id_count": len(target["numeric_resource_ids"]),
        "numeric_resource_id_sha256": target["numeric_resource_id_sha256"],
        "type_spec_id_count": target["type_spec_id_count"],
        "configured_entry_id_count": target["configured_entry_id_count"],
        "all_bytes_outside_name_field_unchanged": True,
    }
    return patched, audit


def smoke_test_apk(
    apk_path: str | Path,
    old_package: str = OLD_PACKAGE,
    new_package: str = NEW_PACKAGE,
) -> dict[str, Any]:
    """Run an in-memory forward/reverse resource-table smoke against an APK."""
    path = Path(apk_path)
    with zipfile.ZipFile(path, "r") as archive:
        try:
            original = archive.read("resources.arsc")
        except KeyError as exc:
            raise ResourceTableError(f"{path} has no resources.arsc") from exc

    renamed, audit = rename_resource_package(original, old_package, new_package)
    reverse, reverse_audit = rename_resource_package(renamed, new_package, old_package)
    if reverse != original:
        raise AssertionError("Reverse package-name replacement did not restore original bytes")

    return {
        "apk": str(path),
        "resources_arsc_zip_uncompressed_size": len(original),
        "forward": audit,
        "reverse": {
            "old_package": reverse_audit["old_package"],
            "new_package": reverse_audit["new_package"],
            "sha256_after": reverse_audit["sha256_after"],
            "restored_original_byte_for_byte": True,
            "numeric_resource_ids_unchanged": reverse_audit[
                "numeric_resource_ids_unchanged"
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path, help="APK containing resources.arsc")
    parser.add_argument("--old-package", default=OLD_PACKAGE)
    parser.add_argument("--new-package", default=NEW_PACKAGE)
    args = parser.parse_args()
    print(json.dumps(smoke_test_apk(args.apk, args.old_package, args.new_package), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
