from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from openvino_chat.settings import CONFIG_PATH, SESSION_DIR

DEFAULT_SESSION_DIR = SESSION_DIR


class CrashRecoveryStore:
    """Debounced, atomic recovery state kept outside normal session listings."""

    def __init__(self, path: Path | None = None, debounce_seconds: float = 0.4) -> None:
        env_path = os.environ.get("OPENVINO_CHAT_RECOVERY_PATH")
        config_path = Path(os.environ.get("OPENVINO_CHAT_CONFIG", CONFIG_PATH))
        self.path = path or (Path(env_path) if env_path else config_path.parent / "recovery.json")
        self.debounce_seconds = max(0.01, float(debounce_seconds))
        self._lock = threading.Lock()
        self._io_lock = threading.Lock()
        self._revision = 0
        self.last_error: str | None = None
        self._timer: threading.Timer | None = None
        self._pending: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def schedule(self, session: str, draft: str, *, pending: bool = False) -> None:
        payload = self._payload(session, draft, pending)
        with self._lock:
            self._revision += 1
            self._pending = payload
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self.flush, (self._revision,))
            self._timer.daemon = True
            self._timer.start()

    def save_now(self, session: str, draft: str, *, pending: bool = False) -> None:
        with self._lock:
            self._revision += 1
            revision = self._revision
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending = None
        self._commit(revision, self._payload(session, draft, pending))

    def flush(self, revision: int | None = None) -> None:
        with self._lock:
            if revision is not None and revision != self._revision:
                return
            revision = self._revision
            payload = self._pending
            self._pending = None
            if self._timer is not None:
                self._timer.cancel()
            self._timer = None
        if payload is not None:
            self._commit(revision, payload)

    def clear(self) -> None:
        with self._lock:
            self._revision += 1
            revision = self._revision
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending = None
        self._commit(revision, None)

    def _commit(self, revision: int, payload: dict[str, Any] | None) -> None:
        # Serialize disk writes without blocking keystrokes on fsync. A cancelled
        # timer must never resurrect a cleared or superseded recovery record.
        with self._io_lock:
            with self._lock:
                if revision != self._revision:
                    return
            try:
                if payload is None:
                    self.path.unlink(missing_ok=True)
                else:
                    self._write(payload)
                self.last_error = None
            except OSError as exc:
                self.last_error = str(exc)

    @staticmethod
    def _payload(session: str, draft: str, pending: bool) -> dict[str, Any]:
        return {
            "version": 1,
            "session": str(session or "default"),
            "draft": str(draft),
            "pending": bool(pending),
            "pid": os.getpid(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


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
