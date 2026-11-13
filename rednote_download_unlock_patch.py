"""Pinned REDnote 9.48.1 author-disabled download unlock.

The server marks notes whose author disabled saving through
``MediaSaveConfig.disableSaveMedia`` (serialized field ``disable_save``).
Every client-side save/download gate reads that value through
``MediaSaveConfig.d()``: the image-gallery state, the long-press and
note-detail click handlers, the paid-download path and the gallery
controllers. Returning false from this getter makes all of them take their
normal allowed branch while the stored field, Parcel representation, equals,
hashCode and the server payload stay untouched.
"""

import hashlib
import re
from pathlib import Path
import struct
import sys
import zipfile

CLASS = "com.xingin.entities.MediaSaveConfig"
DESCRIPTOR = "Lcom/xingin/entities/MediaSaveConfig;"
# The getter name is obfuscated per build: 9.48.1 used ``d()``, 9.54.0 uses ``b()``.
METHOD = "b"
PROTO = "()Z"
# Pinned sha256 of ``MediaSaveConfig.b()Z`` in REDnote 9.54.0 (9540804),
# APKEditor 1.4.9 / jf decode. Recompute for a new base build.
EXPECTED_METHOD_SHA = "4c2a4a1f4fa80d67009e64a7dd682829bee5cd1cb8e089e890e8328f9724ef10"
DISABLED_FIELD_READ = (
    "    iget-boolean v0, p0, Lcom/xingin/entities/MediaSaveConfig;->"
    "disableSaveMedia:Z\n"
)
ALLOWED_RETURN = "    const/4 v0, 0x0\n"


def patch_media_save_config(smali_path: Path) -> dict:
    text = smali_path.read_text()
    pattern = rf"^\.method public final {METHOD}\(\)Z\n.*?^\.end method"
    methods = list(re.finditer(pattern, text, re.M | re.S))
    if len(methods) != 1:
        raise ValueError("Expected exactly one MediaSaveConfig download getter")
    match = methods[0]
    original = match.group()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_METHOD_SHA:
        raise ValueError(
            "MediaSaveConfig download getter differs from the verified REDnote input"
        )
    if original.count(DISABLED_FIELD_READ) != 1:
        raise ValueError("Unexpected MediaSaveConfig download getter layout")
    patched = original.replace(DISABLED_FIELD_READ, ALLOWED_RETURN, 1)
    smali_path.write_text(text[: match.start()] + patched + text[match.end():])
    return {
        "class": CLASS,
        "method": METHOD + PROTO,
        "originalMethodSha256": EXPECTED_METHOD_SHA,
        "disabledFlagBypassed": True,
        "storedFieldPreserved": True,
        "parcelPreserved": True,
        "equalsAndHashCodePreserved": True,
        "serverPayloadUnchanged": True,
        "scope": (
            "MediaSaveConfig.b() is the single permission getter consumed by the image-gallery "
            "state, long-press/detail click gates, paid-download path and gallery controllers. "
            "The disable_save field and every other MediaSaveConfig getter remain unchanged."
        ),
    }


def _compiled_units(dex, descriptor: str, method: str, proto: str) -> list[int]:
    definitions = dex.class_definitions(descriptor)
    if len(definitions) != 1:
        raise ValueError("Expected one MediaSaveConfig class in classes12.dex")
    matches = [
        (index, code)
        for index, _, code in dex.method_records(definitions[0])
        if dex.method_id(index) == (descriptor, method, proto)
    ]
    if len(matches) != 1:
        raise ValueError("Expected one compiled MediaSaveConfig download getter")
    _, code = matches[0]
    insns_off, count = dex.code_info(code)
    return list(struct.unpack_from("<" + "H" * count, dex.data, insns_off))


def verify_compiled_download_unlock(apk: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read("classes12.dex"), "classes12.dex")
    units = _compiled_units(dex, DESCRIPTOR, METHOD, PROTO)
    if units != [0x0012, 0x000F]:
        raise ValueError(
            "Compiled MediaSaveConfig download getter is not const/4 v0, 0 followed by return v0"
        )
    return {
        "verified": True,
        "dex": "classes12.dex",
        "class": CLASS,
        "method": METHOD + PROTO,
        "returnsFalse": True,
        "instructionCount": 2,
    }
