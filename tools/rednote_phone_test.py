#!/usr/bin/env python3
"""Conservative, one-pass REDnote login UI check. Never reads or submits an OTP."""

import argparse, json, os, re, stat, subprocess, time
import xml.etree.ElementTree as ET
from pathlib import Path

ACTIVITY = "com.xingin.xhs.index.v2.IndexActivityV2"
PACKAGES = ("com.xingin.xhs", "com.kirikira.rednote.fold")
REMOTE_XML = "/data/local/tmp/rednote-phone-test-ui.xml"
PHONE_RE = re.compile(r"\+861[3-9]\d{9}\Z")
BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
PHONE_HINTS = ("手机号", "手机号码", "电话号码", "phone number", "mobile number", "phone", "mobile")
OTP_HINTS = ("验证码", "短信码", "verification code", "sms code", "otp")
PRIVACY = ("隐私政策", "用户协议", "个人信息保护", "privacy policy", "terms of service")
UNSAFE = ("环境不安全", "环境异常", "设备环境异常", "设备环境不安全", "环境风险",
          "unsafe environment", "abnormal environment", "environment is unsafe",
          "insecure environment", "environment is not secure")
CHALLENGE = ("安全验证", "风险验证", "安全风险", "存在风险", "风险提示", "security verification", "unusual activity")
CAPTCHA = ("人机验证", "滑动验证", "图形验证", "captcha", "complete the verification")
AGREE = ("同意并继续", "同意并使用", "同意", "接受", "agree", "accept")
PHONE_LOGIN = ("其他手机号登录", "其他手机号码登录", "手机号登录", "手机号码登录", "手机号登陆",
               "phone number login", "log in with phone", "use phone number")
GET_CODE = ("获取验证码", "发送验证码", "next", "get code")
COUNTRY_NAMES = ("中国", "中国大陆", "china", "mainland china", "中国(+86)", "中国 +86", "china (+86)", "china +86")
TERMS = ("用户协议", "隐私政策", "服务条款", "terms", "privacy policy")
def norm(s): return re.sub(r"\s+", " ", s or "").strip().lower()
def attrs(n): return [n.attrib.get(k, "") for k in ("text", "content-desc", "hint", "hint-text", "resource-id")]
def visible(n): return n.attrib.get("visible-to-user", "true").lower() != "false"
def ui_text(root, package=None):
    return [norm(v) for n in root.iter() if visible(n)
            and (package is None or n.attrib.get("package") == package)
            for v in attrs(n) if v]
def matches(texts, terms): return [p for p in terms if any(norm(p) in t for t in texts)]
def package_visible(root, package):
    return any(visible(n) and n.attrib.get("package") == package for n in root.iter())
