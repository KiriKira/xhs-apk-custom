#!/usr/bin/env python3
"""Navigate to REDnote phone login without entering account data or requesting SMS."""

import argparse
import base64
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import rednote_emulator_smoke as smoke
import rednote_phone_test as ui


PREVIEW_SECONDS = 180
CAPTURE_RESERVE_SECONDS = 60
PHONE_DIRECT = ("其他手机号登录", "其他手机号码登录", "手机号登录", "手机号码登录", "手机号登陆",
                "phone number login", "log in with phone", "use phone number",
                "continue with phone number")
OTHER_LOGIN = ("其他登录方式", "其他方式登录", "更多登录方式", "other login options", "more sign-in options")
LOGIN = ("登录/注册", "登录", "注册/登录", "log in", "sign in", "login", "sign up")
ME = ("我", "我的", "me", "profile", "my profile")
AGREE = ("同意并继续", "同意并使用", "同意", "接受", "agree", "accept")
PERMISSION_PACKAGES = {
    "com.google.android.permissioncontroller",
    "com.android.permissioncontroller",
}
PERMISSION_MESSAGE_ID = "com.android.permissioncontroller:id/permission_message"
PERMISSION_DENY_ID = "com.android.permissioncontroller:id/permission_deny_button"
PERMISSION_MESSAGE = "allow rednote to send you notifications?"
FOREIGN_PACKAGES = {
    "com.google.android.gms": "google_gms",
    "com.android.launcher3": "android_launcher",
    "com.google.android.apps.nexuslauncher": "google_launcher",
    "com.google.android.permissioncontroller": "permission_controller",
    "com.android.permissioncontroller": "permission_controller",
}
EXIT_RECORD_RE = re.compile(r"(?m)^\s*#\d+\s*:\s*")
EXIT_PROCESS_RE = re.compile(r"\b(?:process|processName)\s*[=:]\s*([^,\s)]+)", re.I)
EXIT_REASON_RE = re.compile(r"\breason\s*[=:]\s*(\d+)(?:\s*\(([A-Z0-9_]+)\))?", re.I)
EXIT_STATUS_RE = re.compile(r"\bstatus\s*[=:]\s*(-?\d+)", re.I)
EXIT_PID_RE = re.compile(r"\bpid\s*[=:]\s*(\d+)", re.I)
NATIVE_FRAME_RE = re.compile(r"#\s*\d+\s+pc\s+([0-9a-fA-F]+)\s+([^\s(]+)")
TOMBSTONE_CMDLINE_RE = re.compile(r"\bCmdline:\s*([A-Za-z0-9_.:-]+)")
TOMBSTONE_PROC_RE = re.compile(r">>>\s*([A-Za-z0-9_.:-]+)\s*<<<")


class BoundedAdb(ui.Adb):
    """Reuse the phone-test helper while capping every ADB call to the preview deadline."""
    def __init__(self, serial, deadline):
        super().__init__(serial)
        self.deadline = deadline

    def run(self, *args, timeout=15):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.timed_out = True
            return False, b"", True
        return super().run(*args, timeout=min(timeout, remaining))


def notification_deny_target(root):
    texts = [n for n in root.iter() if ui.visible(n)
             and n.attrib.get("package") in PERMISSION_PACKAGES
             and n.attrib.get("resource-id") == PERMISSION_MESSAGE_ID
             and ui.norm(n.attrib.get("text")) == PERMISSION_MESSAGE]
    if not texts:
        return False, None, 0
    if len(texts) != 1:
        return True, None, len(texts)
    prompt_package = texts[0].attrib.get("package")
    targets = {}
    for node in root.iter():
        if (ui.visible(node) and node.attrib.get("package") == prompt_package
                and node.attrib.get("resource-id") == PERMISSION_DENY_ID
                and ui.norm(node.attrib.get("text")) in ("don't allow", "don’t allow")
                and node.attrib.get("enabled", "true") == "true"):
            target = ui.clickable(root, node)
            if target is not None and target.attrib.get("resource-id") == PERMISSION_DENY_ID:
                targets[id(target)] = target
    if len(targets) != 1:
        return True, None, len(targets)
    return True, next(iter(targets.values())), 1


