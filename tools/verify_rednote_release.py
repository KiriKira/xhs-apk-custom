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

from verify_fold_dex import verify_fold_gates
from verify_rednote_process_gate import verify_process_gate
from verify_rednote_signature_compat import verify_signature_compat

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rednote_ad_patch import verify_compiled_feed_patch

PACKAGE = "com.kirikira.rednote.fold"
SOURCE_SHA = "bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0"
SOURCE_CERT = "dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd"
OUTPUT_CERT = "637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(apk, report_path, expect_ads=None):
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
    expected_entries = {
        "AndroidManifest.xml", "classes17.dex", "classes4.dex", compat["helperDexEntry"]
    }
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
        require({"META-INF/XINGIN.SF", "META-INF/XINGIN.RSA"} <= set(archive.namelist()),
                "XINGIN V1 signature entries are missing")
        require(hashlib.sha256(archive.read(compat["helperDexEntry"])).hexdigest() == compat["helperDexSha256"],
                "Helper DEX hash mismatch")
        if ads["enabled"]:
            require(hashlib.sha256(archive.read(ads["helperDexEntry"])).hexdigest() == ads["helperDexSha256"],
                    "Ad helper DEX hash mismatch")
    report["compiledSignatureCompatibilityVerification"] = verify_signature_compat(apk, PACKAGE, SOURCE_CERT)
    report["compiledMainProcessGateVerification"] = verify_process_gate(apk, PACKAGE)
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
    args = parser.parse_args()
    expected = True if args.expect_ads else False if args.expect_no_ads else None
    verify(args.apk, args.report, expected)
