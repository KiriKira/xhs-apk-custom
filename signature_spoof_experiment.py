import glob
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import requests

from download_bins import download_apkeditor
from xhs_build_ci import (
    BASE_APK_DIR,
    BINS_DIR,
    OUTPUT_DIR,
    download_apk,
    ensure_dirs,
    find_tool,
    run,
    sha256,
    sign_apk,
    strip_old_v1_signatures,
)

OFFICIAL_CERT_B64 = (
    "MIICTTCCAbagAwIBAgIEU8Y4ojANBgkqhkiG9w0BAQUFADBrMQswCQYDVQQGEwI4"
    "NjERMA8GA1UECBMIc2hhbmdoYWkxETAPBgNVBAcTCHNoYW5naGFpMQ8wDQYDVQQK"
    "EwZ4aW5naW4xDzANBgNVBAsTBnhpbmdpbjEUMBIGA1UEAxMLeGlhb2hvbmdzaHUw"
    "HhcNMTQwNzE2MDgzMjM0WhcNMzkwNzEwMDgzMjM0WjBrMQswCQYDVQQGEwI4NjER"
    "MA8GA1UECBMIc2hhbmdoYWkxETAPBgNVBAcTCHNoYW5naGFpMQ8wDQYDVQQKEwZ4"
    "aW5naW4xDzANBgNVBAsTBnhpbmdpbjEUMBIGA1UEAxMLeGlhb2hvbmdzaHUwgZ8w"
    "DQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBAJ2e1aSoXdiiEXvIr9y/lE3hPyjgaOG1"
    "FJLAy6aILwe7qe6xqykRGCJG+J0ifbPzWP5Jw/+31951kq3RrHS/ElrtxxkUIM9j"
    "LSwWOJjGAayFwLyQ59kydj6UVBKK4zmU9cxiLLPUJEiuTalGNtn7MrTFAGp6vOwy"
    "JpFwbI7vpIJlAgMBAAEwDQYJKoZIhvcNAQEFBQADgYEACYuNBV2HxudqYzsbIoO8"
    "okCKF6zUMCw4Y7IwJyObHnj/L8Qjk6GYHHjWt6IHMB9Ll+oPO3ncuakiEETStqo1"
    "MpYMSeS9zOCvssU6uqlK4igMMr24Caw7zzzsvoHg7v2HW8bNYNywJMxaMiG7dvqI"
    "+OLZZRMIho8HN0EJAwzMPJk="
)

OFFICIAL_SHA256 = "f375f0f6af7c94c364b35cd6f6a66d64aefae66e32f935b48773c0faad04c121"
OFFICIAL_SHA1 = "4ae949b443ed2e33b71f024af9ef24ff14f2e4d0"
OFFICIAL_MD5 = "6cfca61d9d1eca56844806706ba18cf7"


def env(name, default=""):
    value = os.environ.get(name, "").strip()
    return value if value else default


def dex_name_for_smali(path):
    normalized = str(path).replace("\\", "/")
    marker = "/smali/"
    if marker not in normalized:
        raise RuntimeError(f"Cannot infer dex from smali path: {path}")
    first = normalized.split(marker, 1)[1].split("/", 1)[0]
    if first == "classes":
        return "classes.dex"
    if re.fullmatch(r"classes\d+", first):
        return first + ".dex"
    raise RuntimeError(f"Unexpected smali dex directory: {first}")


