"""Decode Dunst history without treating notification text as markup or commands."""

import html
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from ui_preferences import read_json, write_json


def read_history():
    # dunstctl history requires systemd's busctl, absent on our BusyBox desktop.
    try:
        from gi.repository import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
            "org.dunstproject.cmd0", "NotificationListHistory", None,
            GLib.VariantType.new("(aa{sv})"), Gio.DBusCallFlags.NONE, 3000, None,
        )
        return 0, json.dumps(result.unpack())
    except Exception as exc:
        return 1, str(exc)


def plain_text(value, limit):
    text = html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))
    return text[:limit]


def parse_history(text):
    if len(text) > 2_000_000:
        return []
    try:
        payload = json.loads(text)
    except (ValueError, TypeError, RecursionError):
        return []

    def unwrap(value, depth=0):
        if depth > 12:
            return None
        if isinstance(value, dict):
            if "type" in value and "data" in value:
                return unwrap(value["data"], depth + 1)
            return {key: unwrap(item, depth + 1) for key, item in value.items()}
        if isinstance(value, list):
            return [unwrap(item, depth + 1) for item in value]
        return value

    records = []
    seen = set()

    def collect(value):
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict) and "summary" in value:
            try:
                identifier = int(value.get("id", 0))
                timestamp = max(0, int(value.get("timestamp", 0)))
            except (ValueError, TypeError):
                return
            if identifier <= 0 or identifier in seen:
                return
            seen.add(identifier)
            records.append({
                "id": identifier, "timestamp": timestamp,
                "app": plain_text(value.get("appname"), 128) or "Desktop app",
                "summary": plain_text(value.get("summary"), 256) or "Notification",
                "body": plain_text(value.get("body"), 4096),
            })
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)

    collect(unwrap(payload))
    return sorted(records, key=lambda record: record["timestamp"], reverse=True)[:80]


def notification_age(timestamp, now=None):
    if timestamp <= 0:
        return "Saved"
    seconds = max(0, int((time.monotonic() if now is None else now) - timestamp / 1_000_000))
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"


def record_key(record):
    value = [record.get(key, "") for key in ("id", "timestamp", "app", "summary", "body")]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode("utf-8")).hexdigest()


class NotificationState:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "ooonana"
        self.seen_path = self.directory / "notification-read.json"
        self.archive_path = self.directory / "notification-history.json"

    def seen(self):
        values = read_json(self.seen_path, [])
        return set(value for value in values[:500] if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)) if isinstance(values, list) else set()

    def mark_read(self, records):
        keys = [record_key(record) for record in records]
        write_json(self.seen_path, list(dict.fromkeys(keys + sorted(self.seen())))[:500])

    def unread(self, records):
        seen = self.seen()
        return sum(record_key(record) not in seen for record in records)

    def archive(self):
        values = read_json(self.archive_path, [])
        if not isinstance(values, list):
            return []
        result = []
        for value in values[:80]:
            if not isinstance(value, dict):
                continue
            if not isinstance(value.get("id"), int) or value["id"] <= 0 or not isinstance(value.get("timestamp"), int):
                continue
            if not all(isinstance(value.get(key), str) for key in ("app", "summary", "body")):
                continue
            result.append({"id": value["id"], "timestamp": value["timestamp"], "app": value["app"][:128], "summary": value["summary"][:256], "body": value["body"][:4096]})
        return result

    def merge(self, live, remember):
        live = live[:80]
        if not remember:
            return [{**record, "archived": False} for record in live]
        keys = {record_key(record) for record in live}
        previous = [record for record in self.archive() if record_key(record) not in keys]
        merged = (live + previous)[:80]
        write_json(self.archive_path, merged)
        return [{**record, "archived": record_key(record) not in keys} for record in merged]

    def forget(self, record):
        key = record_key(record)
        write_json(self.archive_path, [item for item in self.archive() if record_key(item) != key])

    def clear_saved(self):
        self.archive_path.unlink(missing_ok=True)


def notification_badge():
    def query(*arguments):
        try:
            result = subprocess.run(["dunstctl", *arguments], text=True, capture_output=True, timeout=2)
            return result.stdout.strip() if result.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    if query("is-paused") == "true":
        return "%{T2}\uf1f6%{T-} DND"
    rc, history = read_history()
    if rc != 0:
        return "%{T2}\uf0f3%{T-} --"
    count = NotificationState().unread(parse_history(history))
    for queue in ("displayed", "waiting"):
        value = query("count", queue)
        if value.isdigit():
            count += min(999, int(value))
    return "%{T2}\uf0f3%{T-}" + (f" {min(count, 999)}" if count else "")


if __name__ == "__main__":
    import sys
    if "--badge" in sys.argv:
        print(notification_badge())
        raise SystemExit(0)
    rc, text = read_history()
    print(text)
    raise SystemExit(rc)
