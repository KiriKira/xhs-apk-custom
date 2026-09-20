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
OUTPUT_APK = os.path.join(OUTPUT_DIR, "xhs-fold8-custom.apk")


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


def make_apk(base_apk, rebuilt_apk, touched_dexes, helper_dex, output_unsigned):
    if os.path.exists(output_unsigned):
        os.remove(output_unsigned)

    shutil.copy2(base_apk, output_unsigned)
    strip_old_v1_signatures(output_unsigned)

    work_dir = Path("xhs_release_build")
    work_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(rebuilt_apk, "r") as rebuilt:
        for dex_name in sorted(touched_dexes):
            tmp = work_dir / dex_name
            tmp.write_bytes(rebuilt.read(dex_name))
            result = os.system(f"zip -q -d {output_unsigned} {dex_name}")
            if result != 0:
                raise RuntimeError(f"Could not remove {dex_name} from {output_unsigned}")
            run("zip", "-q", "-0", "-j", output_unsigned, tmp)

    helper_name = next_dex_name(base_apk)
    helper_named = work_dir / helper_name
    shutil.copy2(helper_dex, helper_named)
    run("zip", "-q", "-0", "-j", output_unsigned, helper_named)
    return helper_name


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

    decoded = "xhs_release_decoded"
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

    # Device-tested working baseline:
    # 1) spoof XHS's official certificate for in-process PackageInfo/SigningInfo queries
    # 2) keep the v1 signer entry name XINGIN
    patch_application_startup(app_smali)
    helper_work_dir, helper_dex = build_signature_spoof_dex()

    # Device-tested foldable layout gates.
    patch_bool_method(device_smali, "isHorizontalFolderDevice", True)
    patch_bool_method(device_smali, "isPad", True)

    rebuilt = os.path.join(OUTPUT_DIR, "xhs-release-rebuilt-temp.apk")
    unsigned = os.path.join(OUTPUT_DIR, "xhs-fold8-custom-unsigned.apk")

    build_rebuilt(decoded, rebuilt)
    helper_name = make_apk(
        base_apk,
        rebuilt,
        {app_dex, device_dex},
        helper_dex,
        unsigned,
    )

    # Preserve the working experiment #3 signing surface.
    sign_apk(unsigned, OUTPUT_APK, v1_signer_name="XINGIN")

    print(f"Injected helper dex: {helper_name}")
    print(f"Built {OUTPUT_APK}")
    print(f"sha256={sha256(OUTPUT_APK)}")

    for path in (rebuilt, unsigned):
        if os.path.exists(path):
            os.remove(path)

    for path in (Path("xhs_release_build"), helper_work_dir):
        if path.exists():
            shutil.rmtree(path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
