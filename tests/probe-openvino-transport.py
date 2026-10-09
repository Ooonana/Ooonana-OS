#!/usr/bin/env python3
"""Real packaged bubblewrap/API transport, never compile model weights.

Requires the disposable runner, cached Linux venv and read-only model mount.
Default probe overrides old cached app with source. Opt-in runner installs current
app offline into a disposable venv copy and tests without that override.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import hashlib
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
                          "app_source": "offline installed app" if installed_app else "QA current-source override",
                          "app_version": importlib.metadata.version("openvino-chat"),
                          "app_install_validated": installed_app,
                          "pinned_dependencies_validated": installed_app,
                          "installed_web_assets_validated": installed_app,
                          "generation_pointer": "passed",
                          "setup_validated": False, "inference_validated": False}, sort_keys=True), flush=True)
    finally:
        if server_pid is not None:
            try:
                os.kill(server_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    main()
