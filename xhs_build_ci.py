import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from download_bins import download_apkeditor


BASE_APK_DIR = ".base_apk_xhs"
BINS_DIR = "bins"
OUTPUT_DIR = "output_apks"


def env(name, default=""):
    value = os.environ.get(name, "").strip()
    return value if value else default


def ensure_dirs():
    os.makedirs(BASE_APK_DIR, exist_ok=True)
    os.makedirs(BINS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def download_apk(url):
    out = os.path.join(BASE_APK_DIR, "xhs-base.apk")
    if os.path.exists(out):
        return out
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 17; SM-F971Q) AppleWebKit/537.36 Chrome/140 Mobile Safari/537.36",
        "Referer": "https://www.coolapk.com/",
        "Accept": "*/*",
    }
    print(f"Downloading XHS APK: {url}")
    with requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        with open(out, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    if os.path.getsize(out) < 10 * 1024 * 1024:
        raise RuntimeError(f"Downloaded file is unexpectedly small: {os.path.getsize(out)} bytes")
    return out


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args):
    print("+", " ".join(map(str, args)))
    subprocess.run(list(map(str, args)), check=True)


def patch_boolean_methods(smali_text, names, value):
    wanted = set(names)
    method_re = re.compile(
        r"(?ms)^(\.method[^\n]*?\s(?P<name>[A-Za-z0-9_$<>]+)\([^\n]*?\)Z\s*)\n"
        r".*?^\.end method\s*$"
    )
    count = 0

    def repl(match):
        nonlocal count
        if match.group("name") not in wanted:
            return match.group(0)
        count += 1
        literal = "0x1" if value else "0x0"
        return (
            match.group(1)
            + "\n    .locals 1\n\n"
            + f"    const/4 v0, {literal}\n\n"
            + "    return v0\n.end method"
        )

    return method_re.sub(repl, smali_text), count


def patch_class(decoded_dir, class_suffix, true_methods=(), false_methods=()):
    matches = []
    for path in glob.glob(os.path.join(decoded_dir, "smali", "**", "*.smali"), recursive=True):
        normalized = path.replace("\\", "/")
        if normalized.endswith(class_suffix):
            matches.append(path)

    if not matches:
        raise RuntimeError(f"Could not find class ending with {class_suffix}")

    total = 0
    for path in matches:
        text = Path(path).read_text(encoding="utf-8")
        changed = 0
        if true_methods:
            text, n = patch_boolean_methods(text, true_methods, True)
            changed += n
        if false_methods:
            text, n = patch_boolean_methods(text, false_methods, False)
            changed += n
        if changed:
            Path(path).write_text(text, encoding="utf-8", newline="\n")
            print(f"Patched {changed} method(s): {path}")
            total += changed

    if total == 0:
        raise RuntimeError(
            f"Found class {class_suffix}, but none of the target methods were present. "
            "XHS may have changed its implementation."
        )
    dex_names = set()
    for path in matches:
        normalized = path.replace("\\", "/")
        marker = "/smali/"
        if marker in normalized:
            rel = normalized.split(marker, 1)[1]
            first = rel.split("/", 1)[0]
            if first == "classes":
                dex_names.add("classes.dex")
            elif re.fullmatch(r"classes\d+", first):
                dex_names.add(first + ".dex")
    return total, dex_names


def patch_xhs(decoded_dir):
    # OneLab's XHS foldable support shows that the home feed gate is this method.
    # Forcing it true makes XHS treat the device as its horizontal-fold target and
    # activates the built-in large-screen/four-column home route.
    count, dex_names = patch_class(
        decoded_dir,
        "/com/xingin/adaptation/device/DeviceInfoContainer.smali",
        true_methods=("isHorizontalFolderDevice",),
    )

    if env("XHS_PATCH_VIDEO", "false").lower() == "true":
        n, names = patch_class(
            decoded_dir,
            "/com/xingin/adaptation/device/DeviceInfoContainer.smali",
            true_methods=("isPad",),
        )
        count += n
        dex_names |= names
        n, names = patch_class(
            decoded_dir,
            "/com/xingin/detailfeed/abtest/DetailFeedAbTestHelper.smali",
            true_methods=(
                "enableNewVideoFeedFrame",
                "padVideoPlayNewFramework",
                "padVideoIsNewVideoFrame",
                "padVideoNewFrameStyleAdjust",
                "padVideoCommentTextOptCombo",
            ),
        )
        count += n
        dex_names |= names
        n, names = patch_class(
            decoded_dir,
            "/com/xingin/matrix/detail/intent/DetailFeedIntentData.smali",
            true_methods=("isNewVideoFeedFrame", "y1"),
            false_methods=("isOldVideoFeedStyle",),
        )
        count += n
        dex_names |= names

    return count, dex_names


def strip_old_v1_signatures(apk_path):
    # APK Signature Scheme v2/v3 blocks are replaced by apksigner. Remove old
    # JAR/v1 signature entries so the output has one coherent signer.
    patterns = [
        "META-INF/MANIFEST.MF",
        "META-INF/*.SF",
        "META-INF/*.RSA",
        "META-INF/*.DSA",
        "META-INF/*.EC",
    ]
    subprocess.run(["zip", "-q", "-d", apk_path, *patterns], check=False)


