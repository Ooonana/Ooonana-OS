#!/usr/bin/env python3
"""Serve vendored OpenVINO GUI with fake idle state for visual QA only."""

import sys
import time
from pathlib import Path

from prompt_toolkit.application.current import create_app_session, set_app
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput


source = Path(__file__).resolve().parents[1] / "packages/openvino-chat/source/src"
sys.path.insert(0, str(source))
from openvino_chat import gui, tui  # noqa: E402


with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
    buffer = tui.ChatBuffer()
    buffer.append_user("OpenVINO GUI preview")
    buffer.append("Layout check only. No model loaded.\n")
    ui = tui._TuiInputMediator(lambda: "device: CPU", lambda: "", buffer)
    ui.build_app()
    ui._gui_active = True
    ui._busy.set()
    ui._request_event.set()
    with set_app(ui._app):
        server = gui.GuiServer(ui, idle_timeout=600)
        server.bridge.on_ui = lambda callback: callback()
        server.start(open_browser=False)
        print(server.url, flush=True)
        try:
            time.sleep(180)
        finally:
            server.stop()
