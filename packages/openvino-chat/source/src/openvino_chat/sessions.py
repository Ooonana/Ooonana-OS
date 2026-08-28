from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from openvino_chat.settings import SESSION_DIR

DEFAULT_SESSION_DIR = SESSION_DIR


class ChatSessionStore:
    def __init__(self, root: Path | None = None) -> None:
        env_root = os.environ.get("OPENVINO_CHAT_SESSION_DIR")
        self.root = root or (Path(env_root) if env_root else DEFAULT_SESSION_DIR)

    def list_sessions(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(path.stem for path in self.root.glob("*.json"))

    def save(
        self,
        name: str,
        history: list[tuple[str, str]],
        metadata: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(name)
        merged_metadata = {
            "title": name,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "message_count": len(history),
        }
        if metadata:
            merged_metadata.update(metadata)
        payload = {
            "metadata": merged_metadata,
            "history": history,
        }
        if state is not None:
            payload["state"] = state
        encoded = json.dumps(payload, ensure_ascii=False, indent=2)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.root,
                prefix=f".{path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    def load(self, name: str) -> list[tuple[str, str]]:
        data = json.loads(self._path(name).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("history")
        if not isinstance(data, list):
            raise ValueError("invalid session history")
        history: list[tuple[str, str]] = []
        for item in data:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError("invalid session history")
            role, content = item
            history.append((str(role), str(content)))
        return history

    def metadata(self, name: str) -> dict[str, Any]:
        data = json.loads(self._path(name).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("metadata"), dict):
            return data["metadata"]
        history = self.load(name)
        return {
            "title": name,
            "message_count": len(history),
        }

    def load_state(self, name: str) -> dict[str, Any]:
        data = json.loads(self._path(name).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("state"), dict):
            return data["state"]
        return {}

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def _path(self, name: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-")
        if not safe:
            raise ValueError("missing session name")
        return self.root / f"{safe}.json"