def make_minimal_patched_apk(base_apk, rebuilt_apk, dex_names, output_apk):
    work_dir = "xhs_minimal_dex"
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir)

    import zipfile
    with zipfile.ZipFile(rebuilt_apk, "r") as rebuilt:
        for dex_name in sorted(dex_names):
            target = os.path.join(work_dir, dex_name)
            with rebuilt.open(dex_name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)

    shutil.copy2(base_apk, output_apk)
    strip_old_v1_signatures(output_apk)

    # Replace only the touched DEX file(s). Resources, native libraries, assets,
    # manifest and every untouched dex remain byte-for-byte from the official APK.
    for dex_name in sorted(dex_names):
        subprocess.run(["zip", "-q", "-d", output_apk, dex_name], check=True)
        run("zip", "-q", "-0", "-j", output_apk, os.path.join(work_dir, dex_name))

    shutil.rmtree(work_dir)


def make_resigned_control(base_apk, output_apk):
    shutil.copy2(base_apk, output_apk)
    strip_old_v1_signatures(output_apk)


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    android_home = env("ANDROID_HOME") or env("ANDROID_SDK_ROOT")
    if android_home:
        candidates = sorted(
            glob.glob(os.path.join(android_home, "build-tools", "*", name)),
            reverse=True,
        )
        if candidates:
            return candidates[0]
    raise RuntimeError(f"{name} was not found")


def sign_apk(unsigned_apk, output_apk):
    zipalign = find_tool("zipalign")
    apksigner = find_tool("apksigner")
    aligned = unsigned_apk + ".aligned.apk"
    run(zipalign, "-p", "-f", "4", unsigned_apk, aligned)

    keystore = env("SIGNING_KEYSTORE_PATH", "ks_pkcs12.keystore")
    ks_pass = env("KEYSTORE_PASSWORD", "123456789")
    alias = env("KEY_ALIAS", "jhc")
    key_pass = env("KEY_PASSWORD", ks_pass)

    if not os.path.exists(keystore):
        raise RuntimeError(f"Keystore not found: {keystore}")

    run(
        apksigner,
        "sign",
        "--ks",
        keystore,
        "--ks-pass",
        f"pass:{ks_pass}",
        "--ks-key-alias",
        alias,
        "--key-pass",
        f"pass:{key_pass}",
        "--out",
        output_apk,
        aligned,
    )
    run(apksigner, "verify", "--verbose", output_apk)
    os.remove(aligned)


def main():
    ensure_dirs()
    base_url = env("BASE_APK_URL")
    if not base_url:
        raise RuntimeError("BASE_APK_URL is required")

    base_apk = download_apk(base_url)
    print(f"Base APK: {os.path.getsize(base_apk)} bytes, sha256={sha256(base_apk)}")

    apkeditor = os.path.join(BINS_DIR, "apkeditor.jar")
    if not os.path.exists(apkeditor):
        download_apkeditor()

    decoded = "xhs_decoded"
    if os.path.exists(decoded):
        shutil.rmtree(decoded)

    run("java", "-Xmx8g", "-jar", apkeditor, "d", "-f", "-i", base_apk, "-o", decoded)
    patched_count, dex_names = patch_xhs(decoded)
    print(f"Applied {patched_count} foldable gate patch(es); touched DEX: {sorted(dex_names)}")

    rebuilt = os.path.join(OUTPUT_DIR, "xhs-rebuilt-patched-temp.apk")
    minimal_unsigned = os.path.join(OUTPUT_DIR, "xhs-fold8-custom-minimal-unsigned.apk")
    output = os.path.join(OUTPUT_DIR, "xhs-fold8-custom-minimal.apk")
    control_unsigned = os.path.join(OUTPUT_DIR, "xhs-resigned-control-unsigned.apk")
    control_output = os.path.join(OUTPUT_DIR, "xhs-resigned-control.apk")
    for path in (rebuilt, minimal_unsigned, output, control_unsigned, control_output):
        if os.path.exists(path):
            os.remove(path)

    # APKEditor is used only as a DEX compiler here. Its fully rebuilt APK is NOT
    # shipped, because rebuilding every resource/native entry can trip XHS startup
    # integrity assumptions even when the APK signature itself verifies.
    run("java", "-Xmx8g", "-jar", apkeditor, "b", "-f", "-no-cache", "-i", decoded, "-o", rebuilt)

    make_minimal_patched_apk(base_apk, rebuilt, dex_names, minimal_unsigned)
    sign_apk(minimal_unsigned, output)

    # Diagnostic control: identical official APK payload, only re-signed with our
    # persistent key. If this one also crashes, the remaining blocker is XHS's
    # own certificate/signature self-check rather than resource rebuilding.
    make_resigned_control(base_apk, control_unsigned)
    sign_apk(control_unsigned, control_output)

    for path in (rebuilt, minimal_unsigned, control_unsigned):
        if os.path.exists(path):
            os.remove(path)

    print(f"Built minimal patch: {output}")
    print(f"minimal sha256={sha256(output)}")
    print(f"Built resigned control: {control_output}")
    print(f"control sha256={sha256(control_output)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
