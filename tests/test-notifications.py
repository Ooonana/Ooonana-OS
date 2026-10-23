#!/usr/bin/env python3
import json
from pathlib import Path
import sys
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
from notification_utils import notification_age, parse_history  # noqa: E402
import notification_utils


def field(value, kind="s"):
    return {"type": kind, "data": value}


record = {
    "id": field(12, "i"), "timestamp": field(1_000_000, "x"),
    "appname": field("Desktop test"), "summary": field("<b>Ready</b>"),
    "body": field("Saved &amp; safe. %{A1:untrusted:}"),
}
parsed = parse_history(json.dumps({"type": "aa{sv}", "data": [[record, record]]}))
assert len(parsed) == 1
assert parsed[0] == {"id": 12, "timestamp": 1_000_000, "app": "Desktop test", "summary": "Ready", "body": "Saved & safe. %{A1:untrusted:}"}
assert parse_history("invalid JSON") == []
assert parse_history(json.dumps({"data": [[{"summary": "Bad", "id": "command"}]]})) == []
assert notification_age(1_000_000, now=1.5) == "Just now"
assert notification_age(1_000_000, now=121) == "2m ago"
assert notification_age(0, now=121) == "Saved"
for value, expected in (("", 0), ("no", 0), ("-1", 0), ("１２", 0), ("0012", 12),
                        ("999", 999), ("1000", 1000), ("9" * 10000, 1000), ("0" * 10000 + "1", 1)):
    assert notification_utils.bounded_badge_count(value) == expected
for count, expected in (("0", ""), ("17", " 34"), ("999", " 999+"), ("9" * 10000, " 999+")):
    def query(command, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="false" if command[1] == "is-paused" else count)
    with patch.object(notification_utils, "read_history", return_value=(0, '{"data": []}')), \
            patch.object(notification_utils, "NotificationState") as state, patch.object(notification_utils.subprocess, "run", side_effect=query):
        state.return_value.unread.return_value = 0
        assert notification_utils.notification_badge() == "%{T2}\uf0f3%{T-}" + expected
print("ok notifications")
