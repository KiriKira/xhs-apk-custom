#!/usr/bin/env python3
"""Reproduce REDnote home-feed refresh/card navigation failures safely."""

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rednote_phone_test as ui
import rednote_private_input as private_input

HOME_TAB_ID = ":id/index_home"
ME_TAB_ID = ":id/index_me"
PROFILE_PAGE_ID = ":id/matrix_profile_new_page_container_layout"
FEED_ID = ":id/mLoadMoreRecycleView"
REFRESH_ID = ":id/exploreSwipeRefreshLayout"
CARD_ID = ":id/card_view"
DETAIL_VIEW_IDS = (":id/detail_feed_middle_area", ":id/detail_feed_nice_video_list")
DETAIL_ACTIVITY_NAMES = (
    "com.xingin.matrix.notedetail.NoteDetailActivity",
    "com.xingin.matrix.detail.activity.DetailFeedActivity",
    "com.xingin.detailpage.videonote.page.MediumVideoPageActivity",
)
SERIAL_RE = re.compile(r"[A-Za-z0-9._:-]+\Z")
COMPONENT_RE = re.compile(r"\{([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)\}")
FRAME_RE = re.compile(
    r"^\s*at\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\."
    r"([A-Za-z_$<>][\w$<>]*)\(([^():\s]+|Native Method|Unknown Source|Compiled Code)"
    r"(?::(\d+))?\)\s*$"
)
EXCEPTION_RE = re.compile(
    r"(?<![\w$])([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*"
    r"(?:Exception|Error|Throwable))(?=[:\s])"
)


def report_template(run_id, package, result_suffix="restart-debug"):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "package": package,
        "result_suffix": result_suffix,
        "attempts": [],
        "published": False,
        "result_category": "unsupported_ui",
    }


def own_nodes(root, package):
    return [n for n in root.iter() if ui.visible(n) and n.attrib.get("package") == package]


def resource_nodes(root, package, suffix):
    return [n for n in own_nodes(root, package)
            if n.attrib.get("resource-id", "").endswith(suffix)]


def parse_bounds(value):
    match = ui.BOUNDS.fullmatch(value or "")
    return tuple(map(int, match.groups())) if match else None


def descendants_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def is_descendant(node, ancestor, parents):
    current = node
    while current is not None:
        if current is ancestor:
            return True
        current = parents.get(current)
    return False


def tap_unique_resource(adb, root, package, suffix):
    nodes = resource_nodes(root, package, suffix)
    if len(nodes) != 1:
        return False, len(nodes)
    target = ui.clickable(root, nodes[0], package)
    if target is None:
        return False, 0
    return adb.tap(target.attrib.get("bounds")), 1


def feed_node(root, package):
    matches = resource_nodes(root, package, FEED_ID)
    if len(matches) == 1 and parse_bounds(matches[0].attrib.get("bounds")):
        return matches[0]
    return None


def safe_card(root, package, feed):
    parents = descendants_map(root)
    feed_bounds = parse_bounds(feed.attrib.get("bounds"))
    if not feed_bounds:
        return None, None
    _, feed_top, _, feed_bottom = feed_bounds
    candidates = []
    for node in resource_nodes(root, package, CARD_ID):
        if "cardview" not in node.attrib.get("class", "").lower():
            continue
        if not is_descendant(node, feed, parents):
            continue
        bounds = parse_bounds(node.attrib.get("bounds"))
        if not bounds or bounds[1] < feed_top or bounds[3] > feed_bottom:
            continue
        target = ui.clickable(root, node, package)
        if target is None or target is feed or not is_descendant(target, feed, parents):
            continue
        target_id = target.attrib.get("resource-id", "")
        if re.search(r"(?:like|collect|comment|share|follow|publish|post)$", target_id, re.I):
            continue
        candidates.append((bounds[1], bounds[0], node, target))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, card, target = candidates[0]
    return card, target


