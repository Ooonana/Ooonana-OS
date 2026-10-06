"""Bounded private conversation store. Legacy transcript remains untouched."""
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

MAX_THREADS = 60
MAX_MESSAGES = 120
MAX_CONTENT = 32000


class ChatStore:
    def __init__(self, path):
        self.path = Path(path)
        self.threads = []
        self.load_error = ""
        self._load_failed = False
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                text = stream.read(16 * 1024 * 1024 + 1)
            if len(text) > 16 * 1024 * 1024:
                raise ValueError("saved history exceeds size limit")
            else:
                data = json.loads(text)
                for item in data.get("threads", [])[:MAX_THREADS]:
                    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                        continue
                    messages = []
                    for message in item.get("messages", [])[-MAX_MESSAGES:]:
                        if isinstance(message, dict) and message.get("role") in {"user", "assistant", "system"} and isinstance(message.get("content"), str):
                            messages.append({"role": message["role"], "content": message["content"][:MAX_CONTENT], "heading": str(message.get("heading", ""))[:80]})
                    self.threads.append(dict(id=item["id"][:64], title=str(item.get("title", "New chat"))[:80], updated=float(item.get("updated", 0)), messages=messages))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError, RecursionError) as error:
            self.threads = []
            self.load_error = str(error)
            self._load_failed = True

    def new(self):
        self.threads = [thread for thread in self.threads if thread["messages"]]
        item = dict(id=uuid.uuid4().hex, title="New chat", updated=time.time(), messages=[])
        self.threads.insert(0, item)
        return item

    def append(self, item, role, content, heading=""):
        if item not in self.threads:
            self.threads.append(item)
        item["messages"].append(dict(role=role, content=str(content)[:MAX_CONTENT], heading=heading[:80]))
        item["messages"] = item["messages"][-MAX_MESSAGES:]
        if role == "user" and item["title"] == "New chat":
            item["title"] = " ".join(content.split())[:60] or "New chat"
        item["updated"] = time.time()
        self.save()

    def save(self):
        if self._load_failed:
            return
        try:
            self._save()
            self.load_error = ""
        except (OSError, ValueError, TypeError, RecursionError) as error:
            self.load_error = str(error)

    def _save(self):
        if self._load_failed:
            return  # Preserve unreadable existing file; never silently overwrite.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.threads.sort(key=lambda item: item["updated"], reverse=True)
        self.threads = self.threads[:MAX_THREADS]
        encoded = json.dumps({"version": 1, "threads": self.threads}, ensure_ascii=False)
        while len(encoded.encode("utf-8")) > 8 * 1024 * 1024 and len(self.threads) > 1:
            self.threads.pop()
            encoded = json.dumps({"version": 1, "threads": self.threads}, ensure_ascii=False)
        descriptor, temporary = tempfile.mkstemp(prefix=".chat-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def context(item):
        messages, remaining = [], 60000
        for message in reversed(item["messages"]):
            if message["role"] not in {"user", "assistant"}:
                continue
            size = len(message["content"].encode("utf-8"))
            if size > remaining:
                break
            messages.insert(0, {"role": message["role"], "content": message["content"]})
            remaining -= size + 100
            if len(messages) == 24:
                break
        return messages
