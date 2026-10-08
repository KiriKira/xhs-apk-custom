"""Narrow WeChat share identity experiment for the cloned REDnote app.

Only ``MMessageActV2.send`` is edited. The app's real package name is still
read from Context; the declared official package is used for the two
identity-bearing fields only when the outgoing command is SendMessageToWX
(command 2) and the target is the official WeChat package.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
import zipfile


REAL_PACKAGE = "com.kirikira.rednote.fold"
OFFICIAL_PACKAGE = "com.xingin.xhs"
WECHAT_PACKAGE = "com.tencent.mm"
COMMAND_TYPE = 2
COMMAND_KEY = "_wxapi_command_type"
TARGET_CLASS = "Lcom/tencent/mm/opensdk/channel/MMessageActV2;"
TARGET_METHOD = "send"
TARGET_PROTO = "(Landroid/content/Context;Lcom/tencent/mm/opensdk/channel/MMessageActV2$Args;)Z"
TARGET_DEX = "classes4.dex"
METHOD_PATTERN = (
    r"^\.method public static send\(Landroid/content/Context;"
    r"Lcom/tencent/mm/opensdk/channel/MMessageActV2\$Args;\)Z\n"
    r".*?^\.end method"
)
EXPECTED_SEND_SHA256 = "222d8c3510ecf31ad90d09de9a3a3c7a8fc12eb939ff6ca5ee8d9fb4154accba"
PATCH_MARKER = "# rednote-wechat-share-identity-command2"

CONTEXT_PACKAGE_CALL = (
    "invoke-virtual {p0}, Landroid/content/Context;->getPackageName()Ljava/lang/String;"
)
APP_PACKAGE_EXTRA_KEY = 'const-string v4, "_mmessage_appPackage"'
APP_PACKAGE_EXTRA_CALL = (
    "invoke-virtual {v2, v4, v3}, "
    "Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;"
)
CHECKSUM_CALL = (
    "invoke-static {v4, v5, v3}, "
    "Lcom/tencent/mm/opensdk/channel/a/a;->a(Ljava/lang/String;ILjava/lang/String;)[B"
)


def _validate_package(package: str) -> None:
    if not isinstance(package, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", package
    ):
        raise ValueError("Claimed package must be a dotted Android package name")


def _guard(claimed_package: str) -> str:
    return f"""    {PATCH_MARKER}
    # v3 remains the Context package except for WeChat SendMessageToWX.
    iget-object v4, p1, Lcom/tencent/mm/opensdk/channel/MMessageActV2$Args;->bundle:Landroid/os/Bundle;
    if-eqz v4, :rednote_wechat_share_identity_done
    const-string v5, "{COMMAND_KEY}"
    const/4 v6, 0x0
    invoke-virtual {{v4, v5, v6}}, Landroid/os/BaseBundle;->getInt(Ljava/lang/String;I)I
    move-result v4
    const/4 v5, 0x2
    if-ne v4, v5, :rednote_wechat_share_identity_done
    iget-object v4, p1, Lcom/tencent/mm/opensdk/channel/MMessageActV2$Args;->targetPkgName:Ljava/lang/String;
    const-string v5, "{WECHAT_PACKAGE}"
    invoke-virtual {{v4, v5}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-eqz v4, :rednote_wechat_share_identity_done
    const-string v3, "{claimed_package}"
    :rednote_wechat_share_identity_done
"""


def _count_method_baseline(method: str) -> dict[str, int]:
    return {
        "contextGetPackageName": method.count(CONTEXT_PACKAGE_CALL),
        "appPackageExtraKey": method.count(APP_PACKAGE_EXTRA_KEY),
        "appPackageExtraCall": method.count(APP_PACKAGE_EXTRA_CALL),
        "checksumHelperCall": method.count(CHECKSUM_CALL),
        "bundleFieldRead": method.count(
            "iget-object v3, p1, Lcom/tencent/mm/opensdk/channel/MMessageActV2$Args;->bundle:Landroid/os/Bundle;"
        ),
    }


def patch_send_share_identity(smali_path: Path, claimed_package: str) -> dict:
    """Patch exactly the pinned SDK send method and return a review audit."""

    _validate_package(claimed_package)
    smali_path = Path(smali_path)
    text = smali_path.read_text(encoding="utf-8")
    matches = list(re.finditer(METHOD_PATTERN, text, re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        raise ValueError("Expected exactly one pinned MMessageActV2.send method")
    match = matches[0]
    original = match.group()
    if PATCH_MARKER in original:
        raise ValueError("WeChat share identity method is already patched")
    original_sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if original_sha != EXPECTED_SEND_SHA256:
        raise ValueError("MMessageActV2.send differs from the pinned source method")

    before_counts = _count_method_baseline(original)
    if before_counts != {
        "contextGetPackageName": 1,
        "appPackageExtraKey": 1,
        "appPackageExtraCall": 2,
        "checksumHelperCall": 1,
        "bundleFieldRead": 1,
    }:
        raise ValueError("Pinned MMessageActV2.send has unexpected identity call counts")
    anchor = CONTEXT_PACKAGE_CALL + "\n\n    move-result-object v3\n"
    if original.count(anchor) != 1:
        raise ValueError("Pinned MMessageActV2.send has an unexpected package read anchor")

    patched = original.replace(anchor, anchor + "\n" + _guard(claimed_package), 1)
    # Keep the on-disk change bounded to this exact method.
    smali_path.write_text(text[: match.start()] + patched + text[match.end() :], encoding="utf-8")
    return {
        "enabled": True,
        "strategy": "experiment",
        "realPackage": REAL_PACKAGE,
        "claimedPackage": claimed_package,
        "commandType": COMMAND_TYPE,
        "commandKey": COMMAND_KEY,
        "targetPackage": WECHAT_PACKAGE,
        "class": TARGET_CLASS,
        "method": f"{TARGET_METHOD}{TARGET_PROTO}",
        "originalMethodSha256": EXPECTED_SEND_SHA256,
        "methodCount": len(matches),
        "methodScopedCounts": {
            **before_counts,
            "commandTypeGuard": 1,
            "targetPackageGuard": 1,
            "claimedPackageConst": 1,
        },
        "contextPackageRetained": True,
        "shareOnlyGuard": True,
        "packageExtraAndChecksumUseClaim": True,
        "originalCallsRetained": True,
    }


def _instructions(method):
    try:
        return list(method.get_instructions())
    except Exception as exc:  # Androguard errors need an actionable boundary.
        raise ValueError(f"Could not decode compiled MMessageActV2.send: {exc}") from exc


def _output(instruction) -> str:
    return instruction.get_output()


def _matching_indexes(instructions, predicate) -> list[int]:
    return [index for index, instruction in enumerate(instructions) if predicate(instruction)]


def _branch_target_units(instruction, current_units: int) -> int | None:
    # Androguard exposes DEX branch offsets in 16-bit code units.
    for operand in instruction.get_operands():
        if len(operand) >= 2 and getattr(operand[0], "name", "") == "OFFSET":
            return current_units + int(operand[1])
    return None


def _is_literal(instruction, register: str, value: int) -> bool:
    if instruction.get_name() != "const/4" or not _output(instruction).replace(" ", "").startswith(
        register + ","
    ):
        return False
    return any(
        len(operand) >= 2
        and getattr(operand[0], "name", "") == "LITERAL"
        and int(operand[1]) == value
        for operand in instruction.get_operands()
    )


def _verify_compiled_method(method, claimed_package: str) -> dict:
    instructions = _instructions(method)
    # Androguard formats method/field prototypes with spaces between types;
    # compact disassembly references before matching exact descriptors.
    outputs = [_output(item).replace(" ", "") for item in instructions]
    names = [item.get_name() for item in instructions]
    joined = "\n".join(outputs)

    package_call_indexes = _matching_indexes(
        instructions,
        lambda item: "Landroid/content/Context;->getPackageName()Ljava/lang/String;" in _output(item),
    )
    if len(package_call_indexes) != 1:
        raise ValueError("Compiled send must retain one Context.getPackageName call")
    package_call_index = package_call_indexes[0]

    def has_output(fragment: str):
        return lambda item: fragment in _output(item).replace(" ", "")

    command_key_indexes = _matching_indexes(instructions, has_output(COMMAND_KEY))
    get_int_indexes = _matching_indexes(
        instructions,
        has_output("Landroid/os/BaseBundle;->getInt(Ljava/lang/String;I)I"),
    )
    target_pkg_indexes = _matching_indexes(
        instructions,
        has_output("MMessageActV2$Args;->targetPkgNameLjava/lang/String;"),
    )
    bundle_indexes = _matching_indexes(
        instructions,
        has_output("MMessageActV2$Args;->bundleLandroid/os/Bundle;"),
    )
    string_equals_indexes = _matching_indexes(
        instructions, has_output("Ljava/lang/String;->equals(Ljava/lang/Object;)Z")
    )
    claim_indexes = _matching_indexes(
        instructions,
        lambda item: item.get_name() in ("const-string", "const-string/jumbo")
        and claimed_package in _output(item),
    )
    wechat_indexes = _matching_indexes(
        instructions,
        lambda item: item.get_name() in ("const-string", "const-string/jumbo")
        and WECHAT_PACKAGE in _output(item),
    )
    package_extra_key_indexes = _matching_indexes(
        instructions, has_output("_mmessage_appPackage")
    )
    package_extra_call_indexes = _matching_indexes(
        instructions,
        has_output("Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;"),
    )
    checksum_indexes = _matching_indexes(
        instructions,
        has_output("Lcom/tencent/mm/opensdk/channel/a/a;->a(Ljava/lang/String;ILjava/lang/String;)[B"),
    )
    if not all(
        len(found) == 1
        for found in (
            command_key_indexes,
            get_int_indexes,
            string_equals_indexes,
            claim_indexes,
            wechat_indexes,
            package_extra_key_indexes,
            checksum_indexes,
        )
    ):
        raise ValueError("Compiled send is missing a unique share identity guard or original identity call")
    if len(target_pkg_indexes) < 1 or len(bundle_indexes) != 2 or len(package_extra_call_indexes) != 3:
        raise ValueError("Compiled send has unexpected target or Intent extra call counts")

    command_key_index = command_key_indexes[0]
    get_int_index = get_int_indexes[0]
    claim_index = claim_indexes[0]
    wechat_index = wechat_indexes[0]
    package_extra_key_index = package_extra_key_indexes[0]
    checksum_index = checksum_indexes[0]
    guard_bundle_indexes = [
        index for index in bundle_indexes
        if package_call_index < index < command_key_index
    ]
    if len(guard_bundle_indexes) != 1:
        raise ValueError("Compiled share guard must read exactly one Args bundle after Context identity")
    if not (
        package_call_index < command_key_index < get_int_index < claim_index
        < package_extra_key_index < checksum_index
    ):
        raise ValueError("Compiled share identity guard is outside the package/checksum path")
    if not (
        command_key_index < target_pkg_indexes[-1] < string_equals_indexes[0] < claim_index
        and wechat_index < string_equals_indexes[0]
        and guard_bundle_indexes[0] < command_key_index
    ):
        raise ValueError("Compiled target package check does not guard the claimed package")

    # Both mismatch branches must jump over the claimed-package const-string.
    code_units: list[int] = []
    cursor_bytes = 0
    for instruction in instructions:
        code_units.append(cursor_bytes // 2)
        cursor_bytes += instruction.get_length()
    claim_register = re.search(r"^(v\d+),", outputs[claim_index])
    if claim_register is None or claim_register.group(1) != "v3":
        raise ValueError("Compiled claimed package is not loaded into the identity register v3")
    after_claim_units = code_units[claim_index] + instructions[claim_index].get_length() // 2
    guard_branch_indexes = [
        index
        for index in range(package_call_index + 1, claim_index)
        if names[index] in ("if-ne", "if-eqz")
    ]
    if len(guard_branch_indexes) != 3:
        # The third branch handles a null bundle and must also skip the override.
        raise ValueError("Compiled share-only guard must contain null, command, and target branches")
    branch_names = [names[index] for index in guard_branch_indexes]
    if branch_names.count("if-ne") != 1 or branch_names.count("if-eqz") != 2:
        raise ValueError("Compiled share-only guard has unexpected branch conditions")
    command_branch = next(i for i in guard_branch_indexes if names[i] == "if-ne")
    null_or_target_branches = [i for i in guard_branch_indexes if names[i] == "if-eqz"]
    guard_bundle = guard_bundle_indexes[0]
    bundle_branch_indexes = [
        i for i in null_or_target_branches if guard_bundle < i < command_key_index
    ]
    target_branch_indexes = [
        i for i in null_or_target_branches if string_equals_indexes[0] < i < claim_index
    ]
    target_pkg_index = target_pkg_indexes[-1]
    equals_index = string_equals_indexes[0]
    if not (
        len(bundle_branch_indexes) == 1
        and len(target_branch_indexes) == 1
        and bundle_branch_indexes[0] == guard_bundle + 1
        and command_key_index == bundle_branch_indexes[0] + 1
        and names[command_key_index + 1] == "const/4"
        and outputs[command_key_index + 1].startswith("v6,")
        and _is_literal(instructions[command_key_index + 1], "v6", 0)
        and get_int_index == command_key_index + 2
        and outputs[guard_bundle].startswith("v4,")
        and outputs[command_key_index].startswith("v5,")
        and outputs[get_int_index].startswith("v4,v5,v6,")
        and get_int_index + 1 < len(instructions)
        and names[get_int_index + 1] == "move-result"
        and outputs[get_int_index + 1] == "v4"
        and command_branch == get_int_index + 3
        and _is_literal(instructions[command_branch - 1], "v5", COMMAND_TYPE)
        and outputs[command_branch].startswith("v4,v5,")
        and target_pkg_index == command_branch + 1
        and outputs[target_pkg_index].startswith("v4,")
        and wechat_index == target_pkg_index + 1
        and outputs[wechat_index].startswith("v5,")
        and equals_index == wechat_index + 1
        and outputs[equals_index].startswith("v4,v5,")
        and equals_index + 1 < len(instructions)
        and names[equals_index + 1] == "move-result"
        and outputs[equals_index + 1] == "v4"
        and len(target_branch_indexes) == 1
        and target_branch_indexes[0] == equals_index + 2
        and outputs[target_branch_indexes[0]].startswith("v4,")
        and claim_index == target_branch_indexes[0] + 1
    ):
        raise ValueError("Compiled guard does not compare command 2 and target com.tencent.mm")
    if any(
        _branch_target_units(instructions[index], code_units[index]) != after_claim_units
        for index in guard_branch_indexes
    ):
        raise ValueError("Compiled non-share branch can reach the claimed identity override")

    # The original intent/checksum path remains present and still consumes v3.
    app_put = [
        i for i in package_extra_call_indexes
        if i == package_extra_key_index + 1 and "v2,v4,v3" in outputs[i]
    ]
    if len(app_put) != 1 or "v4,v5,v3" not in outputs[checksum_index]:
        raise ValueError("Compiled appPackage extra and checksum do not consume the guarded identity")
    required_original = (
        "Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;",
        "Intent;->putExtras(Landroid/os/Bundle;)Landroid/content/Intent;",
        "_mmessage_content",
        "_message_token",
        "Context;->startActivity(Landroid/content/Intent;)V",
        "MMessageActV2;->sendUsingPendingIntent(Landroid/content/Context;Landroid/content/Intent;)V",
    )
    if not all(fragment in joined for fragment in required_original):
        raise ValueError("Compiled send no longer retains the original intent and dispatch calls")
    return {
        "verified": True,
        "dexMethod": f"{TARGET_CLASS}->{TARGET_METHOD}{TARGET_PROTO}",
        "contextPackageRetained": True,
        "shareOnlyGuard": True,
        "guardBranchesSkipOverride": True,
        "packageExtraAndChecksumUseClaim": True,
        "originalCallsRetained": True,
        "commandType": COMMAND_TYPE,
        "targetPackage": WECHAT_PACKAGE,
        "claimedPackage": claimed_package,
    }


def verify_compiled_wechat_share_identity(apk: Path, package: str) -> dict:
    """Inspect the compiled DEX with Androguard and verify the bounded guard."""

    _validate_package(package)
    try:
        from androguard.core.dex import DEX
        from loguru import logger
    except ImportError as exc:
        raise RuntimeError("Androguard is required to verify compiled WeChat share identity") from exc
    logger.disable("androguard")

    apk = Path(apk)
    matches = []
    with zipfile.ZipFile(apk) as archive:
        if TARGET_DEX not in archive.namelist():
            raise ValueError(f"Expected {TARGET_DEX} in the APK")
        dex = DEX(archive.read(TARGET_DEX))
        for class_def in dex.get_classes():
            if class_def.get_name() != TARGET_CLASS:
                continue
            for method in class_def.get_methods():
                descriptor = method.get_descriptor().replace(" ", "")
                if method.get_name() == TARGET_METHOD and descriptor == TARGET_PROTO:
                    matches.append((TARGET_DEX, method))
    if len(matches) != 1:
        raise ValueError("Expected exactly one compiled MMessageActV2.send method in the APK")
    dex_name, method = matches[0]
    return {
        "verified": True,
        "dex": dex_name,
        **_verify_compiled_method(method, package),
    }
