"""Pinned REDnote 9.48.1 image-download function-switch unlock.

Note-level function switches carry ``type``, ``enable`` and ``reason``.
``FunctionSwitch.b()`` returns ``enable`` and is read by every panel that
renders an image-download action. For notes whose author disabled downloads,
the server sends ``type=image_download`` with ``enable=false`` and the reason
text used as the greyed item's toast.

Return true only for ``image_download``; every other function switch keeps the
server's enable value, and the stored fields/payload stay untouched.
"""

import hashlib
import re
from pathlib import Path
import struct
import sys
import zipfile

CLASS = "com.xingin.entities.notedetail.FunctionSwitch"
DESCRIPTOR = "Lcom/xingin/entities/notedetail/FunctionSwitch;"
METHOD = "b"
PROTO = "()Z"
DOWNLOAD_TYPE = "image_download"
EXPECTED_METHOD_SHA = "d4c07204691b2a6dd49e349e01c78decb89e43481da3fd6532137e66a5868689"
ORIGINAL_BODY = (
    ".method public final b()Z\n"
    "    .locals 1\n"
    "\n"
    "    .line 1\n"
    "    iget-boolean v0, p0, Lcom/xingin/entities/notedetail/FunctionSwitch;->enable:Z\n"
    "\n"
    "    return v0\n"
    ".end method"
)
PATCHED_BODY = (
    ".method public final b()Z\n"
    "    .locals 2\n"
    "\n"
    "    .line 1\n"
    "    iget-object v0, p0, Lcom/xingin/entities/notedetail/FunctionSwitch;->type:Ljava/lang/String;\n"
    "\n"
    '    const-string v1, "image_download"\n'
    "\n"
    "    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n"
    "\n"
    "    move-result v0\n"
    "\n"
    "    if-eqz v0, :cond_0\n"
    "\n"
    "    const/4 v0, 0x1\n"
    "\n"
    "    return v0\n"
    "\n"
    "    :cond_0\n"
    "    iget-boolean v0, p0, Lcom/xingin/entities/notedetail/FunctionSwitch;->enable:Z\n"
    "\n"
    "    return v0\n"
    ".end method"
)


def patch_image_download_switch(smali_path: Path) -> dict:
    text = smali_path.read_text()
    pattern = r"^\.method public final b\(\)Z\n.*?^\.end method"
    methods = list(re.finditer(pattern, text, re.M | re.S))
    if len(methods) != 1:
        raise ValueError("Expected exactly one FunctionSwitch enable getter")
    match = methods[0]
    original = match.group()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_METHOD_SHA:
        raise ValueError(
            "FunctionSwitch enable getter differs from the verified REDnote 9.48.1 input"
        )
    if original != ORIGINAL_BODY:
        raise ValueError("Unexpected FunctionSwitch enable getter layout")
    smali_path.write_text(text[: match.start()] + PATCHED_BODY + text[match.end():])
    return {
        "class": CLASS,
        "method": METHOD + PROTO,
        "originalMethodSha256": EXPECTED_METHOD_SHA,
        "downloadType": DOWNLOAD_TYPE,
        "imageDownloadEnabled": True,
        "otherFunctionSwitchesUnchanged": True,
        "serverPayloadUnchanged": True,
        "scope": (
            "Only FunctionSwitch entries whose type is image_download report enabled; every "
            "other function switch, including edit, privacy, quote and video, keeps the "
            "server's enable value."
        ),
    }


def _compiled_units(dex, descriptor: str, method: str, proto: str) -> list[int]:
    definitions = dex.class_definitions(descriptor)
    if len(definitions) != 1:
        raise ValueError("Expected one FunctionSwitch class in classes12.dex")
    matches = [
        (index, code)
        for index, _, code in dex.method_records(definitions[0])
        if dex.method_id(index) == (descriptor, method, proto)
    ]
    if len(matches) != 1:
        raise ValueError("Expected one compiled FunctionSwitch enable getter")
    _, code = matches[0]
    insns_off, count = dex.code_info(code)
    return list(struct.unpack_from("<" + "H" * count, dex.data, insns_off))


def verify_compiled_image_download_switch(apk: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read("classes12.dex"), "classes12.dex")
    units = _compiled_units(dex, DESCRIPTOR, METHOD, PROTO)

    string_hits = 0
    equals_calls = 0
    branch_count = 0
    true_return = 0
    field_reads = 0
    position = 0
    decoded: list[tuple[int, int]] = []
    while position < len(units):
        decoded.append((position, units[position]))
        position += dex._instruction_width(units, position)

    for position, unit in decoded:
        opcode = unit & 0xFF
        if opcode == 0x1A:
            if dex.string(units[position + 1]) == DOWNLOAD_TYPE:
                string_hits += 1
        elif opcode in (0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78):
            if dex.method_id(units[position + 1]) == (
                "Ljava/lang/String;",
                "equals",
                "(Ljava/lang/Object;)Z",
            ):
                equals_calls += 1
        elif opcode == 0x38:
            branch_count += 1
        elif opcode == 0x55:
            if dex.field_id(units[position + 1]) == (DESCRIPTOR, "enable", "Z"):
                field_reads += 1
        if opcode == 0x12:
            register = (unit >> 8) & 0xF
            literal = (unit >> 12) & 0xF
            if register == 0 and literal == 1:
                if position + 1 < len(units) and (units[position + 1] & 0xFF) == 0x0F:
                    true_return += 1

    if string_hits != 1:
        raise ValueError("Compiled image-download switch lost the type check")
    if equals_calls != 1:
        raise ValueError("Compiled image-download switch lost the type comparison")
    if branch_count != 1:
        raise ValueError("Compiled image-download switch lost the type branch")
    if true_return != 1:
        raise ValueError("Compiled image-download switch does not return true for image_download")
    if field_reads != 1:
        raise ValueError("Compiled image-download switch lost the original enable field read")
    return {
        "verified": True,
        "dex": "classes12.dex",
        "class": CLASS,
        "method": METHOD + PROTO,
        "downloadType": DOWNLOAD_TYPE,
        "returnsTrueForImageDownload": True,
        "otherSwitchesKeepStoredFlag": True,
    }