def find_text_manifest(decoded_dir):
    for path in Path(decoded_dir).rglob("AndroidManifest.xml"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if "<manifest" in text and "<application" in text:
            return path, text
    return None, None


def resolve_application_class(decoded_dir, base_apk):
    manifest_path, manifest_text = find_text_manifest(decoded_dir)
    if manifest_text:
        pkg_match = re.search(r'<manifest[^>]*\bpackage="([^"]+)"', manifest_text, re.S)
        app_match = re.search(
            r'<application[^>]*\bandroid:name="([^"]+)"',
            manifest_text,
            re.S,
        )
        if app_match:
            package_name = pkg_match.group(1) if pkg_match else "com.xingin.xhs"
            app_name = app_match.group(1)
            if app_name.startswith("."):
                app_name = package_name + app_name
            elif "." not in app_name:
                app_name = package_name + "." + app_name
            return app_name, str(manifest_path)

    # Fallback to aapt2's binary manifest dump.
    aapt2 = find_tool("aapt2")
    proc = subprocess.run(
        [aapt2, "dump", "xmltree", "--file", "AndroidManifest.xml", base_apk],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    lines = proc.stdout.splitlines()
    in_application = False
    package_name = "com.xingin.xhs"
    app_name = None
    for line in lines:
        package_match = re.search(r'A: package(?:\([^)]*\))?="([^"]+)"', line)
        if package_match:
            package_name = package_match.group(1)
        if re.search(r"E: application\b", line):
            in_application = True
            continue
        if in_application:
            if re.search(r"^\s*E:", line):
                break
            name_match = re.search(r'A: android:name(?:\([^)]*\))?="([^"]+)"', line)
            if name_match:
                app_name = name_match.group(1)
                break
    if not app_name:
        raise RuntimeError("Could not determine Android application class")
    if app_name.startswith("."):
        app_name = package_name + app_name
    elif "." not in app_name:
        app_name = package_name + "." + app_name
    return app_name, "aapt2:AndroidManifest.xml"


def find_smali_class(decoded_dir, fqcn):
    suffix = "/" + fqcn.replace(".", "/") + ".smali"
    matches = []
    for path in Path(decoded_dir, "smali").rglob("*.smali"):
        normalized = str(path).replace("\\", "/")
        if normalized.endswith(suffix):
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one smali class for {fqcn}, found {len(matches)}: {matches}")
    return matches[0]


def patch_application_startup(smali_path):
    text = smali_path.read_text(encoding="utf-8")
    hook = "    invoke-static {}, Ldev/kiri/xhsspoof/SignatureSpoof;->install()V"

    method_re = re.compile(
        r"(?ms)^(\.method[^\n]*\sattachBaseContext\(Landroid/content/Context;\)V\n)"
        r"(?P<body>.*?)"
        r"(^\.end method\s*$)"
    )
    match = method_re.search(text)
    if match:
        if "Ldev/kiri/xhsspoof/SignatureSpoof;->install()V" in match.group(0):
            return False
        body = match.group("body")
        lines = body.splitlines()
        insert_at = None
        for i, line in enumerate(lines):
            if re.match(r"\s*\.(locals|registers)\b", line):
                insert_at = i + 1
                break
        if insert_at is None:
            raise RuntimeError("attachBaseContext has no .locals/.registers directive")
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, hook)
        lines.insert(insert_at + 2, "")
        new_body = "\n".join(lines)
        replacement = match.group(1) + new_body + "\n" + match.group(3)
        text = text[:match.start()] + replacement + text[match.end():]
        smali_path.write_text(text, encoding="utf-8", newline="\n")
        return True

    super_match = re.search(r"(?m)^\.super\s+(L[^;]+;)", text)
    if not super_match:
        raise RuntimeError(f"Could not determine superclass for {smali_path}")
    super_desc = super_match.group(1)
    new_method = textwrap.dedent(
        f"""

        .method protected attachBaseContext(Landroid/content/Context;)V
            .locals 0

            invoke-static {{}}, Ldev/kiri/xhsspoof/SignatureSpoof;->install()V

            invoke-super {{p0, p1}}, {super_desc}->attachBaseContext(Landroid/content/Context;)V

            return-void
        .end method
        """
    )
    smali_path.write_text(text.rstrip() + "\n" + new_method, encoding="utf-8", newline="\n")
    return True


def download_hiddenapi_classes(work_dir):
    aar = Path(work_dir, "hiddenapibypass-6.1.aar")
    classes_jar = Path(work_dir, "hiddenapi-classes.jar")
    url = (
        "https://repo.maven.apache.org/maven2/org/lsposed/hiddenapibypass/"
        "hiddenapibypass/6.1/hiddenapibypass-6.1.aar"
    )
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with aar.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    with zipfile.ZipFile(aar, "r") as zf:
        with zf.open("classes.jar") as src, classes_jar.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    return classes_jar


def build_signature_spoof_dex():
    work_dir = Path("signature_spoof_build")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    src_dir = work_dir / "src" / "dev" / "kiri" / "xhsspoof"
    classes_dir = work_dir / "classes"
    dex_dir = work_dir / "dex"
    src_dir.mkdir(parents=True)
    classes_dir.mkdir(parents=True)
    dex_dir.mkdir(parents=True)

    java_source = f"""package dev.kiri.xhsspoof;

import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Parcel;
import android.os.Parcelable;
import android.util.Base64;
import android.util.Log;

import org.lsposed.hiddenapibypass.HiddenApiBypass;

import java.lang.reflect.Field;
import java.util.Map;

public final class SignatureSpoof {{
    private static final String TAG = "XhsSigSpoof";
    private static final String PACKAGE_NAME = "com.xingin.xhs";
    private static final String CERT_B64 = "{OFFICIAL_CERT_B64}";
    private static boolean installed;

    private SignatureSpoof() {{}}

    public static synchronized void install() {{
        if (installed) return;
        try {{
            try {{
                HiddenApiBypass.addHiddenApiExemptions(
                    "Landroid/os/Parcel;",
                    "Landroid/content/pm",
                    "Landroid/app"
                );
            }} catch (Throwable ignored) {{
            }}

            final Signature fakeSignature =
                new Signature(Base64.decode(CERT_B64, Base64.DEFAULT));
            final Parcelable.Creator<PackageInfo> originalCreator = PackageInfo.CREATOR;

            Parcelable.Creator<PackageInfo> creator = new Parcelable.Creator<PackageInfo>() {{
                @Override
                @SuppressWarnings("deprecation")
                public PackageInfo createFromParcel(Parcel source) {{
                    PackageInfo info = originalCreator.createFromParcel(source);
                    if (PACKAGE_NAME.equals(info.packageName)) {{
                        if (info.signatures != null && info.signatures.length > 0) {{
                            info.signatures[0] = fakeSignature;
                        }}
                        if (info.signingInfo != null) {{
                            Signature[] signers = info.signingInfo.getApkContentsSigners();
                            if (signers != null && signers.length > 0) {{
                                signers[0] = fakeSignature;
                            }}
                        }}
                    }}
                    return info;
                }}

                @Override
                public PackageInfo[] newArray(int size) {{
                    return originalCreator.newArray(size);
                }}
            }};

            findField(PackageInfo.class, "CREATOR").set(null, creator);

            try {{
                Object cache = findField(PackageManager.class, "sPackageInfoCache").get(null);
                if (cache != null) {{
                    cache.getClass().getMethod("clear").invoke(cache);
                }}
            }} catch (Throwable ignored) {{
            }}

            try {{
                Map<?, ?> creators = (Map<?, ?>) findField(Parcel.class, "mCreators").get(null);
                if (creators != null) creators.clear();
            }} catch (Throwable ignored) {{
            }}

            try {{
                Map<?, ?> paired = (Map<?, ?>) findField(Parcel.class, "sPairedCreators").get(null);
                if (paired != null) paired.clear();
            }} catch (Throwable ignored) {{
            }}

            installed = true;
            Log.i(TAG, "PackageInfo signature spoof installed");
        }} catch (Throwable t) {{
            Log.e(TAG, "PackageInfo signature spoof failed", t);
        }}
    }}

    private static Field findField(Class<?> cls, String fieldName)
        throws NoSuchFieldException {{
        Class<?> current = cls;
        while (current != null && current != Object.class) {{
            try {{
                Field field = current.getDeclaredField(fieldName);
                field.setAccessible(true);
                return field;
            }} catch (NoSuchFieldException ignored) {{
                current = current.getSuperclass();
            }}
        }}
        throw new NoSuchFieldException(fieldName);
    }}
}}
"""
    java_file = src_dir / "SignatureSpoof.java"
    java_file.write_text(java_source, encoding="utf-8")

    hiddenapi_jar = download_hiddenapi_classes(work_dir)
    android_homes = [env("ANDROID_HOME"), env("ANDROID_SDK_ROOT")]
    android_jar = None
    for home in filter(None, android_homes):
        candidates = sorted(
            glob.glob(os.path.join(home, "platforms", "android-*", "android.jar")),
            reverse=True,
        )
        if candidates:
            android_jar = candidates[0]
            break
    if not android_jar:
        raise RuntimeError("No Android platform android.jar found")

    javac = shutil.which("javac")
    if not javac:
        raise RuntimeError("javac not found")
    classpath = os.pathsep.join([android_jar, str(hiddenapi_jar)])
    run(
        javac,
        "-source",
        "8",
        "-target",
        "8",
        "-classpath",
        classpath,
        "-d",
        classes_dir,
        java_file,
    )

    d8 = find_tool("d8")
    class_files = [str(p) for p in classes_dir.rglob("*.class")]
    run(
        d8,
        "--min-api",
        "23",
        "--lib",
        android_jar,
        "--output",
        dex_dir,
        *class_files,
        hiddenapi_jar,
    )

    dex = dex_dir / "classes.dex"
    if not dex.exists():
        raise RuntimeError("D8 did not produce helper classes.dex")
    return work_dir, dex


def next_dex_name(base_apk):
    highest = 1
    with zipfile.ZipFile(base_apk, "r") as zf:
        for name in zf.namelist():
            match = re.fullmatch(r"classes(\d*)\.dex", name)
            if not match:
                continue
            n = int(match.group(1)) if match.group(1) else 1
            highest = max(highest, n)
    return f"classes{highest + 1}.dex"


def make_code_spoof_apk(base_apk, rebuilt_apk, touched_dex, helper_dex, output_apk):
    shutil.copy2(base_apk, output_apk)
    strip_old_v1_signatures(output_apk)

    subprocess.run(["zip", "-q", "-d", output_apk, touched_dex], check=True)
    with zipfile.ZipFile(rebuilt_apk, "r") as zf:
        data = zf.read(touched_dex)
    tmp_dex = Path("signature_spoof_build") / touched_dex
    tmp_dex.write_bytes(data)
    run("zip", "-q", "-0", "-j", output_apk, tmp_dex)

    helper_name = next_dex_name(base_apk)
    helper_named = Path("signature_spoof_build") / helper_name
    shutil.copy2(helper_dex, helper_named)
    run("zip", "-q", "-0", "-j", output_apk, helper_named)
    return helper_name


def make_signer_name_control(base_apk, unsigned_apk):
    shutil.copy2(base_apk, unsigned_apk)
    strip_old_v1_signatures(unsigned_apk)


def collect_analysis(decoded_dir, app_name, app_smali, touched_dex, helper_dex_name):
    report = []
    report.append("XHS signature spoof experiment")
    report.append("=" * 36)
    report.append(f"application_class={app_name}")
    report.append(f"application_smali={app_smali}")
    report.append(f"touched_dex={touched_dex}")
    report.append(f"helper_dex={helper_dex_name}")
    report.append(f"official_cert_sha256={OFFICIAL_SHA256}")
    report.append(f"official_cert_sha1={OFFICIAL_SHA1}")
    report.append(f"official_cert_md5={OFFICIAL_MD5}")
    report.append("")
    report.append("External callers of com/split/signature")
    report.append("-" * 36)

    external = []
    pm_refs = []
    digest_refs = []
    pm_patterns = (
        "getPackageInfo(",
        "GET_SIGNATURES",
        "GET_SIGNING_CERTIFICATES",
        "getApkContentsSigners",
        "hasSigningCertificate",
        "Landroid/content/pm/SigningInfo;",
    )
    digest_needles = (OFFICIAL_SHA256, OFFICIAL_SHA1, OFFICIAL_MD5)

    for path in Path(decoded_dir, "smali").rglob("*.smali"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(path).replace("\\", "/")
        if "Lcom/split/signature/" in text and "/com/split/signature/" not in rel:
            for no, line in enumerate(text.splitlines(), 1):
                if "Lcom/split/signature/" in line:
                    external.append(f"{rel}:{no}: {line.strip()}")
        for no, line in enumerate(text.splitlines(), 1):
            if any(p in line for p in pm_patterns):
                pm_refs.append(f"{rel}:{no}: {line.strip()}")
            low = line.lower().replace(":", "").replace("-", "")
            if any(d in low for d in digest_needles):
                digest_refs.append(f"{rel}:{no}: {line.strip()}")

    report.extend(external[:300] or ["(none found)"])
    report.append("")
    report.append("Direct package-signature API references")
    report.append("-" * 36)
    report.extend(pm_refs[:500] or ["(none found)"])
    report.append("")
    report.append("Embedded official certificate digest references")
    report.append("-" * 36)
    report.extend(digest_refs[:200] or ["(none found)"])

    report_path = Path(OUTPUT_DIR, "signature-experiment-info.txt")
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    return report_path


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

    decoded = "xhs_sigspoof_decoded"
    if os.path.exists(decoded):
        shutil.rmtree(decoded)
    run("java", "-Xmx8g", "-jar", apkeditor, "d", "-f", "-i", base_apk, "-o", decoded)

    app_name, manifest_source = resolve_application_class(decoded, base_apk)
    app_smali = find_smali_class(decoded, app_name)
    touched_dex = dex_name_for_smali(app_smali)
    print(f"Application: {app_name}")
    print(f"Manifest source: {manifest_source}")
    print(f"Application smali: {app_smali}")
    print(f"Application dex: {touched_dex}")

    patch_application_startup(app_smali)
    helper_work_dir, helper_dex = build_signature_spoof_dex()

    rebuilt = os.path.join(OUTPUT_DIR, "xhs-signature-spoof-rebuilt-temp.apk")
    if os.path.exists(rebuilt):
        os.remove(rebuilt)
    run(
        "java", "-Xmx8g", "-jar", apkeditor,
        "b", "-f", "-no-cache", "-dex-lib", "jf",
        "-i", decoded, "-o", rebuilt,
    )

    unsigned_spoof = os.path.join(OUTPUT_DIR, "xhs-java-signature-spoof-control-unsigned.apk")
    spoof_output = os.path.join(OUTPUT_DIR, "xhs-java-signature-spoof-control.apk")
    unsigned_spoof_xingin = os.path.join(OUTPUT_DIR, "xhs-java-signature-spoof-xinginname-unsigned.apk")
    spoof_xingin_output = os.path.join(OUTPUT_DIR, "xhs-java-signature-spoof-xinginname.apk")
    signer_control_unsigned = os.path.join(OUTPUT_DIR, "xhs-signername-xingin-control-unsigned.apk")
    signer_control_output = os.path.join(OUTPUT_DIR, "xhs-signername-xingin-control.apk")

    for p in (
        unsigned_spoof,
        spoof_output,
        unsigned_spoof_xingin,
        spoof_xingin_output,
        signer_control_unsigned,
        signer_control_output,
    ):
        if os.path.exists(p):
            os.remove(p)

    helper_name = make_code_spoof_apk(
        base_apk,
        rebuilt,
        touched_dex,
        helper_dex,
        unsigned_spoof,
    )
    shutil.copy2(unsigned_spoof, unsigned_spoof_xingin)

    # Experiment A: Java PackageInfo spoof, otherwise normal persistent test signing.
    sign_apk(unsigned_spoof, spoof_output)

    # Experiment B: same Java spoof plus the original v1 signer entry name.
    sign_apk(unsigned_spoof_xingin, spoof_xingin_output, v1_signer_name="XINGIN")

    # Experiment C: no code changes; only keep the v1 signer entry name XINGIN.
    make_signer_name_control(base_apk, signer_control_unsigned)
    sign_apk(signer_control_unsigned, signer_control_output, v1_signer_name="XINGIN")

    report = collect_analysis(decoded, app_name, app_smali, touched_dex, helper_name)
    print(report.read_text(encoding="utf-8")[:12000])

    for p in (rebuilt, unsigned_spoof, unsigned_spoof_xingin, signer_control_unsigned):
        if os.path.exists(p):
            os.remove(p)
    if helper_work_dir.exists():
        # Keep report only; helper build intermediates are not artifacts.
        shutil.rmtree(helper_work_dir)

    for p in (spoof_output, spoof_xingin_output, signer_control_output):
        print(f"Built {p}: sha256={sha256(p)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
