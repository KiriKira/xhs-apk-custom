"""Pinned REDnote 9.48.1 share-panel download unlock.

The share sheet's save entry is a ``ShareInfoDetail$Operate`` of type
``download_all_image_new``. When the author disabled downloads, the server
sets ``disable=true`` and ``disableToast``; ``ShareUserView`` renders the icon
at 50% alpha and the click handler shows the toast instead of saving.

``Operate.b()`` is the single getter every share-panel consumer uses for the
disabled flag. Return false only for that download entry, keep the stored
value for every other share action, and leave ``disableToast`` and the rest
of the model untouched.
"""

import hashlib
import re
from pathlib import Path
import struct
import sys
import zipfile

CLASS = "com.xingin.entities.ShareInfoDetail$Operate"
DESCRIPTOR = "Lcom/xingin/entities/ShareInfoDetail$Operate;"
METHOD = "b"
PROTO = "()Z"
DOWNLOAD_TYPE = "download_all_image_new"
EXPECTED_METHOD_SHA = "90676c712d0c077e10515130c6cb47188023373b6a264ea12e8e7586d0e96434"
ORIGINAL_BODY = (
    ".method public final b()Z\n"
    "    .locals 1\n"
    "\n"
    "    .line 1\n"
    "    iget-boolean v0, p0, Lcom/xingin/entities/ShareInfoDetail$Operate;->disable:Z\n"
    "\n"
    "    return v0\n"
    ".end method"
)
PATCHED_BODY = (
    ".method public final b()Z\n"
    "    .locals 2\n"
    "\n"
    "    .line 1\n"
    "    iget-object v0, p0, Lcom/xingin/entities/ShareInfoDetail$Operate;->type:Ljava/lang/String;\n"
    "\n"
    '    const-string v1, "download_all_image_new"\n'
    "\n"
    "    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n"
    "\n"
    "    move-result v0\n"
    "\n"
    "    if-eqz v0, :cond_0\n"
    "\n"
    "    const/4 v0, 0x0\n"
    "\n"
    "    return v0\n"
    "\n"
    "    :cond_0\n"
    "    iget-boolean v0, p0, Lcom/xingin/entities/ShareInfoDetail$Operate;->disable:Z\n"
    "\n"
    "    return v0\n"
    ".end method"
)


def patch_share_panel_download(smali_path: Path) -> dict:
    text = smali_path.read_text()
    pattern = r"^\.method public final b\(\)Z\n.*?^\.end method"
    methods = list(re.finditer(pattern, text, re.M | re.S))
    if len(methods) != 1:
        raise ValueError("Expected exactly one ShareInfoDetail$Operate disable getter")
    match = methods[0]
    original = match.group()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_METHOD_SHA:
        raise ValueError(
            "ShareInfoDetail$Operate disable getter differs from the verified REDnote 9.48.1 input"
        )
    if original != ORIGINAL_BODY:
        raise ValueError("Unexpected ShareInfoDetail$Operate disable getter layout")
    smali_path.write_text(text[: match.start()] + PATCHED_BODY + text[match.end():])
    return {
        "class": CLASS,
        "method": METHOD + PROTO,
        "originalMethodSha256": EXPECTED_METHOD_SHA,
        "downloadType": DOWNLOAD_TYPE,
        "downloadEntryEnabled": True,
        "otherShareEntriesUnchanged": True,
        "disableToastPreserved": True,
        "serverPayloadUnchanged": True,
        "scope": (
            "Only ShareInfoDetail$Operate entries whose type is download_all_image_new "
            "report enabled; every other share entry keeps the server's disable value."
        ),
    }


def _compiled_units(dex, descriptor: str, method: str, proto: str) -> list[int]:
    definitions = dex.class_definitions(descriptor)
    if len(definitions) != 1:
        raise ValueError("Expected one ShareInfoDetail$Operate class in classes12.dex")
    matches = [
        (index, code)
        for index, _, code in dex.method_records(definitions[0])
        if dex.method_id(index) == (descriptor, method, proto)
    ]
    if len(matches) != 1:
        raise ValueError("Expected one compiled ShareInfoDetail$Operate disable getter")
    _, code = matches[0]
    insns_off, count = dex.code_info(code)
    return list(struct.unpack_from("<" + "H" * count, dex.data, insns_off))


def verify_compiled_share_panel_patch(apk: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read("classes12.dex"), "classes12.dex")
    units = _compiled_units(dex, DESCRIPTOR, METHOD, PROTO)

    string_hits = 0
    equals_calls = 0
    branch_count = 0
    false_return = 0
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
            if dex.field_id(units[position + 1]) == (
                DESCRIPTOR,
                "disable",
                "Z",
            ):
                field_reads += 1
        if opcode == 0x12 and ((unit >> 8) & 0xF) == 0 and ((unit >> 12) & 0xF) == 0:
            if position + 1 < len(units) and (units[position + 1] & 0xFF) == 0x0F:
                false_return += 1

    if string_hits != 1:
        raise ValueError("Compiled share-panel patch lost the download type check")
    if equals_calls != 1:
        raise ValueError("Compiled share-panel patch lost the type comparison")
    if branch_count != 1:
        raise ValueError("Compiled share-panel patch lost the type branch")
    if false_return != 1:
        raise ValueError("Compiled share-panel patch does not return false for the download entry")
    if field_reads != 1:
        raise ValueError("Compiled share-panel patch lost the original disable field read")
    return {
        "verified": True,
        "dex": "classes12.dex",
        "class": CLASS,
        "method": METHOD + PROTO,
        "downloadType": DOWNLOAD_TYPE,
        "returnsFalseForDownloadEntry": True,
        "otherEntriesKeepStoredFlag": True,
    }
