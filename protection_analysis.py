import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from download_bins import download_apkeditor
from xhs_build_ci import BINS_DIR, OUTPUT_DIR, download_apk, ensure_dirs, run, sha256

OFFICIAL_DIGESTS = (
    "f375f0f6af7c94c364b35cd6f6a66d64aefae66e32f935b48773c0faad04c121",
    "4ae949b443ed2e33b71f024af9ef24ff14f2e4d0",
    "6cfca61d9d1eca56844806706ba18cf7",
)

JAVA_PATTERNS = (
    "Landroid/content/pm/PackageManager;->getPackageInfo",
    "Landroid/content/pm/PackageManager;->getPackageArchiveInfo",
    "Landroid/content/pm/PackageManager;->hasSigningCertificate",
    "Landroid/content/pm/SigningInfo;->getApkContentsSigners",
    "Landroid/content/pm/PackageInfo;->signatures",
    "Landroid/content/pm/PackageInfo;->signingInfo",
    "Landroid/content/pm/Signature;",
    "META-INF/",
    "XINGIN.RSA",
)

SUSPECT_LIBS = (
    "libsecurebase.so",
    "libdexvmp.so",
    "libentryexpro.so",
    "libxEF4.so",
    "libcapahook.so",
    "libapkpatch.so",
    "libSystemHealer.so",
)


def env(name, default=""):
    value = os.environ.get(name, "").strip()
    return value if value else default


def context(lines, index, radius=8):
    lo = max(0, index - radius)
    hi = min(len(lines), index + radius + 1)
    return "\n".join(f"{i + 1:6d}: {lines[i]}" for i in range(lo, hi))


def scan_smali(decoded):
    report = []
    outside_split = []
    api_hits = []
    digest_hits = []
    startup_hits = []

    for path in Path(decoded, "smali").rglob("*.smali"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(path).replace("\\", "/")
        lines = text.splitlines()

        for i, line in enumerate(lines):
            if "Lcom/split/signature/" in line and "/com/split/signature/" not in rel:
                outside_split.append((rel, i, context(lines, i)))
            if any(p in line for p in JAVA_PATTERNS):
                api_hits.append((rel, i, context(lines, i)))
            normalized = re.sub(r"[^0-9a-f]", "", line.lower())
            if any(d in normalized for d in OFFICIAL_DIGESTS):
                digest_hits.append((rel, i, context(lines, i)))
            if any(k in line for k in ("System;->loadLibrary", "Runtime;->loadLibrary", "System;->load(")):
                if any(name.replace("lib", "").replace(".so", "") in text for name in SUSPECT_LIBS):
                    startup_hits.append((rel, i, context(lines, i)))

    def emit(title, hits, limit):
        report.append("")
        report.append(title)
        report.append("=" * len(title))
        if not hits:
            report.append("(none found)")
            return
        for n, (rel, idx, ctx) in enumerate(hits[:limit], 1):
            report.append(f"\n[{n}] {rel}:{idx + 1}")
            report.append(ctx)
        if len(hits) > limit:
            report.append(f"\n... {len(hits) - limit} more omitted")

    emit("External callers of com/split/signature", outside_split, 120)
    emit("Package/signature API and META-INF references", api_hits, 180)
    emit("Embedded official certificate digest references", digest_hits, 80)
    emit("Suspicious native-library load contexts", startup_hits, 100)
    return report


def scan_native(decoded):
    report = ["", "Native string scan", "=================="]
    roots = list(Path(decoded).rglob("*.so"))
    by_name = {p.name: p for p in roots}
    pattern = re.compile(
        r"(signature|certificate|cert|integrity|tamper|apk|package|xingin|sha-?1|sha-?256|kill|abort)",
        re.I,
    )
    for name in SUSPECT_LIBS:
        path = by_name.get(name)
        if not path:
            report.append(f"\n## {name}\n(not present)")
            continue
        report.append(f"\n## {name} :: {path}")
        try:
            proc = subprocess.run(
                ["strings", "-a", "-n", "5", str(path)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                errors="replace",
            )
            hits = [line for line in proc.stdout.splitlines() if pattern.search(line)]
            report.extend(hits[:250] or ["(no matching strings)"])
            if len(hits) > 250:
                report.append(f"... {len(hits) - 250} more omitted")
        except Exception as exc:
            report.append(f"(strings failed: {exc})")
    return report


def main():
    ensure_dirs()
    base_url = env("BASE_APK_URL")
    if not base_url:
        raise RuntimeError("BASE_APK_URL is required")

    base_apk = download_apk(base_url)
    apkeditor = os.path.join(BINS_DIR, "apkeditor.jar")
    if not os.path.exists(apkeditor):
        download_apkeditor()

    decoded = "xhs_protection_analysis"
    if os.path.exists(decoded):
        shutil.rmtree(decoded)
    run("java", "-Xmx8g", "-jar", apkeditor, "d", "-f", "-i", base_apk, "-o", decoded)

    report = [
        "XHS protection static analysis",
        "==============================",
        f"base_sha256={sha256(base_apk)}",
    ]
    report.extend(scan_smali(decoded))
    report.extend(scan_native(decoded))

    out = Path(OUTPUT_DIR, "protection-analysis.txt")
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8")[:60000])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
