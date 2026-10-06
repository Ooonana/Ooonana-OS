"""Small, user-owned desktop presentation preferences."""

import json
import os
from pathlib import Path
import tempfile

DEFAULTS = {"reduce_motion": False, "remember_notifications": False}


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "ooonana" / "ui.json"


def read_json(path, fallback, limit=1_000_000):
    try:
        with path.open("r", encoding="utf-8") as stream:
            text = stream.read(limit + 1)
        if len(text) > limit:
            return fallback
        return json.loads(text)
    except (OSError, ValueError, TypeError, RecursionError):
        return fallback


def write_json(path, value):
    if read_json(path, None) == value:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_preferences():
    data = read_json(config_path(), {}, limit=4096)
    return {key: data.get(key, default) if isinstance(data, dict) and isinstance(data.get(key), bool) else default for key, default in DEFAULTS.items()}


def save_preferences(**changes):
    data = load_preferences()
    data.update({key: value for key, value in changes.items() if key in DEFAULTS and isinstance(value, bool)})
    write_json(config_path(), data)
    return data


def transition_ms():
    return 0 if load_preferences()["reduce_motion"] else 180
