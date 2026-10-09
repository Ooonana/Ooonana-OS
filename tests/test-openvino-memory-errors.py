#!/usr/bin/env python3
"""Memory failure wire format and GPU-to-CPU fallback; no model allocations."""
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/openvino-chat/source/src"))
from openvino_chat import api, engine
from openvino_chat.memory_guard import MIB, MemoryEstimate


class Runtime:
    model_id = "fixture"
    loaded = False
    active_device = "CPU"
    failure = MemoryError("Physical RAM available 128 MiB; choose smaller INT4 model")

    def complete(self, body, on_token=None):
        raise self.failure

    chat = complete


runtime = Runtime()
server = api.OpenVinoApiServer(("127.0.0.1", 0), runtime)
worker = threading.Thread(target=server.serve_forever, daemon=True)
worker.start()
base = f"http://127.0.0.1:{server.server_port}"


def request(endpoint, body=None):
    data = None if body is None else json.dumps(body).encode()
    call = urllib.request.Request(base + endpoint, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(call, timeout=3) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


try:
    for endpoint in ("/v1/completions", "/v1/chat/completions"):
        status, body = request(endpoint, {"prompt": "hello", "messages": [], "stream": False})
        assert status == 503
        error = json.loads(body)["error"]
        assert error["type"] == error["code"] == "insufficient_memory"
        assert "Physical RAM available" in error["message"]
        status, body = request(endpoint, {"prompt": "hello", "messages": [], "stream": True})
        assert status == 200  # Streaming headers already sent.
        events = [line[6:] for line in body.splitlines() if line.startswith("data: ")]
        errors = [json.loads(value)["error"] for value in events
                  if value != "[DONE]" and "error" in json.loads(value)]
        assert errors[0]["type"] == errors[0]["code"] == "insufficient_memory"
        assert events[-1] == "[DONE]" and "server_error" not in body
        status, body = request("/health")
        assert status == 200 and json.loads(body)["loaded"] is False
    for failure, expected, kind in ((ValueError("bad input"), 400, "invalid_request_error"),
                                    (RuntimeError("unrelated failure"), 500, "server_error")):
        runtime.failure = failure
        status, body = request("/v1/completions", {"prompt": "hello"})
        assert status == expected and json.loads(body)["error"]["type"] == kind
finally:
    server.shutdown()
    server.server_close()
    worker.join(timeout=3)
    assert not worker.is_alive()

report = MemoryEstimate(8 * 1024 * MIB, 2 * 1024 * MIB, 0, 3 * 1024 * MIB,
                        256 * MIB, 512 * MIB, 4096, 512)
calls = []


def failed_cpu(model, device, **properties):
    calls.append(device)
    raise RuntimeError("GPU missing" if device == "GPU" else "std::bad_alloc")


with patch.object(engine, "preflight_model", return_value=report):
    try:
        engine.load_engine(Path("/fixture"), pipeline_cls=failed_cpu)
        raise AssertionError("Fallback allocation failure did not propagate")
    except MemoryError as failure:
        assert isinstance(failure.__cause__, RuntimeError)
        assert "OpenVINO allocation failed" in str(failure)
        assert "Physical RAM available" in str(failure)
    assert calls == ["GPU", "CPU"]
    calls.clear()

    def failed_gpu(model, device, **properties):
        calls.append(device)
        raise MemoryError("allocation failed")

    try:
        engine.load_engine(Path("/fixture"), pipeline_cls=failed_gpu)
        raise AssertionError("First allocation failure did not propagate")
    except MemoryError:
        pass
    assert calls == ["GPU"]  # Never retry weights after out-of-memory.
    calls.clear()

    def unsupported_cpu(model, device, **properties):
        calls.append(device)
        raise RuntimeError("unsupported layer")

    try:
        engine.load_engine(Path("/fixture"), pipeline_cls=unsupported_cpu)
        raise AssertionError("Unsupported model unexpectedly loaded")
    except RuntimeError as failure:
        assert not isinstance(failure, MemoryError) and str(failure) == "unsupported layer"
    assert calls == ["GPU", "CPU"]

class GenerationPipeline:
    def __init__(self, failures):
        self.failures = iter(failures)
        self.calls = 0

    def generate(self, inputs, **kwargs):
        self.calls += 1
        failure = next(self.failures)
        if failure is not None:
            raise failure
        return "recovered"


for failure in (MemoryError("allocation failed"), RuntimeError("std::bad_alloc"),
                RuntimeError("cl_out_of_resources"),
                RuntimeError("grammar parser error: out of memory")):
    pipeline = GenerationPipeline([failure, None])
    chat_engine = engine.OpenVinoChatEngine(pipeline, "CPU")
    try:
        chat_engine._generate_input("hello", prompt_text="hello", max_new_tokens=4,
                                    structured_output_config=object())
        raise AssertionError("Generation OOM did not propagate")
    except MemoryError as error:
        assert error.__cause__ is failure
        assert "Reduce context/output length" in str(error)
    assert pipeline.calls == 1  # OOM must not trigger grammar retry.
    assert chat_engine.generate("hello", max_new_tokens=4) == "recovered"

pipeline = GenerationPipeline([RuntimeError("grammar parser error"), RuntimeError("std::bad_alloc")])
chat_engine = engine.OpenVinoChatEngine(pipeline, "CPU")
try:
    chat_engine._generate_input("hello", prompt_text="hello", max_new_tokens=4,
                                structured_output_config=object())
    raise AssertionError("Retry OOM did not propagate")
except MemoryError:
    pass
assert pipeline.calls == 2

pipeline = GenerationPipeline([RuntimeError("unsupported layer")])
try:
    engine.OpenVinoChatEngine(pipeline, "CPU").generate("hello", max_new_tokens=4)
    raise AssertionError("Unrelated generation error swallowed")
except RuntimeError as error:
    assert str(error) == "unsupported layer" and not isinstance(error, MemoryError)

print("ok openvino-memory-errors: JSON/SSE, healthy server, CPU fallback, generation/fallback OOM, no OOM retry")