def phone_form_indicators(root, expected_package):
    """Only app-owned nodes can establish that the phone form is visible."""
    phone_field = any(
        node.attrib.get("package") == expected_package
        for node in ui.fields(root, ui.PHONE_HINTS)
    )
    app_texts = [
        ui.norm(value)
        for node in root.iter()
        if ui.visible(node) and node.attrib.get("package") == expected_package
        for value in ui.attrs(node) if value
    ]
    return phone_field, any("+86" in text for text in app_texts)


def scoped_action(adb, root, package, labels, preferred=False):
    """Click a unique matching control only when both it and its click target belong to the app."""
    groups = []
    for label in labels:
        found = {}
        for node in root.iter():
            if (ui.visible(node) and node.attrib.get("package") == package
                    and any(ui.norm(value) == ui.norm(label) for value in ui.attrs(node))):
                target = ui.clickable(root, node)
                if target is not None and target.attrib.get("package") == package:
                    found[id(target)] = target
        if found:
            groups.append((label, list(found.values())))
            if preferred:
                break
    targets = {id(node): node for _, group in groups for node in group}
    if not targets:
        return False, None, 0
    if len(targets) != 1:
        return False, None, len(targets)
    label, target = next((label, node) for label, group in groups for node in group)
    return adb.tap(target.attrib.get("bounds")), label, 1


def foreign_ui_category(root, expected_package):
    visible_packages = {node.attrib.get("package") for node in root.iter() if ui.visible(node)}
    if expected_package in visible_packages:
        return None
    return next((category for package, category in FOREIGN_PACKAGES.items()
                 if package in visible_packages), None)


def serialize_ui(root, expected_package):
    """Keep the hierarchy while withholding text from system and other foreign windows."""
    copy = ET.fromstring(ET.tostring(root, encoding="utf-8"))
    for node in copy.iter():
        if node.attrib.get("package") != expected_package:
            for key in ("text", "content-desc", "hint", "hint-text"):
                if node.attrib.get(key):
                    node.attrib[key] = "[FOREIGN_UI_TEXT_REDACTED]"
    return ET.tostring(copy, encoding="unicode")


def parse_exit_info(output, package):
    """Extract only structured exit fields for this package; discard all raw text."""
    starts = list(EXIT_RECORD_RE.finditer(output))
    blocks = [output[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(output)]
              for i, m in enumerate(starts)] or [output]
    records = []
    for block in blocks:
        process = EXIT_PROCESS_RE.search(block)
        if not process or not (process.group(1) == package or process.group(1).startswith(package + ":")):
            continue
        reason = EXIT_REASON_RE.search(block)
        status = EXIT_STATUS_RE.search(block)
        pid = EXIT_PID_RE.search(block)
        records.append({
            "reason_code": int(reason.group(1)) if reason else None,
            "reason_enum": reason.group(2).upper() if reason and reason.group(2) else None,
            "status": int(status.group(1)) if status else None,
            "pid": int(pid.group(1)) if pid else None,
        })
        if len(records) == 5:
            break
    return records


def combine_crash_summaries(*summaries):
    events, seen = [], set()
    for summary in summaries:
        for event in summary.get("events", []):
            key = json.dumps(event, sort_keys=True)
            if key not in seen:
                events.append(event)
                seen.add(key)
            if len(events) >= 10:
                break
    return {"detected": bool(events), "events": events}


def extract_native_frames(logcat, package):
    """Return at most ten package-tombstone frames with path and symbols removed."""
    lines = logcat.splitlines()
    package_prefix = package + ":"
    anchors = []
    for index, line in enumerate(lines):
        match = TOMBSTONE_CMDLINE_RE.search(line) or TOMBSTONE_PROC_RE.search(line)
        if match and (match.group(1) == package or match.group(1).startswith(package_prefix)):
            anchors.append(index)
    frames, seen = [], set()
    for start in anchors:
        for line in lines[start + 1:start + 301]:
            if "*** *** ***" in line or "--------- beginning of crash" in line:
                break
            other = TOMBSTONE_CMDLINE_RE.search(line) or TOMBSTONE_PROC_RE.search(line)
            if other:
                break
            match = NATIVE_FRAME_RE.search(line)
            if not match:
                continue
            library = match.group(2).rsplit("/", 1)[-1]
            if library in ("", "??"):
                continue
            frame = {"library": library, "pc": match.group(1).lower()}
            key = (frame["library"], frame["pc"])
            if key not in seen:
                frames.append(frame)
                seen.add(key)
            if len(frames) >= 10:
                return frames
    return frames


