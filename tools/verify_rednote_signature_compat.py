#!/usr/bin/env python3
"""Verify the signature-compatibility hook in a built REDnote APK without smali."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile


APPLICATION_CLASS = "Lcom/xingin/xhs/app/XhsApplication;"
HELPER_CLASS = "Ldev/kiri/xhsspoof/SignatureSpoof;"
HELPER_INSTALL = "Ldev/kiri/xhsspoof/SignatureSpoof;->install()V"
ATTACH_BASE_CONTEXT_PROTO = "(Landroid/content/Context;)V"
DEFAULT_PACKAGE = "com.kirikira.rednote.fold"
DEFAULT_CERT_SHA256 = "dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd"


class VerificationError(ValueError):
    """A bounded, user-readable verification failure."""


class DexFile:
    """Small DEX binary reader for class, field, method and const-string checks."""

    def __init__(self, data: bytes, entry_name: str):
        self.data = data
        self.entry_name = entry_name
        self._strings: dict[int, str] = {}
        if len(data) < 112 or not data.startswith(b"dex\n") or data[7] != 0:
            raise VerificationError(f"{entry_name}: invalid DEX header")
        if self.u32(32) != len(data) or self.u32(40) != 0x12345678:
            raise VerificationError(f"{entry_name}: invalid DEX size or endian tag")
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
            raise VerificationError(f"{self.entry_name}: DEX offset outside file")

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
        raise VerificationError(f"{self.entry_name}: malformed ULEB128")

    def string(self, index: int) -> str:
        if index in self._strings:
            return self._strings[index]
        if index < 0 or index >= self.string_count:
            raise VerificationError(f"{self.entry_name}: string index outside table")
        offset = self.u32(self.string_off + 4 * index)
        _, offset = self.uleb(offset)  # UTF-16 length; the target values are ASCII.
        end = self.data.find(b"\0", offset)
        if end < 0:
            raise VerificationError(f"{self.entry_name}: unterminated DEX string")
        value = self.data[offset:end].decode("utf-8", errors="replace")
        self._strings[index] = value
        return value

    def type_descriptor(self, index: int) -> str:
        if index < 0 or index >= self.type_count:
            raise VerificationError(f"{self.entry_name}: type index outside table")
        return self.string(self.u32(self.type_off + 4 * index))

    def proto_descriptor(self, index: int) -> str:
        if index < 0 or index >= self.proto_count:
            raise VerificationError(f"{self.entry_name}: prototype index outside table")
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
            raise VerificationError(f"{self.entry_name}: method index outside table")
        offset = self.method_off + 8 * index
        class_index, proto_index, name_index = struct.unpack_from("<HHI", self.data, offset)
        return (
            self.type_descriptor(class_index),
            self.string(name_index),
            self.proto_descriptor(proto_index),
        )

    def field_id(self, index: int) -> tuple[str, str, str]:
        if index < 0 or index >= self.field_count:
            raise VerificationError(f"{self.entry_name}: field index outside table")
        offset = self.field_off + 8 * index
        class_index, type_index, name_index = struct.unpack_from("<HHI", self.data, offset)
        return (
            self.type_descriptor(class_index),
            self.string(name_index),
            self.type_descriptor(type_index),
        )

    def class_definitions(self, descriptor: str | None = None) -> list[dict[str, int]]:
        found = []
        for index in range(self.class_count):
            offset = self.class_off + index * 32
            item = {
                "class_idx": self.u32(offset),
                "class_data_off": self.u32(offset + 24),
                "static_values_off": self.u32(offset + 28),
            }
            if descriptor is None or self.type_descriptor(item["class_idx"]) == descriptor:
                item["descriptor"] = self.type_descriptor(item["class_idx"])
                found.append(item)
        return found

    def class_data(self, offset: int) -> dict[str, list[tuple[int, int]] | list[tuple[int, int, int]]]:
        if not offset:
            return {"static_fields": [], "instance_fields": [], "direct_methods": [], "virtual_methods": []}
        counts = []
        for _ in range(4):
            value, offset = self.uleb(offset)
            counts.append(value)

        def read_fields(count: int, cursor: int) -> tuple[list[tuple[int, int]], int]:
            fields = []
            field_index = 0
            for _ in range(count):
                delta, cursor = self.uleb(cursor)
                access, cursor = self.uleb(cursor)
                field_index += delta
                fields.append((field_index, access))
            return fields, cursor

        def read_methods(count: int, cursor: int) -> tuple[list[tuple[int, int, int]], int]:
            methods = []
            method_index = 0
            for _ in range(count):
                delta, cursor = self.uleb(cursor)
                access, cursor = self.uleb(cursor)
                code_off, cursor = self.uleb(cursor)
                method_index += delta
                methods.append((method_index, access, code_off))
            return methods, cursor

        static_fields, offset = read_fields(counts[0], offset)
        instance_fields, offset = read_fields(counts[1], offset)
        direct_methods, offset = read_methods(counts[2], offset)
        virtual_methods, _ = read_methods(counts[3], offset)
        return {
            "static_fields": static_fields,
            "instance_fields": instance_fields,
            "direct_methods": direct_methods,
            "virtual_methods": virtual_methods,
        }

    def _encoded_value(self, offset: int) -> tuple[tuple[str, object], int]:
        self._check(offset, 1)
        header = self.data[offset]
        offset += 1
        value_type, value_arg = header & 0x1F, header >> 5
        if value_type == 0x17:  # VALUE_STRING
            size = value_arg + 1
            self._check(offset, size)
            index = int.from_bytes(self.data[offset:offset + size], "little")
            return ("string", self.string(index)), offset + size
        if value_type == 0x1E:  # VALUE_NULL
            return ("null", None), offset
        if value_type == 0x1F:  # VALUE_BOOLEAN
            return ("boolean", bool(value_arg)), offset
        if value_type == 0x1C:  # VALUE_ARRAY
            if value_arg != 0:
                raise VerificationError(f"{self.entry_name}: malformed encoded array")
            count, offset = self.uleb(offset)
            for _ in range(count):
                _, offset = self._encoded_value(offset)
            return ("other", None), offset
        if value_type == 0x1D:  # VALUE_ANNOTATION
            if value_arg != 0:
                raise VerificationError(f"{self.entry_name}: malformed encoded annotation")
            _, offset = self.uleb(offset)  # type_idx
            count, offset = self.uleb(offset)
            for _ in range(count):
                _, offset = self.uleb(offset)  # name_idx
                _, offset = self._encoded_value(offset)
            return ("other", None), offset
        if value_type in {0x00, 0x02, 0x03, 0x04, 0x06, 0x10, 0x11, 0x15, 0x16, 0x18, 0x19, 0x1A, 0x1B}:
            size = value_arg + 1
            self._check(offset, size)
            return ("other", None), offset + size
        raise VerificationError(f"{self.entry_name}: unsupported encoded-value type")

    def static_string_field(self, definition: dict[str, int], field_name: str) -> str | None:
        data = self.class_data(definition["class_data_off"])
        fields = data["static_fields"]
        assert isinstance(fields, list)
        values: list[tuple[str, object]] = []
        values_off = definition["static_values_off"]
        if values_off:
            count, offset = self.uleb(values_off)
            for _ in range(count):
                value, offset = self._encoded_value(offset)
                values.append(value)
        for position, (field_index, _) in enumerate(fields):
            class_name, name, field_type = self.field_id(field_index)
            if class_name != definition["descriptor"] or name != field_name:
                continue
            if field_type != "Ljava/lang/String;" or position >= len(values):
                return None
            kind, value = values[position]
            return value if kind == "string" and isinstance(value, str) else None
        return None

    def method_records(self, definition: dict[str, int]) -> list[tuple[int, int, int]]:
        data = self.class_data(definition["class_data_off"])
        return list(data["direct_methods"]) + list(data["virtual_methods"])  # type: ignore[arg-type]

    def code_info(self, code_off: int) -> tuple[int, int]:
        if not code_off:
            raise VerificationError(f"{self.entry_name}: method has no code")
        self._check(code_off, 16)
        units_count = self.u32(code_off + 12)
        self._check(code_off + 16, units_count * 2)
        return code_off + 16, units_count

    def first_instruction_method(self, code_off: int) -> tuple[str, int, int]:
        insns_off, size = self.code_info(code_off)
        if not size:
            raise VerificationError(f"{self.entry_name}: startup hook has empty code")
        first = self.u16(insns_off)
        opcode = first & 0xFF
        if opcode == 0x71:  # invoke-static, 35c format
            if size < 3:
                raise VerificationError(f"{self.entry_name}: truncated invoke-static")
            argument_count = (first >> 8) & 0x0F
            method_index = self.u16(insns_off + 2)
            return "invoke-static", method_index, argument_count
        if opcode == 0x77:  # invoke-static/range, 3rc format
            if size < 3:
                raise VerificationError(f"{self.entry_name}: truncated invoke-static/range")
            argument_count = (first >> 8) & 0xFF
            method_index = self.u16(insns_off + 2)
            return "invoke-static/range", method_index, argument_count
        return f"opcode-0x{opcode:02x}", -1, -1

    @staticmethod
    def _instruction_width(units: list[int], position: int) -> int:
        first = units[position]
        opcode = first & 0xFF
        if opcode == 0x00:
            ident = first >> 8
            if ident == 0:
                return 1
            if ident == 1:  # packed-switch-payload
                if position + 2 > len(units):
                    raise VerificationError("truncated packed-switch payload")
                return 4 + 2 * units[position + 1]
            if ident == 2:  # sparse-switch-payload
                if position + 2 > len(units):
                    raise VerificationError("truncated sparse-switch payload")
                return 2 + 4 * units[position + 1]
            if ident == 3:  # fill-array-data-payload
                if position + 4 > len(units):
                    raise VerificationError("truncated array-data payload")
                element_width = units[position + 1]
                element_count = units[position + 2] | (units[position + 3] << 16)
                return 4 + (element_width * element_count + 1) // 2
            raise VerificationError("unknown DEX payload")
        if opcode in {0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1A, 0x1C, 0x1F, 0x20,
                      0x22, 0x23, 0x29}:
            return 2
        if opcode in {0x03, 0x06, 0x09, 0x14, 0x17, 0x1B, 0x24, 0x25, 0x26, 0x2A, 0x2B, 0x2C,
                      0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78,
                      0xFC, 0xFD}:
            return 3
        if 0x2D <= opcode <= 0x3D or 0x44 <= opcode <= 0x6D or 0x90 <= opcode <= 0xAF or 0xD0 <= opcode <= 0xE2:
            return 2
        if 0x7B <= opcode <= 0x8F or 0xB0 <= opcode <= 0xCF or 0x01 <= opcode <= 0x12:
            return 1
        if opcode in {0x18}:
            return 5
        if opcode in {0xFA, 0xFB}:
            return 4
        if opcode in {0xFE, 0xFF}:
            return 2
        if opcode in {0x00, 0x1D, 0x1E, 0x21, 0x27, 0x28}:
            return 1
        raise VerificationError(f"unsupported DEX opcode 0x{opcode:02x}")

    def code_strings(self, code_off: int) -> list[str]:
        insns_off, size = self.code_info(code_off)
        units = [self.u16(insns_off + 2 * i) for i in range(size)]
        strings: list[str] = []
        position = 0
        while position < size:
            first = units[position]
            opcode = first & 0xFF
            if opcode == 0x1A:  # const-string, 21c
                if position + 1 >= size:
                    raise VerificationError(f"{self.entry_name}: truncated const-string")
                strings.append(self.string(units[position + 1]))
            elif opcode == 0x1B:  # const-string/jumbo, 31c
                if position + 2 >= size:
                    raise VerificationError(f"{self.entry_name}: truncated const-string/jumbo")
                index = units[position + 1] | (units[position + 2] << 16)
                strings.append(self.string(index))
            width = self._instruction_width(units, position)
            if width < 1 or position + width > size:
                raise VerificationError(f"{self.entry_name}: invalid DEX instruction width")
            position += width
        return strings


def _dex_entries(names: list[str]) -> list[str]:
    pattern = re.compile(r"classes(?:([0-9]+))?\.dex\Z")
    entries = [name for name in names if pattern.fullmatch(name)]
    if any(name != "classes.dex" and int(pattern.fullmatch(name).group(1)) < 2 for name in entries):
        raise VerificationError("APK has an invalid numbered DEX entry")
    return sorted(entries, key=lambda name: 1 if name == "classes.dex" else int(name[7:-4]))


def _one_class(dex: DexFile, descriptor: str) -> dict[str, int] | None:
    matches = dex.class_definitions(descriptor)
    if len(matches) > 1:
        raise VerificationError(f"{dex.entry_name}: duplicate class {descriptor}")
    return matches[0] if matches else None


def _package_from_badging(apk: Path) -> str:
    candidates = []
    configured = os.environ.get("AAPT2")
    if configured:
        candidates.append(Path(configured).expanduser())
    found = shutil.which("aapt2")
    if found:
        candidates.append(Path(found))
    candidates.extend((
        Path("/workspace/android-tools/android-15/aapt2"),
        Path("/workspace/android-tools/android-14/aapt2"),
    ))
    tool = next((candidate.resolve() for candidate in candidates if candidate.is_file() and os.access(candidate, os.X_OK)), None)
    if tool is None:
        raise VerificationError("aapt2 was not found for manifest package verification")
    try:
        result = subprocess.run(
            [str(tool), "dump", "badging", str(apk)],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError(f"aapt2 could not inspect the APK ({type(exc).__name__})") from None
    if result.returncode:
        raise VerificationError(f"aapt2 rejected the APK (exit {result.returncode})")
    for line in result.stdout.splitlines():
        match = re.match(r"package:\s+name='([^']+)'(?:\s|$)", line)
        if match:
            return match.group(1)
    raise VerificationError("aapt2 output has no package name")


def _helper_strings(dex: DexFile, definition: dict[str, int]) -> list[str]:
    result = []
    for method_index, _, code_off in dex.method_records(definition):
        if code_off:
            result.extend(dex.code_strings(code_off))
    return result


def _decode_cert_sha256(encoded: str) -> str | None:
    compact = re.sub(r"\s+", "", encoded)
    try:
        der = base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error):
        return None
    if not der or der[0] != 0x30:
        return None
    return hashlib.sha256(der).hexdigest()


def verify_signature_compat(
    apk: str | Path,
    expected_package: str,
    expected_cert_sha256: str,
) -> dict[str, object]:
    apk_path = Path(apk).expanduser().resolve()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_cert_sha256):
        raise VerificationError("expected certificate SHA-256 must be 64 hexadecimal characters")
    if not apk_path.is_file():
        raise VerificationError("APK file does not exist")
    expected_cert_sha256 = expected_cert_sha256.lower()
    actual_package = _package_from_badging(apk_path)
    if actual_package != expected_package:
        raise VerificationError(f"APK package mismatch: expected {expected_package}, got {actual_package}")

    try:
        with zipfile.ZipFile(apk_path) as archive:
            names = archive.namelist()
            dex_names = _dex_entries(names)
            if len(dex_names) != len(set(dex_names)):
                raise VerificationError("APK has duplicate DEX entry names")
            if "classes17.dex" not in dex_names:
                raise VerificationError("classes17.dex is missing")
            dex_files = {name: DexFile(archive.read(name), name) for name in dex_names}
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, VerificationError):
            raise
        raise VerificationError(f"APK or DEX data could not be read ({type(exc).__name__})") from None

    application_dex = dex_files["classes17.dex"]
    application_definition = _one_class(application_dex, APPLICATION_CLASS)
    if application_definition is None:
        raise VerificationError("XhsApplication is missing from classes17.dex")
    application_data = application_dex.class_data(application_definition["class_data_off"])
    application_methods = list(application_data["direct_methods"]) + list(application_data["virtual_methods"])
    startup_methods = []
    for method_index, access, code_off in application_methods:
        if application_dex.method_id(method_index) == (
            APPLICATION_CLASS,
            "attachBaseContext",
            ATTACH_BASE_CONTEXT_PROTO,
        ):
            startup_methods.append((method_index, access, code_off))
    if len(startup_methods) != 1:
        raise VerificationError("attachBaseContext(Context) was not found exactly once")
    _, _, startup_code = startup_methods[0]
    first_opcode, first_target, argument_count = application_dex.first_instruction_method(startup_code)
    if first_opcode not in {"invoke-static", "invoke-static/range"} or argument_count != 0:
        raise VerificationError("attachBaseContext does not begin with a no-argument static invoke")
    if application_dex.method_id(first_target) != (
        HELPER_CLASS,
        "install",
        "()V",
    ):
        raise VerificationError("first attachBaseContext instruction does not call SignatureSpoof.install()V")

    helper_locations = []
    for dex_name, dex in dex_files.items():
        definition = _one_class(dex, HELPER_CLASS)
        if definition is not None:
            helper_locations.append((dex_name, dex, definition))
    if len(helper_locations) != 1:
        raise VerificationError(f"expected one SignatureSpoof helper class, found {len(helper_locations)}")
    helper_dex_name, helper_dex, helper_definition = helper_locations[0]
    if helper_dex_name in {"classes.dex", "classes17.dex"} or int(helper_dex_name[7:-4]) < 2:
        raise VerificationError("SignatureSpoof helper must live in a separate numbered classesN.dex")

    helper_data = helper_dex.class_data(helper_definition["class_data_off"])
    helper_methods = list(helper_data["direct_methods"]) + list(helper_data["virtual_methods"])
    install_methods = [
        (method_index, access, code_off)
        for method_index, access, code_off in helper_methods
        if helper_dex.method_id(method_index) == (HELPER_CLASS, "install", "()V")
    ]
    if len(install_methods) != 1 or not (install_methods[0][1] & 0x8) or not install_methods[0][2]:
        raise VerificationError("SignatureSpoof.install()V is missing, non-static, or has no code")

    package_value = helper_dex.static_string_field(helper_definition, "PACKAGE_NAME")
    cert_value = helper_dex.static_string_field(helper_definition, "CERT_B64")
    helper_code_strings = _helper_strings(helper_dex, helper_definition)
    if package_value is None:
        if expected_package not in helper_code_strings:
            raise VerificationError("expected package constant is absent from SignatureSpoof fields and code")
        package_source = "helper_code_const_string"
    else:
        if package_value != expected_package:
            raise VerificationError("SignatureSpoof.PACKAGE_NAME does not match expected package")
        package_source = "static_field_value"

    if cert_value is not None:
        cert_sha256 = _decode_cert_sha256(cert_value)
        if cert_sha256 != expected_cert_sha256:
            raise VerificationError("SignatureSpoof.CERT_B64 DER SHA-256 mismatch")
        cert_source = "static_field_value"
    else:
        matches = sorted({
            sha
            for value in helper_code_strings
            if (sha := _decode_cert_sha256(value)) == expected_cert_sha256
        })
        if len(matches) != 1:
            raise VerificationError("expected certificate DER is absent from SignatureSpoof fields and code")
        cert_sha256 = matches[0]
        cert_source = "helper_code_const_string"

    return {
        "ok": True,
        "apk": apk_path.name,
        "package": actual_package,
        "applicationDex": "classes17.dex",
        "applicationClass": APPLICATION_CLASS,
        "startupMethod": "attachBaseContext(Landroid/content/Context;)V",
        "firstInstruction": first_opcode,
        "firstInstructionTarget": HELPER_INSTALL,
        "helperDex": helper_dex_name,
        "helperClass": HELPER_CLASS,
        "helperPackage": expected_package,
        "helperPackageSource": package_source,
        "certificateDerSha256": cert_sha256,
        "certificateSource": cert_source,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--expected-package", default=DEFAULT_PACKAGE)
    parser.add_argument("--expected-cert-sha256", default=DEFAULT_CERT_SHA256)
    args = parser.parse_args(argv)
    try:
        report = verify_signature_compat(
            args.apk,
            args.expected_package,
            args.expected_cert_sha256,
        )
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
