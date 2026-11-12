#!/usr/bin/env python3
"""Real installed-runtime/tokenizer/API probe; never compile heavyweight weights.

Run nonroot in a disposable network/PID namespace with read-only model storage
and a fresh OPENVINO_HOME. No downloads, inference claims, or production state.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    arguments = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() == 0:
        raise SystemExit("Require Linux nonroot disposable probe")
    if os.getpid() != 1 or os.environ.get("OOONANA_OPENVINO_PROBE_ISOLATED") != "1":
        raise SystemExit("Require private network/PID namespace")
    home = Path(os.environ["OPENVINO_HOME"]).resolve()
    if not home.is_relative_to(Path("/var/tmp")) or (home / "api/server.json").exists():
        raise SystemExit("Require fresh disposable OPENVINO_HOME")
    model_root = arguments.model_root.resolve(strict=True)
    if not os.statvfs(model_root).f_flag & os.ST_RDONLY:
        raise SystemExit("Require read-only model filesystem")
    source = Path(__file__).resolve().parents[1] / "packages/openvino-chat/source/src"
    sys.path.insert(0, str(source))
    # API subprocesses must import current vendored source, not an older install.
    os.environ["PYTHONPATH"] = str(source)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["OPENVINO_MEMORY_POLICY"] = "strict"
    for name, relative in {
        "OPENVINO_CHAT_API_DIR": "api", "OPENVINO_CHAT_CONFIG": "config.json",
        "OPENVINO_CHAT_KNOWLEDGE_DIR": "knowledge",
        "OPENVINO_CHAT_KNOWLEDGE_INDEX": "knowledge/index.json",
        "OPENVINO_CHAT_KNOWLEDGE_MODELS": "knowledge/models",
        "OPENVINO_CHAT_REPORT_DIR": "reports", "OPENVINO_CHAT_SESSION_DIR": "sessions",
        "OPENVINO_CHAT_EXPORT_DIR": "exports", "OPENVINO_CHAT_BENCHMARK_PATH": "benchmarks.json",
    }.items():
        os.environ[name] = str(home / relative)
    import openvino
    import openvino_genai
    from openvino_chat import api
    from openvino_chat.memory_guard import estimate_memory, memory_snapshot
    assert api.API_DIR.resolve() == home / "api" and not api.API_STATE_PATH.exists()

    versions = {name: importlib.metadata.version(name) for name in
                ("openvino", "openvino-genai", "openvino-tokenizers")}
    reports = []
    models = []
    snapshot = memory_snapshot()
    for folder in sorted(model_root.iterdir()):
        if not folder.is_dir() or not (folder / "config.json").is_file():
            continue
        if not any((folder / name).is_file() for name in
                   ("openvino_model.xml", "openvino_language_model.xml")):
            continue
        estimate = estimate_memory(folder, snapshot=snapshot)
        reports.append({"model": folder.name, **estimate.report()})
        if (folder / "openvino_model.xml").is_file():
            models.append((estimate.weights, folder))
    if not models:
        raise RuntimeError("No exported text-only model available")
    _, model = min(models)
    tokenizer = openvino_genai.Tokenizer(str(model))
    encoded = tokenizer.encode("Ooonana hello 안녕", add_special_tokens=False)
    token_count = int(encoded.input_ids.shape[-1])
    assert token_count > 0
    decoded = tokenizer.decode(encoded.input_ids)
    assert decoded and "Ooonana" in str(decoded)

    # Force a real strict preflight refusal; no pipeline/weight allocation needed.
    per_token = estimate_memory(model, context=2).estimated_kv // 2
    context = max(131072, snapshot[1] // max(1, per_token) + 8192)
    assert estimate_memory(model, context=context).estimated_required > snapshot[1]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    def request(path: str, body: dict | None = None) -> tuple[int, str]:
        data = None if body is None else json.dumps(body).encode()
        call = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(call, timeout=15) as response:
                return response.status, response.read(1024 * 1024).decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read(1024 * 1024).decode()

    server = api.start_api_process(model, port=port, device="CPU", context_length=context)
    current_pid = server["pid"]
    try:
        status, body = request("/health")
        assert status == 200 and json.loads(body)["loaded"] is False
        status, body = request("/v1/models")
        assert status == 200 and json.loads(body)["data"]
        status, body = request("/v1/completions", {
            "prompt": "Hello", "max_tokens": 1, "knowledge_mode": "offline",
        })
        failure = json.loads(body)["error"]
        assert status == 503 and failure["type"] == "insufficient_memory"
        assert "Physical RAM available" in failure["message"]
        stream_status, stream_body = request("/v1/completions", {
            "prompt": "Hello", "max_tokens": 1, "knowledge_mode": "offline", "stream": True,
        })
        assert stream_status == 200 and '"type": "insufficient_memory"' in stream_body
        assert "data: [DONE]" in stream_body
        assert api.api_status()["loaded"] is False
        # Kill only this probe's daemon; check stale state and new-instance recovery.
        os.kill(current_pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while api.api_status()["running"] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert api.api_status()["running"] is False
        recovered = api.start_api_process(model, port=port, device="CPU", context_length=context)
        current_pid = recovered["pid"]
        assert recovered["instance_id"] != server["instance_id"]
        assert recovered["loaded"] is False
        assert api.stop_api_process()
        current_pid = None
        assert not api.api_status()["running"] and not api.API_STATE_PATH.exists()
        print(json.dumps({
            "versions": versions, "devices": openvino.Core().available_devices,
            "model_memory": reports, "tokenizer_model": model.name,
            "tokenizer_tokens": token_count, "memory_http_status": status,
            "memory_error_type": failure["type"], "api_crash_restart": "passed",
            "nonroot": True, "models_read_only": True, "inference_validated": False,
        }, sort_keys=True), flush=True)
    finally:
        if current_pid is not None:
            try:
                os.kill(current_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    main()
