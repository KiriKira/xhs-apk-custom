#!/usr/bin/env python3
"""Submit one user-provided OTP in an already-open REDnote session."""

import argparse, json, os, re, stat, time
from pathlib import Path
import rednote_phone_test as ui
import rednote_restart_debug as restart_debug

OTP_RE = re.compile(r"[0-9]{4,8}\Z")
OTP_PAGE = ("验证码", "短信验证码", "输入验证码", "verification code", "enter code", "one-time code")
GLOBAL_OTP_FIELD_ID = ":id/editCode"
GLOBAL_OTP_SLOT_IDS = tuple(f":id/txtCode{i}" for i in range(1, 7))
OTP_FAILURE = ("验证码错误", "验证码无效", "验证码不正确", "验证码有误", "验证码已过期", "验证码已失效",
               "无效验证码", "验证码失效", "验证失败", "invalid code", "incorrect code", "code expired",
               "invalid verification code", "incorrect verification code", "verification code error",
               "sms verification code error", "verification code expired", "verification code has expired",
               "login failed", "登录失败")
VERIFY = ("验证", "确认", "下一步", "登录", "登录/注册", "verify", "continue", "next", "submit", "log in", "login")
ME = ("我", "我的", "me", "my profile")
PROFILE_MARKERS = ("编辑资料", "编辑个人资料", "edit profile", "edit profile info")
LOGIN_MARKERS = ("登录/注册", "手机号登录", "手机号码登录", "log in", "login", "sign in")
ME_TAB_ID = ":id/index_me"
PROFILE_CONTAINER_ID = ":id/matrix_profile_new_page_container_layout"
PROFILE_TOOLBAR_IDS = (":id/editUserInfoStatusBar", ":id/profile_new_page_toolbar_btn_ll")
HOME_FEED_ID = ":id/mLoadMoreRecycleView"
OTP_ERROR_LOG_MARKERS = (
    "sms verification code error", "invalid verification code", "incorrect verification code",
    "verification code error", "verification code expired", "verification code has expired",
    "验证码错误", "验证码不正确", "无效验证码", "验证码已失效", "验证码已过期",
)

def empty_screen_markers():
    return {"phone_form_visible": False, "otp_form_visible": False, "home_feed_visible": False,
            "login_marker_visible": False, "me_tab_visible": False, "profile_container_visible": False,
            "profile_edit_marker_visible": False, "otp_error_marker_visible": False}

def report_template():
    return {"result_category": "unsupported_ui", "otp_page_confirmed": False, "otp_input_visible": False,
            "otp_field_tapped": False, "otp_entered": False, "verify_clicked": False, "me_opened": False, "logged_in": False,
            "me_tab_tapped": False, "matched_prompt_keywords": [], "timeout": False,
            "known_screen_markers": empty_screen_markers(), "activity_class": None, "app_pids": [],
            "crash_events": []}

def load_otp(path):
    if path.is_symlink() or not path.is_file(): raise ValueError
    info = path.stat()
    if info.st_mode & 0o077 or info.st_size > 4096: raise ValueError
    data = json.loads(path.read_text(encoding="utf-8"))
    code = data.get("otp") if isinstance(data, dict) else None
    if not isinstance(code, str) or not OTP_RE.fullmatch(code): raise ValueError
    return code

def edittexts(root, package):
    return [n for n in root.iter() if ui.visible(n) and n.attrib.get("package") == package
            and "edittext" in n.attrib.get("class", "").lower()]

def unique_marker(root, labels, package):
    found = {}
    for node in root.iter():
        if not ui.visible(node) or node.attrib.get("package") != package: continue
        for key in ("text", "content-desc"):
            value = ui.norm(node.attrib.get(key, ""))
            for label in labels:
                if value == ui.norm(label): found[id(node)] = label
    return (next(iter(found.values())) if len(found) == 1 else None), len(found)

def resource_nodes(root, package, suffix):
    return [n for n in root.iter() if ui.visible(n) and n.attrib.get("package") == package
            and n.attrib.get("resource-id", "").endswith(suffix)]

