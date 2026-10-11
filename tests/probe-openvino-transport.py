#!/usr/bin/env python3
"""Real packaged bubblewrap/API transport; bounded inference requires opt-in.

Requires the disposable runner, cached Linux venv and read-only model mount.
Default probe overrides old cached app with source. Opt-in runner installs current
app offline into a disposable venv copy and tests without that override.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import hashlib
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() == 0 or os.environ.get("OOONANA_TRANSPORT_ISOLATED") != "1":
        raise SystemExit("Require disposable Linux nonroot runner")
    qa = args.qa.resolve(strict=True)
    if not qa.is_relative_to(Path("/var/tmp")):
        raise SystemExit("Require disposable QA directory")
    models = qa / "workspace/models"
    assert os.statvfs(models).f_flag & os.ST_RDONLY
    assert (qa / "state/rootfs").is_symlink()
    source = args.source.resolve(strict=True)
    installed_app = os.environ.get("OOONANA_TRANSPORT_INSTALL_APP") == "1"
    if installed_app:
        expected = tomllib.loads((source / "packages/openvino-chat/source/pyproject.toml").read_text())["project"]["version"]
        assert importlib.metadata.version("openvino-chat") == expected
        import openvino_chat
        assert Path(openvino_chat.__file__).resolve().is_relative_to(qa / "venv")
        for line in (source / "packages/openvino-chat/source/requirements-linux-full.lock").read_text().splitlines():
            if line and not line.startswith("#"):
                name, version = line.split(" --hash=", 1)[0].split("==", 1)
                actual = importlib.metadata.version(name)
                assert actual == version, (name, actual, version)
        web = source / "packages/openvino-chat/source/src/openvino_chat/web"
        installed_web = Path(openvino_chat.__file__).parent / "web"
        for resource in web.iterdir():
            if resource.is_file():
                assert hashlib.sha256(resource.read_bytes()).digest() == hashlib.sha256(
                    (installed_web / resource.name).read_bytes()).digest(), resource.name
    else:
        sys.path.insert(0, str(source / "packages/openvino-chat/source/src"))
    from openvino_chat import api
    from openvino_chat.memory_guard import estimate_memory, memory_snapshot

    state_home = qa / "home/.openvino"
    assert api.API_DIR.resolve() == state_home / "api" and not api.API_STATE_PATH.exists()
    choices = [folder for folder in models.iterdir() if (folder / "openvino_model.xml").is_file()]
    model = min(choices, key=lambda folder: estimate_memory(folder).weights)
    inference = os.environ.get("OOONANA_TRANSPORT_INFERENCE") == "1"
    if inference:
        assert installed_app, "Inference requires current installed app"
        total, available, _ = memory_snapshot()
        assert 0 < total <= 1280 * 1024 * 1024, "Require cgroup memory cap <= 1280 MiB"
        estimate = estimate_memory(model, context=512)
        assert 0 < estimate.weights <= 256 * 1024 * 1024, "Require small disposable QA model"
        assert estimate.estimated_required < available, estimate.message()
    assert estimate_memory(model, context=131072).estimated_required > estimate_memory(model).available_ram
    # Actual packaged launcher, existing real runtime, current vendored source.
    # The latter is a QA override, not proof that setup installed this snapshot.
    environment = {**os.environ, "OOONANA_OPENVINO_STATE_DIR": str(qa / "state"),
                   "OOONANA_OPENVINO_PROJECT": str(source / "packages/openvino-chat/source"),
                   "OOONANA_OPENVINO_HOME": str(state_home),
                   "OOONANA_OPENVINO_WORKSPACE": str(qa / "workspace"),
                   "OPENVINO_MEMORY_POLICY": "strict"}
    environment.pop("PYTHONPATH", None)
    if not installed_app:
        environment["PYTHONPATH"] = "/opt/openvino-chat/src"
    launcher = source / "packages/openvino-chat/rootfs/usr/bin/openvino"

    def run(*arguments: str) -> str:
        call = subprocess.run(["sh", str(launcher), *arguments], env=environment,
                              text=True, capture_output=True, timeout=30)
        if call.returncode:
            raise RuntimeError(f"Launcher {arguments} failed: {call.stdout}\n{call.stderr}")
        assert not list((qa / "home/.cache/ooonana-openvino").glob(".gui-bridge.*"))
        return call.stdout

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    def request(path: str, body: dict | None = None, *, timeout: float = 15) -> tuple[int, str]:
        data = None if body is None else json.dumps(body).encode()
        call = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                      headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(call, timeout=timeout) as response:
                return response.status, response.read(1024 * 1024).decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read(1024 * 1024).decode()

    server_pid = None
    try:
        run("--model-dir", f"/workspace/models/{model.name}", "api", "start",
            "--device", "CPU", "--port", str(port), "--ctx", "131072")
        state = api.api_status()
        assert state["running"] and not state["loaded"]
        server_pid = state["pid"]
        mount_rows = [line.split() for line in Path(f"/proc/{server_pid}/mountinfo").read_text().splitlines()]
        assert any(row[4] == "/workspace/models" and "ro" in row[5].split(",") for row in mount_rows)
        uid_row = next(line for line in Path(f"/proc/{server_pid}/status").read_text().splitlines()
                       if line.startswith("Uid:"))
        assert all(int(value) == os.getuid() for value in uid_row.split()[1:])
        assert "running" in run("api", "status")
        status, body = request("/health")
        assert status == 200 and not json.loads(body)["loaded"]
        for stream in (False, True):
            status, body = request("/v1/completions", {
                "prompt": "Hello", "max_tokens": 1, "knowledge_mode": "offline", "stream": stream,
            })
            assert "insufficient_memory" in body and status == (200 if stream else 503)
            if stream:
                assert "data: [DONE]" in body
        inference_result = {}
        context = "131072"
        if inference:
            assert "stopped" in run("api", "stop")
            server_pid = None
            context = "512"
            run("--model-dir", f"/workspace/models/{model.name}", "api", "start",
                "--device", "CPU", "--port", str(port), "--ctx", context)
            state = api.api_status()
            server_pid = state["pid"]
            started = time.monotonic()
            status, body = request("/v1/completions", {
                "prompt": "The capital of France is", "max_tokens": 12,
                "knowledge_mode": "offline", "duck": False, "temperature": 0,
            }, timeout=120)
            completed = json.loads(body)
            assert status == 200 and completed["choices"][0]["text"].strip(), body
            assert completed["usage"]["completion_tokens"] > 0
            assert api.api_status()["loaded"]
            load_and_infer = time.monotonic() - started
            print(f"CPU_LOADED_AND_INFERRED seconds={load_and_infer:.3f}", flush=True)
            status, body = request("/v1/completions", {
                "prompt": "Count from one to ten:", "max_tokens": 20, "stream": True,
                "knowledge_mode": "offline", "duck": False, "temperature": 0,
            }, timeout=30)
            chunks = [json.loads(line[6:]) for line in body.splitlines()
                      if line.startswith("data: ") and line != "data: [DONE]"]
            assert status == 200 and "data: [DONE]" in body and "\"error\"" not in body
            assert any(chunk["choices"][0]["text"] for chunk in chunks), body
            print("CPU_SSE_GENERATED", flush=True)
            # Real SSE cancellation: abort socket after first generated text.
            # Next request must finish promptly on the same loaded engine.
            cancel_seconds = {}
            for endpoint in ("/v1/completions", "/v1/chat/completions"):
                cancel_body = {
                    "prompt": "List every integer from 1 to 500 with explanations:",
                    "messages": [{"role": "user", "content": "List integers from 1 to 500 with explanations:"}],
                    "max_tokens": 480, "stream": True, "temperature": 0,
                    "knowledge_mode": "offline", "duck": False,
                    "reasoning_effort": "off", "auto_compact": False,
                }
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                try:
                    connection.request("POST", endpoint, json.dumps(cancel_body),
                                       headers={"Content-Type": "application/json"})
                    stream_socket = connection.sock
                    assert stream_socket is not None
                    response = connection.getresponse()
                    assert response.status == 200
                    for _ in range(100):
                        line = response.readline().decode()
                        assert line and line.strip() != "data: [DONE]", "No generated cancellation token"
                        if line.startswith("data: "):
                            event = json.loads(line[6:])
                            assert "error" not in event, event
                            choice = event["choices"][0]
                            if choice.get("text") or choice.get("delta", {}).get("content"):
                                break
                    else:
                        raise AssertionError("No generated cancellation token")
                    stream_socket.shutdown(socket.SHUT_RDWR)
                    response.close()
                finally:
                    connection.close()
                cancelled = time.monotonic()
                cancel_body.update(prompt="Hello", messages=[{"role": "user", "content": "Hello"}],
                                   max_tokens=3, stream=False)
                status, body = request(endpoint, cancel_body, timeout=15)
                completed = json.loads(body)
                assert status == 200, body
                choice = completed["choices"][0]
                assert (choice.get("text") or choice.get("message", {}).get("content", "")).strip(), body
                assert api.api_status()["pid"] == server_pid and api.api_status()["loaded"]
                cancel_seconds[endpoint] = round(time.monotonic() - cancelled, 3)
            inference_result = {"model": model.name, "load_and_inference_seconds": round(load_and_infer, 3),
                                "cpu_inference": "passed", "real_sse": "passed",
                                "disconnect_cancel_reuse_seconds": cancel_seconds}
        # Daemon survives launcher exit, but stale state recovers after owned kill.
        os.kill(server_pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while api.api_status()["running"] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not api.api_status()["running"]
        run("--model-dir", f"/workspace/models/{model.name}", "api", "start",
            "--device", "CPU", "--port", str(port), "--ctx", context)
        recovered = api.api_status()
        server_pid = recovered["pid"]
        assert recovered["running"] and recovered["instance_id"] != state["instance_id"]
        if inference:
            status, body = request("/v1/completions", {
                "prompt": "Hello again", "max_tokens": 3, "temperature": 0,
                "knowledge_mode": "offline", "duck": False,
            }, timeout=120)
            assert status == 200 and json.loads(body)["choices"][0]["text"].strip(), body
            assert api.api_status()["loaded"]
            inference_result["loaded_engine_restart"] = "passed"
        assert "stopped" in run("api", "stop")
        server_pid = None
        assert not api.API_STATE_PATH.exists()
        print(json.dumps({"transport": "packaged bubblewrap", "nonroot": True,
                          "models_read_only": True, "idle_restart": "passed",
                          "daemon_host_uid": os.getuid(), "daemon_model_mount": "read-only",
                          "memory_json_sse": "passed", "bridge_cleanup": "passed",
                          "runtime_versions": {name: importlib.metadata.version(name) for name in
                                               ("openvino", "openvino-genai", "openvino-tokenizers")},
                          "app_source": "offline installed app" if installed_app else "QA current-source override",
                          "app_version": importlib.metadata.version("openvino-chat"),
                          "app_install_validated": installed_app,
                          "pinned_dependencies_validated": installed_app,
                          "installed_web_assets_validated": installed_app,
                          "generation_pointer": "passed",
                          "setup_validated": False, "inference_validated": inference,
                          "inference": inference_result}, sort_keys=True), flush=True)
    finally:
        if server_pid is not None:
            try:
                os.kill(server_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    main()
