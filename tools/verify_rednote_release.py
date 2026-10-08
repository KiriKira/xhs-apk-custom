"""Verify the pinned release configuration against the built APK and its report."""

import hashlib
import argparse
import json
from pathlib import Path
import sys
import zipfile
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rednote_resource_package import package_records
from rednote_launcher_icon import verify_launcher_icons
from rednote_wechat_share_patch import verify_compiled_wechat_share_identity
from rednote_ad_patch import verify_compiled_feed_patch
from tools.build_rednote_package_fix import verify_manifest_process
from verify_fold_dex import verify_fold_gates
from verify_rednote_process_gate import verify_process_gate
from verify_rednote_signature_compat import verify_signature_compat

PACKAGE = "com.kirikira.rednote.fold"
SOURCE_PACKAGE = "com.xingin.xhs"
SOURCE_PROCESS = "com.xingin.xhs"
SOURCE_SHA = "bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0"
SOURCE_CERT = "dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd"
OUTPUT_CERT = "637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(apk, report_path, expect_ads=None, expect_launcher_icon=False, expect_wechat_share=None):
    report = json.loads(report_path.read_text())
    require(report["input"]["sha256"] == SOURCE_SHA, "Unexpected source file")
    require(report["input"]["signerCertificateSha256"] == [SOURCE_CERT], "Unexpected source signer")
    output = report["output"]
    require(output["packageName"] == PACKAGE, "Unexpected output package")
    require(output["versionCode"] == "9481803", "Unexpected versionCode")
    require(output["versionName"] == "9.48.1", "Unexpected versionName")
    badging = subprocess.check_output([os.environ.get("AAPT2", "aapt2"), "dump", "badging", str(apk)], text=True)
    package_line = next(line for line in badging.splitlines() if line.startswith("package:"))
    versions = dict(re.findall(r"(?:^|\s)(name|versionCode|versionName)='([^']*)'", package_line))
    require(versions == {"name": PACKAGE, "versionCode": "9481803", "versionName": "9.48.1"},
            "Actual APK versions must remain compatible with the previous release for direct rollback")
    require(output["signerCertificateSha256"] == [OUTPUT_CERT], "Unexpected output signer")
    require(output["signatureVerification"] == "passed", "Signature verification failed")
    require(output["zipalignVerification"] == "passed", "Alignment verification failed")
    with apk.open("rb") as stream:
        actual_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    require(output["sha256"] == actual_sha, "APK hash disagrees with report")
    require(report["foldLayout"]["enabled"] is True, "Fold layout is disabled")
    compat = report["signatureCompatibility"]
    require(compat["enabled"] is True, "Signature compatibility is disabled")
    require(compat["spoofedPackageName"] == PACKAGE, "Helper package mismatch")
    require(compat["sourceSignerCertificateSha256"] == SOURCE_CERT, "Helper certificate mismatch")
    require(report["merge"]["payloadPreservationAudit"]["allSourceDexAndNativePayloadsPreserved"] is True,
            "Split merge did not preserve source payloads")
    require(report["payloadHashAudit"]["allOtherPayloadHashesMatch"] is True,
            "Unexpected payload changes")
    process_compat = report.get("mainProcessCompatibility")
    require(isinstance(process_compat, dict), "Missing main-process compatibility report")
    require(process_compat.get("strategy") == "preserve-source-process",
            "Release must preserve the source main-process behavior")
    require(process_compat.get("effectiveMainProcessName") == SOURCE_PROCESS,
            "Unexpected effective application process name")
    require(process_compat.get("preservedOriginalPredicate") is True,
            "Original source main-process predicate was not preserved")
    require(process_compat.get("touchedDexEntry") == "classes17.dex",
            "Unexpected source main-process predicate DEX entry")

    resource_compat = report.get("resourcePackageCompatibility")
    require(isinstance(resource_compat, dict) and resource_compat.get("enabled") is True,
            "Resource-table package compatibility is disabled")
    resource_audit = resource_compat.get("audit")
    require(isinstance(resource_audit, dict), "Missing resource-table package audit")
    require(resource_audit.get("old_package") == SOURCE_PACKAGE,
            "Resource-table audit has an unexpected source package")
    require(resource_audit.get("new_package") == PACKAGE,
            "Resource-table audit has an unexpected clone package")
    require(resource_audit.get("package_id") == 0x7F,
            "Resource-table audit targets an unexpected package ID")
    require(resource_audit.get("numeric_resource_ids_unchanged") is True,
            "Resource-table audit does not preserve numeric resource IDs")
    require(resource_audit.get("all_bytes_outside_name_field_unchanged") is True,
            "Resource-table audit reports changes outside the package-name field")

    expected_entries = {
        "AndroidManifest.xml", "classes17.dex", "classes4.dex", compat["helperDexEntry"]
    }
    expected_entries.add("resources.arsc")
    wechat_share = report.get("wechatShareIdentity", {"enabled": False})
    require(type(wechat_share.get("enabled")) is bool, "Invalid WeChat share experiment flag")
    if expect_wechat_share is not None:
        require(wechat_share["enabled"] is expect_wechat_share, "Unexpected WeChat share identity variant")
    if wechat_share["enabled"]:
        require(wechat_share.get("realPackage") == PACKAGE, "Unexpected real WeChat caller package")
        require(wechat_share.get("claimedPackage") == SOURCE_PACKAGE, "Unexpected declared WeChat package")
        require(wechat_share.get("touchedDexEntry") == "classes4.dex", "Unexpected WeChat sender DEX")
        report["compiledWechatShareIdentityVerification"] = verify_compiled_wechat_share_identity(apk, SOURCE_PACKAGE)
        expected_entries.add(wechat_share["touchedDexEntry"])
    icon = report.get("launcherIcon", {"enabled": False})
    require(type(icon.get("enabled")) is bool, "Invalid launcher icon flag")
    if expect_launcher_icon:
        require(icon["enabled"] is True, "Launcher icon branding is disabled")
    if icon["enabled"]:
        with zipfile.ZipFile(apk) as archive:
            report["compiledLauncherIconVerification"] = verify_launcher_icons(archive, icon)
        expected_entries.update(entry["path"] for entry in icon["entries"])
    ads = report.get("feedAdDisplay", {"enabled": False})
    require(type(ads.get("enabled")) is bool, "Invalid ad patch flag")
    if expect_ads is not None:
        require(ads["enabled"] is expect_ads, "Unexpected ad display patch configuration")
    if ads["enabled"]:
        require(ads["touchedDexEntry"] == "classes19.dex", "Unexpected feed adapter DEX")
        require(ads["helperDexEntry"] != compat["helperDexEntry"], "Helper DEX collision")
        expected_entries.update({"classes19.dex", ads["helperDexEntry"]})
        ads["compiledVerification"] = verify_compiled_feed_patch(apk)
    require(set(report["modifiedEntries"]) == expected_entries, "Unexpected modified entries")
    with zipfile.ZipFile(apk) as archive:
        resource_table = archive.read("resources.arsc")
        resource_packages = package_records(resource_table)
        app_packages = [record for record in resource_packages if record.get("id") == 0x7F]
        require(len(app_packages) == 1, "Expected one application package in resources.arsc")
        resource_package = app_packages[0]
        require(resource_package.get("name") == PACKAGE,
                "Compiled resources.arsc does not use the clone package name")
        require(resource_audit.get("package_count") == len(resource_packages),
                "Resource-table audit package count disagrees with resources.arsc")
        require(resource_audit.get("resources_arsc_size_after") == len(resource_table),
                "Resource-table audit size disagrees with resources.arsc")
        require(resource_audit.get("sha256_after") == hashlib.sha256(resource_table).hexdigest(),
                "Resource-table audit hash disagrees with resources.arsc")
        require(resource_audit.get("numeric_resource_id_count") == len(resource_package["numeric_resource_ids"]),
                "Resource-table audit resource-ID count disagrees with resources.arsc")
        require(resource_audit.get("numeric_resource_id_sha256") == resource_package["numeric_resource_id_sha256"],
                "Resource-table audit resource-ID digest disagrees with resources.arsc")
        require(resource_audit.get("type_spec_id_count") == resource_package["type_spec_id_count"],
                "Resource-table audit type-spec count disagrees with resources.arsc")
        require(resource_audit.get("configured_entry_id_count") == resource_package["configured_entry_id_count"],
                "Resource-table audit configured-entry count disagrees with resources.arsc")
        require({"META-INF/XINGIN.SF", "META-INF/XINGIN.RSA"} <= set(archive.namelist()),
                "XINGIN V1 signature entries are missing")
        require(hashlib.sha256(archive.read(compat["helperDexEntry"])).hexdigest() == compat["helperDexSha256"],
                "Helper DEX hash mismatch")
        if ads["enabled"]:
            require(hashlib.sha256(archive.read(ads["helperDexEntry"])).hexdigest() == ads["helperDexSha256"],
                    "Ad helper DEX hash mismatch")
    report["compiledSignatureCompatibilityVerification"] = verify_signature_compat(apk, PACKAGE, SOURCE_CERT)
    report["compiledMainProcessGateVerification"] = verify_process_gate(apk, SOURCE_PROCESS)
    manifest_process = verify_manifest_process(apk, os.environ.get("AAPT2", "aapt2"))
    require(manifest_process.get("applicationProcess") == SOURCE_PROCESS,
            "Compiled application manifest does not preserve the source process name")
    report["compiledManifestProcessVerification"] = manifest_process
    report["compiledResourcePackageCompatibilityVerification"] = {
        "verified": True,
        "packageId": resource_package["id"],
        "packageName": resource_package["name"],
        "numericResourceIdCount": len(resource_package["numeric_resource_ids"]),
        "numericResourceIdSha256": resource_package["numeric_resource_id_sha256"],
    }
    report["compiledFoldGateVerification"] = verify_fold_gates(apk)
    report["compiledV1EntryNameVerification"] = {"present": True}
    report["rollbackCompatibility"] = {"package": PACKAGE, "versionCode": 9481803,
                                       "versionName": "9.48.1", "keystoreSignerSha256": OUTPUT_CERT,
                                       "policy": "Keep Android versions unchanged; distinguish patch revisions by Release tags"}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"verified": True, "package": PACKAGE, "apkSha256": actual_sha}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("report", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--expect-ads", action="store_true")
    group.add_argument("--expect-no-ads", action="store_true")
    parser.add_argument("--expect-launcher-icon", action="store_true")
    wxgroup = parser.add_mutually_exclusive_group()
    wxgroup.add_argument("--expect-wechat-share-identity", action="store_true")
    wxgroup.add_argument("--expect-no-wechat-share-identity", action="store_true")
    args = parser.parse_args()
    expected = True if args.expect_ads else False if args.expect_no_ads else None
    expected_wechat = True if args.expect_wechat_share_identity else False if args.expect_no_wechat_share_identity else None
    verify(args.apk, args.report, expected, args.expect_launcher_icon, expected_wechat)
