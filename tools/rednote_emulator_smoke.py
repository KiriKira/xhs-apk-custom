#!/usr/bin/env python3
"""Install and capture a phone-free startup snapshot of three REDnote APK variants."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
ORIGINAL_PACKAGE = "com.xingin.xhs"
CLONE_PACKAGE = "com.kirikira.rednote.fold"
LAUNCH_ACTIVITY = "com.xingin.xhs.index.v2.IndexActivityV2"
ORIGINAL_FILES = (
    "com.xingin.xhs.apk",
    "config.arm64_v8a.apk",
    "config.xxhdpi.apk",
)

PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{5,}\d)(?!\w)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PACKAGE_DIED_RE = re.compile(r"Process\s+([A-Za-z0-9_.]+)\s+\(pid\s+(\d+)\)\s+has died")
FRAME_RE = re.compile(r"\bat\s+([A-Za-z0-9_.$]+)\.([A-Za-z0-9_$<>]+)\(([^)]*)\)")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def redact(value: str) -> str:
    value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    return PHONE_RE.sub("[REDACTED_PHONE]", value)


def decode_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


class Adb:
    def __init__(self, executable: str, serial: str | None, timeout: int):
        self.prefix = [executable]
        if serial:
            self.prefix += ["-s", serial]
        self.timeout = timeout

    def command(self, *args: str, timeout: int | None = None) -> dict[str, Any]:
        argv = self.prefix + list(args)
        result: dict[str, Any] = {"command": argv, "returncode": None, "stdout": "", "stderr": ""}
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout or self.timeout,
                check=False,
            )
            result.update(
                returncode=completed.returncode,
                stdout=completed.stdout.strip(),
                stderr=completed.stderr.strip(),
            )
        except subprocess.TimeoutExpired as exc:
            result.update(
                timed_out=True,
                stdout=decode_output(exc.stdout).strip(),
                stderr=decode_output(exc.stderr).strip(),
            )
        except OSError as exc:
            result["error"] = str(exc)
        return result

    def screenshot(self, timeout: int | None = None) -> tuple[dict[str, Any], bytes]:
        argv = self.prefix + ["exec-out", "screencap", "-p"]
        result: dict[str, Any] = {"command": argv, "returncode": None, "stderr": ""}
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                timeout=timeout or self.timeout,
                check=False,
            )
            result.update(returncode=completed.returncode, stderr=decode_output(completed.stderr).strip())
            return result, completed.stdout
        except subprocess.TimeoutExpired as exc:
            result["timed_out"] = True
            result["stderr"] = decode_output(exc.stderr).strip()
            return result, b""
        except OSError as exc:
            result["error"] = str(exc)
            return result, b""


def path_arg(value: str | None, base: Path, default: Path) -> Path:
    path = Path(value) if value else default
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def collect_environment(adb: Adb) -> dict[str, Any]:
    props = {
        "sys.boot_completed": "sys_boot_completed",
        "ro.build.version.release": "android_release",
        "ro.build.version.sdk": "android_sdk",
        "ro.product.cpu.abi": "primary_abi",
        "ro.product.cpu.abilist": "abi_list",
        "ro.product.cpu.abilist64": "abi_list_64",
        "ro.dalvik.vm.native.bridge": "native_bridge",
    }
    environment: dict[str, Any] = {}
    state = adb.command("get-state")
    environment["adb_state"] = state
    for prop, key in props.items():
        result = adb.command("shell", "getprop", prop)
        environment[key] = result.get("stdout", "")
        if result.get("returncode") != 0 or result.get("timed_out"):
            environment.setdefault("property_errors", {})[prop] = result
    environment["services"] = {
        service: adb.command("shell", "service", "check", service)
        for service in ("package", "activity")
    }
    environment["services_healthy"] = all(
        "found" in item.get("stdout", "").lower()
        and "not found" not in item.get("stdout", "").lower()
        for item in environment["services"].values()
    )
    return environment


def parse_package_paths(result: dict[str, Any]) -> list[str]:
    return [line.strip().removeprefix("package:") for line in result.get("stdout", "").splitlines()
            if line.strip().startswith("package:")]


def extract_crash_summary(logcat: str, package: str) -> dict[str, Any]:
    lines = logcat.splitlines()
    events: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if "FATAL EXCEPTION" in line:
            block = lines[index:index + 24]
            process_line = next((item for item in block if f"Process: {package}," in item), None)
            if process_line:
                throwable = None
                frames: list[str] = []
                for item in block:
                    clean = item.split(": ", 1)[-1].strip()
                    if throwable is None and re.match(r"(?:Caused by: )?[A-Za-z_$][\w.$]*(?:Exception|Error)(?::|$)", clean):
                        throwable = clean.split(":", 1)[0]
                    match = FRAME_RE.search(item)
                    if match and len(frames) < 5:
                        frames.append(f"{match.group(1)}.{match.group(2)}({match.group(3)})")
                events.append({
                    "type": "java_fatal_exception",
                    "thread": redact(line.split("FATAL EXCEPTION", 1)[-1].strip(" :")),
                    "throwable": throwable,
                    "stack_frames": frames,
                })
        if "Fatal signal" in line and any(package in item for item in lines[index:index + 12]):
            events.append({"type": "native_fatal_signal", "summary": redact(line.rsplit(":", 1)[-1].strip())})
        died = PACKAGE_DIED_RE.search(line)
        if died and died.group(1) == package:
            events.append({"type": "process_died", "pid": died.group(2)})
    # Keep the report compact if Android repeats the same process-death line.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        key = json.dumps(event, sort_keys=True)
        if key not in seen:
            unique.append(event)
            seen.add(key)
    return {"detected": bool(unique), "events": unique}


def save_ui_xml(adb: Adb, variant_dir: Path, remote_path: str, timeout: int) -> dict[str, Any]:
    dump = adb.command("shell", "uiautomator", "dump", remote_path, timeout=timeout)
    result: dict[str, Any] = {"dump": dump, "saved": False}
    raw_path = variant_dir / "ui-hierarchy.raw.xml"
    pulled = adb.command("pull", remote_path, str(raw_path), timeout=timeout)
    result["pull"] = pulled
    if pulled.get("returncode") == 0 and raw_path.is_file():
        try:
            root = ET.parse(raw_path).getroot()
            for node in root.iter():
                for name in ("text", "content-desc", "hint-text"):
                    value = node.attrib.get(name)
                    if value:
                        node.attrib[name] = redact(value)
            final_path = variant_dir / "ui-hierarchy.xml"
            ET.ElementTree(root).write(final_path, encoding="utf-8", xml_declaration=True)
            result.update(saved=True, path=str(final_path), bytes=final_path.stat().st_size,
                          sensitive_text_redacted=True)
        except (ET.ParseError, OSError) as exc:
            result["error"] = str(exc)
        finally:
            raw_path.unlink(missing_ok=True)
    return result


def capture_variant(adb: Adb, variant_dir: Path, package: str, timeout: int) -> dict[str, Any]:
    variant_dir.mkdir(parents=True, exist_ok=True)
    shot_result, image = adb.screenshot(timeout=timeout)
    screenshot_path = variant_dir / "screenshot.png"
    screenshot_saved = image.startswith(b"\x89PNG\r\n\x1a\n") and shot_result.get("returncode") == 0
    if screenshot_saved:
        screenshot_path.write_bytes(image)
    ui = save_ui_xml(adb, variant_dir, f"/sdcard/rednote-smoke-{package.replace('.', '-')}.xml", timeout)
    return {
        "screenshot": {
            **shot_result,
            "saved": screenshot_saved,
            "path": str(screenshot_path) if screenshot_saved else None,
            "bytes": len(image) if screenshot_saved else 0,
            "is_login_evidence": False,
        },
        "ui_hierarchy": ui,
    }


def install_and_launch(
    adb: Adb,
    variant: dict[str, Any],
    report_dir: Path,
    install_timeout: int,
    launch_timeout: int,
    capture_timeout: int,
    observe_seconds: int,
) -> dict[str, Any]:
    name = variant["name"]
    package = variant["package"]
    variant_dir = report_dir / name
    variant_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "name": name,
        "package": package,
        "artifact_paths": variant["artifacts"],
        "install": None,
        "installed": False,
        "package_paths": [],
        "launch": {"attempted": False, "activity": f"{package}/{LAUNCH_ACTIVITY}"},
        "app_pid": None,
        "crash_summary": {"detected": False, "events": []},
        "captures": None,
        "phone_input_performed": False,
        "login_status": "not_assessed",
    }

    # Uninstalling each package first gives every variant a clean app-data state.
    result["preinstall_uninstall"] = adb.command("uninstall", package, timeout=install_timeout)
    if variant["install_mode"] == "install-multiple":
        install = adb.command("install-multiple", "-r", *variant["artifacts"], timeout=install_timeout)
    else:
        install = adb.command("install", "-r", variant["artifacts"][0], timeout=install_timeout)
    result["install"] = install
    paths_result = adb.command("shell", "pm", "path", package)
    result["package_paths_result"] = paths_result
    result["package_paths"] = parse_package_paths(paths_result)
    result["installed"] = bool(result["package_paths"])
    result["install_succeeded"] = (
        install.get("returncode") == 0
        and "success" in install.get("stdout", "").lower()
        and not install.get("timed_out")
    )

    if result["installed"] and result["install_succeeded"]:
        adb.command("logcat", "-c")
        launch = adb.command(
            "shell", "am", "start", "-W", "-n", f"{package}/{LAUNCH_ACTIVITY}", timeout=launch_timeout
        )
        output = launch.get("stdout", "")
        status_match = re.search(r"^\s*Status:\s*(.+)$", output, re.M)
        result["launch"] = {
            "attempted": True,
            "activity": f"{package}/{LAUNCH_ACTIVITY}",
            "command_result": launch,
            "status": status_match.group(1).strip() if status_match else None,
            "actual_result": "started" if status_match and status_match.group(1).strip().lower() == "ok" else "unconfirmed",
        }

        observed_pids: list[str] = []
        last_pid_result: dict[str, Any] = {"stdout": ""}
        deadline = time.monotonic() + observe_seconds
        while True:
            last_pid_result = adb.command("shell", "pidof", package)
            observed_pids.extend(re.findall(r"\b\d+\b", last_pid_result.get("stdout", "")))
            if time.monotonic() >= deadline:
                break
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        final_pids = re.findall(r"\b\d+\b", last_pid_result.get("stdout", ""))
        result["app_pid"] = final_pids[-1] if final_pids else None
        result["observed_pids"] = list(dict.fromkeys(observed_pids))
        log_result = adb.command("logcat", "-d", "-v", "brief", "-t", "2500", timeout=capture_timeout)
        result["logcat_capture"] = {k: v for k, v in log_result.items() if k != "stdout"}
        result["crash_summary"] = extract_crash_summary(log_result.get("stdout", ""), package)

    result["captures"] = capture_variant(adb, variant_dir, package, capture_timeout)
    result["post_capture_force_stop"] = adb.command("shell", "am", "force-stop", package)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install three REDnote variants on a booted Android device and save startup evidence."
    )
    parser.add_argument("--base-dir", type=Path, default=REPO_DIR,
                        help="base for relative APK and report paths (default: repository root)")
    parser.add_argument("--original-dir", type=Path, default=Path("/workspace/rednote-input/verify"),
                        help="directory containing the original base and two split APKs")
    parser.add_argument("--control-apk", type=Path,
                        help="renamed-control APK (default: output_apks/rednote-9.48.1-renamed-control.apk)")
    parser.add_argument("--fold-apk", type=Path,
                        help="fold-custom APK (default: output_apks/rednote-9.48.1-fold-custom.apk)")
    parser.add_argument("--report-dir", type=Path, default=Path("runtime_reports/rednote-emulator-smoke"),
                        help="directory for JSON, screenshots, and UI XML")
    parser.add_argument("--adb", default=os.environ.get("ADB", "adb"), help="adb executable (default: adb or $ADB)")
    parser.add_argument("--serial", help="ADB serial; omit when exactly one device is connected")
    parser.add_argument("--install-timeout", type=int, default=300, help="install/uninstall timeout in seconds")
    parser.add_argument("--command-timeout", type=int, default=45, help="ordinary adb command timeout in seconds")
    parser.add_argument("--launch-timeout", type=int, default=45, help="activity launch timeout in seconds")
    parser.add_argument("--capture-timeout", type=int, default=45, help="screenshot/UI/logcat timeout in seconds")
    parser.add_argument("--observe-seconds", type=int, default=20,
                        help="seconds to observe the app process after launch (default: 20)")
    return parser


def validation_failures(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for item in variants:
        reasons = []
        if item.get("install_succeeded") is not True:
            reasons.append("install_not_succeeded")
        if item.get("installed") is not True:
            reasons.append("not_installed")
        launch = item.get("launch")
        if not isinstance(launch, dict) or launch.get("actual_result") != "started":
            reasons.append("launch_not_started")
        if not item.get("app_pid"):
            reasons.append("end_pid_missing")
        if item.get("crash_summary", {}).get("detected") is True:
            reasons.append("crash_detected")
        if reasons:
            failures.append({"name": item.get("name", "unknown"), "reasons": reasons})
    return failures


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base = args.base_dir.resolve()
    original_dir = path_arg(str(args.original_dir), base, Path())
    control_apk = path_arg(str(args.control_apk) if args.control_apk else None, base,
                           Path("output_apks/rednote-9.48.1-renamed-control.apk"))
    fold_apk = path_arg(str(args.fold_apk) if args.fold_apk else None, base,
                        Path("output_apks/rednote-9.48.1-fold-custom.apk"))
    report_dir = path_arg(str(args.report_dir), base, Path())
    report_path = report_dir / "rednote-emulator-smoke.json"
    original_apks = [original_dir / name for name in ORIGINAL_FILES]
    variants = [
        {"name": "original", "package": ORIGINAL_PACKAGE, "artifacts": [str(p) for p in original_apks],
         "install_mode": "install-multiple"},
        {"name": "renamed-control", "package": CLONE_PACKAGE, "artifacts": [str(control_apk)],
         "install_mode": "install"},
        {"name": "fold-custom", "package": CLONE_PACKAGE, "artifacts": [str(fold_apk)],
         "install_mode": "install"},
    ]
    missing = [str(path) for variant in variants for path in map(Path, variant["artifacts"]) if not path.is_file()]
    if missing:
        build_parser().error("APK file(s) not found: " + ", ".join(missing))
    if args.observe_seconds < 0:
        build_parser().error("--observe-seconds must be non-negative")

    report_dir.mkdir(parents=True, exist_ok=True)
    adb = Adb(args.adb, args.serial, args.command_timeout)
    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": now_utc(),
        "serial": args.serial,
        "base_dir": str(base),
        "environment": collect_environment(adb),
        "variants": [],
        "test_boundary": {
            "phone_input_performed": False,
            "security_detection_skipped": False,
            "identity_spoof_installed": False,
            "login_status": "not_assessed",
            "screenshot_is_login_evidence": False,
        },
    }

    def write_report() -> None:
        report["updated_at"] = now_utc()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_report()
    if report["environment"].get("adb_state", {}).get("stdout") != "device":
        report["error"] = "ADB device is not ready; no APK was installed."
        write_report()
        print(f"ADB is not ready; report saved to {report_path}", file=sys.stderr)
        return 2
    if report["environment"].get("sys_boot_completed") != "1":
        report["error"] = "Android sys.boot_completed is not 1; no APK was installed."
        write_report()
        print(f"Android is not booted; report saved to {report_path}", file=sys.stderr)
        return 2
    if not report["environment"].get("services_healthy"):
        report["error"] = "Android package or activity service is unavailable; no APK was installed."
        write_report()
        print(f"Android services are not ready; report saved to {report_path}", file=sys.stderr)
        return 2

    for variant in variants:
        item = install_and_launch(adb, variant, report_dir, args.install_timeout,
                                  args.launch_timeout, args.capture_timeout, args.observe_seconds)
        report["variants"].append(item)
        write_report()

    report["finished_at"] = now_utc()
    report["report_path"] = str(report_path)
    failures = validation_failures(report["variants"])
    report["validation"] = {"passed": not failures, "failed_variants": failures}
    write_report()
    print(json.dumps({"report": str(report_path), "validation": report["validation"]}, ensure_ascii=False))
    if failures:
        print("Emulator smoke validation failed; evidence report saved.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
