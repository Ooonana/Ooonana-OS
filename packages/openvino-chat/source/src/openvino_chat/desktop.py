from __future__ import annotations

import json
import os
import sys
import threading
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


def launch_url(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.username or parsed.password:
        raise ValueError("Desktop GUI requires authenticated loopback URL")
    if parsed.path not in {"/duck.html", "/openvino.html"}:
        raise ValueError("Unknown desktop entry point")
    token = parse_qs(parsed.fragment).get("token", [""])[0]
    if len(token) < 32:
        raise ValueError("GUI token missing")
    return f"http://127.0.0.1:{parsed.port}", token


def main() -> int:
    url = sys.stdin.readline(4096).strip()
    origin, token = launch_url(url)
    import webview

    webview.settings["ALLOW_DOWNLOADS"] = False
    window = webview.create_window("OpenVINO / Quack", url, width=1180, height=840,
                                   min_size=(680, 560), text_select=True, maximized=True,
                                   background_color="#101112")
    closed = threading.Event()

    def return_to_terminal(*_args):
        closed.set()
        print("OPENVINO_GUI_CLOSED", file=sys.stderr, flush=True)
        try:
            request = Request(origin + "/action", data=b'{"action":"frontend","mode":"tui"}',
                              headers={"X-OpenVINO-Token": token, "Content-Type": "application/json"})
            with urlopen(request, timeout=2):
                pass
        except OSError:
            pass

    window.events.closed += return_to_terminal

    def watch():
        permission_was_open = False
        while not closed.wait(1):
            try:
                request = Request(origin + "/health", headers={"X-OpenVINO-Token": token})
                with urlopen(request, timeout=3) as response:
                    state = json.load(response)
                permission_open = bool(state.get("permission_pending"))
                if permission_open != permission_was_open:
                    window.set_title("OpenVINO / Quack - Approval needed" if permission_open else "OpenVINO / Quack")
                permission_was_open = permission_open
                if state["mode"] == "tui":
                    window.destroy()
                    return
            except (OSError, ValueError):
                # A missed heartbeat is not an explicit request to close the GUI.
                continue

    webview.start(watch, gui="edgechromium" if os.name == "nt" else None, debug=False, private_mode=True)
    closed.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