def component_from_text(text, package):
    match = COMPONENT_RE.search(text or "")
    if not match:
        match = re.search(r"\bcmp=([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)", text or "")
    if not match:
        return None
    component_package, class_name = match.groups()
    if not re.fullmatch(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*", component_package):
        return None
    if not re.fullmatch(r"(?:\.)?[A-Za-z_$][A-Za-z0-9_.$]*", class_name):
        return None
    return {"package": component_package, "class": class_name}


def _activity_class(adb, package):
    ok, raw, _ = adb.run("shell", "dumpsys", "activity", "activities", timeout=15)
    if not ok:
        return None
    text = raw.decode("utf-8", errors="ignore")
    package_re = re.escape(package)
    component = re.compile(package_re + r"/([A-Za-z0-9_.$]+)")
    lines = text.splitlines()
    priority = ("topresumedactivity", "mresumedactivity", "resumedactivity", "mfocusedactivity")
    for marker in priority:
        for line in lines:
            if marker in line.lower():
                match = component.search(line)
                if match:
                    name = match.group(1)
                    return package + name if name.startswith(".") else name
    return None


def app_snapshot(adb, package):
    ok, raw, _ = adb.run("shell", "pidof", package, timeout=8)
    pids = []
    if ok:
        pids = [int(value) for value in raw.decode("ascii", errors="ignore").split()
                if value.isdigit()][:8]
    return {"pids": pids, "activity_class": _activity_class(adb, package)}


def _log_payload(line):
    match = re.search(
        r"\b(AndroidRuntime|System\.err|DEBUG|libc|ActivityManager|ActivityTaskManager)\s*:\s*(.*)$",
        line,
    )
    return match.group(2).strip() if match else None


def _safe_frame(line):
    match = FRAME_RE.match(line)
    if not match:
        return None
    class_name, method, source, line_number = match.groups()
    if not re.fullmatch(r"[A-Za-z0-9_.$]+", class_name):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_$<>]+", method):
        return None
    if source not in ("Native Method", "Unknown Source", "Compiled Code"):
        source = Path(source).name
        if not re.fullmatch(r"[A-Za-z0-9_.$-]+", source):
            return None
    frame = {"class": class_name, "method": method, "source": source}
    if line_number:
        frame["line"] = int(line_number)
    return frame


def parse_logcat(raw_text, since_epoch, target_package):
    messages = []
    for line in raw_text.splitlines():
        first = line.split(" ", 1)[0]
        try:
            timestamp = float(first)
        except ValueError:
            continue
        if timestamp < since_epoch:
            continue
        payload = _log_payload(line)
        if payload is not None:
            messages.append(payload)
    blocks, current = [], None
    for message in messages:
        if "FATAL EXCEPTION" in message:
            if current:
                blocks.append(current)
            current = [message]
        elif current is not None:
            current.append(message)
        elif "ActivityNotFoundException" in message:
            current = [message]
    if current:
        blocks.append(current)

    events, seen = [], set()
    for block in blocks:
        exception_types = []
        frames = []
        component = None
        process_name = None
        for message in block:
            process_match = re.match(r"Process:\s*([A-Za-z0-9_.]+)(?:,\s*PID:\s*\d+)?", message)
            if process_match:
                process_name = process_match.group(1).split(":", 1)[0]
            for found in EXCEPTION_RE.findall(message):
                if found not in exception_types:
                    exception_types.append(found)
            frame = _safe_frame(message)
            if frame and frame not in frames:
                frames.append(frame)
            if "ActivityNotFoundException" in message or "activity class" in message.lower():
                component = component_from_text(message, "") or component
        if process_name and process_name != target_package:
            continue
        if not process_name and target_package not in " ".join(block):
            continue
        if not exception_types and not frames:
            continue
        event = {
            "exception_type": exception_types[0] if exception_types else "unknown",
            "caused_by": exception_types[1:6],
            "java_frames": frames[:12],
        }
        if component:
            event["intent_component"] = component
        fingerprint = json.dumps(event, sort_keys=True, separators=(",", ":"))
        if fingerprint not in seen:
            seen.add(fingerprint)
            events.append(event)

    native_event = None
    native_is_target = False
    for message in messages:
        if ">>>" in message and "<<<" in message:
            native_is_target = target_package in message
        signal_match = re.search(r"Fatal signal\s+(\d+)\s+\((SIG[A-Z0-9]+)\)", message)
        if signal_match:
            if native_event and native_is_target:
                events.append(native_event)
            native_event = {
                "exception_type": "native_crash",
                "signal_number": int(signal_match.group(1)),
                "signal_name": signal_match.group(2),
                "native_frames": [],
            }
            continue
        if native_event is None or not native_is_target:
            continue
        frame_match = re.match(r"\s*#\d+\s+pc\s+([0-9a-fA-F]+)\s+(.+)$", message)
        if not frame_match:
            continue
        offset, image_path = frame_match.groups()
        image_name = Path(image_path.strip().split(" ", 1)[0]).name
        if re.fullmatch(r"lib[A-Za-z0-9_.+-]+\.so", image_name):
            native_event["native_frames"].append({"image": image_name, "pc": offset.lower()})
    if native_event and native_is_target:
        native_event["native_frames"] = native_event["native_frames"][:12]
        events.append(native_event)
    return events[:8]


