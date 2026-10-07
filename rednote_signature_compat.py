"""Helpers for the optional in-process Rednote signature compatibility mode.

The injected helper only changes PackageInfo/SigningInfo values returned inside
the app process. APK signing remains the responsibility of apksigner.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
import textwrap


EXPECTED_REDNOTE_CERT_SHA256 = (
    "dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd"
)
HIDDEN_API_BYPASS_URL = (
    "https://repo.maven.apache.org/maven2/org/lsposed/hiddenapibypass/"
    "hiddenapibypass/6.1/hiddenapibypass-6.1.aar"
)
HIDDEN_API_BYPASS_SHA256 = (
    "e3161dd21c97a4540b1698a33f7062aeaa1450008e1e2176070e5380f7a6324c"
)
SIGNATURE_HELPER_CLASS = "dev.kiri.xhsspoof.SignatureSpoof"
SIGNATURE_HOOK = "Ldev/kiri/xhsspoof/SignatureSpoof;->install()V"
ANDROID_TOOL_ROOTS = (
    Path("/workspace/android-tools/android-35"),
    Path("/workspace/android-tools/android-15"),
    Path("/workspace/android-tools/android-14"),
)
SIGNATURE_ENTRY_SUFFIXES = (".RSA", ".DSA", ".EC")


def _run(command: list[str | Path], *, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    args = [str(value) for value in command]
    try:
        result = subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not run {Path(args[0]).name}: {exc}") from exc
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {Path(args[0]).name}\n{result.stdout[-4000:]}"
        )
    return result


def extract_signer_certificate(
    apk_path: Path,
    work_dir: Path,
    expected_sha256: str = EXPECTED_REDNOTE_CERT_SHA256,
) -> bytes:
    """Extract the matching V1 signer certificate and return its DER bytes."""
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl is required to extract the verified source APK certificate")

    expected_sha256 = expected_sha256.lower().replace(":", "")
    cert_work = work_dir / "source-certificate"
    cert_work.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk_path, "r") as archive:
        signature_entries = [
            info
            for info in archive.infolist()
            if info.filename.upper().startswith("META-INF/")
            and "/" not in info.filename[len("META-INF/") :]
            and info.filename.upper().endswith(SIGNATURE_ENTRY_SUFFIXES)
        ]
        for index, info in enumerate(signature_entries):
            pkcs7_path = cert_work / f"signer-{index}.pkcs7"
            pem_path = cert_work / f"signer-{index}.pem"
            pkcs7_path.write_bytes(archive.read(info))
            result = subprocess.run(
                [openssl, "pkcs7", "-inform", "DER", "-in", str(pkcs7_path), "-print_certs", "-out", str(pem_path)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
            )
            if result.returncode:
                continue
            pem_bytes = pem_path.read_bytes()
            blocks = re.findall(
                rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                pem_bytes,
                flags=re.DOTALL,
            )
            for cert_index, pem in enumerate(blocks):
                cert_pem_path = cert_work / f"signer-{index}-{cert_index}.pem"
                cert_der_path = cert_work / f"signer-{index}-{cert_index}.der"
                cert_pem_path.write_bytes(pem + b"\n")
                converted = subprocess.run(
                    [openssl, "x509", "-inform", "PEM", "-in", str(cert_pem_path), "-outform", "DER", "-out", str(cert_der_path)],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                )
                if converted.returncode:
                    continue
                certificate = cert_der_path.read_bytes()
                digest = hashlib.sha256(certificate).hexdigest()
                if digest == expected_sha256:
                    return certificate

    raise RuntimeError(
        f"Could not extract expected source signer certificate {expected_sha256} from {apk_path.name}"
    )


def patch_application_startup(smali_path: Path) -> bool:
    """Install the helper at the start of Application.attachBaseContext()."""
    text = smali_path.read_text(encoding="utf-8")
    hook_line = f"    invoke-static {{}}, {SIGNATURE_HOOK}"
    method_re = re.compile(
        r"(?ms)^(\.method[^\n]*\sattachBaseContext\(Landroid/content/Context;\)V\n)"
        r"(?P<body>.*?)"
        r"(^\.end method\s*$)"
    )
    matches = list(method_re.finditer(text))
    if len(matches) > 1:
        raise RuntimeError(f"Expected at most one attachBaseContext method in {smali_path}")
    if matches:
        match = matches[0]
        if SIGNATURE_HOOK in match.group(0):
            return False
        body_lines = match.group("body").splitlines()
        directive_index = next(
            (i for i, line in enumerate(body_lines) if re.match(r"\s*\.(locals|registers)\b", line)),
            None,
        )
        if directive_index is None:
            raise RuntimeError(f"attachBaseContext has no .locals/.registers directive in {smali_path}")
        body_lines[directive_index + 1 : directive_index + 1] = ["", hook_line, ""]
        updated_body = "\n".join(body_lines)
        replacement = match.group(1) + updated_body + "\n" + match.group(3)
        text = text[: match.start()] + replacement + text[match.end() :]
        smali_path.write_text(text, encoding="utf-8", newline="\n")
        return True

    super_match = re.search(r"(?m)^\.super\s+(L[^;]+;)", text)
    if not super_match:
        raise RuntimeError(f"Could not determine superclass for {smali_path}")
    super_descriptor = super_match.group(1)
    new_method = textwrap.dedent(
        f"""

        .method protected attachBaseContext(Landroid/content/Context;)V
            .locals 0

            invoke-static {{}}, {SIGNATURE_HOOK}

            invoke-super {{p0, p1}}, {super_descriptor}->attachBaseContext(Landroid/content/Context;)V

            return-void
        .end method
        """
    )
    smali_path.write_text(text.rstrip() + "\n" + new_method, encoding="utf-8", newline="\n")
    return True


def _download_hiddenapi_classes(work_dir: Path) -> Path:
    aar_path = work_dir / "hiddenapibypass-6.1.aar"
    classes_jar = work_dir / "hiddenapi-classes.jar"
    try:
        with urllib.request.urlopen(HIDDEN_API_BYPASS_URL, timeout=120) as response:
            data = response.read(8 * 1024 * 1024 + 1)
    except Exception as exc:
        raise RuntimeError(f"Could not download pinned HiddenApiBypass dependency: {exc}") from exc
    if len(data) > 8 * 1024 * 1024:
        raise RuntimeError("HiddenApiBypass AAR exceeds the expected size limit")
    digest = hashlib.sha256(data).hexdigest()
    if digest != HIDDEN_API_BYPASS_SHA256:
        raise RuntimeError(
            f"HiddenApiBypass AAR SHA-256 mismatch: expected {HIDDEN_API_BYPASS_SHA256}, got {digest}"
        )
    aar_path.write_bytes(data)
    try:
        with zipfile.ZipFile(aar_path, "r") as archive:
            classes_jar.write_bytes(archive.read("classes.jar"))
    except (KeyError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"Pinned HiddenApiBypass AAR is invalid: {exc}") from exc
    return classes_jar


def _resolve_android_jar() -> Path:
    configured = os.environ.get("ANDROID_JAR", "").strip()
    candidates: list[Path] = []
    if configured:
        configured_path = Path(configured).expanduser()
        candidates.append(configured_path)
        if configured_path.is_dir():
            candidates.extend(sorted(configured_path.glob("platforms/android-*/android.jar"), reverse=True))
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(env_name, "").strip()
        if value:
            root = Path(value).expanduser()
            candidates.extend(sorted(root.glob("platforms/android-*/android.jar"), reverse=True))
    for root in ANDROID_TOOL_ROOTS:
        candidates.append(root / "android.jar")
        candidates.extend(sorted(root.glob("platforms/android-*/android.jar"), reverse=True))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "Android platform android.jar was not found; set ANDROID_JAR to the platform JAR"
    )


def _resolve_d8() -> Path:
    configured = os.environ.get("D8", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    found = shutil.which("d8")
    if found:
        candidates.append(Path(found))
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(env_name, "").strip()
        if value:
            candidates.extend(sorted(Path(value).glob("build-tools/*/d8"), reverse=True))
    for root in ANDROID_TOOL_ROOTS:
        candidates.append(root / "d8")
        candidates.extend(sorted(root.glob("build-tools/*/d8"), reverse=True))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise RuntimeError("D8 was not found; set D8 to the Android dexer executable")


def build_signature_spoof_dex(
    work_dir: Path,
    application_id: str,
    certificate_der: bytes,
) -> Path:
    """Compile the Java helper for the selected clone package and cert."""
    helper_root = work_dir / "signature-spoof-helper"
    if helper_root.exists():
        shutil.rmtree(helper_root)
    source_dir = helper_root / "src" / "dev" / "kiri" / "xhsspoof"
    classes_dir = helper_root / "classes"
    dex_dir = helper_root / "dex"
    source_dir.mkdir(parents=True)
    classes_dir.mkdir()
    dex_dir.mkdir()

    cert_b64 = base64.b64encode(certificate_der).decode("ascii")
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
    private static final String TAG = "RednoteSigSpoof";
    private static final String PACKAGE_NAME = "{application_id}";
    private static final String CERT_B64 = "{cert_b64}";
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
                if (cache != null) cache.getClass().getMethod("clear").invoke(cache);
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
            Log.i(TAG, "PackageInfo signature compatibility helper installed");
        }} catch (Throwable t) {{
            Log.e(TAG, "PackageInfo signature compatibility helper failed", t);
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
    java_file = source_dir / "SignatureSpoof.java"
    java_file.write_text(java_source, encoding="utf-8")

    android_jar = _resolve_android_jar()
    hiddenapi_jar = _download_hiddenapi_classes(helper_root)
    classpath = os.pathsep.join([str(android_jar), str(hiddenapi_jar)])
    compiler_args: list[str | Path] = [
        "-source",
        "8",
        "-target",
        "8",
        "-classpath",
        classpath,
        "-d",
        classes_dir,
        java_file,
    ]
    javac = shutil.which("javac")
    if javac:
        _run([javac, *compiler_args])
    else:
        java = shutil.which("java")
        if not java:
            raise RuntimeError("Neither javac nor java was found for helper compilation")
        _run([java, "com.sun.tools.javac.Main", *compiler_args])

    d8 = _resolve_d8()
    class_files = sorted(classes_dir.rglob("*.class"))
    if not class_files:
        raise RuntimeError("Java compiler did not produce helper class files")
    _run(
        [
            d8,
            "--min-api",
            "21",
            "--lib",
            android_jar,
            "--output",
            dex_dir,
            *class_files,
            hiddenapi_jar,
        ],
        timeout=3600,
    )

    dex = dex_dir / "classes.dex"
    if not dex.is_file():
        raise RuntimeError("D8 did not produce helper classes.dex")
    return dex


def next_dex_name(apk_path: Path) -> str:
    highest = 1
    with zipfile.ZipFile(apk_path, "r") as archive:
        for name in archive.namelist():
            match = re.fullmatch(r"classes(\d*)\.dex", name)
            if match:
                number = int(match.group(1) or "1")
                highest = max(highest, number)
    return f"classes{highest + 1}.dex"
