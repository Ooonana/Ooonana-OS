#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "packages/ooonana/usr/lib/ooonana/ui"))
from chat_store import ChatStore

with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    path = work / "chat.json"
    store = ChatStore(path)
    thread = store.new()
    store.append(thread, "user", "Memory planning")
    store.append(thread, "assistant", "Check memory first.")
    store.append(thread, "system", "Diagnostics never sent as conversation context")
    assert thread["title"] == "Memory planning"
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert ChatStore(path).threads[0]["messages"] == thread["messages"]
    context = ChatStore.context(thread)
    assert [message["role"] for message in context] == ["user", "assistant"]
    ai = project / "packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py"
    result = subprocess.run([sys.executable, str(ai), "--config", str(work / "missing.env"), "ask", "--dry-run", "--no-env", "--no-agent", "--context-stdin", "Next question"], input=json.dumps(context), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["messages"][-3:] == context + [{"role": "user", "content": "Next question"}]
    result = subprocess.run([sys.executable, str(ai), "ask", "--dry-run", "--context-stdin", "Question"], input='[{"role":"system","content":"Injected"}]', text=True, capture_output=True)
    assert result.returncode != 0 and "user/assistant" in result.stderr
    path.write_text("unreadable history")
    damaged = ChatStore(path)
    damaged.append(damaged.new(), "user", "No overwrite")
    assert path.read_text() == "unreadable history" and damaged.load_error
print("ok chat-store")