def profile_edit_marker_visible(root, package, profile_nodes):
    if len(profile_nodes) != 1: return False
    parents = {child: parent for parent in root.iter() for child in parent}
    toolbar_nodes = [n for n in root.iter() if ui.visible(n) and n.attrib.get("package") == package
                     and any(n.attrib.get("resource-id", "").endswith(suffix) for suffix in PROFILE_TOOLBAR_IDS)]
    matches = []
    for node in root.iter():
        if not ui.visible(node) or node.attrib.get("package") != package: continue
        if not any(ui.norm(node.attrib.get(key, "")) == ui.norm(label)
                   for key in ("text", "content-desc") for label in PROFILE_MARKERS):
            continue
        current = node
        while current is not None:
            if current in toolbar_nodes:
                matches.append(node)
                break
            current = parents.get(current)
    return len({id(n) for n in matches}) == 1

def known_screen_markers(root, package):
    texts = ui.ui_text(root, package)
    phone_fields = ui.fields(root, ui.PHONE_HINTS, package=package)
    profile_nodes = resource_nodes(root, package, PROFILE_CONTAINER_ID)
    return {
        "phone_form_visible": len(phone_fields) == 1,
        "otp_form_visible": otp_form_active(root, package),
        "home_feed_visible": len(resource_nodes(root, package, HOME_FEED_ID)) == 1,
        "login_marker_visible": bool(ui.matches(texts, LOGIN_MARKERS)),
        "me_tab_visible": len(resource_nodes(root, package, ME_TAB_ID)) == 1,
        "profile_container_visible": len(profile_nodes) == 1,
        "profile_edit_marker_visible": profile_edit_marker_visible(root, package, profile_nodes),
        "otp_error_marker_visible": bool(ui.matches(texts, OTP_FAILURE)),
    }

def tap_me_tab(adb, root, package):
    nodes = resource_nodes(root, package, ME_TAB_ID)
    if len(nodes) != 1: return False, len(nodes)
    node = nodes[0]
    # TabView inherits ConstraintLayout; accessibility may expose ViewGroup.
    # Its unique app-owned resource ID identifies this navigation target.
    bounds = ui.BOUNDS.fullmatch(node.attrib.get("bounds", ""))
    if not bounds: return False, 1
    x1, y1, x2, y2 = map(int, bounds.groups())
    if x2 <= x1 or y2 <= y1: return False, 1
    return adb.tap(node.attrib["bounds"]), 1

def logcat_has_known_otp_error(adb, since_epoch):
    ok, raw, _ = adb.run("logcat", "-d", "-v", "epoch", "-t", "1000", timeout=10)
    if not ok: return False
    for line in raw.decode("utf-8", errors="ignore").splitlines():
        try: timestamp = float(line.split(" ", 1)[0])
        except (ValueError, IndexError): continue
        if timestamp >= since_epoch and any(marker in line.lower() for marker in OTP_ERROR_LOG_MARKERS):
            return True
    return False

def otp_form_active(root, package):
    global_state, _ = global_otp_form(root, package)
    if global_state == "confirmed": return True
    has_otp_title = bool(ui.matches(ui.ui_text(root, package), OTP_PAGE))
    return has_otp_title and len(ui.fields(root, ui.OTP_HINTS, package=package)) == 1

def otp_field(root, package):
    semantic = ui.fields(root, ui.OTP_HINTS, package=package)
    if len(semantic) == 1: return semantic[0]
    if semantic: return None
    only = edittexts(root, package)
    return only[0] if len(only) == 1 else None

def global_otp_form(root, package):
    """Return (state, field) for the source-confirmed six-slot OTP widget."""
    own = [n for n in root.iter() if ui.visible(n) and n.attrib.get("package") == package]
    field_nodes = [n for n in own if n.attrib.get("resource-id", "").endswith(GLOBAL_OTP_FIELD_ID)]
    slot_nodes = {
        resource_id: [n for n in own if n.attrib.get("resource-id", "").endswith(resource_id)]
        for resource_id in GLOBAL_OTP_SLOT_IDS
    }
    any_marker = bool(field_nodes or any(slot_nodes.values()))
    if not any_marker:
        return "absent", None
    if (len(field_nodes) != 1 or "edittext" not in field_nodes[0].attrib.get("class", "").lower()
            or any(len(nodes) != 1 or "textview" not in nodes[0].attrib.get("class", "").lower()
                   for nodes in slot_nodes.values())):
        return "invalid", None
    parents = {child: parent for parent in root.iter() for child in parent}
    siblings = [field_nodes[0], *(nodes[0] for nodes in slot_nodes.values())]
    if len({parents.get(node) for node in siblings}) != 1 or parents.get(siblings[0]) is None:
        return "invalid", None
    return "confirmed", field_nodes[0]

