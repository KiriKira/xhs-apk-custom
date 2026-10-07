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


PREVIEW_SECONDS = 120
CAPTURE_RESERVE_SECONDS = 45
PHONE_DIRECT = ("其他手机号登录", "其他手机号码登录", "手机号登录", "手机号码登录", "手机号登陆",
                "phone number login", "log in with phone", "use phone number")
OTHER_LOGIN = ("其他登录方式", "其他方式登录", "更多登录方式", "other login options", "more sign-in options")
LOGIN = ("登录/注册", "登录", "注册/登录", "log in", "sign in", "login", "sign up")
ME = ("我", "我的", "me", "profile", "my profile")
AGREE = ("同意并继续", "同意并使用", "同意", "接受", "agree", "accept")
PERMISSION_PACKAGE = "com.google.android.permissioncontroller"
PERMISSION_MESSAGE_ID = "com.android.permissioncontroller:id/permission_message"
PERMISSION_DENY_ID = "com.android.permissioncontroller:id/permission_deny_button"
PERMISSION_MESSAGE = "allow rednote to send you notifications?"


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
             and n.attrib.get("package") == PERMISSION_PACKAGE
             and n.attrib.get("resource-id") == PERMISSION_MESSAGE_ID
             and ui.norm(n.attrib.get("text")) == PERMISSION_MESSAGE]
    if not texts:
        return False, None, 0
    if len(texts) != 1:
        return True, None, len(texts)
    targets = {}
    for node in root.iter():
        if (ui.visible(node) and node.attrib.get("package") == PERMISSION_PACKAGE
                and node.attrib.get("resource-id") == PERMISSION_DENY_ID
                and ui.norm(node.attrib.get("text")) in ("don't allow", "don’t allow")
                and node.attrib.get("enabled", "true") == "true"):
            target = ui.clickable(root, node)
            if target is not None and target.attrib.get("resource-id") == PERMISSION_DENY_ID:
                targets[id(target)] = target
    if len(targets) != 1:
        return True, None, len(targets)
    return True, next(iter(targets.values())), 1


def run(serial, package):
    deadline = time.monotonic() + PREVIEW_SECONDS
    adb = BoundedAdb(serial, deadline)
    report = {
        "package": package, "launched": False, "launches": [], "result_category": "unsupported_ui",
        "matched_prompt_keywords": [], "steps": [], "phone_input_performed": False,
        "sms_requested": False, "phone_form_visible": False,
        "screenshot_png_base64": None, "ui_xml": None,
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
                    last_xml = ET.tostring(root, encoding="unicode")
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

                    # The preview ends at a clearly identified phone field or country code.
                    phone_field = bool(ui.fields(root, ui.PHONE_HINTS))
                    has_country_code = any("+86" in text for text in texts)
                    if phone_field or has_country_code:
                        report["phone_form_visible"] = True
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
                        did_click, label, count = ui.action(adb, root, labels, preferred=preferred)
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
                    report.update(result_category="timeout", timeout=True)
                if last_xml is not None:
                    report["ui_xml"] = last_xml

    except Exception as exc:
        report["result_category"] = "preview_error"
        report["error_type"] = type(exc).__name__

    # Keep only process IDs and a redacted crash summary; never persist raw logcat.
    adb.deadline = deadline
    try:
        ok, output, timed = adb.run("shell", "pidof", package, timeout=5)
        final_pids = re.findall(r"\b\d+\b", output.decode("utf-8", errors="replace")) if ok else []
        report["app_pid"] = final_pids[-1] if final_pids else None
        report["observed_pids"] = list(dict.fromkeys(observed_pids))
        if final_pids:
            report["observed_pids"] = list(dict.fromkeys(observed_pids + final_pids))
        ok, logs, log_timed = adb.run("logcat", "-d", "-v", "brief", "-t", "1000", timeout=10)
        summary = smoke.extract_crash_summary(logs.decode("utf-8", errors="replace") if ok else "", package)
        report["runtime_diagnostics"] = {
            "pidof_timed_out": timed, "logcat_timed_out": log_timed,
            "crash_summary": summary,
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
                report["ui_xml"] = ET.tostring(root, encoding="unicode")
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
