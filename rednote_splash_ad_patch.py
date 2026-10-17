"""Pinned REDnote 9.48.1 cold-start splash-ad display patch; requests stay intact.

The cold-start controller waits for a splash-ad result and hands it to
``uy.f.a(qe.o, onAd, onNoAd)``. That method is the single dispatcher used by
``SplashV2Controller``; the callback path with an ad builds the home view with
the ad attached, while the no-ad path builds it without one. Forcing the
dispatch to the no-ad branch removes the splash ad without touching the
request, its payload download, or any surrounding startup logic.
"""

import hashlib
import re
from pathlib import Path
import struct
import sys
import zipfile

DISPATCH_CLASS = "uy.f"
DISPATCH_DESCRIPTOR = "Luy/f;"
DISPATCH_METHOD = "a"
DISPATCH_PROTO = (
    "(Lqe/o;Lkotlin/jvm/functions/Function1;Lkotlin/jvm/functions/Function1;)V"
)
EXPECTED_METHOD_SHA = "00b0227cecdab5073d2806b8d44aa79d7fa6e3d4e17e3e8151987b277d5e72dc"
AD_BRANCH = "    if-eqz v0, :cond_0\n"
NO_AD_BRANCH = "    goto :cond_0\n"
QUERY_CALL = "    invoke-virtual {p1}, Lqe/o;->c()Z\n"
AD_CALLBACK = (
    "    invoke-interface {p2, p1}, Lkotlin/jvm/functions/Function1;->"
    "invoke(Ljava/lang/Object;)Ljava/lang/Object;\n"
)
NO_AD_CALLBACK = (
    "    invoke-interface {p3, p1}, Lkotlin/jvm/functions/Function1;->"
    "invoke(Ljava/lang/Object;)Ljava/lang/Object;\n"
)
NO_AD_MARKER_FIELD = ("Lgz/f;", "a", "Lgz/f;")
FUNCTION1_INVOKE = (
    "Lkotlin/jvm/functions/Function1;",
    "invoke",
    "(Ljava/lang/Object;)Ljava/lang/Object;",
)


def patch_splash_ad_dispatch(smali_path: Path) -> dict:
    text = smali_path.read_text()
    pattern = r"^\.method public final a\(Lqe/o;.*?^\.end method"
    methods = list(re.finditer(pattern, text, re.M | re.S))
    if len(methods) != 1:
        raise ValueError("Expected exactly one cold-start splash-ad dispatch method")
    match = methods[0]
    original = match.group()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_METHOD_SHA:
        raise ValueError(
            "Splash-ad dispatch method differs from the verified REDnote 9.48.1 input"
        )
    if original.count(AD_BRANCH) != 1 or original.count(QUERY_CALL) != 1:
        raise ValueError("Unexpected splash-ad dispatch branch layout")
    if original.count(AD_CALLBACK) != 1 or original.count(NO_AD_CALLBACK) != 1:
        raise ValueError("Unexpected splash-ad callback layout")
    patched = original.replace(AD_BRANCH, NO_AD_BRANCH, 1)
    smali_path.write_text(text[: match.start()] + patched + text[match.end():])
    return {
        "class": DISPATCH_CLASS,
        "method": DISPATCH_METHOD + DISPATCH_PROTO,
        "originalMethodSha256": EXPECTED_METHOD_SHA,
        "adBranchBypassed": True,
        "adCallbackRetained": True,
        "noAdCallbackRetained": True,
        "requestsUnchanged": True,
        "displayState": "The home view is created through the original no-ad path",
        "scope": (
            "Cold-start splash-ad result dispatch in SplashV2Controller. The ad request, "
            "payload download, telemetry and all other ad surfaces are unchanged."
        ),
    }


def _signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


def _signed_short(value: int) -> int:
    return value - 65536 if value >= 32768 else value


def _signed_int(value: int) -> int:
    return value - 4294967296 if value >= 2147483648 else value


def _compiled_layout(dex) -> tuple[list[int], list[tuple[int, int]]]:
    definitions = dex.class_definitions(DISPATCH_DESCRIPTOR)
    if len(definitions) != 1:
        raise ValueError("Expected one splash-ad dispatcher in classes4.dex")
    records = dex.method_records(definitions[0])
    matches = [
        (index, code)
        for index, _, code in records
        if dex.method_id(index) == (DISPATCH_DESCRIPTOR, DISPATCH_METHOD, DISPATCH_PROTO)
    ]
    if len(matches) != 1:
        raise ValueError("Expected one compiled splash-ad dispatch method")
    _, code = matches[0]
    _, count = dex.code_info(code)
    units = list(struct.unpack_from("<" + "H" * count, dex.data, code + 16))
    instructions: list[tuple[int, int]] = []
    position = 0
    while position < len(units):
        instructions.append((position, units[position]))
        position += dex._instruction_width(units, position)
    return units, instructions


def verify_compiled_splash_patch(apk: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read("classes4.dex"), "classes4.dex")
    units, instructions = _compiled_layout(dex)

    query_positions = []
    callback_count = 0
    eqz_positions = []
    for position, unit in instructions:
        opcode = unit & 0xFF
        if opcode in (0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78):
            method = dex.method_id(units[position + 1])
            if method == ("Lqe/o;", "c", "()Z"):
                query_positions.append(position)
            if method == FUNCTION1_INVOKE and opcode in (0x72, 0x78):
                callback_count += 1
        elif opcode == 0x38:
            eqz_positions.append(position)

    if len(query_positions) != 1:
        raise ValueError("Expected one compiled splash-ad query call")
    if eqz_positions:
        raise ValueError("Compiled splash-ad dispatch still contains a conditional branch")
    if callback_count != 2:
        raise ValueError("Compiled splash-ad dispatch must retain both result callbacks")

    query_position = query_positions[0]
    following = [item for item in instructions if item[0] > query_position]
    if not following or following[0][1] & 0xFF != 0x0A:
        raise ValueError("Compiled splash-ad query is not followed by move-result")
    branch = next(
        (item for item in following if (item[1] & 0xFF) in (0x28, 0x29, 0x2A, 0x38)),
        None,
    )
    if branch is None or branch[1] & 0xFF == 0x38:
        raise ValueError("Compiled splash-ad dispatch does not jump to the no-ad branch")

    branch_position = branch[0]
    branch_opcode = branch[1] & 0xFF
    if branch_opcode == 0x28:
        target = branch_position + _signed_byte((units[branch_position] >> 8) & 0xFF)
    elif branch_opcode == 0x29:
        target = branch_position + _signed_short(units[branch_position + 1])
    else:
        target = branch_position + _signed_int(
            units[branch_position + 1] | (units[branch_position + 2] << 16)
        )
    target_instruction = next((u for p, u in instructions if p == target), None)
    if target_instruction is None or target_instruction & 0xFF != 0x62:
        raise ValueError("Splash-ad branch target is not the no-ad marker load")
    if dex.field_id(units[target + 1]) != NO_AD_MARKER_FIELD:
        raise ValueError("Splash-ad branch target is not the verified no-ad path")

    return {
        "verified": True,
        "dex": "classes4.dex",
        "class": DISPATCH_CLASS,
        "method": DISPATCH_METHOD + DISPATCH_PROTO,
        "conditionalBranchRemoved": True,
        "unconditionalNoAdBranch": True,
        "bothResultCallbacksRetained": True,
    }
