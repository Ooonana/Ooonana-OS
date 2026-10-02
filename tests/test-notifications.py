#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
from notification_utils import notification_age, parse_history  # noqa: E402


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
print("ok notifications")