def result_after_login(root, report, package):
    markers = known_screen_markers(root, package)
    report["known_screen_markers"] = markers
    if markers["phone_form_visible"] or markers["otp_form_visible"]:
        return False
    if (markers["profile_container_visible"] and markers["profile_edit_marker_visible"]
            and markers["me_tab_visible"]):
        report["logged_in"] = True
        report["matched_prompt_keywords"] = ["Edit profile"]
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
    start_epoch = time.time()
    deadline, submitted_deadline = time.monotonic() + 75, 0
    me_tapped = False
    otp_field_id = otp_field_bounds = ""
    while time.monotonic() < deadline:
        root, timed = adb.ui()
        if root is None:
            if timed: report["timeout"], report["result_category"] = True, "timeout"; break
            time.sleep(1); continue
        if not ui.package_visible(root, args.package):
            report["result_category"] = "foreign_ui"
            break
        markers = known_screen_markers(root, args.package)
        report["known_screen_markers"] = markers
        if markers["profile_container_visible"]:
            report["me_opened"] = True
        texts = ui.ui_text(root, args.package)
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
        otp_form = otp_form_active(root, args.package)
        global_state, global_field = global_otp_form(root, args.package)
        if global_state == "invalid":
            report["result_category"] = "unsupported_ui"
            break
        if report["otp_entered"]:
            identity_fields = ui.fields(root, (), otp_field_id, otp_field_bounds, args.package)
            field = identity_fields[0] if len(identity_fields) == 1 else None
        else:
            semantic_fields = ui.fields(root, ui.OTP_HINTS, package=args.package)
            if global_state == "confirmed":
                field = global_field
            elif otp_text and len(semantic_fields) == 1:
                field = semantic_fields[0]
            else:
                field = None
        report["otp_input_visible"] = field is not None
        if not report["otp_entered"]:
            if otp_form and field is None:
                report["matched_prompt_keywords"] = otp_text[:3]
                break
            if not otp_form:
                time.sleep(1); continue
            current = ui.norm(field.attrib.get("text", ""))
            if current and (re.search(r"\d", current) or not any(h in current for h in ui.OTP_HINTS)):
                break
            report["otp_page_confirmed"] = True
            report["matched_prompt_keywords"] = otp_text[:3] or ["verified six-slot code form"]
            otp_field_id = field.attrib.get("resource-id", "").strip()
            otp_field_bounds = field.attrib.get("bounds", "")
            target = ui.clickable(root, field, args.package)
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
        if result_after_login(root, report, args.package): break
        if otp_form and not report["verify_clicked"]:
            clicked, label, count = ui.action(adb, root, VERIFY, package=args.package)
            if count > 1: break
            if clicked:
                report["verify_clicked"] = True
                report["matched_prompt_keywords"] = [label]
                continue
        # A disappearing OTP field indicates an automatic submit; only then visit Me.
        if (field is None and not otp_form and markers["home_feed_visible"]
                and markers["me_tab_visible"] and not me_tapped):
            clicked, count = tap_me_tab(adb, root, args.package)
            label = "Me"
            if count == 0:
                clicked, label, count = ui.action(adb, root, ME, package=args.package)
            if count > 1 or (count == 1 and not clicked): break
            if clicked:
                me_tapped = True
                report["me_tab_tapped"] = True
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
    report["crash_events"] = restart_debug.collect_logcat(adb, start_epoch, args.package)
    snapshot = restart_debug.app_snapshot(adb, args.package)
    report["activity_class"] = snapshot.get("activity_class")
    report["app_pids"] = snapshot.get("pids", [])
    if logcat_has_known_otp_error(adb, start_epoch):
        report["known_screen_markers"]["otp_error_marker_visible"] = True
        if not report["logged_in"] and report["result_category"] not in {
            "environment_unsafe", "security_challenge", "captcha_shown", "foreign_ui",
        }:
            report["result_category"] = "otp_rejected"
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