class Adb:
    def __init__(self, serial): self.base, self.timed_out = ["adb", "-s", serial], False
    def run(self, *args, timeout=15):
        try:
            r = subprocess.run(self.base + list(args), capture_output=True, timeout=timeout, check=False)
            return r.returncode == 0, r.stdout, False
        except subprocess.TimeoutExpired:
            self.timed_out = True
            return False, b"", True
        except OSError: return False, b"", False
    def ui(self):
        self.run("shell", "rm", "-f", REMOTE_XML)
        try:
            ok, _, timed = self.run("shell", "uiautomator", "dump", REMOTE_XML, timeout=20)
            if not ok: return None, timed
            ok, raw, timed = self.run("exec-out", "cat", REMOTE_XML, timeout=12)
            if not ok: return None, timed
            try: return ET.fromstring(raw), False
            except ET.ParseError: return None, False
        finally: self.run("shell", "rm", "-f", REMOTE_XML)
    def tap(self, bounds):
        m = BOUNDS.fullmatch(bounds or "")
        if not m: return False
        x1, y1, x2, y2 = map(int, m.groups())
        return self.run("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))[0]
def clickable(root, node, package=None):
    parents, cur = {c: p for p in root.iter() for c in p}, node
    while cur is not None:
        if package is not None and cur.attrib.get("package") != package:
            return None
        if (visible(cur) and cur.attrib.get("enabled", "true") == "true"
                and cur.attrib.get("clickable") == "true" and cur.attrib.get("bounds")):
            return cur
        cur = parents.get(cur)
    return None
def action(adb, root, labels, preferred=False, package=None):
    """Click exactly one semantic target; priority mode prefers earlier labels."""
    groups = []
    for label in labels:
        found = {}
        for node in root.iter():
            if (visible(node) and (package is None or node.attrib.get("package") == package)
                    and any(norm(v) == norm(label) for v in attrs(node))):
                target = clickable(root, node, package)
                if target is not None: found[id(target)] = target
        if found:
            groups.append((label, list(found.values())))
            if preferred: break
    if not groups: return False, None, 0
    targets = {id(n): n for _, group in groups for n in group}
    if len(targets) != 1: return False, None, len(targets)
    label = groups[0][0]
    return adb.tap(next(iter(targets.values())).attrib.get("bounds")), label, 1
def fields(root, hints, field_id="", field_bounds="", package=None):
    return [n for n in root.iter() if visible(n) and "edittext" in n.attrib.get("class", "").lower()
            and (package is None or n.attrib.get("package") == package)
            and ((hints and any(h in " ".join(norm(v) for v in attrs(n)) for h in hints))
                 or (field_id and n.attrib.get("resource-id") == field_id)
                 or (not field_id and field_bounds and n.attrib.get("bounds") == field_bounds))]
def country_state(root, package=None):
    texts = ui_text(root, package)
    codes = {t for t in texts if re.fullmatch(r"\+\d{1,3}", t)}
    if len(codes) > 1: return "picker"
    if codes == {"+86"} or any(t in COUNTRY_NAMES for t in texts): return "cn"
    return "other" if codes else "unknown"
def code_targets(root, package=None):
    found = {}
    for n in root.iter():
        if (visible(n) and (package is None or n.attrib.get("package") == package)
                and any(re.fullmatch(r"\+\d{1,3}", norm(v)) for v in attrs(n))):
            target = clickable(root, n, package)
            if target is not None: found[id(target)] = target
    return list(found.values())
def terms_boxes(root, package=None):
    parents, found = {c: p for p in root.iter() for c in p}, []
    for n in root.iter():
        if (not visible(n) or n.attrib.get("checkable") != "true"
                or (package is not None and n.attrib.get("package") != package)): continue
        context, cur = [], n
        for _ in range(3):
            if cur is None or (package is not None and cur.attrib.get("package") != package): break
            context.extend(attrs(cur))
            context.extend(v for child in list(cur)[:8]
                           if package is None or child.attrib.get("package") == package
                           for v in attrs(child))
            cur = parents.get(cur)
        if any(h in norm(v) for v in context for h in TERMS): found.append(n)
    return found
def load_phone(path):
    if path.is_symlink() or not path.is_file(): raise ValueError
    info = path.stat()
    if info.st_mode & 0o077 or info.st_size > 4096: raise ValueError
    data = json.loads(path.read_text(encoding="utf-8"))
    phone = data.get("phone") if isinstance(data, dict) else None
    if not isinstance(phone, str) or not PHONE_RE.fullmatch(phone): raise ValueError
    return phone[3:]
def report_template():
    keys = ("launched", "privacy_accepted", "phone_login_opened", "country_confirmed", "phone_entered", "terms_checked", "get_code_clicked")
    return {"steps": {k: False for k in keys}, "result_category": "unsupported_ui", "matched_prompt_keywords": [], "otp_input_visible": False, "timeout": False}
def run(args):
    report = report_template()
    try: phone = load_phone(Path(args.payload_file))
    except (OSError, ValueError, json.JSONDecodeError):
        report["result_category"] = "payload_invalid"
        return report
    adb = Adb(args.serial)
    ok, _, timed = adb.run("get-state")
    if not ok:
        report["timeout"], report["result_category"] = timed, "timeout" if timed else "device_unavailable"
        return report
    ok, _, timed = adb.run("shell", "am", "start", "-n", args.package + "/" + ACTIVITY, timeout=25)
    if not ok:
        report["timeout"], report["result_category"] = timed, "timeout" if timed else "unsupported_ui"
        return report
    report["steps"]["launched"] = True
    login_tapped = country_opened = country_selected = phone_typed = terms_tapped = sms_clicked = False
    phone_field_id = phone_field_bounds = ""
    sms_deadline, deadline = 0, time.monotonic() + 90
    while time.monotonic() < deadline:
        root, timed = adb.ui()
        if root is None:
            if timed: report["timeout"], report["result_category"] = True, "timeout"; break
            time.sleep(1); continue
        if not package_visible(root, args.package):
            report["result_category"] = "foreign_ui"
            break
        texts = ui_text(root, args.package)
        unsafe, captcha, challenge = matches(texts, UNSAFE), matches(texts, CAPTCHA), matches(texts, CHALLENGE)
        if unsafe:
            report["matched_prompt_keywords"], report["result_category"] = unsafe, "environment_unsafe"; break
        if captcha or challenge:
            report["matched_prompt_keywords"] = captcha or challenge
            report["result_category"] = "captcha_shown" if captcha else "security_challenge"; break
        if sms_clicked and fields(root, OTP_HINTS, package=args.package):
            report["otp_input_visible"], report["result_category"] = True, "otp_screen"; break
        if sms_clicked:
            if time.monotonic() >= sms_deadline:
                report["result_category"] = "request_attempted_outcome_unconfirmed"; break
            time.sleep(1); continue
        phone_fields = (fields(root, PHONE_HINTS, package=args.package) if not phone_typed
                        else fields(root, (), phone_field_id, phone_field_bounds, args.package))
        if country_opened and not phone_fields:
            if country_selected: break
            clicked, label, count = action(adb, root, COUNTRY_NAMES, package=args.package)
            if clicked:
                country_selected = True; report["matched_prompt_keywords"] = [label]
                time.sleep(1); continue
            if count > 1: break
            time.sleep(1); continue
        if not phone_fields and matches(texts, PRIVACY):
            clicked, _, count = action(adb, root, AGREE, package=args.package)
            if clicked:
                report["steps"]["privacy_accepted"] = True
                report["matched_prompt_keywords"] = matches(texts, PRIVACY)[:3]
                time.sleep(1); continue
            if count > 1: break
        if not phone_fields and not login_tapped:
            clicked, label, count = action(adb, root, PHONE_LOGIN, preferred=True, package=args.package)
            if clicked:
                login_tapped = True; report["steps"]["phone_login_opened"] = True
                report["matched_prompt_keywords"] = [label]; time.sleep(1); continue
            if count > 1: break
        if not phone_fields:
            time.sleep(1); continue
        if len(phone_fields) != 1: break
        country = country_state(root, args.package)
        if country == "other" and not country_opened:
            targets = code_targets(root, args.package)
            if len(targets) != 1 or not adb.tap(targets[0].attrib.get("bounds")): break
            country_opened = True; time.sleep(1); continue
        if country == "unknown" and not country_opened:
            clicked, _, _ = action(adb, root, ("国家/地区", "地区", "country/region", "country code"),
                                   True, args.package)
            if clicked: country_opened = True; time.sleep(1); continue
            break
        if country != "cn": break
        report["steps"]["phone_login_opened"] = True
        report["steps"]["country_confirmed"] = True
        if not phone_typed:
            node = phone_fields[0]
            current = norm(node.attrib.get("text", ""))
            if current and (re.search(r"\d", current) or not any(h in current for h in PHONE_HINTS)): break
            target = clickable(root, node, args.package)
            if target is None or not adb.tap(target.attrib.get("bounds")): break
            phone_field_id = node.attrib.get("resource-id", "").strip()
            phone_field_bounds = node.attrib.get("bounds", "")
            ok, _, timed = adb.run("shell", "input", "text", phone, timeout=12)
            if not ok:
                report["timeout"], report["result_category"] = timed, "timeout" if timed else "unsupported_ui"; break
            phone_typed = True; report["steps"]["phone_entered"] = True; time.sleep(1); continue
        boxes = terms_boxes(root, args.package)
        if len(boxes) != 1: break
        box = boxes[0]
        if box.attrib.get("checked") != "true":
            if terms_tapped: break
            target = clickable(root, box, args.package)
            if target is None or not adb.tap(target.attrib.get("bounds")): break
            terms_tapped = True; time.sleep(1); continue
        report["steps"]["terms_checked"] = True
        clicked, label, count = action(adb, root, GET_CODE, preferred=True, package=args.package)
        if clicked:
            sms_clicked, sms_deadline = True, time.monotonic() + 20
            deadline = max(deadline, sms_deadline)
            report["steps"]["get_code_clicked"] = True; report["matched_prompt_keywords"] = [label]
            continue
        if count > 1: break
        time.sleep(1)
    else:
        if sms_clicked:
            report["result_category"] = "request_attempted_outcome_unconfirmed"
        else:
            report["timeout"], report["result_category"] = True, "timeout"
    if report["result_category"] == "unsupported_ui" and adb.timed_out:
        report["timeout"], report["result_category"] = True, "timeout"
    return report

def main():
    p = argparse.ArgumentParser(description="One-pass REDnote phone UI check; never enters or submits an OTP.")
    p.add_argument("--payload-file", required=True); p.add_argument("--serial", required=True)
    p.add_argument("--report-file", required=True); p.add_argument("--package", required=True, choices=PACKAGES)
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", args.serial):
        report = report_template(); report["result_category"] = "device_unavailable"
    else:
        try: report = run(args)
        except Exception: report = report_template()
    path = Path(args.report_file); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, separators=(",", ":")); f.write("\n")
    os.replace(temp, path); os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
if __name__ == "__main__": main()
