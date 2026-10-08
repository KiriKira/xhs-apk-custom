#!/usr/bin/env python3
"""Restore the published REDnote clone's main-process label in classes17.dex.

This module is intentionally narrow: it accepts only the published
``rednote-fold-custom.apk`` baseline, and changes the ``const-string`` index in
``Lddc/a;->invoke()Ljava/lang/Object;`` from the clone package to the existing
``com.xingin.xhs`` DEX string. It does not modify the APK, manifest, resources,
signing data, or any other DEX method.

The returned audit proves the source APK/DEX identity, pinned instruction-array
hash, selected DEX instruction, DEX checksum/signature validity, and byte-level
change scope. The caller can then put the returned DEX bytes into its own
packaging/signing flow.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Any


BASELINE_CLASSES17_SHA256 = "abf919f753f5fc390a320d6778169f07b7a17f02f750c1548ec2310fc28a6ccd"
PATCHED_CLASSES17_SHA256 = "3dfdabbeaf8e75930eb3a111a9ff237a81c5c419e918601fe689e4b552da0728"
BASELINE_METHOD_INSN_SHA256 = "39954f2739bd905e9fab9655ea2ed665a19fda8a270d94399b776944b6511f82"
PATCHED_METHOD_INSN_SHA256 = "9e6879d1a28caceefcfd40d3d0ded6c9fd3dd3174d0fec58266deb8b8f0707e1"

DEX_ENTRY = "classes17.dex"
TARGET_CLASS = "Lddc/a;"
TARGET_METHOD = "invoke"
TARGET_PROTO = "()Ljava/lang/Object;"
SOURCE_PACKAGE = "com.xingin.xhs"
CLONE_PACKAGE = "com.kirikira.rednote.fold"
PROCESS_FIELD = ("Lddc/b;", "b", "Ljava/lang/String;")
EQUALS_METHOD = (
    "Lkotlin/jvm/internal/Intrinsics;",
    "areEqual",
    "(Ljava/lang/Object;Ljava/lang/Object;)Z",
)


class PackageCompatError(ValueError):
    """Raised when the exact pinned baseline/method is not present."""


class DexReader:
    """Small self-contained DEX reader for the single pinned edit."""

    def __init__(self, data: bytes, entry_name: str = DEX_ENTRY):
        self.data = data
        self.entry_name = entry_name
        self._strings: dict[int, str] = {}
        if len(data) < 112 or not data.startswith(b"dex\n") or data[7] != 0:
            raise PackageCompatError(f"{entry_name}: invalid DEX magic/header")
        if self.u32(32) != len(data) or self.u32(40) != 0x12345678:
            raise PackageCompatError(f"{entry_name}: invalid DEX size/endian tag")
        self.string_count, self.string_off = self.u32(56), self.u32(60)
        self.type_count, self.type_off = self.u32(64), self.u32(68)
        self.proto_count, self.proto_off = self.u32(72), self.u32(76)
        self.field_count, self.field_off = self.u32(80), self.u32(84)
        self.method_count, self.method_off = self.u32(88), self.u32(92)
        self.class_count, self.class_off = self.u32(96), self.u32(100)
        self._check(self.string_off, self.string_count * 4)
        self._check(self.type_off, self.type_count * 4)
        self._check(self.proto_off, self.proto_count * 12)
        self._check(self.field_off, self.field_count * 8)
        self._check(self.method_off, self.method_count * 8)
        self._check(self.class_off, self.class_count * 32)

    def _check(self, offset: int, size: int) -> None:
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise PackageCompatError(f"{self.entry_name}: DEX offset outside file")

    def u16(self, offset: int) -> int:
        self._check(offset, 2)
        return struct.unpack_from("<H", self.data, offset)[0]

    def u32(self, offset: int) -> int:
        self._check(offset, 4)
        return struct.unpack_from("<I", self.data, offset)[0]

    def uleb(self, offset: int) -> tuple[int, int]:
        value = shift = 0
        for _ in range(5):
            self._check(offset, 1)
            byte = self.data[offset]
            offset += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value, offset
            shift += 7
        raise PackageCompatError(f"{self.entry_name}: malformed ULEB128")

    def string(self, index: int) -> str:
        if index in self._strings:
            return self._strings[index]
        if index < 0 or index >= self.string_count:
            raise PackageCompatError(f"{self.entry_name}: string index outside table")
        offset = self.u32(self.string_off + 4 * index)
        _, offset = self.uleb(offset)  # UTF-16 length; the pinned strings are ASCII.
        end = self.data.find(b"\0", offset)
        if end < 0:
            raise PackageCompatError(f"{self.entry_name}: unterminated string")
        # DEX uses Modified UTF-8, which can encode UTF-16 surrogate halves
        # that strict UTF-8 rejects. The pinned package literals are ASCII;
        # replacement decoding is enough for a bounded table lookup.
        value = self.data[offset:end].decode("utf-8", errors="replace")
        self._strings[index] = value
        return value

    def string_indices(self, value: str) -> list[int]:
        return [i for i in range(self.string_count) if self.string(i) == value]

    def type_descriptor(self, index: int) -> str:
        if index < 0 or index >= self.type_count:
            raise PackageCompatError(f"{self.entry_name}: type index outside table")
        return self.string(self.u32(self.type_off + 4 * index))

    def proto_descriptor(self, index: int) -> str:
        if index < 0 or index >= self.proto_count:
            raise PackageCompatError(f"{self.entry_name}: proto index outside table")
        offset = self.proto_off + 12 * index
        return_type = self.type_descriptor(self.u32(offset + 4))
        parameters_off = self.u32(offset + 8)
        parameters: list[str] = []
        if parameters_off:
            count = self.u32(parameters_off)
            self._check(parameters_off + 4, count * 2)
            parameters = [
                self.type_descriptor(self.u16(parameters_off + 4 + 2 * i))
                for i in range(count)
            ]
        return f"({''.join(parameters)}){return_type}"

    def method_id(self, index: int) -> tuple[str, str, str]:
        if index < 0 or index >= self.method_count:
            raise PackageCompatError(f"{self.entry_name}: method index outside table")
        offset = self.method_off + 8 * index
        class_index, proto_index, name_index = struct.unpack_from("<HHI", self.data, offset)
        return (
            self.type_descriptor(class_index),
            self.string(name_index),
            self.proto_descriptor(proto_index),
        )

    def field_id(self, index: int) -> tuple[str, str, str]:
        if index < 0 or index >= self.field_count:
            raise PackageCompatError(f"{self.entry_name}: field index outside table")
        offset = self.field_off + 8 * index
        class_index, type_index, name_index = struct.unpack_from("<HHI", self.data, offset)
        return (
            self.type_descriptor(class_index),
            self.string(name_index),
            self.type_descriptor(type_index),
        )

    def class_definitions(self, descriptor: str) -> list[dict[str, int]]:
        found = []
        for index in range(self.class_count):
            offset = self.class_off + index * 32
            class_index = self.u32(offset)
            if self.type_descriptor(class_index) == descriptor:
                found.append(
                    {
                        "class_idx": class_index,
                        "class_data_off": self.u32(offset + 24),
                    }
                )
        return found

    def class_methods(self, class_data_off: int) -> list[tuple[int, int, int]]:
        if not class_data_off:
            return []
        counts = []
        offset = class_data_off
        for _ in range(4):
            value, offset = self.uleb(offset)
            counts.append(value)
        static_count, instance_count, direct_count, virtual_count = counts

        for count in (static_count, instance_count):
            for _ in range(count):
                _, offset = self.uleb(offset)  # field_idx_diff
                _, offset = self.uleb(offset)  # access_flags

        methods: list[tuple[int, int, int]] = []
        for count in (direct_count, virtual_count):
            method_index = 0
            for _ in range(count):
                delta, offset = self.uleb(offset)
                access, offset = self.uleb(offset)
                code_off, offset = self.uleb(offset)
                method_index += delta
                methods.append((method_index, access, code_off))
        return methods

    def code_info(self, code_off: int) -> tuple[int, int]:
        if not code_off:
            raise PackageCompatError(f"{self.entry_name}: target method has no code")
        self._check(code_off, 16)
        units_count = self.u32(code_off + 12)
        insns_off = code_off + 16
        self._check(insns_off, units_count * 2)
        return insns_off, units_count

    @staticmethod
    def instruction_width(units: list[int], position: int) -> int:
        first = units[position]
        opcode = first & 0xFF
        if opcode == 0x00:
            ident = first >> 8
            if ident == 0:
                return 1
            if ident == 1:  # packed-switch payload
                if position + 2 > len(units):
                    raise PackageCompatError("truncated packed-switch payload")
                return 4 + 2 * units[position + 1]
            if ident == 2:  # sparse-switch payload
                if position + 2 > len(units):
                    raise PackageCompatError("truncated sparse-switch payload")
                return 2 + 4 * units[position + 1]
            if ident == 3:  # fill-array-data payload
                if position + 4 > len(units):
                    raise PackageCompatError("truncated fill-array-data payload")
                element_width = units[position + 1]
                element_count = units[position + 2] | (units[position + 3] << 16)
                return 4 + (element_width * element_count + 1) // 2
            raise PackageCompatError("unknown DEX instruction payload")
        if opcode in {
            0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1A, 0x1C, 0x1F,
            0x20, 0x22, 0x23, 0x29,
        }:
            return 2
        if opcode in {
            0x03, 0x06, 0x09, 0x14, 0x17, 0x1B, 0x24, 0x25, 0x26, 0x2A,
            0x2B, 0x2C, 0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76,
            0x77, 0x78, 0xFC, 0xFD,
        }:
            return 3
        if (
            0x2D <= opcode <= 0x3D
            or 0x44 <= opcode <= 0x6D
            or 0x90 <= opcode <= 0xAF
            or 0xD0 <= opcode <= 0xE2
        ):
            return 2
        if 0x7B <= opcode <= 0x8F or 0xB0 <= opcode <= 0xCF or 0x01 <= opcode <= 0x12:
            return 1
        if opcode == 0x18:
            return 5
        if opcode in {0xFA, 0xFB}:
            return 4
        if opcode in {0xFE, 0xFF, 0x1D, 0x1E, 0x21, 0x27, 0x28}:
            return 1
        raise PackageCompatError(f"unsupported DEX opcode 0x{opcode:02x}")

    def target_method(self) -> tuple[int, int, int, bytes, list[tuple[int, int, int]]]:
        classes = self.class_definitions(TARGET_CLASS)
        if len(classes) != 1:
            raise PackageCompatError(
                f"{self.entry_name}: expected one {TARGET_CLASS}; found {len(classes)}"
            )
        found = []
        for method_index, access, code_off in self.class_methods(classes[0]["class_data_off"]):
            class_name, method_name, proto = self.method_id(method_index)
            if (class_name, method_name, proto) == (TARGET_CLASS, TARGET_METHOD, TARGET_PROTO):
                insns_off, units_count = self.code_info(code_off)
                insns = self.data[insns_off:insns_off + 2 * units_count]
                units = [self.u16(insns_off + i * 2) for i in range(units_count)]
                decoded: list[tuple[int, int, int]] = []  # (code-unit position, opcode, first unit)
                position = 0
                while position < units_count:
                    first = units[position]
                    opcode = first & 0xFF
                    width = self.instruction_width(units, position)
                    if width < 1 or position + width > units_count:
                        raise PackageCompatError(f"{self.entry_name}: invalid instruction width")
                    decoded.append((position, opcode, first))
                    position += width
                found.append((code_off, insns_off, units_count, insns, decoded))
        if len(found) != 1:
            raise PackageCompatError(
                f"{self.entry_name}: expected one {TARGET_CLASS}->{TARGET_METHOD}{TARGET_PROTO}; "
                f"found {len(found)}"
            )
        return found[0]


def _resolve_target(
    dex: DexReader,
    expected_name: str,
    expected_instruction_sha256: str,
) -> tuple[dict[str, Any], list[tuple[int, int, int]]]:
    code_off, insns_off, units_count, insns, decoded = dex.target_method()
    instruction_hash = hashlib.sha256(insns).hexdigest()
    if instruction_hash != expected_instruction_sha256:
        raise PackageCompatError(
            "ddc/a.invoke instruction hash mismatch: "
            f"expected {expected_instruction_sha256}, found {instruction_hash}"
        )

    units = [dex.u16(insns_off + i * 2) for i in range(units_count)]
    string_loads: list[dict[str, Any]] = []
    has_process_field = False
    has_equals_call = False
    for position, opcode, first in decoded:
        if opcode == 0x1A:  # const-string, format 21c
            index = units[position + 1]
            string_loads.append(
                {
                    "codeUnitPosition": position,
                    "register": (first >> 8) & 0xFF,
                    "stringIndex": index,
                    "value": dex.string(index),
                    "indexByteOffset": insns_off + 2 * (position + 1),
                    "indexWidth": 2,
                    "opcode": "const-string",
                }
            )
        elif opcode == 0x1B:  # const-string/jumbo, format 31c
            index = units[position + 1] | (units[position + 2] << 16)
            string_loads.append(
                {
                    "codeUnitPosition": position,
                    "register": (first >> 8) & 0xFF,
                    "stringIndex": index,
                    "value": dex.string(index),
                    "indexByteOffset": insns_off + 2 * (position + 1),
                    "indexWidth": 4,
                    "opcode": "const-string/jumbo",
                }
            )
        elif opcode == 0x62:  # sget-object, format 21c
            field_index = units[position + 1]
            if dex.field_id(field_index) == PROCESS_FIELD:
                has_process_field = True
        elif opcode in {0x71, 0x77}:  # invoke-static / invoke-static-range
            method_index = units[position + 1]
            if dex.method_id(method_index) == EQUALS_METHOD:
                has_equals_call = True

    target_loads = [load for load in string_loads if load["value"] == expected_name]
    if len(target_loads) != 1:
        raise PackageCompatError(
            f"ddc/a.invoke: expected one {expected_name!r} const-string; found {len(target_loads)}"
        )
    if not has_process_field or not has_equals_call:
        raise PackageCompatError("ddc/a.invoke no longer has its pinned process-name predicate")
    expected_indices = dex.string_indices(expected_name)
    if len(expected_indices) != 1:
        raise PackageCompatError(
            f"{DEX_ENTRY}: expected one DEX string {expected_name!r}; found {len(expected_indices)}"
        )
    if expected_indices[0] > 0xFFFF:
        raise PackageCompatError("source package index does not fit const-string 21c")

    target = target_loads[0]
    if target["opcode"] != "const-string" or target["indexWidth"] != 2:
        raise PackageCompatError("pinned target is no longer a 16-bit const-string")
    if target["codeUnitPosition"] != 15 or target["register"] != 1:
        raise PackageCompatError("pinned const-string location/register changed")
    expected_index = 42689 if expected_name == CLONE_PACKAGE else 43358
    if target["stringIndex"] != expected_index or expected_indices[0] != expected_index:
        raise PackageCompatError("pinned DEX string index changed")

    return (
        {
            "codeItemOffset": code_off,
            "instructionArrayOffset": insns_off,
            "instructionUnits": units_count,
            "instructionByteLength": len(insns),
            "instructionSha256Before": instruction_hash,
            "targetConstString": target,
            "expectedStringIndex": expected_indices[0],
        },
        decoded,
    )


def _validate_dex_checksums(data: bytes) -> dict[str, Any]:
    dex = DexReader(data)
    expected_signature = hashlib.sha1(data[32:]).digest()
    expected_checksum = zlib.adler32(data[12:]) & 0xFFFFFFFF
    actual_signature = data[12:32]
    actual_checksum = dex.u32(8)
    return {
        "sha1SignatureValid": actual_signature == expected_signature,
        "adler32ChecksumValid": actual_checksum == expected_checksum,
        "expectedSha1": expected_signature.hex(),
        "actualSha1": actual_signature.hex(),
        "expectedAdler32": f"{expected_checksum:08x}",
        "actualAdler32": f"{actual_checksum:08x}",
    }


def patch_ddc_main_process(dex: bytes) -> tuple[bytes, dict[str, Any]]:
    """Patch the pinned DEX instruction from clone ID to source process name.

    The caller authenticates the containing APK. This function pins the exact
    input classes17.dex SHA-256 and the original target instruction-array hash.
    """
    dex_bytes = dex
    original_sha = hashlib.sha256(dex_bytes).hexdigest()
    if original_sha != BASELINE_CLASSES17_SHA256:
        raise PackageCompatError(
            f"classes17.dex SHA-256 mismatch: expected {BASELINE_CLASSES17_SHA256}, found {original_sha}"
        )
    before_checksums = _validate_dex_checksums(dex_bytes)
    if not before_checksums["sha1SignatureValid"] or not before_checksums["adler32ChecksumValid"]:
        raise PackageCompatError("baseline classes17.dex has invalid DEX signature/checksum")

    before = DexReader(dex_bytes)
    target_audit, _ = _resolve_target(
        before, CLONE_PACKAGE, BASELINE_METHOD_INSN_SHA256
    )
    output = bytearray(dex_bytes)
    target = target_audit["targetConstString"]
    operand_offset = target["indexByteOffset"]
    old_index = target["stringIndex"]
    new_index = before.string_indices(SOURCE_PACKAGE)[0]
    if before.u16(operand_offset) != old_index:
        raise PackageCompatError("target const-string operand does not match pinned clone index")
    struct.pack_into("<H", output, operand_offset, new_index)

    # DEX header fields: Adler-32 at [8:12], SHA-1 at [12:32].
    output[12:32] = hashlib.sha1(output[32:]).digest()
    struct.pack_into("<I", output, 8, zlib.adler32(output[12:]) & 0xFFFFFFFF)
    patched = bytes(output)

    # Prove that the exact instruction hash guard still finds the target with
    # the restored source process name. (The hash is checked before mutation.)
    after = DexReader(patched)
    after_code_off, after_insns_off, after_units, after_insns, _ = after.target_method()
    after_insn_hash = hashlib.sha256(after_insns).hexdigest()
    after_audit, _ = _resolve_target(
        after, SOURCE_PACKAGE, PATCHED_METHOD_INSN_SHA256
    )
    if after_audit["targetConstString"]["stringIndex"] != new_index:
        raise PackageCompatError("patched const-string did not resolve to source process package")
    after_checksums = _validate_dex_checksums(patched)
    if not after_checksums["sha1SignatureValid"] or not after_checksums["adler32ChecksumValid"]:
        raise PackageCompatError("patched DEX SHA-1/Adler-32 validation failed")

    changed_offsets = [i for i, (a, b) in enumerate(zip(dex_bytes, patched)) if a != b]
    allowed = set(range(8, 32)) | {operand_offset, operand_offset + 1}
    unexpected = [offset for offset in changed_offsets if offset not in allowed]
    if unexpected:
        raise PackageCompatError(
            f"patch changed bytes outside target operand and DEX header: {unexpected[:8]}"
        )
    if operand_offset not in changed_offsets or operand_offset + 1 not in changed_offsets:
        raise PackageCompatError("expected both bytes of the const-string index to change")

    audit = {
        "patch": "ddc/a.invoke clone package const-string index -> source package index",
        "dexEntry": DEX_ENTRY,
        "dexSize": len(dex_bytes),
        "dexSha256Before": original_sha,
        "dexSha256After": hashlib.sha256(patched).hexdigest(),
        "class": TARGET_CLASS,
        "method": f"{TARGET_METHOD}{TARGET_PROTO}",
        "methodInstructionArray": {
            **target_audit,
            "codeItemOffsetAfter": after_code_off,
            "instructionArrayOffsetAfter": after_insns_off,
            "instructionUnitsAfter": after_units,
            "instructionSha256After": after_insn_hash,
        },
        "literalChange": {
            "from": CLONE_PACKAGE,
            "to": SOURCE_PACKAGE,
            "oldStringIndex": old_index,
            "newStringIndex": new_index,
            "constStringRegister": target["register"],
            "codeUnitPosition": target["codeUnitPosition"],
            "dexByteOffset": operand_offset,
            "changedOperandBytes": [operand_offset, operand_offset + 1],
        },
        "dexHeader": {
            "checksumAndSignatureRange": [8, 32],
            "before": before_checksums,
            "after": after_checksums,
        },
        "byteDiff": {
            "changedByteCount": len(changed_offsets),
            "changedOffsets": changed_offsets,
            "allowedNonInstructionRange": [8, 32],
            "unexpectedChangedOffsets": unexpected,
            "onlyTargetOperandAndDexHeaderChanged": not unexpected,
        },
    }
    return patched, audit


def verify_ddc_main_process(dex: bytes, expected_name: str) -> dict[str, Any]:
    """Verify the pinned baseline or restored DEX process-name predicate."""
    expected_hashes = {
        CLONE_PACKAGE: (BASELINE_CLASSES17_SHA256, BASELINE_METHOD_INSN_SHA256),
        SOURCE_PACKAGE: (PATCHED_CLASSES17_SHA256, PATCHED_METHOD_INSN_SHA256),
    }
    if expected_name not in expected_hashes:
        raise PackageCompatError(
            f"expected_name must be {CLONE_PACKAGE!r} or {SOURCE_PACKAGE!r}"
        )
    expected_dex_sha, expected_insn_sha = expected_hashes[expected_name]
    actual_dex_sha = hashlib.sha256(dex).hexdigest()
    if actual_dex_sha != expected_dex_sha:
        raise PackageCompatError(
            f"classes17.dex SHA-256 mismatch: expected {expected_dex_sha}, found {actual_dex_sha}"
        )
    checksum_audit = _validate_dex_checksums(dex)
    if not checksum_audit["sha1SignatureValid"] or not checksum_audit["adler32ChecksumValid"]:
        raise PackageCompatError("DEX SHA-1/Adler-32 validation failed")
    dex_reader = DexReader(dex)
    target_audit, _ = _resolve_target(dex_reader, expected_name, expected_insn_sha)
    return {
        "dexEntry": DEX_ENTRY,
        "dexSha256": actual_dex_sha,
        "expectedProcessName": expected_name,
        "class": TARGET_CLASS,
        "method": f"{TARGET_METHOD}{TARGET_PROTO}",
        "targetConstString": target_audit["targetConstString"],
        "instructionSha256": target_audit["instructionSha256Before"],
        "dexHeader": checksum_audit,
        "verified": True,
    }
