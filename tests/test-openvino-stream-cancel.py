#!/usr/bin/env python3
"""Real HTTP disconnect must stop native-style generation, not throw into it."""
import http.client
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/openvino-chat/source/src"))
from openvino_chat import api


class Engine:
    device = "CPU"
    last_metrics = None
    supported_thinking_efforts = ("off",)
    calls = []

    def format_chat(self, *args, **kwargs):
        return "hello"

    def count_tokens(self, value):
        return len(value.split())

    def generate(self, prompt, on_token=None, should_stop=None, max_new_tokens=1, **kwargs):
        call = {"tokens": 0, "exceptions": 0, "stopped": False}
        self.calls.append(call)
        for _ in range(max_new_tokens):
            call["tokens"] += 1
            if on_token:
                try:
                    on_token("word ")
                except Exception:
                    # Reproduce native runtime swallowing streamer exceptions.
                    call["exceptions"] += 1
            if should_stop and should_stop():
                call["stopped"] = True
                break
            time.sleep(.01)
        return "word " * call["tokens"]


with tempfile.TemporaryDirectory() as temporary:
    engine = Engine()
    runtime = api.ApiRuntime(Path(temporary), device="CPU", context_length=512,
                             knowledge_mode="offline", duck_mode=False,
                             engine_loader=lambda *args, **kwargs: engine)
    server = api.OpenVinoApiServer(("127.0.0.1", 0), runtime)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        for endpoint in ("/v1/completions", "/v1/chat/completions"):
            body = {"prompt": "hello", "messages": [{"role": "user", "content": "hello"}],
                    "knowledge_mode": "offline", "duck": False, "auto_compact": False,
                    "reasoning_effort": "off",
                    "max_tokens": 480, "stream": True}
            client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            client.request("POST", endpoint, json.dumps(body), {"Content-Type": "application/json"})
            stream_socket = client.sock
            response = client.getresponse()
            assert response.status == 200
            received = []
            while True:
                line = response.readline().decode()
                received.append(line)
                assert line and "[DONE]" not in line, received
                if line.startswith("data: ") and "word" in line:
                    break
            stream_socket.shutdown(socket.SHUT_RDWR)
            response.close()
            client.close()
            deadline = time.monotonic() + 2
            call = engine.calls[-1]
            while not call["stopped"] and time.monotonic() < deadline:
                time.sleep(.01)
            assert call["stopped"] and call["tokens"] < 20 and call["exceptions"] == 0, call
            # Same loaded engine and serialization lock remain usable.
            body.update(stream=False, max_tokens=2)
            client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            client.request("POST", endpoint, json.dumps(body), {"Content-Type": "application/json"})
            response = client.getresponse()
            assert response.status == 200, response.read()
            assert json.loads(response.read())["usage"]["completion_tokens"] == 2
            client.close()
            assert runtime.loaded and runtime._engine is engine
        # Explicit stop strings and external cancellation compose.
        assert api._generate(engine, "hello", {"max_tokens": 10, "stop": "word"}, 512) == ""
        assert engine.calls[-1]["tokens"] == 1 and engine.calls[-1]["stopped"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        assert not worker.is_alive()
print("ok openvino-stream-cancel: chat/completion disconnect, stop signals, same-engine reuse")
