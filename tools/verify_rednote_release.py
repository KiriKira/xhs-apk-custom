"""Verify the pinned release configuration against the built APK and its report."""

import hashlib
import json
from pathlib import Path
import sys
import zipfile

from verify_fold_dex import verify_fold_gates
from verify_rednote_process_gate import verify_process_gate
from verify_rednote_signature_compat import verify_signature_compat

PACKAGE = "com.kirikira.rednote.fold"
SOURCE_SHA = "bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0"
SOURCE_CERT = "dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd"
OUTPUT_CERT = "637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(apk, report_path):
    report = json.loads(report_path.read_text())
    require(report["input"]["sha256"] == SOURCE_SHA, "Unexpected source file")
    require(report["input"]["signerCertificateSha256"] == [SOURCE_CERT], "Unexpected source signer")
    output = report["output"]
    require(output["packageName"] == PACKAGE, "Unexpected output package")
    require(output["versionCode"] == "9481803", "Unexpected versionCode")
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
    require(set(report["modifiedEntries"]) == {
        "AndroidManifest.xml", "classes17.dex", "classes4.dex", compat["helperDexEntry"]
    }, "Unexpected modified entries")
    with zipfile.ZipFile(apk) as archive:
        require({"META-INF/XINGIN.SF", "META-INF/XINGIN.RSA"} <= set(archive.namelist()),
                "XINGIN V1 signature entries are missing")
        require(hashlib.sha256(archive.read(compat["helperDexEntry"])).hexdigest() == compat["helperDexSha256"],
                "Helper DEX hash mismatch")
    report["compiledSignatureCompatibilityVerification"] = verify_signature_compat(apk, PACKAGE, SOURCE_CERT)
    report["compiledMainProcessGateVerification"] = verify_process_gate(apk, PACKAGE)
    report["compiledFoldGateVerification"] = verify_fold_gates(apk)
    report["compiledV1EntryNameVerification"] = {"present": True}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"verified": True, "package": PACKAGE, "apkSha256": actual_sha}))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_rednote_release.py APK REPORT")
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
