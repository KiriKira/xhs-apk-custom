import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

from download_bins import download_apkeditor
from signature_spoof_experiment import (
    build_signature_spoof_dex,
    dex_name_for_smali,
    find_smali_class,
    next_dex_name,
    patch_application_startup,
    resolve_application_class,
)
from xhs_build_ci import (
    BINS_DIR,
    OUTPUT_DIR,
    download_apk,
    ensure_dirs,
    patch_boolean_methods,
    run,
    sha256,
    sign_apk,
    strip_old_v1_signatures,
)

DEVICE_INFO_CLASS = "com.xingin.adaptation.device.DeviceInfoContainer"


def env(name, default=""):
    value = os.environ.get(name, "").strip()
    return value if value else default


def patch_bool_method(path, method_name, value=True):
    text = path.read_text(encoding="utf-8")
    patched, count = patch_boolean_methods(text, (method_name,), value)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {method_name}()Z in {path}, patched {count}"
        )
    path.write_text(patched, encoding="utf-8", newline="\n")


def build_rebuilt(decoded, output):
    if os.path.exists(output):
        os.remove(output)
    run(
        "java", "-Xmx8g", "-jar", os.path.join(BINS_DIR, "apkeditor.jar"),
        "b", "-f", "-no-cache", "-dex-lib", "jf",
        "-i", decoded, "-o", output,
    )


def make_variant(base_apk, rebuilt_apk, touched_dexes, helper_dex, output_unsigned):
    if os.path.exists(output_unsigned):
        os.remove(output_unsigned)
    shutil.copy2(base_apk, output_unsigned)
    strip_old_v1_signatures(output_unsigned)

    with zipfile.ZipFile(rebuilt_apk, "r") as rebuilt:
        for dex_name in sorted(touched_dexes):
            data = rebuilt.read(dex_name)
            tmp = Path("fold_home_build") / dex_name
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            # Replace only the DEX we intentionally modified.
            result = os.system(f"zip -q -d {output_unsigned} {dex_name}")
            if result != 0:
                raise RuntimeError(f"Could not remove {dex_name} from {output_unsigned}")
            run("zip", "-q", "-0", "-j", output_unsigned, tmp)

    helper_name = next_dex_name(base_apk)
    helper_named = Path("fold_home_build") / helper_name
    shutil.copy2(helper_dex, helper_named)
    run("zip", "-q", "-0", "-j", output_unsigned, helper_named)
    return helper_name


def write_report(app_name, app_smali, device_smali, app_dex, device_dex, helper_dex_name):
    text = f"""XHS fold-home experiment
========================

Known-good prerequisite:
- Java PackageInfo/SigningInfo signature spoof is required for the re-signed APK to launch.
- The plain re-signed control crashes.
- The device-tested working baseline is experiment #3: Java signature spoof + XINGIN v1 signer name.

Application:
- class: {app_name}
- smali: {app_smali}
- dex: {app_dex}

Device gate:
- class: {DEVICE_INFO_CLASS}
- smali: {device_smali}
- dex: {device_dex}

Injected helper dex:
- {helper_dex_name}

Variant A:
- Java signature spoof
- v1 signer entry name: XINGIN
- DeviceInfoContainer.isHorizontalFolderDevice() -> true
- isPad() left unchanged

Variant B:
- Java signature spoof
- v1 signer entry name: XINGIN
- DeviceInfoContainer.isHorizontalFolderDevice() -> true
- DeviceInfoContainer.isPad() -> true

Rationale:
OneLab's "启用首页四列显示" hook only forces isHorizontalFolderDevice() true.
isPad() is used by OneLab's separate Pad/video-layout eligibility path, so Variant B is
kept as a controlled second variable in case XHS also gates pinch/large-screen behavior
on the Pad flag in this XHS build.

No Build.MODEL / Build.MANUFACTURER / region spoofing is performed in either variant.
"""
    out = Path(OUTPUT_DIR, "fold-home-experiment-info.txt")
    out.write_text(text, encoding="utf-8")
    return out


def main():
    ensure_dirs()
    base_url = env("BASE_APK_URL")
    if not base_url:
        raise RuntimeError("BASE_APK_URL is required")
    base_apk = download_apk(base_url)
    print(f"Base APK sha256={sha256(base_apk)}")

    apkeditor = os.path.join(BINS_DIR, "apkeditor.jar")
    if not os.path.exists(apkeditor):
        download_apkeditor()

    decoded = "xhs_foldhome_decoded"
    if os.path.exists(decoded):
        shutil.rmtree(decoded)
    run("java", "-Xmx8g", "-jar", apkeditor, "d", "-f", "-i", base_apk, "-o", decoded)

    app_name, _ = resolve_application_class(decoded, base_apk)
    app_smali = find_smali_class(decoded, app_name)
    device_smali = find_smali_class(decoded, DEVICE_INFO_CLASS)
    app_dex = dex_name_for_smali(app_smali)
    device_dex = dex_name_for_smali(device_smali)

    print(f"Application: {app_name}")
    print(f"Application dex: {app_dex}")
    print(f"DeviceInfoContainer dex: {device_dex}")

    # Keep the signature workaround identical to the already device-tested working control.
    patch_application_startup(app_smali)
    helper_work_dir, helper_dex = build_signature_spoof_dex()

    # Variant A: exact OneLab home-feed gate only.
    patch_bool_method(device_smali, "isHorizontalFolderDevice", True)

    rebuilt_a = os.path.join(OUTPUT_DIR, "xhs-foldhome-rebuilt-temp.apk")
    unsigned_a = os.path.join(OUTPUT_DIR, "xhs-java-sigspoof-foldhome-unsigned.apk")
    output_a = os.path.join(OUTPUT_DIR, "xhs-java-sigspoof-foldhome.apk")
    build_rebuilt(decoded, rebuilt_a)
    helper_name = make_variant(
        base_apk,
        rebuilt_a,
        {app_dex, device_dex},
        helper_dex,
        unsigned_a,
    )
    sign_apk(unsigned_a, output_a, v1_signer_name="XINGIN")

    # Variant B: add only isPad=true on top of A.
    patch_bool_method(device_smali, "isPad", True)

    rebuilt_b = os.path.join(OUTPUT_DIR, "xhs-foldhome-pad-rebuilt-temp.apk")
    unsigned_b = os.path.join(OUTPUT_DIR, "xhs-java-sigspoof-foldhome-pad-unsigned.apk")
    output_b = os.path.join(OUTPUT_DIR, "xhs-java-sigspoof-foldhome-pad.apk")
    build_rebuilt(decoded, rebuilt_b)
    make_variant(
        base_apk,
        rebuilt_b,
        {app_dex, device_dex},
        helper_dex,
        unsigned_b,
    )
    sign_apk(unsigned_b, output_b, v1_signer_name="XINGIN")

    report = write_report(
        app_name,
        app_smali,
        device_smali,
        app_dex,
        device_dex,
        helper_name,
    )
    print(report.read_text(encoding="utf-8"))

    for path in (rebuilt_a, rebuilt_b, unsigned_a, unsigned_b):
        if os.path.exists(path):
            os.remove(path)
    if Path("fold_home_build").exists():
        shutil.rmtree("fold_home_build")
    if helper_work_dir.exists():
        shutil.rmtree(helper_work_dir)

    print(f"Built {output_a}: sha256={sha256(output_a)}")
    print(f"Built {output_b}: sha256={sha256(output_b)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
