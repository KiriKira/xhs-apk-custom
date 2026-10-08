#!/usr/bin/env python3
"""Build the reversible package-compatibility experiment from release -1."""

import argparse
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_rednote as base
from rednote_package_compat import patch_ddc_main_process
from rednote_resource_package import rename_resource_package

BASELINE_SHA256 = '776a835279b476bd0314dc77488fc43f03244869f2fed48aa8ee0e4d9e930773'
SIGNER_SHA256 = '637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4'
PACKAGE = 'com.kirikira.rednote.fold'
PROCESS = 'com.xingin.xhs'


def verify_manifest_process(apk, aapt2):
    result = base.run_command([aapt2, 'dump', 'xmltree', apk, '--file', 'AndroidManifest.xml'])
    lines = result.stdout.splitlines()
    in_application = False
    found = []
    for line in lines:
        if re.match(r'\s*E: application(?:\s|$)', line):
            in_application = True
            continue
        if in_application and re.match(r'\s*E:', line):
            in_application = False
        if in_application and 'A: android:process(' in line:
            found.append(line)
    if len(found) != 1 or f'"{PROCESS}"' not in found[0]:
        raise base.BuildError('Compiled application process name does not match the experiment')
    return {'installedPackage': PACKAGE, 'applicationProcess': PROCESS,
            'privateComponentProcessesRemainPackageScoped': True}


def build(args):
    source = args.input.resolve()
    base.check_expected_digest(source, BASELINE_SHA256)
    aapt2, apksigner, zipalign = (base.find_tool(name) for name in ('aapt2', 'apksigner', 'zipalign'))
    if base.sha256_file(base.APKEDITOR) != 'a9cd40df818845456be6d696de6110c89edf4b0a0580cb83438ed6b25a366e67':
        raise base.BuildError('Unexpected APKEditor version/hash')
    signer = base.verify_apk_signature(source, apksigner)
    if signer['signerCertificateSha256'] != [SIGNER_SHA256]:
        raise base.BuildError('Baseline signer differs from the existing release signer')
    baseline_badging = base.get_badging(source, aapt2)
    if (baseline_badging['packageName'] != PACKAGE or
            baseline_badging['versionCode'] != '9481803' or baseline_badging['versionName'] != '9.48.1'):
        raise base.BuildError('Baseline package/version differs from release -1')
    with zipfile.ZipFile(source) as archive:
        patched_dex, dex_audit = patch_ddc_main_process(archive.read('classes17.dex'))
        patched_resources, resources_audit = rename_resource_package(archive.read('resources.arsc'))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rednote-package-fix-') as folder:
        temp = Path(folder)
        decoded = temp / 'decoded'
        base.run_command(['java', '-Xmx4g', '-jar', base.APKEDITOR, 'd', '-t', 'xml',
                          '-dex', '-f', '-i', source, '-o', decoded], timeout=600)
        manifest, tree, root = base.find_decoded_manifest(decoded)
        application = root.find('application')
        if root.get('package') != PACKAGE or application is None or application.get(base.ANDROID + 'process'):
            raise base.BuildError('Unexpected baseline application manifest')
        base._register_xml_namespaces(manifest.read_bytes())
        before = base.ET.tostring(root)
        application.set(base.ANDROID + 'process', PROCESS)
        tree.write(manifest, encoding='utf-8', xml_declaration=True)
        application.attrib.pop(base.ANDROID + 'process')
        if base.ET.tostring(root) != before:
            raise base.BuildError('Unexpected manifest change outside application process')
        rebuilt = temp / 'rebuilt.apk'
        base.run_command(['java', '-Xmx4g', '-jar', base.APKEDITOR, 'b', '-f', '-no-cache',
                          '-i', decoded, '-o', rebuilt], timeout=600)
        replacements = temp / 'replacements.apk'
        with zipfile.ZipFile(rebuilt) as archive, zipfile.ZipFile(replacements, 'w') as changed:
            changed.writestr('AndroidManifest.xml', archive.read('AndroidManifest.xml'))
            changed.writestr('classes17.dex', patched_dex)
            changed.writestr('resources.arsc', patched_resources)
        changes = {'AndroidManifest.xml', 'classes17.dex', 'resources.arsc'}
        candidate = temp / 'unsigned.apk'
        base.make_minimal_candidate(source, replacements, changes, candidate)
        signed = base.sign_candidate(candidate, output, args.keystore.resolve(), args.key_alias,
                                     zipalign, apksigner, v1_signer_name='XINGIN')
        if signed['signerCertificateSha256'] != [SIGNER_SHA256]:
            raise base.BuildError('Output does not use the existing release signer')
        output_badging = base.get_badging(output, aapt2)
        if base.parse_version_record(output_badging) != base.parse_version_record(baseline_badging):
            raise base.BuildError('Changing Android version metadata would prevent ordinary rollback')
        if output_badging['packageName'] != PACKAGE:
            raise base.BuildError('Installed package name changed unexpectedly')
        manifest_audit = verify_manifest_process(output, aapt2)
        payload_audit = base.compare_payload_entries(source, output, changes)
    report = {
        'schemaVersion': 1, 'variant': 'original-main-process-resource-package-compat',
        'baselineRelease': 'rednote-v9.48.1-1', 'baselineApkSha256': BASELINE_SHA256,
        'outputApkSha256': base.sha256_file(output), 'packageName': PACKAGE,
        'versionCode': output_badging['versionCode'], 'versionName': output_badging['versionName'],
        'signerCertificateSha256': signed['signerCertificateSha256'],
        'manifestAudit': manifest_audit, 'dexAudit': dex_audit, 'resourcePackageAudit': resources_audit,
        'payloadAudit': payload_audit, 'feedAdPatchEnabled': False,
        'coldRestartRuntimeVerified': False, 'rollbackRuntimeVerified': False,
        'rollbackMetadataCompatible': True,
        'scope': 'Retains the original main-process label, not the original PackageManager identity.',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'sha256': report['outputApkSha256'],
                      'changedEntries': sorted(changes), 'runtimeVerified': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--keystore', type=Path, default=ROOT / 'ks_pkcs12.keystore')
    parser.add_argument('--key-alias', default='jhc')
    try:
        build(parser.parse_args())
    except base.BuildError as error:
        raise SystemExit(str(error))
