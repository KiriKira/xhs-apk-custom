#!/usr/bin/env python3
"""Create a side-by-side Rednote APK from a locally supplied APK or XAPK.

This entry point intentionally does not use signature spoofing, installer spoofing,
or integrity-bypass helpers. For XAPK inputs it verifies every APK member before
merging the selected split set with APKEditor.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
APKEDITOR = SCRIPT_DIR / "bins" / "apkeditor.jar"
ANDROID_TOOL_ROOTS = (
    Path("/workspace/android-tools/android-15"),
    Path("/workspace/android-tools/android-14"),
)
ANDROID_NS = "http://schemas.android.com/apk/res/android"
ANDROID = "{" + ANDROID_NS + "}"
DEFAULT_APPLICATION_ID = "com.kirikira.rednote.fold"
DEFAULT_OUTPUT = SCRIPT_DIR / "output_apks" / "rednote-custom.apk"
MAX_XAPK_APK_BYTES = 1_500_000_000
MAX_XAPK_TOTAL_APK_BYTES = 2_000_000_000
MAX_XAPK_APK_COUNT = 64
MAX_XAPK_MANIFEST_BYTES = 4 * 1024 * 1024

COMPONENT_TAGS = {
    "activity",
    "activity-alias",
    "provider",
    "receiver",
    "service",
}
PERMISSION_NAME_TAGS = {
    "permission",
    "permission-group",
    "permission-tree",
    "uses-permission",
    "uses-permission-sdk-23",
    "uses-permission-sdk-m",
    "uses-permission-sdk-29",
    "uses-permission-sdk-33",
    "uses-permission-sdk-34",
    "uses-permission-sdk-35",
}
PERMISSION_DECLARATION_TAGS = {
    "permission",
    "permission-group",
    "permission-tree",
}
PERMISSION_REFERENCE_ATTRS = {
    "permission",
    "readPermission",
    "writePermission",
    "permissionGroup",
}
SIGNATURE_ENTRY_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC")


class BuildError(RuntimeError):
    """A user-actionable build failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_command(
    args: list[str | Path], *, env: dict[str, str] | None = None, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    command = [str(arg) for arg in args]
    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError(f"Could not run {Path(command[0]).name}: {exc}") from exc
    if result.returncode:
        tail = result.stdout[-5000:]
        raise BuildError(
            f"Command failed ({result.returncode}): {Path(command[0]).name}\n{tail}"
        )
    return result


def get_apkeditor_version() -> str:
    # APKEditor 1.4.9 prints its version and exits with status 2 for this
    # informational option. Accept that status only when a version is present.
    try:
        result = subprocess.run(
            ["java", "-jar", str(APKEDITOR), "-version"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError(f"Could not query APKEditor version: {exc}") from exc
    match = re.search(r"APKEditor version\s+[^\r\n]+", result.stdout)
    if result.returncode not in (0, 2) or not match:
        raise BuildError(
            f"Could not verify APKEditor version (exit {result.returncode}): {result.stdout[-2000:]}"
        )
    return match.group(0).strip()


def find_tool(name: str) -> Path:
    env_name = {
        "apksigner": "APKSIGNER",
        "aapt2": "AAPT2",
        "zipalign": "ZIPALIGN",
    }[name]
    candidates: list[Path] = []
    configured = os.environ.get(env_name)
    if configured:
        candidates.append(Path(configured).expanduser())
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    for android_home_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        android_home = os.environ.get(android_home_name)
        if android_home:
            candidates.extend(sorted(Path(android_home).glob(f"build-tools/*/{name}"), reverse=True))
            candidates.append(Path(android_home) / name)
    for root in ANDROID_TOOL_ROOTS:
        candidates.append(root / name)
        candidates.extend(sorted(root.glob(f"build-tools/*/{name}"), reverse=True))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    checked = ", ".join(str(candidate) for candidate in candidates if str(candidate))
    raise BuildError(f"Android tool {name} was not found. Checked: {checked or '(PATH)'}")


def validate_application_id(value: str) -> str:
    value = value.strip()
    if len(value) > 255 or len(value.split(".")) < 2:
        raise BuildError(f"Invalid applicationId: {value!r}")
    if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in value.split(".")):
        raise BuildError(
            f"Invalid applicationId {value!r}; use dot-separated Java package segments"
        )
    return value


def verify_apk_signature(path: Path, apksigner: Path) -> dict[str, Any]:
    result = run_command([apksigner, "verify", "--verbose", "--print-certs", path])
    signer_certs = sorted(
        set(
            re.findall(
                r"Signer #\d+ certificate SHA-256 digest:\s*([0-9a-fA-F]{64})",
                result.stdout,
            )
        )
    )
    if not signer_certs:
        raise BuildError(f"apksigner verified {path.name} but reported no signer certificate")
    source_stamp_certs = sorted(
        set(
            re.findall(
                r"Source Stamp Signer certificate SHA-256 digest:\s*([0-9a-fA-F]{64})",
                result.stdout,
            )
        )
    )
    return {
        "signerCertificateSha256": [value.lower() for value in signer_certs],
        "sourceStampCertificateSha256": [value.lower() for value in source_stamp_certs],
        "verification": "passed",
    }


def get_badging(path: Path, aapt2: Path) -> dict[str, str | None]:
    result = run_command([aapt2, "dump", "badging", path])
    package_line = next(
        (line for line in result.stdout.splitlines() if line.startswith("package:")), None
    )
    if not package_line:
        raise BuildError(f"aapt2 could not read package metadata from {path.name}")

    def field(name: str) -> str | None:
        match = re.search(rf"(?:^|\s){re.escape(name)}='([^']*)'", package_line)
        return match.group(1) if match else None

    package_name = field("name")
    version_code = field("versionCode")
    if not package_name or not version_code:
        raise BuildError(f"Incomplete package/version metadata in {path.name}: {package_line}")
    return {
        "packageName": package_name,
        "versionCode": version_code,
        "versionName": field("versionName") or None,
        "split": field("split"),
    }


def check_expected_digest(path: Path, expected: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected.strip()):
        raise BuildError("--sha256 must be a 64-character hexadecimal SHA-256 digest")
    actual = sha256_file(path)
    if actual.lower() != expected.strip().lower():
        raise BuildError(
            f"Input SHA-256 mismatch: expected {expected.strip().lower()}, got {actual}"
        )
    return actual


def _safe_member_basename(name: str) -> str:
    normalized = name.replace("\\", "/")
    basename = PurePosixPath(normalized).name
    if not basename or basename in {".", ".."}:
        raise BuildError(f"Invalid APK member name in XAPK: {name!r}")
    return basename


def extract_xapk_apks(xapk: Path, extract_dir: Path) -> tuple[list[Path], dict[str, Any] | None]:
    try:
        archive = zipfile.ZipFile(xapk)
    except (OSError, zipfile.BadZipFile) as exc:
        raise BuildError(f"XAPK is not a readable ZIP archive: {exc}") from exc

    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        apk_infos = [info for info in infos if info.filename.lower().endswith(".apk")]
        if not apk_infos:
            raise BuildError("XAPK contains no .apk files")
        if len(apk_infos) > MAX_XAPK_APK_COUNT:
            raise BuildError(f"XAPK contains too many APK files ({len(apk_infos)})")
        total_size = sum(info.file_size for info in apk_infos)
        if total_size > MAX_XAPK_TOTAL_APK_BYTES:
            raise BuildError(f"XAPK APK members exceed the {MAX_XAPK_TOTAL_APK_BYTES}-byte limit")

        names: set[str] = set()
        extracted: list[Path] = []
        for info in apk_infos:
            if info.flag_bits & 0x1:
                raise BuildError(f"Encrypted APK member is unsupported: {info.filename}")
            if info.file_size <= 0 or info.file_size > MAX_XAPK_APK_BYTES:
                raise BuildError(f"APK member size is invalid: {info.filename}")
            if info.compress_size == 0 or info.file_size / info.compress_size > 500:
                raise BuildError(f"Suspicious compression ratio in XAPK member: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise BuildError(f"Symlink APK member is unsupported: {info.filename}")
            basename = _safe_member_basename(info.filename)
            if basename.casefold() in names:
                raise BuildError(f"Duplicate APK member basename in XAPK: {basename}")
            names.add(basename.casefold())
            target = extract_dir / basename
            with archive.open(info, "r") as source, target.open("xb") as destination:
                copied = 0
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > info.file_size or copied > MAX_XAPK_APK_BYTES:
                        raise BuildError(f"APK member expanded beyond its declared size: {basename}")
                    destination.write(chunk)
            if copied != info.file_size:
                raise BuildError(f"Truncated APK member in XAPK: {basename}")
            extracted.append(target)

        xapk_manifest: dict[str, Any] | None = None
        manifest_info = next(
            (info for info in infos if PurePosixPath(info.filename.replace("\\", "/")).name == "manifest.json"),
            None,
        )
        if manifest_info:
            if manifest_info.file_size > MAX_XAPK_MANIFEST_BYTES:
                raise BuildError("XAPK manifest.json exceeds the size limit")
            try:
                value = json.loads(archive.read(manifest_info).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                raise BuildError(f"XAPK manifest.json is invalid: {exc}") from exc
            if isinstance(value, dict):
                xapk_manifest = value

    return extracted, xapk_manifest


def validate_xapk_members(
    apk_paths: list[Path], apksigner: Path, aapt2: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    members: list[dict[str, Any]] = []
    signer_set: tuple[str, ...] | None = None
    package_name: str | None = None
    version_code: str | None = None
    base_members: list[Path] = []
    split_names: set[str] = set()
    base_version_name: str | None = None

    for apk_path in apk_paths:
        signature = verify_apk_signature(apk_path, apksigner)
        badging = get_badging(apk_path, aapt2)
        current_signers = tuple(signature["signerCertificateSha256"])
        if signer_set is None:
            signer_set = current_signers
        elif current_signers != signer_set:
            raise BuildError(
                f"APK split signer mismatch in {apk_path.name}: {current_signers} != {signer_set}"
            )
        if package_name is None:
            package_name = badging["packageName"]
        elif badging["packageName"] != package_name:
            raise BuildError(
                f"APK split package mismatch in {apk_path.name}: {badging['packageName']} != {package_name}"
            )
        if version_code is None:
            version_code = badging["versionCode"]
        elif badging["versionCode"] != version_code:
            raise BuildError(
                f"APK split versionCode mismatch in {apk_path.name}: {badging['versionCode']} != {version_code}"
            )

        split_name = badging["split"]
        if split_name:
            if split_name in split_names:
                raise BuildError(f"Duplicate split name in XAPK: {split_name}")
            split_names.add(split_name)
        else:
            base_members.append(apk_path)
            base_version_name = badging["versionName"]

        with zipfile.ZipFile(apk_path) as member_zip:
            signature_entries = sorted(
                name for name in member_zip.namelist() if is_signature_metadata(name)
            )
        members.append(
            {
                "archiveMember": redact_phone_like_text(apk_path.name),
                "sha256": sha256_file(apk_path),
                "signatureMetadataEntries": signature_entries,
                **badging,
                **signature,
            }
        )

    if len(base_members) != 1:
        raise BuildError(f"XAPK must contain exactly one base APK; found {len(base_members)}")
    if not package_name or not version_code:
        raise BuildError("XAPK package metadata is incomplete")
    return members, {
        "packageName": package_name,
        "versionCode": version_code,
        "versionName": base_version_name,
        "baseApk": base_members[0],
        "splitNames": sorted(split_names),
    }


def validate_xapk_manifest(metadata: dict[str, Any] | None, app: dict[str, Any], apk_paths: list[Path]) -> None:
    if not metadata:
        return
    expected_package = metadata.get("package_name")
    if expected_package and expected_package != app["packageName"]:
        raise BuildError(
            f"XAPK manifest package mismatch: {expected_package} != {app['packageName']}"
        )
    expected_code = metadata.get("version_code")
    if expected_code is not None and str(expected_code) != app["versionCode"]:
        raise BuildError(
            f"XAPK manifest version mismatch: {expected_code} != {app['versionCode']}"
        )
    expected_name = metadata.get("version_name")
    if expected_name and app["versionName"] and expected_name != app["versionName"]:
        raise BuildError(
            f"XAPK manifest versionName mismatch: {expected_name} != {app['versionName']}"
        )
    declared = metadata.get("split_apks")
    if isinstance(declared, list):
        declared_names = {
            _safe_member_basename(str(item.get("file", ""))).casefold()
            for item in declared
            if isinstance(item, dict) and item.get("file")
        }
        extracted_names = {path.name.casefold() for path in apk_paths}
        if declared_names and declared_names != extracted_names:
            raise BuildError(
                "XAPK manifest split list does not match the extracted .apk members"
            )


def find_decoded_manifest(decoded_dir: Path) -> tuple[Path, ET.ElementTree, ET.Element]:
    valid: list[tuple[Path, ET.ElementTree, ET.Element]] = []
    for path in decoded_dir.rglob("AndroidManifest.xml"):
        try:
            tree = ET.parse(path)
        except (ET.ParseError, OSError):
            continue
        root = tree.getroot()
        if _local_name(root.tag) == "manifest":
            valid.append((path, tree, root))
    if len(valid) != 1:
        raise BuildError(f"Expected one decoded AndroidManifest.xml, found {len(valid)}")
    return valid[0]


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def _attr(element: ET.Element, name: str) -> str | None:
    return element.get(ANDROID + name)


def reject_split_manifest(root: ET.Element, context: str) -> None:
    split = root.get("split") or _attr(root, "split")
    required = _attr(root, "requiredSplitTypes")
    split_types = _attr(root, "splitTypes")
    is_required = (_attr(root, "isSplitRequired") or "").lower()
    has_uses_split = any(_local_name(node.tag) == "uses-split" for node in root.iter())
    reasons = []
    if split:
        reasons.append(f"split={split}")
    if required:
        reasons.append(f"android:requiredSplitTypes={required}")
    if split_types:
        reasons.append(f"android:splitTypes={split_types}")
    if is_required == "true":
        reasons.append("android:isSplitRequired=true")
    if has_uses_split:
        reasons.append("uses-split element")
    if reasons:
        raise BuildError(
            f"{context} is a split or requires split APKs ({'; '.join(reasons)}). "
            "Provide the complete .xapk set instead of a base.apk alone."
        )


def _qualify_component_name(value: str, old_package: str) -> str:
    value = value.strip()
    if not value or value.startswith(("@", "?", "${")):
        return value
    if value.startswith("."):
        return old_package + value
    if "." not in value:
        return old_package + "." + value
    return value


def _rebase_package_prefix(value: str, old_package: str, new_package: str) -> str | None:
    if value == old_package:
        return new_package
    if value.startswith(old_package + "."):
        return new_package + value[len(old_package) :]
    return None


def _clone_declared_permission_name(
    value: str, old_package: str, new_package: str
) -> str:
    """Give a permission declared by this app a clone-specific global name.

    The source Rednote manifest contains the literal ``{applicationId}``
    token in one declared permission. Only that token is expanded here because
    it is confirmed in the source artifact; unrelated manifest placeholders and
    resource references are not interpreted.
    """
    if not value or value.startswith(("@", "?")):
        raise BuildError(
            f"Cannot safely clone app-declared permission name {value!r}; "
            "expected a literal manifest name"
        )

    application_id_token = "{applicationId}"
    if value == application_id_token or value.startswith(application_id_token + "."):
        return new_package + value[len(application_id_token) :]

    rebased = _rebase_package_prefix(value, old_package, new_package)
    if rebased is not None:
        return rebased

    # A declaration itself is evidence that the app owns the permission even
    # when a bundled SDK chose a name outside the app's original package.
    return f"{new_package}.clone.{value}"


def _description(element: ET.Element) -> str:
    tag = _local_name(element.tag)
    name = _attr(element, "name")
    return f"{tag}[android:name={name}]" if name else tag


def _register_xml_namespaces(xml_bytes: bytes) -> None:
    text = xml_bytes.decode("utf-8", errors="ignore")
    for match in re.finditer(r"xmlns:([A-Za-z_][\w.-]*)\s*=\s*['\"]([^'\"]+)['\"]", text):
        try:
            ET.register_namespace(match.group(1), match.group(2))
        except ValueError:
            continue
    ET.register_namespace("android", ANDROID_NS)


def transform_manifest(
    root: ET.Element, new_package: str
) -> tuple[str, list[dict[str, str]], list[str], dict[str, Any]]:
    old_package = root.get("package")
    if not old_package:
        raise BuildError("Decoded manifest has no package attribute")
    if old_package == new_package:
        raise BuildError("--application-id must differ from the input package name")

    changes: list[dict[str, str]] = []
    warnings: list[str] = []

    root.set("package", new_package)
    changes.append(
        {"entry": "AndroidManifest.xml", "field": "manifest.package", "from": old_package, "to": new_package}
    )

    application = next(
        (child for child in list(root) if _local_name(child.tag) == "application"), None
    )
    if application is not None:
        class_attrs = {"name"}
        for element in application.iter():
            tag = _local_name(element.tag)
            if tag not in COMPONENT_TAGS | {"application"}:
                continue
            candidate_attrs = set(class_attrs)
            if tag == "activity":
                candidate_attrs.add("parentActivityName")
            if tag == "activity-alias":
                candidate_attrs.add("targetActivity")
            if tag == "application":
                candidate_attrs.update(
                    {"backupAgent", "appComponentFactory", "manageSpaceActivity", "zygotePreloadName"}
                )
            for attr_name in candidate_attrs:
                key = ANDROID + attr_name
                before = element.get(key)
                if before is None:
                    continue
                after = _qualify_component_name(before, old_package)
                if before != after:
                    element.set(key, after)
                    changes.append(
                        {
                            "entry": "AndroidManifest.xml",
                            "field": f"{_description(element)}@android:{attr_name}",
                            "from": before,
                            "to": after,
                        }
                    )

    # Only real application providers are modified. <queries><provider> entries
    # describe other apps and are intentionally left as written.
    if application is not None:
        for provider in application:
            if _local_name(provider.tag) != "provider":
                continue
            key = ANDROID + "authorities"
            before = provider.get(key)
            if before is None:
                continue
            transformed: list[str] = []
            for raw_token in before.split(";"):
                leading = raw_token[: len(raw_token) - len(raw_token.lstrip())]
                trailing = raw_token[len(raw_token.rstrip()) :]
                token = raw_token.strip()
                if not token:
                    transformed.append(raw_token)
                    continue
                if token.startswith(("@", "?", "${")):
                    warnings.append(
                        f"{_description(provider)} authority {token!r} is resource/placeholder based and was left unchanged; inspect it for clone collisions."
                    )
                    transformed.append(raw_token)
                    continue
                rebased = _rebase_package_prefix(token, old_package, new_package)
                if rebased is None:
                    rebased = new_package + ".clone." + token
                    warnings.append(
                        f"{_description(provider)} used non-package authority {token!r}; it was isolated as {rebased!r}. Review any hard-coded content URIs."
                    )
                if len(rebased) > 255:
                    raise BuildError(
                        f"Rebased provider authority exceeds 255 characters: {rebased}"
                    )
                transformed.append(leading + rebased + trailing)
                if rebased != token:
                    changes.append(
                        {
                            "entry": "AndroidManifest.xml",
                            "field": f"{_description(provider)}@android:authorities",
                            "from": token,
                            "to": rebased,
                        }
                    )
            after = ";".join(transformed)
            if before != after:
                provider.set(key, after)

    permission_clone_map: dict[str, str] = {}
    permission_audit_by_name: dict[str, dict[str, Any]] = {}
    unmodified_package_scoped_references: list[dict[str, str]] = []

    # A declaration is the ownership evidence for a custom permission. Clone
    # only those names, then update references by exact source-name match. This
    # avoids rewriting system or SDK permissions that the app merely requests.
    for element in list(root):
        tag = _local_name(element.tag)
        if tag not in PERMISSION_DECLARATION_TAGS:
            continue
        key = ANDROID + "name"
        before = element.get(key)
        if before is None:
            continue
        if before.startswith("android."):
            # Platform namespace declarations are not app-owned custom
            # permissions and must not be rebound by a clone.
            continue
        after = _clone_declared_permission_name(before, old_package, new_package)
        permission_clone_map.setdefault(before, after)
        permission_audit_by_name.setdefault(
            before,
            {
                "declarationTag": tag,
                "sourceName": before,
                "cloneName": after,
                "updatedReferences": [],
            },
        )
        if after != before:
            element.set(key, after)
            changes.append(
                {
                    "entry": "AndroidManifest.xml",
                    "field": f"{tag}@android:name",
                    "from": before,
                    "to": after,
                }
            )

    for element in list(root):
        tag = _local_name(element.tag)
        if tag not in PERMISSION_NAME_TAGS and not tag.startswith("uses-permission-sdk-"):
            continue
        if tag in PERMISSION_DECLARATION_TAGS:
            continue
        key = ANDROID + "name"
        before = element.get(key)
        if before is None:
            continue
        after = permission_clone_map.get(before)
        if after is not None and after != before:
            element.set(key, after)
            changes.append(
                {
                    "entry": "AndroidManifest.xml",
                    "field": f"{tag}@android:name",
                    "from": before,
                    "to": after,
                }
            )
            permission_audit_by_name[before]["updatedReferences"].append(
                {"element": tag, "attribute": "android:name"}
            )
        elif _rebase_package_prefix(before, old_package, new_package) is not None:
            unmodified_package_scoped_references.append(
                {"element": tag, "attribute": "android:name", "value": before}
            )

    for element in root.iter():
        for key, before in list(element.attrib.items()):
            attr_name = _local_name(key)
            if attr_name not in PERMISSION_REFERENCE_ATTRS:
                continue
            after = permission_clone_map.get(before)
            if after is not None and after != before:
                element.set(key, after)
                changes.append(
                    {
                        "entry": "AndroidManifest.xml",
                        "field": f"{_description(element)}@android:{attr_name}",
                        "from": before,
                        "to": after,
                    }
                )
                permission_audit_by_name[before]["updatedReferences"].append(
                    {
                        "element": _description(element),
                        "attribute": f"android:{attr_name}",
                    }
                )
            elif _rebase_package_prefix(before, old_package, new_package) is not None:
                unmodified_package_scoped_references.append(
                    {
                        "element": _description(element),
                        "attribute": f"android:{attr_name}",
                        "value": before,
                    }
                )

    if permission_audit_by_name:
        warnings.append(
            "App-declared custom permissions were assigned clone-specific names and exact manifest references were updated; compiled DEX/native permission literals were not rewritten."
        )
    if unmodified_package_scoped_references:
        warnings.append(
            "Old-package-prefixed permission references without a matching app declaration were preserved; see permissionCloneAudit.unmodifiedPackageScopedReferences."
        )
    permission_clone_audit = {
        "policy": "Rename app-declared custom permissions only; update uses-permission and component permission attributes on exact name matches.",
        "clonedDeclarations": list(permission_audit_by_name.values()),
        "unmodifiedPackageScopedReferences": unmodified_package_scoped_references,
    }
    return old_package, changes, warnings, permission_clone_audit


def find_smali_class(decoded_dir: Path, class_name: str) -> Path:
    relative = Path(*class_name.split("."))
    matches = [
        path
        for path in decoded_dir.glob("smali*/**/*.smali")
        if path.relative_to(decoded_dir).as_posix().endswith(relative.as_posix() + ".smali")
    ]
    if len(matches) != 1:
        raise BuildError(f"Expected one smali file for {class_name}; found {len(matches)}")
    return matches[0]


def dex_name_for_smali(decoded_dir: Path, smali_path: Path) -> str:
    relative = smali_path.relative_to(decoded_dir)
    root = relative.parts[0]
    if root == "smali":
        if len(relative.parts) > 1:
            folder = relative.parts[1]
            if folder == "classes":
                return "classes.dex"
            match = re.fullmatch(r"classes(\d+)", folder)
            if match:
                return f"classes{match.group(1)}.dex"
        return "classes.dex"
    match = re.fullmatch(r"smali_classes(\d+)", root)
    if match:
        return f"classes{match.group(1)}.dex"
    raise BuildError(f"Cannot map smali directory to a dex entry: {root}")


def prepare_selective_dex_rebuild(
    decoded_dir: Path, baseline_apk: Path, rebuilt_dex_names: set[str]
) -> dict[str, list[str]]:
    """Keep only touched DEXes as smali and pass every other DEX through raw.

    APKEditor can encode raw DEX files from ``dex/`` alongside selected smali
    class directories. This avoids recompiling all of a large app just to
    change one package-dependent process predicate.
    """
    if not rebuilt_dex_names:
        raise BuildError("At least one DEX must be selected for rebuilding")
    invalid = sorted(
        name for name in rebuilt_dex_names if not re.fullmatch(r"classes(?:\d+)?\.dex", name)
    )
    if invalid:
        raise BuildError(f"Invalid DEX names for selective rebuild: {invalid}")

    smali_root = decoded_dir / "smali"
    if not smali_root.is_dir():
        raise BuildError(f"Decoded smali directory is missing: {smali_root}")

    available_smali_dirs: dict[str, Path] = {}
    for path in smali_root.iterdir():
        if not path.is_dir():
            continue
        if path.name == "classes":
            dex_name = "classes.dex"
        else:
            match = re.fullmatch(r"classes(\d+)", path.name)
            if not match:
                continue
            dex_name = f"classes{match.group(1)}.dex"
        available_smali_dirs[dex_name] = path

    missing_smali = sorted(rebuilt_dex_names - available_smali_dirs.keys())
    if missing_smali:
        raise BuildError(f"No decoded smali directory for selected DEX entries: {missing_smali}")

    raw_dex_dir = decoded_dir / "dex"
    if raw_dex_dir.exists():
        shutil.rmtree(raw_dex_dir)
    raw_dex_dir.mkdir(parents=True)

    with zipfile.ZipFile(baseline_apk, "r") as baseline:
        source_names = {
            name
            for name in baseline.namelist()
            if re.fullmatch(r"classes(?:\d+)?\.dex", name)
        }
        missing_source = sorted(rebuilt_dex_names - source_names)
        if missing_source:
            raise BuildError(f"Selected DEX entries are missing from baseline APK: {missing_source}")
        passthrough = sorted(source_names - rebuilt_dex_names)
        for name in passthrough:
            with baseline.open(name, "r") as source, (raw_dex_dir / name).open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

    for dex_name, path in available_smali_dirs.items():
        if dex_name not in rebuilt_dex_names:
            shutil.rmtree(path)

    return {
        "rebuiltDexEntries": sorted(rebuilt_dex_names),
        "passthroughDexEntries": passthrough,
    }


def patch_boolean_method(path: Path, method_name: str, value: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    method_re = re.compile(
        rf"(?ms)^(\.method[^\n]*?\s{re.escape(method_name)}\([^\n]*?\)Z\s*)\n"
        r".*?^\.end method\s*$"
    )
    literal = "0x1" if value else "0x0"
    def replacement(match: re.Match[str]) -> str:
        return (
            match.group(1)
            + "\n\n    .locals 1\n\n    const/4 v0, "
            + literal
            + "\n\n    return v0\n.end method"
        )

    updated, count = method_re.subn(replacement, text)
    if count != 1:
        raise BuildError(
            f"Expected exactly one {method_name}()Z method in {path}; found {count}"
        )
    path.write_text(updated, encoding="utf-8", newline="\n")


def patch_main_process_package_gate(
    path: Path, old_package: str, new_package: str
) -> dict[str, str]:
    """Rebase the app's one hard-coded main-process name comparison.

    Rednote 9.48.1 stores its current process name in ``ddc/b.b`` and compares
    that value to the source package in ``ddc/a.invoke()``. After a package
    clone, Android names the default process after the new package, so the app
    otherwise takes its subprocess initialization path in the main process.
    Keep this scoped to that exact predicate; other source-package literals
    may be external protocol names or SDK configuration and are left alone.
    """
    if old_package == new_package:
        raise BuildError("Main-process package gate does not need rebasing")

    text = path.read_text(encoding="utf-8")
    if not re.search(r"(?m)^\.class[^\n]*\sLddc/a;\s*$", text):
        raise BuildError(f"Expected ddc/a class in {path}")

    method_re = re.compile(
        r"(?ms)^(\.method[^\n]*\binvoke\(\)Ljava/lang/Object;[^\n]*\n)"
        r"(.*?)"
        r"(^\.end method\s*$)"
    )
    matches = list(method_re.finditer(text))
    if len(matches) != 1:
        raise BuildError(
            f"Expected one ddc/a.invoke()Ljava/lang/Object; method in {path}; found {len(matches)}"
        )

    match = matches[0]
    body = match.group(2)
    old_literal = re.escape(old_package)
    predicate = re.compile(
        rf"(?ms)sget-object\s+(?P<process_register>[vp]\d+),\s*"
        rf"Lddc/b;->b:Ljava/lang/String;.*?"
        rf"const-string\s+(?P<package_register>[vp]\d+),\s*\"{old_literal}\".*?"
        rf"invoke-static\s*\{{\s*(?P=process_register)\s*,\s*"
        rf"(?P=package_register)\s*\}},\s*"
        r"Lkotlin/jvm/internal/Intrinsics;->areEqual\(Ljava/lang/Object;Ljava/lang/Object;\)Z"
    )
    predicate_matches = list(predicate.finditer(body))
    if len(predicate_matches) != 1:
        raise BuildError(
            "Expected exactly one source-package main-process comparison in "
            f"ddc/a.invoke(); found {len(predicate_matches)}"
        )

    literal_re = re.compile(rf'(?m)^(\s*const-string\s+[vp]\d+,\s*)"{old_literal}"(\s*)$')
    updated_body, replacement_count = literal_re.subn(
        lambda found: found.group(1) + '"' + new_package + '"' + found.group(2),
        body,
    )
    if replacement_count != 1:
        raise BuildError(
            f"Expected one {old_package!r} literal in ddc/a.invoke(); found {replacement_count}"
        )

    updated = text[: match.start(2)] + updated_body + text[match.end(2) :]
    path.write_text(updated, encoding="utf-8", newline="\n")
    return {
        "class": "ddc.a",
        "method": "invoke()Ljava/lang/Object;",
        "sourceProcessName": old_package,
        "cloneProcessName": new_package,
    }


def dex_entry_names(apk: Path) -> set[str]:
    with zipfile.ZipFile(apk) as archive:
        return {
            name
            for name in archive.namelist()
            if re.fullmatch(r"classes(?:\d+)?\.dex", name)
        }


def _zip_entry_sha256(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_merged_dex_native(source_apks: list[Path], merged_apk: Path) -> dict[str, Any]:
    """Confirm APKEditor merge kept every source DEX and native library payload."""
    source_native: dict[str, str] = {}
    source_dex: list[dict[str, str]] = []
    for source_path in source_apks:
        with zipfile.ZipFile(source_path, "r") as source:
            seen: set[str] = set()
            for info in source.infolist():
                name = info.filename
                is_dex = re.fullmatch(r"classes(?:\d+)?\.dex", name) is not None
                is_native = name.lower().endswith(".so")
                if not (is_dex or is_native):
                    continue
                if name in seen:
                    raise BuildError(f"Duplicate DEX/native ZIP entry in {source_path.name}: {name}")
                seen.add(name)
                digest = _zip_entry_sha256(source, info)
                if is_dex:
                    source_dex.append(
                        {
                            "sourceApk": redact_phone_like_text(source_path.name),
                            "sourceEntry": name,
                            "sha256": digest,
                        }
                    )
                else:
                    previous = source_native.get(name)
                    if previous is not None and previous != digest:
                        raise BuildError(
                            f"Conflicting native library payloads share entry name {name} across splits"
                        )
                    source_native[name] = digest

    with zipfile.ZipFile(merged_apk, "r") as merged:
        merged_native: dict[str, str] = {}
        merged_dex_hashes: list[tuple[str, str]] = []
        for info in merged.infolist():
            name = info.filename
            if re.fullmatch(r"classes(?:\d+)?\.dex", name):
                merged_dex_hashes.append((name, _zip_entry_sha256(merged, info)))
            elif name.lower().endswith(".so"):
                if name in merged_native:
                    raise BuildError(f"Duplicate merged native library entry: {name}")
                merged_native[name] = _zip_entry_sha256(merged, info)

    if source_native != merged_native:
        missing = sorted(set(source_native) - set(merged_native))
        extra = sorted(set(merged_native) - set(source_native))
        changed = sorted(
            name
            for name in set(source_native) & set(merged_native)
            if source_native[name] != merged_native[name]
        )
        raise BuildError(
            "APKEditor merge changed native library payloads; "
            f"missing={missing[:10]}, extra={extra[:10]}, changed={changed[:10]}"
        )

    source_dex_hashes = Counter(record["sha256"] for record in source_dex)
    merged_dex_hashes_by_value: dict[str, list[str]] = defaultdict(list)
    for name, digest in merged_dex_hashes:
        merged_dex_hashes_by_value[digest].append(name)
    merged_dex_counts = Counter(digest for _, digest in merged_dex_hashes)
    if source_dex_hashes != merged_dex_counts:
        raise BuildError(
            "APKEditor merge changed DEX payload hashes; "
            f"sourceCount={sum(source_dex_hashes.values())}, mergedCount={sum(merged_dex_counts.values())}"
        )

    mappings = []
    for record in source_dex:
        candidates = merged_dex_hashes_by_value[record["sha256"]]
        if not candidates:
            raise BuildError(f"No merged DEX with source hash {record['sha256']}")
        preferred = next((name for name in candidates if name == record["sourceEntry"]), candidates[0])
        candidates.remove(preferred)
        mappings.append({**record, "mergedEntry": preferred})

    return {
        "sourceDexEntryCount": len(source_dex),
        "mergedDexEntryCount": len(merged_dex_hashes),
        "dexPayloadHashesMatch": True,
        "dexEntryMappings": mappings,
        "sourceNativeLibraryEntryCount": len(source_native),
        "mergedNativeLibraryEntryCount": len(merged_native),
        "nativeLibraryPathAndHashesMatch": True,
        "allSourceDexAndNativePayloadsPreserved": True,
    }


def is_signature_metadata(name: str) -> bool:
    upper = name.upper()
    if upper == "STAMP-CERT-SHA256":
        return True
    if not upper.startswith("META-INF/"):
        return False
    relative = upper[len("META-INF/") :]
    # Preserve nested JAR metadata such as META-INF/versions/9/OSGI-INF/MANIFEST.MF.
    if "/" in relative:
        return False
    return relative == "MANIFEST.MF" or relative.endswith(SIGNATURE_ENTRY_SUFFIXES) or relative.startswith("SIG-")


def make_minimal_candidate(
    base_apk: Path,
    rebuilt_apk: Path,
    changed_entries: set[str],
    candidate: Path,
) -> dict[str, Any]:
    with zipfile.ZipFile(base_apk, "r") as base, zipfile.ZipFile(rebuilt_apk, "r") as rebuilt:
        base_names = [info.filename for info in base.infolist()]
        if len(base_names) != len(set(base_names)):
            raise BuildError("Input APK has duplicate ZIP entries; safe transplant is ambiguous")
        rebuilt_names = set(rebuilt.namelist())
        missing = changed_entries - rebuilt_names
        if missing:
            raise BuildError(f"APKEditor build omitted required entries: {sorted(missing)}")
        if "AndroidManifest.xml" not in base_names:
            raise BuildError("Input APK has no AndroidManifest.xml entry")

        removed_signature_entries: list[str] = []
        with zipfile.ZipFile(candidate, "w") as output:
            for info in base.infolist():
                name = info.filename
                if is_signature_metadata(name):
                    removed_signature_entries.append(name)
                    continue
                if name in changed_entries:
                    data = rebuilt.read(name)
                else:
                    data = base.read(info)
                output.writestr(info, data)

    return {"removedSignatureMetadata": sorted(removed_signature_entries)}


def compare_payload_entries(
    baseline_apk: Path, output_apk: Path, changed_entries: set[str]
) -> dict[str, Any]:
    with zipfile.ZipFile(baseline_apk, "r") as baseline, zipfile.ZipFile(output_apk, "r") as output:
        baseline_names = {info.filename for info in baseline.infolist() if not is_signature_metadata(info.filename)}
        output_names = {info.filename for info in output.infolist() if not is_signature_metadata(info.filename)}
        if baseline_names != output_names:
            missing = sorted(baseline_names - output_names)
            added = sorted(output_names - baseline_names)
            raise BuildError(
                f"Payload entry set changed unexpectedly; missing={missing[:20]}, added={added[:20]}"
            )
        mismatches = []
        unchanged_count = 0
        changed_records = []
        for name in sorted(baseline_names):
            before = sha256_bytes(baseline.read(name))
            after = sha256_bytes(output.read(name))
            if name in changed_entries:
                changed_records.append({"entry": name, "baselineSha256": before, "outputSha256": after})
                if before == after:
                    raise BuildError(f"Expected entry to change, but its content is unchanged: {name}")
            elif before != after:
                mismatches.append(name)
            else:
                unchanged_count += 1
        if mismatches:
            raise BuildError(
                "Unexpected payload changes outside manifest/touched DEX: " + ", ".join(mismatches[:30])
            )
    return {
        "unchangedPayloadEntryCount": unchanged_count,
        "changedPayloadEntries": changed_records,
        "allOtherPayloadHashesMatch": True,
    }


def prompt_secret(prompt: str, env_name: str) -> str:
    value = os.environ.get(env_name)
    if value:
        return value
    if not sys.stdin.isatty():
        raise BuildError(f"Set {env_name} in the environment or run interactively to enter it")
    value = getpass.getpass(prompt)
    if not value:
        raise BuildError(f"{env_name} cannot be empty")
    return value


def sign_candidate(
    candidate: Path,
    output: Path,
    keystore: Path,
    alias: str,
    zipalign: Path,
    apksigner: Path,
) -> dict[str, Any]:
    if not keystore.is_file():
        raise BuildError(f"Signing keystore not found: {keystore}")
    store_password = prompt_secret("Keystore password: ", "KEYSTORE_PASSWORD")
    key_password = os.environ.get("KEY_PASSWORD") or store_password
    signing_env = os.environ.copy()
    signing_env["REDNOTE_BUILD_STORE_PASSWORD"] = store_password
    signing_env["REDNOTE_BUILD_KEY_PASSWORD"] = key_password

    aligned = candidate.with_suffix(".aligned.apk")
    # Align uncompressed native libraries for Android devices requiring 16 KiB
    # memory pages; the legacy -p option only guarantees 4 KiB alignment.
    run_command([zipalign, "-P", "16", "-f", "4", candidate, aligned])
    run_command(
        [
            apksigner,
            "sign",
            "--ks",
            keystore,
            "--ks-pass",
            "env:REDNOTE_BUILD_STORE_PASSWORD",
            "--ks-key-alias",
            alias,
            "--key-pass",
            "env:REDNOTE_BUILD_KEY_PASSWORD",
            "--out",
            output,
            aligned,
        ],
        env=signing_env,
    )
    aligned.unlink(missing_ok=True)
    verify = verify_apk_signature(output, apksigner)
    run_command([zipalign, "-c", "-P", "16", "-v", "4", output])
    return verify


def parse_version_record(badging: dict[str, str | None]) -> dict[str, str | None]:
    return {
        "versionCode": badging["versionCode"],
        "versionName": badging["versionName"],
    }


def redact_phone_like_text(value: str) -> str:
    # Build reports intentionally exclude user phone numbers even when a source
    # description accidentally contains one.
    return re.sub(
        r"(?<![A-Za-z0-9])\+?\d(?:[\d ()-]{5,}\d)(?![A-Za-z0-9])",
        "[redacted-number]",
        value,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a renamed Rednote APK from one local APK or a complete XAPK set."
    )
    parser.add_argument("--input", required=True, type=Path, help="Local .apk or .xapk file")
    parser.add_argument("--sha256", required=True, help="Expected SHA-256 of the exact input file")
    parser.add_argument("--source", required=True, help="Human-readable description or URL for the input")
    parser.add_argument(
        "--application-id", default=DEFAULT_APPLICATION_ID, help=f"New package ID (default: {DEFAULT_APPLICATION_ID})"
    )
    parser.add_argument("--fold-layout", action="store_true", help="Force the two existing fold-layout gates")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output APK path")
    parser.add_argument(
        "--report", type=Path, help="JSON report path (default: sibling rednote-custom-build-report.json)"
    )
    parser.add_argument(
        "--keystore", type=Path, default=SCRIPT_DIR / "ks_pkcs12.keystore", help="APK signing keystore"
    )
    parser.add_argument("--key-alias", default=os.environ.get("KEY_ALIAS", "jhc"), help="Signing key alias")
    return parser.parse_args(argv)


def build(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise BuildError(f"Input file does not exist: {input_path}")
    extension = input_path.suffix.lower()
    if extension not in {".apk", ".xapk"}:
        raise BuildError("--input must be a local .apk or .xapk; split base.apk alone is rejected")
    if not APKEDITOR.is_file():
        raise BuildError(f"APKEditor JAR not found: {APKEDITOR}")
    application_id = validate_application_id(args.application_id)
    source_description = args.source.strip()
    if not source_description:
        raise BuildError("--source must be a non-empty description")

    apksigner = find_tool("apksigner")
    aapt2 = find_tool("aapt2")
    zipalign = find_tool("zipalign")
    input_sha256 = check_expected_digest(input_path, args.sha256)

    output_path = args.output.expanduser().resolve()
    report_path = (
        args.report.expanduser().resolve()
        if args.report
        else output_path.parent / "rednote-custom-build-report.json"
    )
    if output_path == input_path or report_path == input_path or output_path == report_path:
        raise BuildError("Input, output APK, and report paths must be different")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    apkeditor_version = get_apkeditor_version()
    temporary_root = Path(tempfile.mkdtemp(prefix=".rednote-build-", dir=output_path.parent))
    try:
        xapk_members: list[dict[str, Any]] = []
        xapk_manifest: dict[str, Any] | None = None
        merge_input = input_path
        merge_input_sha256 = input_sha256
        xapk_package_record: dict[str, Any] | None = None
        source_apks_for_merge: list[Path] = []
        if extension == ".apk":
            input_signature = verify_apk_signature(input_path, apksigner)
            input_badging = get_badging(input_path, aapt2)
            with zipfile.ZipFile(input_path) as input_zip:
                input_signature_entries = sorted(
                    name for name in input_zip.namelist() if is_signature_metadata(name)
                )
            xapk_members = [
                {
                    "archiveMember": redact_phone_like_text(input_path.name),
                    "sha256": input_sha256,
                    "signatureMetadataEntries": input_signature_entries,
                    **input_badging,
                    **input_signature,
                }
            ]
            xapk_package_record = input_badging
            source_apks_for_merge = [input_path]
        else:
            extracted_dir = temporary_root / "xapk-apks"
            extracted_dir.mkdir()
            extracted_apks, xapk_manifest = extract_xapk_apks(input_path, extracted_dir)
            source_apks_for_merge = extracted_apks
            xapk_members, xapk_package_record = validate_xapk_members(
                extracted_apks, apksigner, aapt2
            )
            validate_xapk_manifest(xapk_manifest, xapk_package_record, extracted_apks)
            merged = temporary_root / "merged-input.apk"
            run_command(
                [
                    "java",
                    "-Xmx8g",
                    "-jar",
                    APKEDITOR,
                    "m",
                    "-clean-meta",
                    "-validate-modules",
                    "-f",
                    "-i",
                    extracted_dir,
                    "-o",
                    merged,
                ],
                timeout=3600,
            )
            merge_input = merged
            merge_input_sha256 = sha256_file(merged)
            merged_badging = get_badging(merged, aapt2)
            if (
                merged_badging["packageName"] != xapk_package_record["packageName"]
                or merged_badging["versionCode"] != xapk_package_record["versionCode"]
            ):
                raise BuildError("APKEditor merge changed the XAPK package or version metadata")

        merge_payload_audit = audit_merged_dex_native(source_apks_for_merge, merge_input)

        decoded_dir = temporary_root / "decoded"
        decode_args: list[str | Path] = [
            "java",
            "-Xmx4g",
            "-jar",
            APKEDITOR,
            "d",
            "-t",
            "xml",
            "-f",
        ]
        decode_args.extend(["-load-dex", "1", "-dex-lib", "jf"])
        decode_args.extend(["-i", merge_input, "-o", decoded_dir])
        run_command(decode_args, timeout=3600)
        manifest_path, manifest_tree, manifest_root = find_decoded_manifest(decoded_dir)
        if extension == ".apk":
            reject_split_manifest(manifest_root, input_path.name)
        else:
            reject_split_manifest(manifest_root, "APKEditor merged XAPK")

        _register_xml_namespaces(manifest_path.read_bytes())
        old_package, manifest_changes, warnings, permission_clone_audit = transform_manifest(
            manifest_root, application_id
        )
        manifest_tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

        touched_dex_names: set[str] = set()
        process_gate_path = find_smali_class(decoded_dir, "ddc.a")
        process_gate_audit = patch_main_process_package_gate(
            process_gate_path, old_package, application_id
        )
        process_gate_dex = dex_name_for_smali(decoded_dir, process_gate_path)
        touched_dex_names.add(process_gate_dex)

        fold_touched_dex_names: set[str] = set()
        if args.fold_layout:
            device_info = find_smali_class(
                decoded_dir, "com.xingin.adaptation.device.DeviceInfoContainer"
            )
            for method_name in ("isHorizontalFolderDevice", "isPad"):
                patch_boolean_method(device_info, method_name, True)
            device_dex = dex_name_for_smali(decoded_dir, device_info)
            touched_dex_names.add(device_dex)
            fold_touched_dex_names.add(device_dex)
            warnings.append(
                "--fold-layout changed DeviceInfoContainer.isHorizontalFolderDevice() and isPad() to return true."
            )

        dex_rebuild_audit = prepare_selective_dex_rebuild(
            decoded_dir, merge_input, touched_dex_names
        )

        rebuilt = temporary_root / "rebuilt.apk"
        build_args: list[str | Path] = [
            "java",
            "-Xmx4g",
            "-jar",
            APKEDITOR,
            "b",
            "-f",
            "-no-cache",
        ]
        build_args.extend(["-dex-lib", "jf"])
        build_args.extend(["-i", decoded_dir, "-o", rebuilt])
        run_command(build_args, timeout=3600)

        with zipfile.ZipFile(merge_input, "r") as baseline, zipfile.ZipFile(rebuilt, "r") as rebuilt_zip:
            baseline_names = set(baseline.namelist())
            if "AndroidManifest.xml" not in baseline_names:
                raise BuildError("Baseline APK has no AndroidManifest.xml")
            changed_entries = {"AndroidManifest.xml"}
            missing_dex = touched_dex_names - baseline_names
            if missing_dex:
                raise BuildError(f"Touched DEX not present in merged input: {sorted(missing_dex)}")
            for dex_name in sorted(touched_dex_names):
                if dex_name not in rebuilt_zip.namelist():
                    raise BuildError(f"APKEditor did not rebuild touched DEX {dex_name}")
                if sha256_bytes(baseline.read(dex_name)) == sha256_bytes(rebuilt_zip.read(dex_name)):
                    raise BuildError(f"Compatibility patch did not change DEX entry {dex_name}")
                changed_entries.add(dex_name)

        candidate = temporary_root / "rednote-unsigned.apk"
        signature_cleanup = make_minimal_candidate(
            merge_input, rebuilt, changed_entries, candidate
        )
        # The comparison baseline for XAPK runs is the APKEditor-merged file. Its
        # resource table and split layout already differ from the original splits.
        signature = sign_candidate(
            candidate,
            output_path,
            args.keystore.expanduser().resolve(),
            args.key_alias,
            zipalign,
            apksigner,
        )
        output_badging = get_badging(output_path, aapt2)
        if output_badging["packageName"] != application_id:
            raise BuildError(
                f"Output package verification failed: expected {application_id}, got {output_badging['packageName']}"
            )
        if output_badging["versionCode"] != xapk_package_record["versionCode"]:
            raise BuildError("Output versionCode differs from the verified input")

        payload_check = compare_payload_entries(merge_input, output_path, changed_entries)
        report = {
            "schemaVersion": 1,
            "sourceDescription": redact_phone_like_text(source_description),
            "input": {
                "format": "XAPK" if extension == ".xapk" else "APK",
                "sha256": input_sha256,
                "packageName": xapk_package_record["packageName"],
                **parse_version_record(xapk_package_record),
                "signerCertificateSha256": sorted(
                    {cert for member in xapk_members for cert in member["signerCertificateSha256"]}
                ),
                "sourceStampCertificateSha256": sorted(
                    {cert for member in xapk_members for cert in member["sourceStampCertificateSha256"]}
                ),
                "signatureVerification": "passed for every APK member",
                "apkMembers": xapk_members,
            },
            "merge": {
                "tool": apkeditor_version,
                "mergedInputSha256": merge_input_sha256,
                "comparisonBaseline": "merged APK" if extension == ".xapk" else "input APK",
                "resourcesMayDifferFromOriginalSplits": extension == ".xapk",
                "xapkManifestPackageName": (xapk_manifest or {}).get("package_name"),
                "xapkManifestVersionCode": (xapk_manifest or {}).get("version_code"),
                "splitNames": xapk_package_record.get("splitNames", []),
                "payloadPreservationAudit": merge_payload_audit,
                "expectedRemovedSignatureMetadataFromInputs": [
                    {
                        "apkMember": member["archiveMember"],
                        "entries": member["signatureMetadataEntries"],
                    }
                    for member in xapk_members
                    if member["signatureMetadataEntries"]
                ],
            },
            "output": {
                "file": redact_phone_like_text(output_path.name),
                "sha256": sha256_file(output_path),
                "packageName": output_badging["packageName"],
                **parse_version_record(output_badging),
                "signerCertificateSha256": signature["signerCertificateSha256"],
                "sourceStampCertificateSha256": [],
                "sourceStampPolicy": "Original input stamps are reported as verification data; no source stamp is created for this output.",
                "signatureVerification": "passed",
                "zipalignVerification": "passed",
            },
            "packageRename": {"from": old_package, "to": application_id},
            "foldLayout": {
                "enabled": bool(args.fold_layout),
                "methods": ["isHorizontalFolderDevice", "isPad"] if args.fold_layout else [],
                "touchedDexEntries": sorted(fold_touched_dex_names),
            },
            "mainProcessCompatibility": {
                **process_gate_audit,
                "touchedDexEntry": process_gate_dex,
                "reason": (
                    "The app's main-process predicate compares the process name to its source package. "
                    "The clone's default process name follows the new applicationId."
                ),
            },
            "dexRebuildAudit": dex_rebuild_audit,
            "buildConfiguration": {
                "dexProcessingLibrary": "jf",
                "decodeLoadDex": 1,
                "decodeHeapLimitGiB": 4,
                "buildHeapLimitGiB": 4,
                "zipalignPageSizeKiB": 16,
            },
            "modifiedEntries": sorted(changed_entries),
            "manifestChanges": manifest_changes,
            "permissionCloneAudit": permission_clone_audit,
            "signatureCleanup": signature_cleanup,
            "payloadHashAudit": payload_check,
            "warnings": sorted(set(warnings)),
            "phoneNumberIncluded": False,
        }
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return output_path, report_path, report
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        output, report_path, report = build(args)
    except BuildError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # Keep tool trace available for unexpected failures.
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
    print(f"Built APK: {output}")
    print(f"Build report: {report_path}")
    print(f"Package: {report['output']['packageName']}")
    print(f"SHA-256: {report['output']['sha256']}")
    for warning in report["warnings"]:
        print(f"[WARNING] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
