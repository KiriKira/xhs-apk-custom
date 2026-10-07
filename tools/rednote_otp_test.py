#!/usr/bin/env python3
"""Submit one user-provided OTP in an already-open REDnote session."""

import argparse, json, os, re, stat, time
from pathlib import Path
import rednote_phone_test as ui

OTP_RE = re.compile(r"[0-9]{4,8}\Z")
OTP_PAGE = ("验证码", "短信验证码", "输入验证码", "verification code", "enter code", "one-time code")
OTP_FAILURE = ("验证码错误", "验证码无效", "验证码不正确", "验证码有误", "验证码已过期", "验证码已失效",
               "验证失败", "invalid code", "incorrect code", "code expired", "login failed", "登录失败")
VERIFY = ("验证", "确认", "下一步", "登录", "登录/注册", "verify", "continue", "next", "submit", "log in", "login")
ME = ("我", "我的", "me", "my profile")
PROFILE_MARKERS = ("编辑资料", "编辑个人资料", "edit profile", "edit profile info")

def report_template():
    return {"result_category": "unsupported_ui", "otp_page_confirmed": False, "otp_input_visible": False,
            "otp_field_tapped": False, "otp_entered": False, "verify_clicked": False, "me_opened": False, "logged_in": False,
            "matched_prompt_keywords": [], "timeout": False}

def load_otp(path):
    if path.is_symlink() or not path.is_file(): raise ValueError
    info = path.stat()
    if info.st_mode & 0o077 or info.st_size > 4096: raise ValueError
    data = json.loads(path.read_text(encoding="utf-8"))
    code = data.get("otp") if isinstance(data, dict) else None
    if not isinstance(code, str) or not OTP_RE.fullmatch(code): raise ValueError
    return code

def edittexts(root):
    return [n for n in root.iter() if ui.visible(n) and "edittext" in n.attrib.get("class", "").lower()]

def unique_marker(root, labels):
    found = {}
    for node in root.iter():
        if not ui.visible(node): continue
        for key in ("text", "content-desc"):
            value = ui.norm(node.attrib.get(key, ""))
            for label in labels:
                if value == ui.norm(label): found[id(node)] = label
    return (next(iter(found.values())) if len(found) == 1 else None), len(found)

def otp_field(root):
    semantic = ui.fields(root, ui.OTP_HINTS)
    if len(semantic) == 1: return semantic[0]
    if semantic: return None
    only = edittexts(root)
    return only[0] if len(only) == 1 else None

def result_after_login(root, report):
    if ui.fields(root, ui.PHONE_HINTS) or otp_field(root) is not None or ui.matches(ui.ui_text(root), OTP_PAGE):
        return False
    marker, count = unique_marker(root, PROFILE_MARKERS)
    if count == 1:
        report["logged_in"] = True
        report["matched_prompt_keywords"] = [marker]
        report["result_category"] = "logged_in"
        return True
    return False

def run(args):
    report = report_template()
    try: code = load_otp(Path(args.payload_file))
    except (OSError, ValueError, json.JSONDecodeError):
        report["result_category"] = "payload_invalid"
        return report
    adb = ui.Adb(args.serial)
    ok, _, timed = adb.run("get-state", timeout=10)
    if not ok:
        report["timeout"], report["result_category"] = timed, "timeout" if timed else "device_unavailable"
        return report
    deadline, submitted_deadline = time.monotonic() + 75, 0
    me_tapped = False
    otp_field_id = otp_field_bounds = ""
    while time.monotonic() < deadline:
        root, timed = adb.ui()
        if root is None:
            if timed: report["timeout"], report["result_category"] = True, "timeout"; break
            time.sleep(1); continue
        texts = ui.ui_text(root)
        unsafe, captcha, challenge = ui.matches(texts, ui.UNSAFE), ui.matches(texts, ui.CAPTCHA), ui.matches(texts, ui.CHALLENGE)
        if unsafe or captcha or challenge:
            report["matched_prompt_keywords"] = unsafe or captcha or challenge
            report["result_category"] = "environment_unsafe" if unsafe else "captcha_shown" if captcha else "security_challenge"
            break
        failure = ui.matches(texts, OTP_FAILURE)
        if failure:
            report["matched_prompt_keywords"], report["result_category"] = failure, "otp_rejected"
            break
        otp_text = ui.matches(texts, OTP_PAGE)
        if report["otp_entered"]:
            identity_fields = ui.fields(root, (), otp_field_id, otp_field_bounds)
            field = identity_fields[0] if len(identity_fields) == 1 else None
        else:
            field = otp_field(root)
        report["otp_input_visible"] = field is not None
        if not report["otp_entered"]:
            if otp_text and field is None:
                report["matched_prompt_keywords"] = otp_text[:3]
                break
            if not otp_text:
                time.sleep(1); continue
            current = ui.norm(field.attrib.get("text", ""))
            if current and (re.search(r"\d", current) or not any(h in current for h in ui.OTP_HINTS)):
                break
            report["otp_page_confirmed"] = True
            report["matched_prompt_keywords"] = otp_text[:3]
            otp_field_id = field.attrib.get("resource-id", "").strip()
            otp_field_bounds = field.attrib.get("bounds", "")
            target = ui.clickable(root, field)
            if target is None or not adb.tap(target.attrib.get("bounds")): break
            report["otp_field_tapped"] = True
            ok, _, timed = adb.run("shell", "input", "text", code, timeout=12)
            if not ok:
                report["timeout"], report["result_category"] = timed, "timeout" if timed else "unsupported_ui"
                break
            report["otp_entered"] = True
            submitted_deadline = time.monotonic() + 45
            deadline = max(deadline, submitted_deadline)
            continue
        if result_after_login(root, report): break
        if (field is not None or otp_text) and not report["verify_clicked"]:
            clicked, label, count = ui.action(adb, root, VERIFY)
            if count > 1: break
            if clicked:
                report["verify_clicked"] = True
                report["matched_prompt_keywords"] = [label]
                continue
        # A disappearing OTP field indicates an automatic submit; only then visit Me.
        if field is None and not otp_text and not me_tapped:
            clicked, label, count = ui.action(adb, root, ME)
            if count > 1: break
            if clicked:
                me_tapped = True
                report["me_opened"] = True
                report["matched_prompt_keywords"] = [label]
                time.sleep(1); continue
        if time.monotonic() >= submitted_deadline:
            report["result_category"] = "otp_submitted_result_unconfirmed"
            break
        time.sleep(1)
    else:
        if report["otp_entered"]:
            report["result_category"] = "otp_submitted_result_unconfirmed"
        else:
            report["timeout"], report["result_category"] = True, "timeout"
    if report["result_category"] == "unsupported_ui" and adb.timed_out:
        report["timeout"], report["result_category"] = True, "timeout"
    return report

def main():
    p = argparse.ArgumentParser(description="Submit one OTP in the current REDnote session and verify a logged-in profile marker.")
    p.add_argument("--payload-file", required=True); p.add_argument("--serial", required=True)
    p.add_argument("--package", required=True, choices=ui.PACKAGES); p.add_argument("--report-file", required=True)
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", args.serial):
        report = report_template(); report["result_category"] = "device_unavailable"
    else:
        try: report = run(args)
        except Exception: report = report_template()
    path = Path(args.report_file); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, separators=(",", ":")); stream.write("\n")
    os.replace(temp, path); os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__": main()
