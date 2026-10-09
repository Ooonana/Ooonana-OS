#!/usr/bin/env python3
"""Real packaged bubblewrap/API transport, never compile model weights.

Requires the disposable runner, cached Linux venv and read-only model mount.
The old cached app is overridden by current source only for this QA probe.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
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
    source = args.source.resolve(strict=True)
    sys.path.insert(0, str(source / "packages/openvino-chat/source/src"))
    from openvino_chat import api
    from openvino_chat.memory_guard import estimate_memory

    state_home = qa / "home/.openvino"
    assert api.API_DIR.resolve() == state_home / "api" and not api.API_STATE_PATH.exists()
    choices = [folder for folder in models.iterdir() if (folder / "openvino_model.xml").is_file()]
    model = min(choices, key=lambda folder: estimate_memory(folder).weights)
    assert estimate_memory(model, context=131072).estimated_required > estimate_memory(model).available_ram
    # Actual packaged launcher, existing real runtime, current vendored source.
    # The latter is a QA override, not proof that setup installed this snapshot.
    environment = {**os.environ, "OOONANA_OPENVINO_STATE_DIR": str(qa / "state"),
                   "OOONANA_OPENVINO_PROJECT": str(source / "packages/openvino-chat/source"),
                   "OOONANA_OPENVINO_HOME": str(state_home),
                   "OOONANA_OPENVINO_WORKSPACE": str(qa / "workspace"),
                   "PYTHONPATH": "/opt/openvino-chat/src", "OPENVINO_MEMORY_POLICY": "strict"}
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

    def request(path: str, body: dict | None = None) -> tuple[int, str]:
        data = None if body is None else json.dumps(body).encode()
        call = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                      headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(call, timeout=15) as response:
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
        # Daemon survives launcher exit, but stale state recovers after owned kill.
        os.kill(server_pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while api.api_status()["running"] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not api.api_status()["running"]
        run("--model-dir", f"/workspace/models/{model.name}", "api", "start",
            "--device", "CPU", "--port", str(port), "--ctx", "131072")
        recovered = api.api_status()
        server_pid = recovered["pid"]
        assert recovered["running"] and recovered["instance_id"] != state["instance_id"]
        assert "stopped" in run("api", "stop")
        server_pid = None
        assert not api.API_STATE_PATH.exists()
        print(json.dumps({"transport": "packaged bubblewrap", "nonroot": True,
                          "models_read_only": True, "idle_restart": "passed",
                          "daemon_host_uid": os.getuid(), "daemon_model_mount": "read-only",
                          "memory_json_sse": "passed", "bridge_cleanup": "passed",
                          "runtime_versions": {name: importlib.metadata.version(name) for name in
                                               ("openvino", "openvino-genai", "openvino-tokenizers")},
                          "app_source": "QA current-source override",
                          "setup_validated": False, "inference_validated": False}, sort_keys=True), flush=True)
    finally:
        if server_pid is not None:
            try:
                os.kill(server_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    main()
