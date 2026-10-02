#!/usr/bin/env python3
import ast
import os
from pathlib import Path
import stat
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from ui_preferences import config_path, load_preferences, save_preferences, transition_ms
from notification_utils import NotificationState
import notification_utils

with tempfile.TemporaryDirectory() as directory:
    os.environ["XDG_CONFIG_HOME"] = directory + "/config"
    assert load_preferences() == {"reduce_motion": False, "remember_notifications": False}
    assert transition_ms() == 180
    save_preferences(reduce_motion=True)
    assert transition_ms() == 0
    assert stat.S_IMODE(config_path().stat().st_mode) == 0o600
    save_preferences(remember_notifications=True)
    assert load_preferences()["remember_notifications"]
    config_path().write_text('{"reduce_motion":"false"}')
    assert not load_preferences()["reduce_motion"]
    state = NotificationState(Path(directory) / "state")
    message = {"id": 3, "timestamp": 100, "app": "Test", "summary": "Ready", "body": "Plain text"}
    assert state.unread([message]) == 1
    state.mark_read([message])
    assert state.unread([message]) == 0
    changed = {**message, "timestamp": 101}
    assert state.unread([changed]) == 1
    assert state.merge([message], False) == [{**message, "archived": False}]
    assert not state.archive_path.exists()
    assert not state.merge([message], True)[0]["archived"]
    assert stat.S_IMODE(state.archive_path.stat().st_mode) == 0o600
    assert state.merge([], True)[0]["archived"]
    state.forget(message)
    assert not state.merge([], True)
    state.merge([message], True)
    state.clear_saved()
    assert not state.archive_path.exists()
    os.environ["XDG_STATE_HOME"] = str(Path(directory) / "badge-state")
    original_history, original_run = notification_utils.read_history, notification_utils.subprocess.run
    notification_utils.read_history = lambda: (0, '[ [{"id":3,"timestamp":100,"appname":"Test","summary":"Ready","body":"Plain text"}] ]')
    from types import SimpleNamespace
    notification_utils.subprocess.run = lambda command, **_kwargs: SimpleNamespace(returncode=0, stdout="false" if command[1] == "is-paused" else "0")
    assert notification_utils.notification_badge().endswith(" 1")
    notification_utils.NotificationState().mark_read([message])
    assert not notification_utils.notification_badge().endswith(" 1")
    notification_utils.read_history, notification_utils.subprocess.run = original_history, original_run

source = (root / "packages/ooonana/usr/lib/ooonana/ui/ai_app.py").read_text()
method = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "offline_stage_labels")
namespace = {}
exec(compile(ast.Module(body=[method], type_ignores=[]), "offline-stages", "exec"), namespace)
stages = namespace["offline_stage_labels"](True, False, 0, False)
assert stages[0][1] == "Installed" and stages[1][1] == "Setup required"
assert stages[2][1] == "Download required" and stages[3][1] == "Stopped / unverified"
print("ok gui-preferences")