def collect_logcat(adb, since_epoch, package):
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        return []
    temp_dir = Path(runner_temp)
    temp_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="rednote-restart-logcat-", suffix=".txt", dir=temp_dir)
    os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "wb") as stream:
            subprocess.run(adb.base + ["logcat", "-d", "-b", "crash", "-b", "main", "-b", "system",
                                       "-v", "epoch", "-t", "5000"],
                           stdout=stream, stderr=subprocess.DEVNULL, timeout=20, check=False)
        raw_text = Path(temp_name).read_text(encoding="utf-8", errors="ignore")
        return parse_logcat(raw_text, since_epoch, package)
    except Exception:
        return []
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def merge_events(destination, events):
    seen = {json.dumps(event, sort_keys=True, separators=(",", ":")) for event in destination}
    for event in events:
        fingerprint = json.dumps(event, sort_keys=True, separators=(",", ":"))
        if fingerprint not in seen:
            destination.append(event)
            seen.add(fingerprint)


def wait_for_feed(adb, package, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root, timed = adb.ui()
        if root is not None:
            if not ui.package_visible(root, package):
                return None, "foreign_ui"
            feed = feed_node(root, package)
            if feed is not None:
                return root, None
        elif timed:
            return None, "timeout"
        time.sleep(1)
    return None, "feed_not_visible"


def refresh_feed(adb, root, package):
    refreshes = resource_nodes(root, package, REFRESH_ID)
    feed = feed_node(root, package)
    target = refreshes[0] if len(refreshes) == 1 else feed
    bounds = parse_bounds(target.attrib.get("bounds")) if target is not None else None
    if not bounds:
        return False
    left, top, right, bottom = bounds
    x = (left + right) // 2
    height = max(1, bottom - top)
    y0 = top + min(80, max(20, height // 12))
    y1 = min(bottom - 5, top + max(180, height // 2))
    if y1 <= y0:
        return False
    ok, _, _ = adb.run("shell", "input", "swipe", str(x), str(y0), str(x), str(y1), "650", timeout=12)
    return ok


def feed_status(root, package):
    """Return a fixed status enum; UI copy itself is never stored in the report."""
    texts = ui.ui_text(root, package)
    if any(term in text for text in texts for term in (
        "网络异常", "网络错误", "网络不给力", "网络出错", "连接失败", "服务器开小差",
        "无法连接服务器", "请检查网络", "加载失败", "network error", "unable to connect", "check your connection",
    )):
        return "network_error"
    if any(term in text for text in texts for term in ("重试", "再试一次", "点击重试", "retry", "try again")):
        return "retry"
    if any(term in text for text in texts for term in (
        "暂无内容", "暂时没有内容", "没有更多内容", "no content", "no data", "nothing here",
    )):
        return "empty"
    return "cards_visible" if resource_nodes(root, package, CARD_ID) else "unknown"


def feed_content_digest(root, package, feed):
    """Hash the visible feed's text and resource IDs without retaining or reporting them."""
    parents = descendants_map(root)
    values = []
    for node in own_nodes(root, package):
        if not is_descendant(node, feed, parents):
            continue
        for attr in ("text", "content-desc", "resource-id"):
            value = node.attrib.get(attr, "")
            if value:
                values.append(attr + "=" + value)
    return hashlib.sha256("\n".join(values).encode("utf-8", errors="ignore")).digest()


def detail_screen(root, package, activity_class, home_activity):
    if not ui.package_visible(root, package):
        return False
    if activity_class in DETAIL_ACTIVITY_NAMES:
        return True
    return any(resource_nodes(root, package, suffix) for suffix in DETAIL_VIEW_IDS)


def run_attempt(adb, package, phase_name, initial, report, phase_start, already_logged_in=False):
    attempt = {
        "phase": phase_name,
        "profile_page_visible": False,
        "home_opened": False,
        "feed_visible": False,
        "refresh_performed": False,
        "refresh_observed": False,
        "feed_still_visible_after_refresh": False,
        "feed_content_changed": False,
        "feed_status_recovered": False,
        "card_selected": False,
        "card_clicked": False,
        "card_opened": False,
        "returned_home": False,
        "refresh_resource_id": REFRESH_ID,
        "feed_resource_id": FEED_ID,
        "card_resource_id": CARD_ID,
        "exceptions": [],
    }
    root, timed = adb.ui()
    if not initial:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if root is not None and ui.package_visible(root, package) and (
                feed_node(root, package) is not None
                or resource_nodes(root, package, HOME_TAB_ID)
            ):
                break
            time.sleep(1)
            root, timed = adb.ui()
    if root is None or not ui.package_visible(root, package):
        attempt["result_category"] = "foreign_ui" if root is not None else ("timeout" if timed else "ui_unavailable")
        attempt.update(app_snapshot(adb, package))
        attempt["exceptions"] = collect_logcat(adb, phase_start, package)
        report["attempts"].append(attempt)
        return attempt

    if initial and already_logged_in:
        if feed_node(root, package) is None:
            attempt["result_category"] = "logged_in_feed_not_found"
            attempt.update(app_snapshot(adb, package))
            attempt["exceptions"] = collect_logcat(adb, phase_start, package)
            report["attempts"].append(attempt)
            return attempt
        attempt["home_opened"] = True
    elif initial:
        profiles = resource_nodes(root, package, PROFILE_PAGE_ID)
        attempt["profile_page_visible"] = len(profiles) == 1
        if len(profiles) != 1:
            attempt["result_category"] = "profile_page_not_found"
            attempt.update(app_snapshot(adb, package))
            attempt["exceptions"] = collect_logcat(adb, phase_start, package)
            report["attempts"].append(attempt)
            return attempt
        clicked, count = tap_unique_resource(adb, root, package, HOME_TAB_ID)
        if not clicked:
            attempt["result_category"] = "home_tab_unresolved" if count != 1 else "home_tab_not_clickable"
            attempt.update(app_snapshot(adb, package))
            attempt["exceptions"] = collect_logcat(adb, phase_start, package)
            report["attempts"].append(attempt)
            return attempt
        attempt["home_opened"] = True
    else:
        current_feed = feed_node(root, package)
        if current_feed is not None:
            attempt["home_opened"] = True
        else:
            homes = resource_nodes(root, package, HOME_TAB_ID)
            if len(homes) == 1:
                attempt["home_opened"] = tap_unique_resource(adb, root, package, HOME_TAB_ID)[0]
            if not attempt["home_opened"]:
                attempt["result_category"] = "home_not_available"
                attempt.update(app_snapshot(adb, package))
                attempt["exceptions"] = collect_logcat(adb, phase_start, package)
                report["attempts"].append(attempt)
                return attempt

    time.sleep(1)
    root, error = wait_for_feed(adb, package, timeout=30)
    if root is None:
        attempt["result_category"] = error or "feed_not_visible"
        attempt.update(app_snapshot(adb, package))
        attempt["exceptions"] = collect_logcat(adb, phase_start, package)
        report["attempts"].append(attempt)
        return attempt
    attempt["feed_visible"] = True
    attempt["feed_status_before_refresh"] = feed_status(root, package)
    feed_before = feed_node(root, package)
    digest_before = feed_content_digest(root, package, feed_before) if feed_before is not None else b""
    before = app_snapshot(adb, package)
    attempt["activity_class"] = before["activity_class"]
    attempt["pids"] = before["pids"]

    attempt["refresh_performed"] = refresh_feed(adb, root, package)
    if attempt["refresh_performed"]:
        time.sleep(3)
        after_refresh, error = wait_for_feed(adb, package, timeout=7)
        attempt["feed_still_visible_after_refresh"] = after_refresh is not None
        merge_events(attempt["exceptions"], collect_logcat(adb, phase_start, package))
        if after_refresh is None:
            attempt["result_category"] = error or "feed_lost_after_refresh"
            attempt.update(app_snapshot(adb, package))
            report["attempts"].append(attempt)
            return attempt
        root = after_refresh
        status_after = feed_status(root, package)
        attempt["feed_status_after_refresh"] = status_after
        feed_after = feed_node(root, package)
        digest_after = feed_content_digest(root, package, feed_after) if feed_after is not None else b""
        attempt["feed_content_changed"] = bool(digest_before and digest_after and digest_before != digest_after)
        attempt["feed_status_recovered"] = (
            attempt["feed_status_before_refresh"] in {"network_error", "retry", "empty"}
            and status_after == "cards_visible"
        )
        attempt["refresh_observed"] = attempt["feed_content_changed"] or attempt["feed_status_recovered"]

    feed = feed_node(root, package)
    card, target = safe_card(root, package, feed) if feed is not None else (None, None)
    if card is None or target is None:
        attempt["result_category"] = "feed_card_not_found"
        merge_events(attempt["exceptions"], collect_logcat(adb, phase_start, package))
        report["attempts"].append(attempt)
        return attempt
    attempt["card_selected"] = True
    attempt["card_clicked"] = adb.tap(target.attrib.get("bounds"))
    if not attempt["card_clicked"]:
        attempt["result_category"] = "card_tap_failed"
        merge_events(attempt["exceptions"], collect_logcat(adb, phase_start, package))
        report["attempts"].append(attempt)
        return attempt

    home_activity = before["activity_class"]
    for _ in range(10):
        time.sleep(1)
        current, timed = adb.ui()
        if current is None:
            continue
        if not ui.package_visible(current, package):
            break
        snapshot = app_snapshot(adb, package)
        if detail_screen(current, package, snapshot["activity_class"], home_activity):
            attempt["card_opened"] = True
            attempt["activity_after_card"] = snapshot["activity_class"]
            attempt["pids_after_card"] = snapshot["pids"]
            root = current
            break
        root = current
    merge_events(attempt["exceptions"], collect_logcat(adb, phase_start, package))
    if not attempt["card_opened"]:
        last = app_snapshot(adb, package)
        attempt["activity_after_card"] = last["activity_class"]
        attempt["pids_after_card"] = last["pids"]

    if attempt["card_opened"]:
        adb.run("shell", "input", "keyevent", "4", timeout=8)
        time.sleep(1)
        home_root, _ = wait_for_feed(adb, package, timeout=8)
        attempt["returned_home"] = home_root is not None
    attempt["result_category"] = "card_opened" if attempt["card_opened"] else "card_open_unconfirmed"
    report["attempts"].append(attempt)
    return attempt


def publish_report(report):
    run_id = report["run_id"]
    branch_ref = os.environ.get("GITHUB_REF", "")
    if not run_id.isdigit() or not branch_ref.startswith("refs/heads/"):
        return False
    branch = branch_ref.removeprefix("refs/heads/")
    suffix = report.get("result_suffix", "restart-debug")
    if not re.fullmatch(r"[a-z-]+", suffix):
        return False
    path = f"runtime-control/rednote-{run_id}.{suffix}.json"
    try:
        current = private_input.api("GET", path)
        body = {
            "message": f"Publish sanitized REDnote restart debug report for run {run_id}",
            "content": base64.b64encode(json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode()).decode("ascii"),
            "branch": branch,
        }
        if current and current.get("sha"):
            body["sha"] = current["sha"]
        private_input.api("PUT", path, body)
        return True
    except BaseException:
        return False


def write_report(path, report):
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
    os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        os.replace(temp_name, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def run(args):
    report = report_template(args.run_id, args.package, args.result_suffix)
    if (not args.run_id.isdigit() or not SERIAL_RE.fullmatch(args.serial)
            or not re.fullmatch(r"[a-z-]+", args.result_suffix)):
        report["result_category"] = "invalid_cli_input"
        return report
    adb = ui.Adb(args.serial)
    ok, _, timed = adb.run("get-state", timeout=10)
    if not ok:
        report["result_category"] = "timeout" if timed else "device_unavailable"
        return report

    start = time.time()
    first = run_attempt(adb, args.package, "initial_profile_to_home", True, report, start,
                        already_logged_in=args.already_logged_in)
    report["result_category"] = first.get("result_category", "unsupported_ui")
    for index in range(1, 3):
        if not first.get("home_opened") or not first.get("feed_visible"):
            break
        attempt_start = time.time()
        force_ok, _, force_timed = adb.run("shell", "am", "force-stop", args.package, timeout=15)
        restart_started = False
        launch_error_component = None
        if force_ok:
            time.sleep(1)
            ok, raw, timed = adb.run("shell", "am", "start", "-n",
                                     args.package + "/" + ui.ACTIVITY, timeout=25)
            launch_text = raw.decode("utf-8", errors="ignore")
            restart_started = ok and not ("Error type 3" in launch_text or "Activity class" in launch_text)
            if not restart_started:
                launch_error_component = component_from_text(launch_text, args.package)
            if not restart_started and launch_error_component:
                report["attempts"][-1]["restart_intent_component"] = launch_error_component
        else:
            timed = force_timed
        restart_attempt = run_attempt(adb, args.package, f"restart_{index}", False, report, attempt_start) if restart_started else {
            "phase": f"restart_{index}", "result_category": "restart_launch_failed" if not timed else "timeout",
            "restart_performed": force_ok, "restart_started": False,
            "exceptions": collect_logcat(adb, attempt_start, args.package),
        }
        restart_attempt["restart_performed"] = force_ok
        restart_attempt["restart_started"] = restart_started
        restart_attempt["force_stop_succeeded"] = force_ok
        if launch_error_component:
            restart_attempt["intent_component"] = launch_error_component
        if not restart_started:
            restart_attempt.update(app_snapshot(adb, args.package))
            report["attempts"].append(restart_attempt)
            report["result_category"] = restart_attempt["result_category"]
            break
        first = restart_attempt
        report["result_category"] = first.get("result_category", "unsupported_ui")

    report["published"] = True
    if not publish_report(report):
        report["published"] = False
        if report["result_category"] == "card_opened":
            report["publish_category"] = "api_unavailable"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", required=True, choices=ui.PACKAGES)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID"), required=os.environ.get("GITHUB_RUN_ID") is None)
    parser.add_argument("--already-logged-in", action="store_true",
                        help="accept only an existing app-owned home feed as the starting point")
    parser.add_argument("--result-suffix", default="restart-debug")
    parser.add_argument("--report-file", required=True)
    args = parser.parse_args()
    try:
        report = run(args)
    except BaseException:
        report = report_template(str(args.run_id or ""), args.package, args.result_suffix)
        report["result_category"] = "script_error"
    if not report.get("published") and str(args.run_id or "").isdigit():
        report["published"] = True
        if not publish_report(report):
            report["published"] = False
        else:
            report.pop("publish_category", None)
    try:
        write_report(args.report_file, report)
    except Exception:
        report = report_template(str(args.run_id or ""), args.package, args.result_suffix)
        report["result_category"] = "report_write_failed"
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
