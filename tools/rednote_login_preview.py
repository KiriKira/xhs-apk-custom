#!/usr/bin/env python3
"""Navigate to the REDnote phone-login form without entering any account data."""

import argparse
import base64
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import rednote_phone_test as ui


PHONE_DIRECT = ("其他手机号登录", "其他手机号码登录", "手机号登录", "手机号码登录", "手机号登陆",
                "phone number login", "log in with phone", "use phone number")
OTHER_LOGIN = ("其他登录方式", "其他方式登录", "更多登录方式", "other login options", "more sign-in options")
LOGIN = ("登录/注册", "登录", "注册/登录", "log in", "sign in", "login", "sign up")
ME = ("我", "我的", "me", "profile", "my profile")
AGREE = ("同意并继续", "同意并使用", "同意", "接受", "agree", "accept")
SAFE_SECONDS = 60


def run(serial, package):
    adb = ui.Adb(serial)
    report = {
        "package": package, "launched": False, "result_category": "unsupported_ui",
        "matched_prompt_keywords": [], "steps": [], "phone_input_performed": False,
        "sms_requested": False, "phone_form_visible": False,
        "screenshot_png_base64": None, "ui_xml": None,
    }
    ok, state, timed = adb.run("get-state", timeout=10)
    report["adb_state"] = state.decode("utf-8", errors="replace").strip()
    if not ok:
        report.update(result_category="timeout" if timed else "device_unavailable", timeout=timed)
        return report

    ok, output, timed = adb.run("shell", "am", "start", "-W", "-n",
                                package + "/" + ui.ACTIVITY, timeout=25)
    report["launch_output"] = output.decode("utf-8", errors="replace").strip()
    report["launched"] = ok
    if not ok:
        report.update(result_category="timeout" if timed else "launch_failed", timeout=timed)
    else:
        report["launch_activity"] = package + "/" + ui.ACTIVITY
        deadline = time.monotonic() + SAFE_SECONDS
        clicked = set()
        latest_xml = None
        while time.monotonic() < deadline:
            root, timed = adb.ui()
            if root is None:
                if timed:
                    report.update(result_category="timeout", timeout=True)
                    break
                time.sleep(1)
                continue

            latest_xml = ET.tostring(root, encoding="unicode")
            texts = ui.ui_text(root)
            unsafe = ui.matches(texts, ui.UNSAFE)
            captcha = ui.matches(texts, ui.CAPTCHA)
            challenge = ui.matches(texts, ui.CHALLENGE)
            if unsafe or captcha or challenge:
                report["matched_prompt_keywords"] = unsafe or captcha or challenge
                report["result_category"] = ("environment_unsafe" if unsafe else
                                             "captcha_shown" if captcha else "security_challenge")
                break

            phone_field = bool(ui.fields(root, ui.PHONE_HINTS))
            has_country_code = any("+86" in text for text in texts)
            if phone_field or has_country_code:
                report["phone_form_visible"] = True
                report["result_category"] = "phone_login_form" if phone_field else "phone_country_code_visible"
                break

            # Only click a single semantic target; each navigation class is tried at most once.
            choices = []
            if ui.matches(texts, ui.PRIVACY) and "privacy_agree" not in clicked:
                choices.append(("privacy_agree", AGREE))
            if "phone_login" not in clicked:
                choices.append(("phone_login", PHONE_DIRECT))
            if "other_login" not in clicked:
                choices.append(("other_login", OTHER_LOGIN))
            if "login" not in clicked:
                choices.append(("login", LOGIN))
            if "me" not in clicked:
                choices.append(("me", ME))

            acted = False
            for step, labels in choices:
                # Privacy and direct phone-login labels take precedence over general navigation.
                preferred = step in ("phone_login", "other_login", "login", "me")
                did_click, label, count = ui.action(adb, root, labels, preferred=preferred)
                if count > 1:
                    report["result_category"] = "ambiguous_ui"
                    report["matched_prompt_keywords"] = [label] if label else []
                    acted = True
                    break
                if did_click:
                    clicked.add(step)
                    report["steps"].append({"step": step, "label": label})
                    time.sleep(1)
                    acted = True
                    break
            if report["result_category"] == "ambiguous_ui":
                break
            if not acted:
                time.sleep(1)
        else:
            report.update(result_category="timeout", timeout=True)
        if latest_xml is not None:
            report["ui_xml"] = latest_xml

    # Always preserve the final no-input screen, including failed navigation and safety prompts.
    _, screenshot, screenshot_timeout = adb.run("exec-out", "screencap", "-p", timeout=15)
    if screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
        report["screenshot_png_base64"] = base64.b64encode(screenshot).decode("ascii")
        report["screenshot_bytes"] = len(screenshot)
    else:
        report["screenshot_error"] = "screenshot unavailable"
        if screenshot_timeout:
            report["timeout"] = True

    # Refresh XML after the last action so the report shows the screen being captured.
    root, _ = adb.ui()
    if root is not None:
        report["ui_xml"] = ET.tostring(root, encoding="unicode")
    return report


def main():
    parser = argparse.ArgumentParser(description="Navigate to the REDnote phone-login form without entering a phone or requesting SMS.")
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