def run(serial, package):
    deadline = time.monotonic() + PREVIEW_SECONDS
    adb = BoundedAdb(serial, deadline)
    report = {
        "package": package, "launched": False, "launches": [], "result_category": "unsupported_ui",
        "matched_prompt_keywords": [], "steps": [], "phone_input_performed": False,
        "sms_requested": False, "phone_form_visible": False,
        "foreign_ui_package": None, "screenshot_png_base64": None, "ui_xml": None,
    }
    observed_pids = []
    last_xml = None
    try:
        ok, state, timed = adb.run("get-state", timeout=8)
        report["adb_state"] = state.decode("utf-8", errors="replace").strip()
        if not ok:
            report.update(result_category="timeout" if timed else "device_unavailable", timeout=timed)
        else:
            # Isolate this run's startup logs so the compact crash report won't include stale events.
            clear_ok, _, clear_timed = adb.run("logcat", "-c", timeout=5)
            report["logcat_cleared_before_launch"] = clear_ok
            report["logcat_clear_timed_out"] = clear_timed
            ok, output, timed = adb.run("shell", "am", "start", "-W", "-n",
                                        package + "/" + ui.ACTIVITY, timeout=22)
            report["launches"].append(output.decode("utf-8", errors="replace").strip())
            report["launched"] = ok
            report["launch_activity"] = package + "/" + ui.ACTIVITY
            if not ok:
                report.update(result_category="timeout" if timed else "launch_failed", timeout=timed)
            else:
                clicked, notification_dismissed, relaunched = set(), False, False
                country_opened = country_searched = country_search_opened = False
                country_scrolls = 0
                navigation_deadline = deadline - CAPTURE_RESERVE_SECONDS
                adb.deadline = navigation_deadline
                while time.monotonic() < navigation_deadline:
                    root, timed = adb.ui()
                    if root is None:
                        if timed:
                            report.update(result_category="timeout", timeout=True)
                            break
                        time.sleep(min(1, max(0, navigation_deadline-time.monotonic())))
                        continue
                    last_xml = serialize_ui(root, package)
                    texts = ui.ui_text(root)
                    unsafe = ui.matches(texts, ui.UNSAFE)
                    captcha = ui.matches(texts, ui.CAPTCHA)
                    challenge = ui.matches(texts, ui.CHALLENGE)
                    if unsafe or captcha or challenge:
                        report["matched_prompt_keywords"] = unsafe or captcha or challenge
                        report["result_category"] = ("environment_unsafe" if unsafe else
                                                     "captcha_shown" if captcha else "security_challenge")
                        break

                    pid_ok, pid_output, _ = adb.run("shell", "pidof", package, timeout=3)
                    if pid_ok:
                        observed_pids.extend(re.findall(r"\b\d+\b", pid_output.decode("utf-8", errors="replace")))

                    is_permission, deny_target, deny_count = notification_deny_target(root)
                    if is_permission:
                        if notification_dismissed or deny_count != 1:
                            report["result_category"] = "notification_prompt_unresolved"
                            break
                        # Tap the single identified deny-button using the shared bounds parser.
                        bounds = ui.BOUNDS.fullmatch(deny_target.attrib.get("bounds", ""))
                        if bounds:
                            x1, y1, x2, y2 = map(int, bounds.groups())
                            ok, _, timed = adb.run("shell", "input", "tap", str((x1+x2)//2),
                                                   str((y1+y2)//2), timeout=8)
                        else:
                            ok, timed = False, False
                        if not ok:
                            report.update(result_category="notification_deny_failed", timeout=timed)
                            break
                        notification_dismissed = True
                        clicked.add("notification_deny")
                        report["steps"].append({"step": "deny_notification_permission", "label": "Don’t allow"})
                        time.sleep(min(1, max(0, navigation_deadline-time.monotonic())))
                        # The app may have exited behind the system dialog. Relaunch the known entry once.
                        if not relaunched and time.monotonic() < navigation_deadline:
                            ok, output, timed = adb.run("shell", "am", "start", "-W", "-n",
                                                        package + "/" + ui.ACTIVITY, timeout=20)
                            report["launches"].append(output.decode("utf-8", errors="replace").strip())
                            report["steps"].append({"step": "relaunch_known_activity", "succeeded": ok})
                            relaunched = True
                            if not ok:
                                report.update(result_category="relaunch_failed", timeout=timed)
                                break
                        continue

                    foreign_category = foreign_ui_category(root, package)
                    if foreign_category:
                        report["foreign_ui_package"] = foreign_category
                        report["result_category"] = "foreign_ui"
                        if foreign_category in ("android_launcher", "google_launcher"):
                            time.sleep(min(1, max(0, navigation_deadline-time.monotonic())))
                            continue
                        break
                    report["foreign_ui_package"] = None

                    # Select the user's requested +86 while this is still account-free.
                    phone_field, has_country_code = phone_form_indicators(root, package)
                    if phone_field and ui.country_state(root, package) == "other" and not country_opened:
                        targets = ui.code_targets(root, package)
                        if len(targets) != 1 or not adb.tap(targets[0].attrib.get("bounds")):
                            report["result_category"] = "country_selector_unresolved"
                            break
                        country_opened = True
                        report["steps"].append({"step": "open_country_selector"})
                        continue
                    if country_opened and not phone_field:
                        did_click, label, count = ui.select_cn_country(adb, root, package)
                        if did_click:
                            report["steps"].append({"step": "select_country", "label": label})
                            continue
                        if count:
                            report["result_category"] = "country_selector_unresolved"
                            break
                        # The global picker may label China differently; its calling code is stable.
                        did_click, label, count = scoped_action(adb, root, package, ("+86",), preferred=True)
                        if count == 0:
                            did_click, label, count = scoped_action(adb, root, package, ui.COUNTRY_NAMES)
                        if count > 1:
                            report["result_category"] = "ambiguous_country_selector"
                            break
                        if did_click:
                            report["steps"].append({"step": "select_country", "label": label})
                            continue
                        searches = ui.fields(root, ("search", "country", "region"), package=package)
                        if not searches and not country_search_opened:
                            did_click, label, count = scoped_action(adb, root, package, ("Search",))
                            if count > 1:
                                report["result_category"] = "ambiguous_country_search"
                                break
                            if did_click:
                                country_search_opened = True
                                report["steps"].append({"step": "open_country_search"})
                                continue
                        if len(searches) == 1 and not country_searched:
                            if adb.tap(searches[0].attrib.get("bounds")):
                                ok, _, _ = adb.run("shell", "input", "text", "China", timeout=8)
                                if ok:
                                    country_searched = True
                                    report["steps"].append({"step": "search_country", "label": "China"})
                                    continue
                        lists = [n for n in root.iter() if ui.visible(n)
                                 and n.attrib.get("package") == package
                                 and n.attrib.get("scrollable") == "true"]
                        if len(lists) == 1 and country_scrolls < 8:
                            bounds = ui.BOUNDS.fullmatch(lists[0].attrib.get("bounds", ""))
                            if bounds:
                                x1, y1, x2, y2 = map(int, bounds.groups())
                                ok, _, _ = adb.run("shell", "input", "swipe", str((x1+x2)//2),
                                                   str(y2-40), str((y1+y2)//2), "400", timeout=8)
                                if ok:
                                    country_scrolls += 1
                                    report["steps"].append({"step": "scroll_country_list"})
                                    continue
                        report["result_category"] = "country_selector_unresolved"
                        break
                    if phone_field and ui.country_state(root, package) != "cn":
                        report["result_category"] = "phone_country_unconfirmed"
                        break
                    if phone_field or has_country_code:
                        report["phone_form_visible"] = True
                        report["country_confirmed"] = ui.country_state(root, package) == "cn"
                        report["result_category"] = "phone_login_form" if phone_field else "phone_country_code_visible"
                        break

                    if ui.matches(texts, ui.PRIVACY) and "privacy_agree" not in clicked:
                        choices = [("privacy_agree", AGREE)]
                    else:
                        choices = []
                    choices.extend((step, labels) for step, labels in (
                        ("phone_login", PHONE_DIRECT), ("other_login", OTHER_LOGIN),
                        ("login", LOGIN), ("me", ME)) if step not in clicked)
                    acted = False
                    for step, labels in choices:
                        preferred = step != "privacy_agree"
                        did_click, label, count = scoped_action(adb, root, package, labels, preferred=preferred)
                        if count > 1:
                            report["result_category"] = "ambiguous_ui"
                            report["matched_prompt_keywords"] = [label] if label else []
                            acted = True
                            break
                        if did_click:
                            clicked.add(step)
                            report["steps"].append({"step": step, "label": label})
                            time.sleep(min(1, max(0, navigation_deadline-time.monotonic())))
                            acted = True
                            break
                    if report["result_category"] == "ambiguous_ui":
                        break
                    if not acted:
                        time.sleep(min(1, max(0, navigation_deadline-time.monotonic())))
                else:
                    if not report["foreign_ui_package"]:
                        report.update(result_category="timeout", timeout=True)
                if last_xml is not None:
                    report["ui_xml"] = last_xml

    except Exception as exc:
        report["result_category"] = "preview_error"
        report["error_type"] = type(exc).__name__

    # Keep only process IDs and structured crash/exit summaries; never persist raw logs.
    adb.deadline = deadline
    try:
        ok, output, timed = adb.run("shell", "pidof", package, timeout=5)
        final_pids = re.findall(r"\b\d+\b", output.decode("utf-8", errors="replace")) if ok else []
        report["app_pid"] = final_pids[-1] if final_pids else None
        report["observed_pids"] = list(dict.fromkeys(observed_pids))
        if final_pids:
            report["observed_pids"] = list(dict.fromkeys(observed_pids + final_pids))
        ok, logs, log_timed = adb.run("logcat", "-d", "-v", "brief", "-t", "1000", timeout=10)
        log_summary = smoke.extract_crash_summary(logs.decode("utf-8", errors="replace") if ok else "", package)
        helper_ok, helper_logs, helper_timed = adb.run(
            "logcat", "-d", "-v", "brief", "-s", "RednoteSigSpoof", timeout=5)
        helper_text = helper_logs.decode("utf-8", errors="replace") if helper_ok else ""
        helper_events = re.findall(
            r"PackageInfo signature compatibility helper (installed|failed)", helper_text)
        crash_ok, crash_logs, crash_timed = adb.run(
            "logcat", "-d", "-b", "crash", "-v", "brief", timeout=10
        )
        crash_summary = smoke.extract_crash_summary(
            crash_logs.decode("utf-8", errors="replace") if crash_ok else "", package
        )
        native_frames = extract_native_frames(
            crash_logs.decode("utf-8", errors="replace") if crash_ok else "", package
        )
        exit_ok, exit_output, exit_timed = adb.run(
            "shell", "dumpsys", "activity", "exit-info", package, timeout=8
        )
        exit_records = parse_exit_info(
            exit_output.decode("utf-8", errors="replace") if exit_ok else "", package
        )
        report["runtime_diagnostics"] = {
            "signature_compat_helper": helper_events[-1] if helper_events else "not_observed",
            "signature_compat_log_timed_out": helper_timed,
            "pidof_timed_out": timed,
            "logcat_timed_out": log_timed,
            "crash_buffer_timed_out": crash_timed,
            "exit_info_timed_out": exit_timed,
            "crash_summary": combine_crash_summaries(log_summary, crash_summary),
            "native_backtrace_frames": native_frames,
            "exit_info": {"parsed_record_count": len(exit_records), "records": exit_records},
        }
    except Exception as exc:
        report["runtime_diagnostics"] = {"error_type": type(exc).__name__,
                                         "crash_summary": {"detected": False, "events": []}}

    try:
        _, screenshot, screenshot_timeout = adb.run("exec-out", "screencap", "-p", timeout=12)
        if screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
            report["screenshot_png_base64"] = base64.b64encode(screenshot).decode("ascii")
            report["screenshot_bytes"] = len(screenshot)
        else:
            report["screenshot_error"] = "screenshot unavailable"
            if screenshot_timeout:
                report["timeout"] = True
        if report["ui_xml"] is None and time.monotonic() < deadline:
            # If navigation never obtained a tree, make one short final read within the reserve.
            adb.deadline = min(deadline, time.monotonic() + 15)
            root, _ = adb.ui()
            if root is not None:
                report["ui_xml"] = serialize_ui(root, package)
    except Exception as exc:
        report["capture_error_type"] = type(exc).__name__
    report["phone_input_performed"] = False
    report["sms_requested"] = False
    report["preview_time_limit_seconds"] = PREVIEW_SECONDS
    return report


def main():
    parser = argparse.ArgumentParser(description="Preview REDnote phone login without entering a phone or requesting SMS.")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", required=True, choices=ui.PACKAGES)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.serial, args.package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "result_category": report["result_category"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
