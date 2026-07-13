from __future__ import annotations

import argparse
import builtins
import gc
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openvino_chat.agent import TOOL_SYSTEM_PROMPT, ToolChatSession
from openvino_chat.api import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    api_status,
    format_api_status,
    run_api_server,
    start_api_process,
    stop_api_process,
)
from openvino_chat.download import delete_named_model, download_named_model
from openvino_chat.engine import (
    OpenVinoChatEngine,
    load_engine,
    model_name_from_dir,
    normalize_kv_cache_precision,
)
from openvino_chat.perf import estimate_model_memory, format_live_status, format_perf_status, get_cpu_usage, get_gpu_usage, get_ram_usage, human_bytes
from openvino_chat.sessions import ChatSessionStore
from openvino_chat.settings import (
    CONFIG_PATH,
    DEFAULT_MODEL_DIR,
    EXPORT_DIR,
    MODEL_DIRS,
    MODEL_REPOS,
    MODEL_ROOT,
    REPORT_DIR,
    package_install_command,
)
from openvino_chat import tui as tui_mod
from openvino_chat.tasks import TaskList, has_visible_tasks
from openvino_chat.tools import ToolRegistry, parse_slash_tool
from openvino_chat.ui import ChatUI, LiveStatusMonitor, format_tool_request_text, split_thinking, status_label
from openvino_chat.visuals import render_big_text, render_chart, render_tilt_text


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class _BufferChatUI:
    """ChatUI facade that routes output to the persistent TUI ChatBuffer.

    Only constructed when the persistent TUI owns the screen so tests (which
    never set the TUI active) are untouched. ``banner`` and ``response_stream``
    stream into the buffer; print/tool methods route there too.
    """

    def __init__(self, inner, chat_buffer, mediator) -> None:
        self._inner = inner
        self._buffer = chat_buffer
        self._mediator = mediator
        self._invalidate = mediator.invalidate

    def banner(self, *_args, **_kwargs) -> None:
        pass

    def user_prompt(self) -> str:
        return "> "

    def print(self, text="", end="\n") -> None:
        value = str(text)
        if end and not value.endswith(end):
            value = value + end
        if tui_mod._has_terminal_markup(value):
            value = tui_mod._render_terminal_markup(value)
        self._buffer.append(value)
        self._invalidate()

    def print_plain(self, text="", end="\n") -> None:
        value = str(text)
        if end and not value.endswith(end):
            value = value + end
        self._buffer.append(value)
        self._invalidate()

    def response_stream(self):
        return tui_mod.response_stream(self._buffer, self._invalidate)

    def tool_request(self, name, args) -> None:
        self._buffer.append_tool(name, _encode_tool_args(args))
        self._invalidate()

    def tool_result(self, text) -> None:
        value = str(text)
        if tui_mod._has_terminal_markup(value):
            value = tui_mod._render_terminal_markup(value).rstrip("\n")
        self._buffer.append_line(value)
        self._invalidate()

    def status_monitor(self, *_args, **_kwargs):
        return tui_mod.TuiStatusMonitor(self._buffer, self._mediator)


def _encode_tool_args(args):
    import json

    try:
        return json.dumps(args, ensure_ascii=False)
    except Exception:
        return repr(args)


def _build_tui_welcome_text(
    device,
    context_length,
    estimate,
    model_dir,
    loaded,
    kv_cache_precision="auto",
) -> str:
    name = model_name_from_dir(model_dir)
    stars = f"{tui_mod.CYAN}OpenVINO Chat{tui_mod.RESET}"
    meta = (
        f"model {name} | device {device} | loaded {'yes' if loaded else 'no'} | "
        f"ctx {context_length} | kv {kv_cache_precision}"
    )
    hint = f"{tui_mod.DIM}/help /model /api /status /ctx /kv /tools /exit{tui_mod.RESET}"
    return f"{stars}\n{meta}\n{hint}\n"


EngineLoader = Callable[..., OpenVinoChatEngine]
Downloader = Callable[[str, Path | None], Path]
InputFn = Callable[[str], str]


@dataclass(frozen=True)
class CommandSpec:
    group: str
    command: str
    usage: str
    description: str


COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec("Chat", "/help", "/help", "Show help."),
    CommandSpec("Chat", "/commands", "/commands", "Show command palette."),
    CommandSpec("Chat", "/copy", "/copy", "Copy latest assistant response."),
    CommandSpec("Chat", "/raw", "/raw", "Toggle raw transcript display."),
    CommandSpec("Chat", "/rewind", "/rewind", "Restore state before previous command."),
    CommandSpec("Chat", "/reset", "/reset", "Clear current chat memory."),
    CommandSpec("Chat", "/clear", "/clear", "Clear screen and redraw banner."),
    CommandSpec("Chat", "/archive", "/archive", "Save current session and quit."),
    CommandSpec("Chat", "/exit", "/exit", "Quit."),
    CommandSpec("Chat", "/mode", "/mode", "Show mode."),
    CommandSpec("Chat", "/mode chat", "/mode chat", "Disable model tool use."),
    CommandSpec("Chat", "/mode agent", "/mode agent", "Enable model tool use."),
    CommandSpec("UI", "/ui", "/ui", "Show UI layout."),
    CommandSpec("UI", "/ui window", "/ui window", "Full terminal chat window."),
    CommandSpec("UI", "/ui statusline", "/ui statusline", "Bottom statusline."),
    CommandSpec("UI", "/ui side", "/ui side", "Side live panel."),
    CommandSpec("UI", "/chart", "/chart a=2 b=4", "Draw terminal bar chart."),
    CommandSpec("UI", "/big", "/big <text>", "Draw large block letters."),
    CommandSpec("UI", "/tilt", "/tilt <text>", "Draw slanted large letters."),
    CommandSpec("Models", "/model", "/model", "Open model picker."),
    CommandSpec("Models", "/models", "/models", "Show available models."),
    CommandSpec("Models", "/model load", "/model load [name|path]", "Load selected model."),
    CommandSpec("Models", "/model unload", "/model unload", "Drop loaded model from memory."),
    CommandSpec("Models", "/model download", "/model download <name>", "Download preconfigured model."),
    CommandSpec("Models", "/model delete", "/model delete <name>", "Delete preconfigured model files."),
    CommandSpec("Models", "/model qwen", "/model qwen", "Switch to Qwen."),
    CommandSpec("Models", "/model tiny", "/model tiny", "Switch to Gemma 4 E2B QAT INT4."),
    CommandSpec("Models", "/model glm", "/model glm", "Switch to GLM."),
    CommandSpec("Models", "/model gemma", "/model gemma", "Switch to Gemma."),
    CommandSpec("Models", "/model use", "/model use <name|path>", "Switch model without loading."),
    CommandSpec("System Prompt", "/system", "/system", "Show current system prompt."),
    CommandSpec("System Prompt", "/system set", "/system set <text>", "Replace system prompt."),
    CommandSpec("System Prompt", "/system append", "/system append <text>", "Append to system prompt."),
    CommandSpec("System Prompt", "/system reset", "/system reset", "Restore default system prompt."),
    CommandSpec("System Prompt", "/system save", "/system save [path]", "Save system prompt."),
    CommandSpec("System Prompt", "/system load", "/system load <path>", "Load system prompt."),
    CommandSpec("Context and Performance", "/ctx", "/ctx [tokens]", "Show or set context tokens."),
    CommandSpec("Context and Performance", "/kv", "/kv [auto|u4|u8|f16]", "Set KV-cache precision."),
    CommandSpec("Context and Performance", "/max-tokens", "/max-tokens [tokens]", "Show or set maximum response tokens."),
    CommandSpec("Context and Performance", "/status", "/status", "Show model, RAM, CPU, GPU, cwd."),
    CommandSpec("Context and Performance", "/perf", "/perf", "Show performance summary."),
    CommandSpec("Context and Performance", "/ram", "/ram", "Show RAM usage."),
    CommandSpec("Context and Performance", "/cpu", "/cpu", "Show CPU usage."),
    CommandSpec("Context and Performance", "/gpu", "/gpu", "Show GPU usage."),
    CommandSpec("Context and Performance", "/bench", "/bench", "Benchmark current loaded model."),
    CommandSpec("Context and Performance", "/doctor", "/doctor", "Check local OpenVINO setup."),
    CommandSpec("Context and Performance", "/report", "/report", "Write debug report."),
    CommandSpec("Context and Performance", "/stats", "/stats", "Show local usage stats."),
    CommandSpec("Context and Performance", "/config", "/config", "Show or update config."),
    CommandSpec("API", "/api", "/api", "Show local OpenAI API status."),
    CommandSpec("API", "/api start", "/api start [port]", "Start lazy local API server."),
    CommandSpec("API", "/api stop", "/api stop", "Stop local API server."),
    CommandSpec("Workspace", "/workspace", "/workspace", "Show workspace and cwd."),
    CommandSpec("Workspace", "/workspace set", "/workspace set <path>", "Set workspace root."),
    CommandSpec("Workspace", "/cd", "/cd <path>", "Change tool cwd inside workspace."),
    CommandSpec("Workspace", "/project", "/project", "Show git project status."),
    CommandSpec("Workspace", "/permissions", "/permissions", "Show tool permission mode."),
    CommandSpec("Workspace", "/permissions ask", "/permissions ask", "Ask before tool actions."),
    CommandSpec("Workspace", "/permissions allow", "/permissions allow", "Always allow tool actions."),
    CommandSpec("Tools", "/tools", "/tools", "List tools."),
    CommandSpec("Tools", "/pwd", "/pwd", "Print tool cwd."),
    CommandSpec("Tools", "/ls", "/ls [path]", "List files."),
    CommandSpec("Tools", "/read", "/read <path>", "Read file."),
    CommandSpec("Tools", "/scan", "/scan [path]", "List project files."),
    CommandSpec("Tools", "/grep", "/grep <pattern> [path]", "Search files."),
    CommandSpec("Tools", "/write", "/write <path> <text>", "Write file."),
    CommandSpec("Tools", "/append", "/append <path> <text>", "Append file."),
    CommandSpec("Tools", "/shell", "/shell <command>", "Run shell command."),
    CommandSpec("Tools", "/storage", "/storage [path]", "Show disk usage."),
    CommandSpec("Tools", "/web", "/web <query>", "Search web."),
    CommandSpec("Tools", "/fetch", "/fetch <url>", "Fetch webpage."),
    CommandSpec("Tools", "/diff", "/diff", "Show tracked tool file changes."),
    CommandSpec("Tools", "/undo", "/undo tool", "Undo last tracked tool file change."),
    CommandSpec("Tasks", "/task", "/task", "Show task list."),
    CommandSpec("Tasks", "/plan", "/plan <goal>", "Create task plan from model."),
    CommandSpec("Tasks", "/task add", "/task add <text>", "Add task."),
    CommandSpec("Tasks", "/task done", "/task done <n>", "Mark task done."),
    CommandSpec("Tasks", "/task clear", "/task clear", "Clear tasks."),
    CommandSpec("Tasks", "/review", "/review", "Review current git/tool diff."),
    CommandSpec("Sessions", "/session", "/session", "Open session picker."),
    CommandSpec("Sessions", "/sessions", "/sessions", "List saved sessions."),
    CommandSpec("Sessions", "/new", "/new [name]", "Start new empty session."),
    CommandSpec("Sessions", "/save", "/save [name]", "Save chat history."),
    CommandSpec("Sessions", "/load", "/load <name>", "Load saved history."),
    CommandSpec("Sessions", "/delete", "/delete [name]", "Delete current or named session."),
    CommandSpec("Sessions", "/export", "/export [path]", "Export chat as markdown."),
)

SLASH_COMMAND_POPUP_LIMIT = 15
SLASH_TOP_COMMANDS = (
    "/help",
    "/model",
    "/models",
    "/model load",
    "/session",
    "/status",
    "/tools",
    "/permissions",
    "/ctx",
    "/kv",
    "/system",
    "/plan",
    "/review",
    "/clear",
    "/reset",
    "/exit",
)

EXACT_USAGE_COMMANDS = {
    "/chart": "/chart a=2 b=4",
    "/big": "/big <text>",
    "/tilt": "/tilt <text>",
    "/model download": "/model download <name>",
    "/model delete": "/model delete <name>",
    "/model use": "/model use <name|path>",
    "/system set": "/system set <text>",
    "/system append": "/system append <text>",
    "/system load": "/system load <path>",
    "/workspace set": "/workspace set <path>",
    "/cd": "/cd <path>",
    "/read": "/read <path>",
    "/grep": "/grep <pattern> [path]",
    "/write": "/write <path> <text>",
    "/append": "/append <path> <text>",
    "/shell": "/shell <command>",
    "/web": "/web <query>",
    "/fetch": "/fetch <url>",
    "/load": "/load <name>",
}


def _prompt_toolkit_prompt(
    prompt_text,
    bottom_toolbar=None,
    refresh_interval=None,
    completer=None,
    complete_while_typing=True,
    reserve_space_for_menu=10,
) -> str:
    from prompt_toolkit import prompt

    return prompt(
        prompt_text,
        bottom_toolbar=bottom_toolbar,
        refresh_interval=refresh_interval,
        completer=completer,
        complete_while_typing=complete_while_typing,
        reserve_space_for_menu=reserve_space_for_menu,
        style=_prompt_style(),
    )


def _input_with_status(
    input_fn: InputFn,
    prompt_text: str,
    status_text: Callable[[], str],
    layout: str = "statusline",
    chat_text: Callable[[], str] | None = None,
    tasks_text: Callable[[], str] | None = None,
) -> str:
    if input_fn is not builtins.input:
        return input_fn(prompt_text)

    mediator = tui_mod.active_mediator()
    if mediator is not None:
        return mediator.request_prompt(prompt_text)

    cache = PromptStatusCache(status_text)
    completer = _command_completer()
    cache.start()
    try:
        if layout == "window":
            task_reader = tasks_text or (lambda: "no tasks")
            return _prompt_toolkit_window_prompt(
                prompt_text,
                bottom_toolbar=cache.toolbar,
                chat_text=chat_text or (lambda: ""),
                tasks_text=task_reader,
                show_tasks=has_visible_tasks(task_reader()),
                completer=completer,
                refresh_interval=0.2,
            )
        return _prompt_toolkit_prompt(
            prompt_text,
            bottom_toolbar=cache.toolbar,
            refresh_interval=0.2,
            completer=completer,
            complete_while_typing=True,
            reserve_space_for_menu=10,
        )
    except (ImportError, ModuleNotFoundError):
        return input_fn(prompt_text)
    finally:
        cache.stop()


class PromptStatusCache:
    def __init__(self, status_text: Callable[[], str], refresh_seconds: float = 3.0) -> None:
        self.status_text = status_text
        self.refresh_seconds = refresh_seconds
        self._value = _toolbar_fragments("status: updating")
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.2)
            self._thread = None

    def toolbar(self) -> list[tuple[str, str]]:
        with self._lock:
            return list(self._value)

    def refresh(self) -> None:
        try:
            value = self.status_text()
        except Exception:
            value = "status: unavailable"
        with self._lock:
            self._value = _toolbar_fragments(value)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            if self._stop.wait(self.refresh_seconds):
                return


def _prompt_style():
    from prompt_toolkit.styles import Style

    return Style.from_dict(
        {
            "bottom-toolbar": "noreverse #6b7280",
            "toolbar.title": "#64748b",
            "toolbar.label": "#38bdf8",
            "toolbar.value": "#9ca3af",
            "toolbar.sep": "#4b5563",
            "input": "#e5e7eb",
            "input.prompt": "#9ca3af",
            "separator": "#374151",
            "task": "#9ca3af",
            "command-bar": "#cbd5e1 bg:#111827",
            "model-menu": "#cbd5e1 bg:#111827",
            "operation.thinking": "#60a5fa",
            "operation.generating": "#facc15",
            "operation.tool": "#4ade80",
            "operation.default": "#9ca3af",
        }
    )


def _toolbar_fragments(status_text: str) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = [("class:toolbar.title", " openvino "), ("", " ")]
    lines = [line.strip() for line in status_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if index:
            fragments.append(("class:toolbar.sep", " | "))
        label, value = _split_toolbar_status(line)
        fragments.append(("class:toolbar.label", label))
        if value is not None:
            fragments.append(("class:toolbar.sep", ": "))
            fragments.append(("class:toolbar.value", value))
    return fragments


def _split_toolbar_status(line: str) -> tuple[str, str | None]:
    if ": " in line:
        label, value = line.split(": ", 1)
        return label.replace("_", " "), value
    if "=" in line:
        label, value = line.split("=", 1)
        return label.replace("_", " "), value
    return line.replace("_", " "), None


def _command_completer():
    from prompt_toolkit.completion import WordCompleter

    words = [spec.command for spec in COMMAND_SPECS]
    meta = {spec.command: spec.description for spec in COMMAND_SPECS}
    return WordCompleter(words, meta_dict=meta, ignore_case=True)


def _slash_command_bar(
    text: str,
    limit: int = SLASH_COMMAND_POPUP_LIMIT,
    selected_index: int | None = None,
) -> str:
    query = text.strip()
    if not query.startswith("/"):
        return ""
    matches = _slash_command_matches(query)
    if not matches:
        return " no matching slash commands"
    has_more = len(matches) > limit
    visible_limit = max(1, limit - 1) if has_more else limit
    selected = 0 if selected_index is None else max(0, min(selected_index, len(matches) - 1))
    start = 0
    if has_more:
        start = max(0, min(selected - visible_limit + 1, len(matches) - visible_limit))
    visible = matches[start : start + visible_limit]
    width = max(len(spec.usage) for spec in visible)
    lines = []
    for offset, spec in enumerate(visible):
        index = start + offset
        marker = ">" if selected_index == index else " "
        lines.append(f"{marker} {spec.usage:<{width}}  {spec.description}")
    if has_more:
        above = start
        below = len(matches) - (start + len(visible))
        lines.append(f"  ... {above} above | {below} below")
    return "\n".join(lines)


def _slash_command_bar_height(text: str, limit: int = SLASH_COMMAND_POPUP_LIMIT) -> int:
    query = text.strip()
    if not query.startswith("/"):
        return 0
    matches = _slash_command_matches(query)
    if not matches:
        return 1
    return min(len(matches), limit)


def _slash_command_matches(query: str) -> list[CommandSpec]:
    matches = [spec for spec in COMMAND_SPECS if spec.command.startswith(query)]
    if query != "/":
        return matches
    by_command = {spec.command: spec for spec in matches}
    prioritized = [by_command[command] for command in SLASH_TOP_COMMANDS if command in by_command]
    seen = {spec.command for spec in prioritized}
    prioritized.extend(spec for spec in matches if spec.command not in seen)
    return prioritized


def _exact_usage_message(text: str) -> str:
    usage = EXACT_USAGE_COMMANDS.get(text.strip().lower())
    return f"usage: {usage}" if usage else ""


def _prompt_toolkit_window_prompt(
    prompt_text: str,
    bottom_toolbar,
    chat_text: Callable[[], str],
    tasks_text: Callable[[], str],
    show_tasks: bool,
    completer=None,
    refresh_interval: float = 0.2,
) -> str:
    from prompt_toolkit.application import Application
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.widgets import TextArea

    input_area = TextArea(
        prompt=prompt_text,
        multiline=False,
        wrap_lines=True,
        height=1,
        style="class:input",
        completer=completer,
        complete_while_typing=True,
    )
    chat_window = Window(
        FormattedTextControl(lambda: ANSI(chat_text())),
        width=Dimension(weight=1),
        height=Dimension(weight=1),
        wrap_lines=True,
        always_hide_cursor=True,
    )
    task_window = None
    if show_tasks:
        task_window = Window(
            FormattedTextControl(lambda: ANSI(_ansi_plain(tasks_text()))),
            wrap_lines=True,
            always_hide_cursor=True,
            width=Dimension(preferred=32, max=40),
            style="class:task",
        )
    vertical_separator = Window(width=1, char="|", style="class:separator", always_hide_cursor=True)
    input_separator = Window(height=1, char="-", style="class:separator", always_hide_cursor=True)
    command_bar = ConditionalContainer(
        Window(
            FormattedTextControl(lambda: ANSI(_ansi_plain(_slash_command_bar(input_area.text)))),
            height=lambda: _slash_command_bar_height(input_area.text),
            style="class:command-bar",
            always_hide_cursor=True,
        ),
        filter=Condition(lambda: bool(_slash_command_bar(input_area.text))),
    )
    toolbar = Window(
        FormattedTextControl(bottom_toolbar),
        height=1,
        style="class:bottom-toolbar",
        always_hide_cursor=True,
    )
    keys = KeyBindings()

    @keys.add("enter")
    def _accept(event) -> None:
        event.app.exit(result=input_area.text)

    @keys.add("c-c")
    def _interrupt(event) -> None:
        event.app.exit(exception=KeyboardInterrupt)

    content = (
        VSplit([chat_window, vertical_separator, task_window], height=Dimension(weight=1))
        if task_window is not None
        else chat_window
    )
    body = HSplit(
        [
            content,
            command_bar,
            input_separator,
            input_area,
            toolbar,
        ]
    )
    app = Application(
        layout=Layout(body, focused_element=input_area),
        key_bindings=keys,
        full_screen=True,
        mouse_support=False,
        refresh_interval=refresh_interval,
        style=_prompt_style(),
    )
    return app.run()


def _ansi_plain(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _session_picker(store: ChatSessionStore, active_session: str) -> tuple[str, str | None]:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        items = []
        for name in store.list_sessions():
            try:
                preview = _session_preview(store.load(name))
            except Exception as exc:
                preview = f"preview unavailable: {exc}"
            items.append(
                {
                    "name": name,
                    "active": name == active_session,
                    "preview": preview,
                }
            )
        return mediator.request_session_picker(items)
    if not _can_use_fullscreen_picker():
        return ("list", None)

    names = store.list_sessions()
    state = {"index": 0}

    def selected() -> str | None:
        if not names:
            return None
        state["index"] = max(0, min(state["index"], len(names) - 1))
        return names[state["index"]]

    def render():
        lines = ["Sessions  Enter load | d delete | n new | s save | Esc cancel", ""]
        if not names:
            lines.append("  no saved sessions")
        for index, name in enumerate(names):
            marker = ">" if index == state["index"] else " "
            active = " active" if name == active_session else ""
            lines.append(f"{marker} {name}{active}")
        name = selected()
        if name:
            lines.extend(["", "Preview:"])
            try:
                history = store.load(name)
            except Exception as exc:
                lines.append(f"  {exc}")
            else:
                lines.extend("  " + line for line in _session_preview(history).splitlines())
        return "\n".join(lines)

    return _run_picker(render, state, len(names), selected)


def _model_picker(active_model_dir: Path, loaded: bool) -> tuple[str, str | None]:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        items = [
            {
                "name": name,
                "state": _model_install_state(path),
                "size": _model_dir_size_text(path),
                "active": path == active_model_dir,
                "repo": MODEL_REPOS.get(name, "-"),
                "path": str(path),
            }
            for name, path in MODEL_DIRS.items()
        ]
        return mediator.request_model_picker(items, loaded)
    if not _can_use_fullscreen_picker():
        return ("list", None)

    entries = list(MODEL_DIRS.items())
    state = {"index": max(0, next((i for i, (_name, path) in enumerate(entries) if path == active_model_dir), 0))}

    def selected() -> str | None:
        if not entries:
            return None
        state["index"] = max(0, min(state["index"], len(entries) - 1))
        return entries[state["index"]][0]

    def render():
        lines = ["Models  Enter load | i download | d delete | u unload | Esc cancel", ""]
        for index, (name, path) in enumerate(entries):
            marker = ">" if index == state["index"] else " "
            active = " active" if path == active_model_dir else ""
            state_text = "loaded" if path == active_model_dir and loaded else "not loaded"
            exists = _model_install_state(path)
            size = _model_dir_size_text(path)
            repo = MODEL_REPOS.get(name, "-")
            lines.append(f"{marker} {name:<8} {exists:<9} {state_text:<10} {size:<10}{active}")
            lines.append(f"  repo: {repo}")
            lines.append(f"  path: {path}")
        return "\n".join(lines)

    return _run_picker(render, state, len(entries), selected, enter_action="load")


def _kv_picker(current: str) -> str | None:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        return mediator.request_kv_picker(current)
    return None


def _run_picker(
    render: Callable[[], str],
    state: dict[str, int],
    count: int,
    selected: Callable[[], str | None],
    enter_action: str = "load",
) -> tuple[str, str | None]:
    from prompt_toolkit.application import Application
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    keys = KeyBindings()

    @keys.add("down")
    def _down(event) -> None:
        if count:
            state["index"] = min(count - 1, state["index"] + 1)

    @keys.add("up")
    def _up(event) -> None:
        if count:
            state["index"] = max(0, state["index"] - 1)

    @keys.add("enter")
    def _enter(event) -> None:
        event.app.exit(result=(enter_action, selected()))

    @keys.add("d")
    def _delete(event) -> None:
        event.app.exit(result=("delete", selected()))

    @keys.add("n")
    def _new(event) -> None:
        event.app.exit(result=("new", None))

    @keys.add("s")
    def _save(event) -> None:
        event.app.exit(result=("save", None))

    @keys.add("u")
    def _unload(event) -> None:
        event.app.exit(result=("unload", None))

    @keys.add("i")
    def _download(event) -> None:
        event.app.exit(result=("download", selected()))

    @keys.add("escape")
    def _cancel(event) -> None:
        event.app.exit(result=("cancel", None))

    app = Application(
        layout=Layout(Window(FormattedTextControl(lambda: ANSI(_ansi_plain(render()))), wrap_lines=True)),
        key_bindings=keys,
        full_screen=True,
        mouse_support=False,
        style=_prompt_style(),
    )
    return app.run()


def _can_use_fullscreen_picker() -> bool:
    if tui_mod.is_tui_active():
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()


def _session_preview(history: list[tuple[str, str]], max_items: int = 4) -> str:
    if not history:
        return "(empty)"
    lines = []
    for role, content in history[-max_items:]:
        one_line = " ".join(_ansi_plain(content).strip().split())
        lines.append(f"{role}: {one_line[:120]}")
    return "\n".join(lines)


def _save_session(
    sessions: ChatSessionStore,
    name: str,
    history: list[tuple[str, str]],
    model_name: str,
    device: str,
) -> Path:
    metadata = {
        "model": model_name,
        "device": device,
    }
    try:
        return sessions.save(name, history, metadata=metadata)
    except TypeError:
        return sessions.save(name, history)


def _auto_session_name(history: list[tuple[str, str]]) -> str:
    first_user = next((content for role, content in history if role == "user"), "chat")
    words = "-".join(first_user.lower().strip().split())[:32].strip("-") or "chat"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in words).strip("-") or "chat"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{safe}"


def _config_path() -> Path:
    env_path = os.environ.get("OPENVINO_CHAT_CONFIG")
    if env_path:
        return Path(env_path)
    return CONFIG_PATH


def _load_config() -> dict[str, str]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_config(config: dict[str, str]) -> Path:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _configured_kv_precision() -> str:
    try:
        return normalize_kv_cache_precision(_load_config().get("kv_cache_precision", "auto"))
    except ValueError:
        return "auto"


def _handle_config_command(prompt: str) -> str:
    config = _load_config()
    lower = prompt.lower().strip()
    if lower == "/config":
        if not config:
            return "config=empty"
        return "\n".join(f"{key}={value}" for key, value in sorted(config.items()))
    if lower.startswith("/config set "):
        _, _, rest = prompt.partition("/config set ")
        key, _, value = rest.strip().partition(" ")
        if not key or not value:
            return "usage: /config set <key> <value>"
        config[key] = value.strip()
        path = _save_config(config)
        return f"config_saved={path}\n{key}={config[key]}"
    return "usage: /config | /config set <key> <value>"


def _doctor_text(model_dir: Path, session_dir: Path, cwd: Path) -> str:
    lines = [
        f"python={sys.executable}",
        f"cwd={cwd}",
        f"model_dir={model_dir}",
        f"model_exists={model_dir.exists()}",
        f"model_valid={_validate_model_dir(model_dir)}",
        f"session_dir={session_dir}",
        f"session_dir_exists={session_dir.exists()}",
    ]
    try:
        import openvino_genai  # noqa: F401
    except Exception as exc:
        lines.append(f"openvino_genai=missing ({exc})")
    else:
        lines.append("openvino_genai=ok")
    try:
        import huggingface_hub  # noqa: F401
    except Exception as exc:
        lines.append(f"huggingface_hub=missing ({exc})")
    else:
        lines.append("huggingface_hub=ok")
    try:
        usage = shutil.disk_usage(str(MODEL_ROOT))
    except Exception:
        pass
    else:
        lines.append(f"model_root_free={human_bytes(usage.free)}")
    for name, path in MODEL_DIRS.items():
        lines.append(f"model.{name}.exists={path.exists()}")
    return "\n".join(lines)


def _validate_model_dir(model_dir: Path) -> bool:
    if not model_dir.exists() or not model_dir.is_dir():
        return False
    return any((model_dir / name).exists() for name in ("openvino_model.xml", "openvino_language_model.xml"))


def _write_report(model_dir: Path, session_dir: Path, cwd: Path, device: str, context_length: int) -> Path:
    root = Path(os.environ.get("OPENVINO_CHAT_REPORT_DIR", REPORT_DIR))
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    body = [
        "# OpenVINO Chat Report",
        "",
        _doctor_text(model_dir, session_dir, cwd),
        "",
        f"device={device}",
        f"ctx={context_length}",
        "",
        "git:",
        _project_status(cwd),
    ]
    target.write_text("\n".join(body), encoding="utf-8")
    return target


def _git_diff_text(cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", "--", "."],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except Exception as exc:
        return f"git diff unavailable: {exc}"
    if completed.returncode != 0:
        return completed.stderr.strip() or "git diff failed"
    return completed.stdout.strip() or "no git diff"


def _is_empty_diff(text: str) -> bool:
    clean = text.strip().lower()
    return clean in {"", "no git diff", "no tracked tool changes"} or clean.startswith("git diff unavailable")


def _bench_engine(
    engine: OpenVinoChatEngine,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    context_length: int,
) -> str:
    chunks: list[str] = []
    start = time.perf_counter()
    engine.generate(
        "Say hello in five words.",
        on_token=chunks.append,
        max_new_tokens=min(max_new_tokens, 64),
        temperature=temperature,
        top_p=top_p,
        context_length=context_length,
    )
    elapsed = max(time.perf_counter() - start, 0.000001)
    text = "".join(chunks)
    tokens = len(text.split()) if text else len(chunks)
    return "\n".join(
        [
            f"tokens={tokens}",
            f"seconds={elapsed:.3f}",
            f"tokens_per_sec={tokens / elapsed:.2f}",
        ]
    )


@dataclass
class ReplSnapshot:
    model_dir: Path
    context_length: int
    max_new_tokens: int
    kv_cache_precision: str
    history: list[tuple[str, str]]
    display_messages: list[tuple[int, str]]
    system_prompt_template: str
    tools_enabled: bool
    workspace_root: Path
    cwd: Path
    permission_mode: str
    active_session: str
    ui_layout: str
    raw_output: bool
    tasks: list[tuple[str, bool]]
    tui_text: str | None


class EscInterrupt:
    def __init__(self, key_reader: Callable[[], str | None] | None = None) -> None:
        self.key_reader = key_reader or _read_console_key
        self._interrupted = threading.Event()
        self._closed = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "EscInterrupt":
        self.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.stop()

    def start(self) -> None:
        self._closed.clear()
        self._interrupted.clear()
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._closed.set()
        if self._thread is not None:
            self._thread.join(timeout=0.2)
            self._thread = None

    def should_stop(self) -> bool:
        return self._interrupted.is_set()

    def _watch(self) -> None:
        while not self._closed.is_set():
            key = self.key_reader()
            if key == "\x1b":
                self._interrupted.set()
                return
            time.sleep(0.05)


def _read_console_key() -> str | None:
    if os.name != "nt":
        return None
    try:
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch()
    except Exception:
        return None
    return None


def main(
    argv: Sequence[str] | None = None,
    engine_loader: EngineLoader = load_engine,
    downloader: Downloader = download_named_model,
    input_fn: InputFn = input,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    model_dir = args.model_dir or DEFAULT_MODEL_DIR
    command = args.command or "chat"

    if command == "status":
        return _status(model_dir)
    if command == "models":
        print(_model_list(model_dir, loaded=False))
        return 0
    if command == "download":
        return _download(args.model, args.model_dir, downloader)
    if command == "delete":
        return _delete_model(args.model)
    if command == "serve":
        if not model_dir.exists():
            print(f"model missing: {model_dir}", file=sys.stderr)
            return 2
        try:
            return run_api_server(
                model_dir=model_dir,
                host=args.host,
                port=args.port,
                device=args.device,
                context_length=args.context_length,
                kv_cache_precision=args.kv_cache_precision or _configured_kv_precision(),
                api_key=args.api_key,
                engine_loader=engine_loader,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"API failed: {exc}", file=sys.stderr)
            return 3
    if command == "api":
        return _api_cli_command(
            args.action,
            model_dir,
            args.host,
            args.port,
            args.device,
            args.context_length,
            args.kv_cache_precision or _configured_kv_precision(),
            args.api_key,
        )
    if command == "chat":
        prompt = " ".join(getattr(args, "prompt", [])).strip()
        return _chat(
            model_dir=model_dir,
            prompt=prompt,
            device=getattr(args, "device", "GPU"),
            max_new_tokens=getattr(args, "max_new_tokens", 4096),
            temperature=getattr(args, "temperature", 0.7),
            top_p=getattr(args, "top_p", 0.9),
            context_length=getattr(args, "context_length", 4096),
            kv_cache_precision=(
                getattr(args, "kv_cache_precision", None) or _configured_kv_precision()
            ),
            engine_loader=engine_loader,
            input_fn=input_fn,
        )
    parser.print_help()
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openvino")
    parser.add_argument("--model-dir", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("status")
    subparsers.add_parser("models")

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("model", choices=sorted(MODEL_REPOS))

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("model", choices=sorted(MODEL_DIRS))

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default=DEFAULT_API_HOST)
    serve_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    serve_parser.add_argument("--device", default="GPU", choices=["GPU", "NPU", "CPU"])
    serve_parser.add_argument("--ctx", "--context-length", dest="context_length", type=int, default=4096)
    serve_parser.add_argument("--kv-cache", dest="kv_cache_precision", choices=["auto", "u4", "u8", "f16"])
    serve_parser.add_argument("--api-key", default=os.environ.get("OPENVINO_CHAT_API_KEY"))

    api_parser = subparsers.add_parser("api")
    api_parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "stop"])
    api_parser.add_argument("--host", default=DEFAULT_API_HOST)
    api_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    api_parser.add_argument("--device", default="GPU", choices=["GPU", "NPU", "CPU"])
    api_parser.add_argument("--ctx", "--context-length", dest="context_length", type=int, default=4096)
    api_parser.add_argument("--kv-cache", dest="kv_cache_precision", choices=["auto", "u4", "u8", "f16"])
    api_parser.add_argument("--api-key", default=os.environ.get("OPENVINO_CHAT_API_KEY"))

    chat_parser = subparsers.add_parser("chat")
    chat_parser.add_argument("prompt", nargs="*")
    chat_parser.add_argument("--device", default="GPU", choices=["GPU", "NPU", "CPU"])
    chat_parser.add_argument("--max-new-tokens", type=int, default=4096)
    chat_parser.add_argument("--ctx", "--context-length", dest="context_length", type=int, default=4096)
    chat_parser.add_argument("--temperature", type=float, default=0.7)
    chat_parser.add_argument("--top-p", type=float, default=0.9)
    chat_parser.add_argument("--kv-cache", dest="kv_cache_precision", choices=["auto", "u4", "u8", "f16"])
    return parser


def _status(model_dir: Path) -> int:
    print(f"model_dir={model_dir}")
    print(f"model_exists={model_dir.exists()}")
    print(f"models_available={_available_models_summary()}")
    if not model_dir.exists():
        print("download=openvino download qwen")
    return 0


def _download(model: str, model_dir: Path | None, downloader: Downloader) -> int:
    if model not in MODEL_REPOS:
        print(f"unknown model: {model}", file=sys.stderr)
        return 2
    try:
        path = downloader(model, model_dir)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ImportError:
        print("missing package: install with " + package_install_command(), file=sys.stderr)
        return 3
    print(f"downloaded={path}")
    return 0


def _delete_model(model: str) -> int:
    try:
        path = delete_named_model(model)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(f"deleted_model={path}")
    return 0


def _api_cli_command(
    action: str,
    model_dir: Path,
    host: str,
    port: int,
    device: str,
    context_length: int,
    kv_cache_precision: str,
    api_key: str | None,
) -> int:
    try:
        if action == "start":
            if not model_dir.exists():
                print(f"model missing: {model_dir}", file=sys.stderr)
                return 2
            status = start_api_process(
                model_dir,
                host=host,
                port=port,
                device=device,
                context_length=context_length,
                kv_cache_precision=kv_cache_precision,
                api_key=api_key,
            )
            print(format_api_status(status))
            return 0
        if action == "stop":
            stopped = stop_api_process()
            print("api: stopped" if stopped else "api: already stopped")
            return 0
        print(format_api_status())
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"API failed: {exc}", file=sys.stderr)
        return 3


def _chat(
    model_dir: Path,
    prompt: str,
    device: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    context_length: int,
    kv_cache_precision: str,
    engine_loader: EngineLoader,
    input_fn: InputFn,
) -> int:
    if not model_dir.exists():
        print(f"model missing: {model_dir}", file=sys.stderr)
        print("run: openvino download qwen", file=sys.stderr)
        return 2
    if prompt:
        try:
            engine = _load_engine_for_cli(
                engine_loader,
                model_dir,
                device,
                kv_cache_precision,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 3
        print(f"device={engine.device}")
        return _run_prompt(engine, prompt, max_new_tokens, temperature, top_p, context_length)
    if _can_use_persistent_tui(input_fn):
        chat_buffer = tui_mod.ChatBuffer()
        return tui_mod.run_persistent_repl(
            repl_worker=lambda: _repl(
                None,
                model_dir,
                device,
                max_new_tokens,
                temperature,
                top_p,
                context_length,
                kv_cache_precision,
                input_fn,
                engine_loader,
            ),
            status_text=lambda: _live_status_text(device, context_length, kv_cache_precision),
            tasks_text=lambda: "",
            chat_buffer=chat_buffer,
            completer=_command_completer(),
        )
    print(f"model={model_dir}")
    print("loaded=no")
    return _repl(
        None,
        model_dir,
        device,
        max_new_tokens,
        temperature,
        top_p,
        context_length,
        kv_cache_precision,
        input_fn,
        engine_loader,
    )


def _can_use_persistent_tui(input_fn: InputFn) -> bool:
    if input_fn is not builtins.input:
        return False
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except Exception:
        return False


def _load_engine_for_cli(
    engine_loader: EngineLoader,
    model_dir: Path,
    device: str,
    kv_cache_precision: str,
) -> OpenVinoChatEngine:
    try:
        return engine_loader(
            model_dir,
            device=device,
            kv_cache_precision=kv_cache_precision,
        )
    except TypeError as exc:
        if "kv_cache_precision" not in str(exc):
            raise
        return engine_loader(model_dir, device=device)


def _run_prompt(
    engine: OpenVinoChatEngine,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    context_length: int,
) -> int:
    ui = ChatUI()
    session = ToolChatSession(engine, ToolRegistry(cwd=Path.cwd(), permission_mode="allow"))
    try:
        _ask_session(session, ui, prompt, max_new_tokens, temperature, top_p, context_length)
    except Exception as exc:
        print(f"generation failed: {exc}", file=sys.stderr)
        return 3
    return 0


def _repl(
    engine: OpenVinoChatEngine | None,
    model_dir: Path,
    device: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    context_length: int,
    kv_cache_precision: str,
    input_fn: InputFn,
    engine_loader: EngineLoader = load_engine,
) -> int:
    ui = ChatUI()
    kv_cache_precision = normalize_kv_cache_precision(kv_cache_precision)
    if engine is not None:
        kv_cache_precision = getattr(engine, "kv_cache_precision", kv_cache_precision)
    _mediator = tui_mod.active_mediator()
    if _mediator is not None:
        if getattr(_mediator, "chat_buffer", None) is not None:
            _buf = _mediator.chat_buffer
            ui = _BufferChatUI(ui, _buf, _mediator)

            def _invalidate_buffer() -> None:
                _mediator.invalidate()
        else:
            _invalidate_buffer = lambda: None
    else:
        _invalidate_buffer = lambda: None

    def _tui_buffer():
        m = tui_mod.active_mediator()
        return getattr(m, "chat_buffer", None) if m is not None else None

    def approve_tool(request):
        prompt_text = f"Allow {request.name}? [y/N] "
        mediator = tui_mod.active_mediator()
        if mediator is not None:
            answer = mediator.request_prompt(prompt_text).strip().lower()
        else:
            answer = input_fn(prompt_text).strip().lower()
        return answer in {"y", "yes", "allow"}

    registry = ToolRegistry(
        cwd=Path.cwd(),
        permission_mode="ask",
        approval_callback=approve_tool,
    )
    session = ToolChatSession(engine, registry)
    estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
    ui.banner(
        device,
        context_length,
        human_bytes(estimate.total_bytes),
        model_name_from_dir(model_dir),
        loaded=engine is not None,
        models_summary=_available_models_summary(),
    )
    sessions = ChatSessionStore()
    active_session = "default"
    snapshots: list[ReplSnapshot] = []
    ui_layout = "window"
    raw_output = False
    tasks = TaskList()
    display_messages: list[tuple[int, str]] = []
    tui_before_prompt: str | None = None

    def active_device() -> str:
        return engine.device if engine is not None else device

    def live_text() -> str:
        return _live_status_text(active_device(), context_length, kv_cache_precision)

    def defer_output() -> bool:
        if tui_mod.active_mediator() is not None:
            return False
        return input_fn is builtins.input and ui_layout == "window"

    def use_live_work_ui() -> bool:
        return not defer_output()

    def show(text: object = "", *, plain: bool = False) -> None:
        value = str(text)
        if defer_output():
            display_messages.append((len(session.history), value))
            return
        if plain:
            ui.print_plain(value)
        else:
            ui.print(value)

    def unload_engine() -> bool:
        nonlocal engine
        old_engine = engine
        was_loaded = engine is not None
        session.engine = None
        engine = None
        del old_engine
        gc.collect()
        return was_loaded

    def take_snapshot() -> ReplSnapshot:
        return ReplSnapshot(
            model_dir=model_dir,
            context_length=context_length,
            max_new_tokens=max_new_tokens,
            kv_cache_precision=kv_cache_precision,
            history=list(session.history),
            display_messages=list(display_messages),
            system_prompt_template=session.system_prompt_template,
            tools_enabled=session.tools_enabled,
            workspace_root=session.tools.workspace_root,
            cwd=session.tools.cwd,
            permission_mode=session.tools.permission_mode,
            active_session=active_session,
            ui_layout=ui_layout,
            raw_output=raw_output,
            tasks=[(item.text, item.done) for item in tasks.items],
            tui_text=tui_before_prompt,
        )

    def push_snapshot() -> None:
        snapshots.append(take_snapshot())
        if len(snapshots) > 50:
            snapshots.pop(0)

    def restore_snapshot(snapshot: ReplSnapshot) -> None:
        nonlocal model_dir, context_length, max_new_tokens, kv_cache_precision, estimate, active_session, raw_output
        if snapshot.model_dir != model_dir or snapshot.kv_cache_precision != kv_cache_precision:
            unload_engine()
        model_dir = snapshot.model_dir
        context_length = snapshot.context_length
        max_new_tokens = snapshot.max_new_tokens
        kv_cache_precision = snapshot.kv_cache_precision
        config = _load_config()
        config["kv_cache_precision"] = kv_cache_precision
        _save_config(config)
        estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
        session.history = list(snapshot.history)
        display_messages[:] = list(snapshot.display_messages)
        session.system_prompt_template = snapshot.system_prompt_template
        session.tools_enabled = snapshot.tools_enabled
        session.tools.workspace_root = snapshot.workspace_root
        session.tools.cwd = snapshot.cwd
        session.tools.permission_mode = snapshot.permission_mode
        active_session = snapshot.active_session
        raw_output = snapshot.raw_output
        tasks.clear()
        for text, done in snapshot.tasks:
            tasks.add(text, done=done)
        set_ui_layout(snapshot.ui_layout)
        buffer = _tui_buffer()
        if buffer is not None and snapshot.tui_text is not None:
            buffer.replace(snapshot.tui_text)
            _invalidate_buffer()

    def ensure_engine() -> bool:
        nonlocal engine, device
        if engine is not None:
            return True
        if use_live_work_ui():
            monitor.start()
            monitor.set("loading model")
        try:
            engine = _load_engine_for_cli(
                engine_loader,
                model_dir,
                device,
                kv_cache_precision,
            )
            session.engine = engine
            device = engine.device
            show(f"model loaded: {model_name_from_dir(model_dir)} ({engine.device})")
            return True
        except RuntimeError as exc:
            show(str(exc))
            return False
        finally:
            if use_live_work_ui():
                _clear_monitor(monitor, refresh=False)
                monitor.stop()

    monitor = ui.status_monitor(live_text, refresh_seconds=1.0, layout=ui_layout, tasks_text=tasks.format)

    def download_with_status(name: str) -> Path:
        if use_live_work_ui():
            monitor.start()
            monitor.set("downloading model")
        try:
            return download_named_model(name)
        finally:
            if use_live_work_ui():
                _clear_monitor(monitor, refresh=False)
                monitor.stop()

    def ask_model(prompt_text: str) -> str | None:
        try:
            return _ask_session(
                session,
                ui,
                prompt_text,
                max_new_tokens,
                temperature,
                top_p,
                context_length,
                monitor if use_live_work_ui() else None,
                stop_checker=tui_should_stop if tui_mod.active_mediator() is not None else None,
            )
        except Exception as exc:
            show(f"generation failed: {exc}")
            return None

    _mediator = tui_mod.active_mediator()
    if _mediator is not None:
        _mediator.status_text = live_text
        _mediator.tasks_text = tasks.format
        if getattr(_mediator, "chat_buffer", None) is not None:
            _welcome = _build_tui_welcome_text(
                device,
                context_length,
                estimate,
                model_dir,
                engine is not None,
                kv_cache_precision,
            )
            _buf = _tui_buffer()
            if _buf is not None:
                _buf.append_line(_welcome)

    def tui_should_stop() -> bool:
        mediator = tui_mod.active_mediator()
        return bool(mediator is not None and mediator.should_stop())

    def redraw_tui_history(include_history: bool = True) -> None:
        buffer = _tui_buffer()
        if buffer is None:
            return
        parts = [
            _build_tui_welcome_text(
                active_device(),
                context_length,
                estimate,
                model_dir,
                engine is not None,
                kv_cache_precision,
            ).rstrip()
        ]
        if include_history and (session.history or display_messages):
            parts.append(
                _chat_window_text(
                    session.history,
                    display_messages,
                    raw=raw_output,
                )
            )
        buffer.replace("\n\n".join(part for part in parts if part).rstrip() + "\n")
        _invalidate_buffer()

    def set_ui_layout(layout: str) -> None:
        nonlocal monitor, ui_layout
        ui_layout = layout
        monitor.stop()
        monitor = ui.status_monitor(live_text, refresh_seconds=3.0, layout=ui_layout, tasks_text=tasks.format)

    def auto_save_session() -> str | None:
        nonlocal active_session
        if not session.history:
            return None
        name = active_session if active_session != "default" else _auto_session_name(session.history)
        _save_session(sessions, name, session.history, model_name_from_dir(model_dir), active_device())
        active_session = name
        return name

    try:
        while True:
            try:
                prompt = _input_with_status(
                    input_fn,
                    ui.user_prompt(),
                    live_text,
                    layout=ui_layout,
                    chat_text=lambda: _chat_window_text(session.history, display_messages, raw=raw_output),
                    tasks_text=tasks.format,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                if tui_mod.active_mediator() is None:
                    print()
                auto_save_session()
                return 0
            if prompt.lower() in {"exit", "quit", ":q", "/exit", "/quit"}:
                auto_save_session()
                return 0
            buffer = _tui_buffer()
            tui_before_prompt = buffer.render() if buffer is not None else None
            if prompt:
                if buffer is not None:
                    buffer.append_user(prompt)
                    _invalidate_buffer()
            usage = _exact_usage_message(prompt)
            if usage:
                show(usage, plain=True)
                continue
            if prompt.lower() == "/archive":
                name = auto_save_session()
                show(f"archived={name}" if name else "nothing to archive")
                return 0
            if prompt.lower() == "/help":
                show(_help_text())
                continue
            if prompt.lower() in {"/commands", "/cmds"}:
                show(_commands_text())
                continue
            if prompt.lower() == "/copy":
                latest = _last_assistant_message(session.history)
                if not latest:
                    show("nothing to copy")
                    continue
                show("copied" if _copy_to_clipboard(latest) else "copy failed")
                continue
            if prompt.lower() in {"/raw", "/raw on", "/raw off"}:
                push_snapshot()
                if prompt.lower() == "/raw on":
                    raw_output = True
                elif prompt.lower() == "/raw off":
                    raw_output = False
                else:
                    raw_output = not raw_output
                redraw_tui_history()
                show(f"raw={'on' if raw_output else 'off'}")
                continue
            if prompt.lower() == "/ui":
                show(f"ui={'window' if tui_mod.active_mediator() is not None else ui_layout}")
                continue
            if prompt.lower() in {"/ui side", "/ui statusline", "/ui window"}:
                if tui_mod.active_mediator() is not None:
                    show("ui=window")
                    continue
                push_snapshot()
                set_ui_layout(prompt.rsplit(" ", 1)[1])
                show(f"ui={ui_layout}")
                continue
            if prompt.lower() in {"/task", "/tasks"} or prompt.lower().startswith(("/task ", "/tasks ")):
                push_snapshot()
                show(tasks.handle_command(prompt), plain=True)
                continue
            if prompt.lower().startswith("/plan"):
                _, _, goal = prompt.partition(" ")
                goal = goal.strip() or "current work"
                if not ensure_engine():
                    continue
                push_snapshot()
                response = ask_model(
                    "Create a concise task plan with markdown checkboxes for: " + goal
                )
                if response is None:
                    continue
                tasks.update_from_text(response)
                auto_save_session()
                continue
            if prompt.lower() == "/review":
                tracked = session.tools.run_name("diff", {}).output
                diff_text = tracked if tracked != "no tracked tool changes" else _git_diff_text(session.tools.cwd)
                if _is_empty_diff(diff_text):
                    show("no diff to review")
                    continue
                if not ensure_engine():
                    continue
                push_snapshot()
                response = ask_model(
                    "Review this diff. Lead with bugs and risky changes. Be concise.\n\n" + diff_text
                )
                if response is None:
                    continue
                tasks.update_from_text(response)
                auto_save_session()
                continue
            if prompt.lower() == "/clear":
                buffer = _tui_buffer()
                if buffer is not None:
                    display_messages.clear()
                    redraw_tui_history(include_history=False)
                    continue
                if defer_output():
                    display_messages.clear()
                    continue
                os.system("cls" if os.name == "nt" else "clear")
                estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                ui.banner(
                    active_device(),
                    context_length,
                    human_bytes(estimate.total_bytes),
                    model_name_from_dir(model_dir),
                    loaded=engine is not None,
                    models_summary=_available_models_summary(),
                )
                continue
            if prompt.lower() == "/reset":
                push_snapshot()
                session.reset()
                redraw_tui_history()
                show("memory reset")
                continue
            if prompt.lower() == "/rewind":
                if not snapshots:
                    show("nothing to rewind")
                    continue
                restore_snapshot(snapshots.pop())
                show("rewound")
                continue
            if prompt.lower() == "/status":
                show(
                    "\n".join(
                        [
                            format_perf_status(
                                active_device(),
                                model_dir,
                                context_length,
                                kv_cache_precision=kv_cache_precision,
                            ),
                            f"max_new_tokens={max_new_tokens}",
                            f"cwd={Path.cwd()}",
                            "loaded=yes" if engine is not None else "loaded=no",
                            f"models_available={_available_models_summary()}",
                        ]
                    )
                )
                continue
            if prompt.lower() == "/doctor":
                show(_doctor_text(model_dir, sessions.root, session.tools.cwd))
                continue
            if prompt.lower().startswith("/config"):
                show(_handle_config_command(prompt))
                continue
            if prompt.lower() == "/report":
                target = _write_report(model_dir, sessions.root, session.tools.cwd, active_device(), context_length)
                show(f"report={target}")
                continue
            if prompt.lower() == "/stats":
                show(_stats_text(sessions, session.history, model_dir, engine is not None, session.tools, context_length))
                continue
            if prompt.lower() == "/bench":
                if not ensure_engine():
                    continue
                show(_bench_engine(engine, max_new_tokens, temperature, top_p, context_length))
                continue
            if prompt.lower() == "/diff":
                tracked = session.tools.run_name("diff", {}).output
                show(tracked if tracked != "no tracked tool changes" else _git_diff_text(session.tools.cwd))
                continue
            if prompt.lower() in {"/perf", "/ram", "/cpu", "/gpu"}:
                if prompt.lower() == "/ram":
                    show(get_ram_usage())
                elif prompt.lower() == "/cpu":
                    show(get_cpu_usage())
                elif prompt.lower() == "/gpu":
                    show(get_gpu_usage())
                else:
                    show(
                        format_perf_status(
                            active_device(),
                            model_dir,
                            context_length,
                            kv_cache_precision=kv_cache_precision,
                        )
                    )
                continue
            if prompt.lower().startswith("/ctx"):
                _, _, value = prompt.partition(" ")
                if value.strip():
                    try:
                        next_context_length = int(value.strip())
                    except ValueError:
                        show("ctx must be number")
                        continue
                    if next_context_length < 128:
                        show("ctx must be at least 128")
                        continue
                    push_snapshot()
                    context_length = next_context_length
                    max_new_tokens = min(max_new_tokens, context_length)
                estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                show(
                    "\n".join(
                        [
                            f"ctx={context_length}",
                            f"est_ram={human_bytes(estimate.total_bytes)}",
                            f"kv_cache={human_bytes(estimate.kv_cache_bytes)}",
                        ]
                    )
                )
                monitor.refresh()
                continue
            if prompt.lower() == "/kv" or prompt.lower().startswith("/kv "):
                _, _, requested = prompt.partition(" ")
                requested = requested.strip().lower()
                if not requested:
                    selected = _kv_picker(kv_cache_precision)
                    if selected is None:
                        show(
                            f"kv_precision={kv_cache_precision}\n"
                            "usage: /kv [auto|u4|u8|f16]"
                        )
                        continue
                    requested = selected
                try:
                    next_kv_precision = normalize_kv_cache_precision(requested)
                except ValueError as exc:
                    show(str(exc))
                    continue
                unloaded = False
                if next_kv_precision != kv_cache_precision:
                    push_snapshot()
                    unloaded = unload_engine()
                    kv_cache_precision = next_kv_precision
                    config = _load_config()
                    config["kv_cache_precision"] = kv_cache_precision
                    _save_config(config)
                estimate = estimate_model_memory(
                    model_dir,
                    context_length,
                    kv_cache_precision,
                )
                show(
                    "\n".join(
                        [
                            f"kv_precision={kv_cache_precision}",
                            f"estimated_kv={human_bytes(estimate.kv_cache_bytes)}",
                            f"estimated_ram={human_bytes(estimate.total_bytes)}",
                            f"model_unloaded={'yes' if unloaded else 'no'}",
                            "applies_on=next model load",
                        ]
                    )
                )
                monitor.refresh()
                continue
            if prompt.lower().startswith("/max-tokens"):
                _, _, value = prompt.partition(" ")
                if value.strip():
                    try:
                        next_max_tokens = int(value.strip())
                    except ValueError:
                        show("max-tokens must be number")
                        continue
                    if next_max_tokens < 1 or next_max_tokens > context_length:
                        show(f"max-tokens must be between 1 and ctx ({context_length})")
                        continue
                    push_snapshot()
                    max_new_tokens = next_max_tokens
                show(f"max_new_tokens={max_new_tokens}\nctx={context_length}")
                continue
            if prompt.lower() == "/api" or prompt.lower().startswith("/api "):
                parts = prompt.split()
                action = parts[1].lower() if len(parts) > 1 else "status"
                if action not in {"status", "start", "stop"}:
                    show("usage: /api [start [port]|stop|status]")
                    continue
                if action == "stop":
                    try:
                        stopped = stop_api_process()
                    except Exception as exc:
                        show(f"API failed: {exc}")
                    else:
                        show("api: stopped" if stopped else "api: already stopped")
                    continue
                if action == "status":
                    show(format_api_status(api_status()))
                    continue
                api_port = DEFAULT_API_PORT
                if len(parts) > 2:
                    try:
                        api_port = int(parts[2])
                    except ValueError:
                        show("API port must be a number")
                        continue
                push_snapshot()
                unloaded = unload_engine()
                if unloaded:
                    redraw_tui_history()
                try:
                    status = start_api_process(
                        model_dir,
                        host=DEFAULT_API_HOST,
                        port=api_port,
                        device=device,
                        context_length=context_length,
                        kv_cache_precision=kv_cache_precision,
                    )
                except Exception as exc:
                    show(f"API failed: {exc}")
                    continue
                text = format_api_status(status)
                if unloaded:
                    text += "\nchat model: unloaded to avoid duplicate RAM"
                show(text)
                continue
            if prompt.lower() == "/tools":
                show("tools: pwd, ls, read, scan, grep, write, append, shell, storage, web_search, web_fetch, diff, undo, chart, big, tilt")
                continue
            if prompt.lower().startswith("/chart "):
                _, _, data = prompt.partition(" ")
                try:
                    show(render_chart(data))
                except ValueError as exc:
                    show(str(exc))
                continue
            if prompt.lower().startswith("/big "):
                _, _, text = prompt.partition(" ")
                show(render_big_text(text))
                continue
            if prompt.lower().startswith("/tilt "):
                _, _, text = prompt.partition(" ")
                show(render_tilt_text(text))
                continue
            if prompt.lower() in {"/model", "/models pick"}:
                action, value = _model_picker(active_model_dir=model_dir, loaded=engine is not None)
                if action == "list":
                    show(_model_list(model_dir, engine is not None))
                    continue
                if action == "cancel":
                    continue
                if action == "unload":
                    push_snapshot()
                    unloaded = unload_engine()
                    redraw_tui_history()
                    show("unloaded=yes" if unloaded else "unloaded=no")
                    continue
                if action == "download" and value:
                    try:
                        target = download_with_status(value)
                    except Exception as exc:
                        show(str(exc))
                        continue
                    show(f"downloaded={target}")
                    continue
                if action == "delete" and value:
                    deleting_active = MODEL_DIRS.get(value.lower()) == model_dir
                    if deleting_active:
                        unload_engine()
                    try:
                        target = delete_named_model(value)
                    except Exception as exc:
                        if deleting_active:
                            redraw_tui_history()
                        show(str(exc))
                        continue
                    if deleting_active:
                        redraw_tui_history()
                    show(f"deleted_model={target}")
                    continue
                if action == "load" and value:
                    next_model_dir = _resolve_model(value)
                    if not next_model_dir.exists():
                        show(f"model missing: {next_model_dir}")
                        continue
                    push_snapshot()
                    switched = next_model_dir != model_dir
                    if switched:
                        unload_engine()
                        session.reset()
                        model_dir = next_model_dir
                        estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                    ensure_engine()
                    if switched:
                        redraw_tui_history()
                    continue
            if prompt.lower() in {"/model list", "/models"}:
                show(_model_list(model_dir, engine is not None))
                continue
            if prompt.lower() == "/model load" or prompt.lower().startswith("/model load "):
                _, _, value = prompt.partition("/model load ")
                pushed = False
                if value.strip():
                    next_model_dir = _resolve_model(value.strip())
                    if not next_model_dir.exists():
                        show(f"model missing: {next_model_dir}")
                        continue
                    if next_model_dir != model_dir:
                        push_snapshot()
                        pushed = True
                        unload_engine()
                        session.reset()
                        model_dir = next_model_dir
                        estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                if not pushed:
                    push_snapshot()
                ensure_engine()
                if pushed:
                    redraw_tui_history()
                continue
            if prompt.lower() == "/model unload":
                push_snapshot()
                unloaded = unload_engine()
                redraw_tui_history()
                show("unloaded=yes" if unloaded else "unloaded=no")
                continue
            if prompt.lower().startswith("/model download "):
                _, _, value = prompt.partition("/model download ")
                try:
                    target = download_with_status(value.strip())
                except Exception as exc:
                    show(str(exc))
                    continue
                show(f"downloaded={target}")
                continue
            if prompt.lower().startswith("/model delete "):
                _, _, value = prompt.partition("/model delete ")
                model_name = value.strip().lower()
                deleting_active = MODEL_DIRS.get(model_name) == model_dir
                if deleting_active:
                    unload_engine()
                try:
                    target = delete_named_model(model_name)
                except Exception as exc:
                    if deleting_active:
                        redraw_tui_history()
                    show(str(exc))
                    continue
                if deleting_active:
                    redraw_tui_history()
                show(f"deleted_model={target}")
                continue
            if prompt.lower().startswith("/model use ") or (
                prompt.lower().startswith("/model ") and prompt.lower() not in {"/model list"}
            ):
                if prompt.lower().startswith("/model use "):
                    _, _, value = prompt.partition("/model use ")
                else:
                    _, _, value = prompt.partition(" ")
                next_model_dir = _resolve_model(value.strip())
                if not next_model_dir.exists():
                    show(f"model missing: {next_model_dir}")
                    continue
                push_snapshot()
                unload_engine()
                session.reset()
                model_dir = next_model_dir
                estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                redraw_tui_history()
                show(
                    "\n".join(
                        [
                            f"model={model_dir}",
                            "loaded=no",
                            f"est_ram={human_bytes(estimate.total_bytes)}",
                        ]
                    )
                )
                continue
            if prompt.lower() == "/workspace":
                show(f"workspace={session.tools.workspace_root}\ncwd={session.tools.cwd}")
                continue
            if prompt.lower().startswith("/workspace set "):
                _, _, path = prompt.partition("/workspace set ")
                try:
                    push_snapshot()
                    session.tools.set_workspace(Path(path.strip()))
                except ValueError as exc:
                    snapshots.pop()
                    show(str(exc))
                    continue
                show(f"workspace={session.tools.workspace_root}")
                continue
            if prompt.lower().startswith("/cd "):
                _, _, path = prompt.partition(" ")
                try:
                    push_snapshot()
                    session.tools.set_cwd(Path(path.strip()))
                except ValueError as exc:
                    snapshots.pop()
                    show(str(exc))
                    continue
                show(f"cwd={session.tools.cwd}")
                continue
            if prompt.lower() == "/permissions":
                show(f"permissions={session.tools.permission_mode}")
                continue
            if prompt.lower() in {"/permissions ask", "/permissions allow"}:
                push_snapshot()
                session.tools.permission_mode = prompt.rsplit(" ", 1)[1]
                show(f"permissions={session.tools.permission_mode}")
                continue
            if prompt.lower() == "/project":
                show(_project_status(session.tools.cwd))
                continue
            if prompt.lower().startswith("/export"):
                _, _, path_text = prompt.partition(" ")
                target = Path(path_text.strip() or (EXPORT_DIR / "openvino-chat.md"))
                if not target.is_absolute():
                    target = session.tools.cwd / target
                _export_markdown(target, session.history)
                show(f"exported={target}")
                continue
            if prompt.lower().startswith("/system"):
                push_snapshot()
                show(_handle_system_command(prompt, session, session.tools.cwd))
                continue
            if prompt.lower() in {"/mode", "/mode chat", "/mode agent"}:
                if prompt.lower() == "/mode chat":
                    push_snapshot()
                    session.tools_enabled = False
                elif prompt.lower() == "/mode agent":
                    push_snapshot()
                    session.tools_enabled = True
                show("mode=agent" if session.tools_enabled else "mode=chat")
                continue
            if prompt.lower() == "/session":
                action, value = _session_picker(store=sessions, active_session=active_session)
                if action == "list":
                    names = sessions.list_sessions()
                    show("\n".join(names) if names else "no saved sessions")
                    continue
                if action == "cancel":
                    continue
                if action == "save":
                    name = auto_save_session()
                    show(f"saved={name}" if name else "nothing to save")
                    continue
                if action == "new":
                    auto_save_session()
                    push_snapshot()
                    active_session = _auto_session_name([])
                    session.reset()
                    redraw_tui_history()
                    show(f"new session: {active_session}")
                    continue
                if action == "delete" and value:
                    sessions.delete(value)
                    show(f"deleted={value}")
                    continue
                if action == "load" and value:
                    auto_save_session()
                    push_snapshot()
                    session.history = sessions.load(value)
                    active_session = value
                    redraw_tui_history()
                    show(f"loaded={active_session}")
                    continue
            if prompt.lower() == "/delete":
                name = active_session
                if name == "default" and session.history:
                    saved = auto_save_session()
                    name = saved or name
                if name != "default":
                    sessions.delete(name)
                    show(f"deleted session={name}")
                else:
                    show("nothing to delete")
                return 0
            if prompt.lower() == "/sessions":
                names = sessions.list_sessions()
                show("\n".join(names) if names else "no saved sessions")
                continue
            if prompt.lower().startswith("/new"):
                _, _, name = prompt.partition(" ")
                push_snapshot()
                active_session = name.strip() or "default"
                session.reset()
                redraw_tui_history()
                show(f"new session: {active_session}")
                continue
            if prompt.lower().startswith("/save"):
                _, _, name = prompt.partition(" ")
                active_session = name.strip() or active_session
                path = _save_session(sessions, active_session, session.history, model_name_from_dir(model_dir), active_device())
                show(f"saved={path}")
                continue
            if prompt.lower().startswith("/load "):
                _, _, name = prompt.partition(" ")
                push_snapshot()
                session.history = sessions.load(name.strip())
                active_session = name.strip()
                redraw_tui_history()
                show(f"loaded={active_session}")
                continue
            if prompt.lower().startswith("/delete "):
                _, _, name = prompt.partition(" ")
                sessions.delete(name.strip())
                show(f"deleted={name.strip()}")
                continue
            if not prompt:
                continue
            request = parse_slash_tool(prompt)
            if request is not None:
                if use_live_work_ui():
                    monitor.start()
                try:
                    if use_live_work_ui():
                        monitor.set(status_label(request.name))
                    request_text = format_tool_request_text(request.name, request.args)
                    if use_live_work_ui() and monitor.active:
                        monitor.write_response(request_text, "dim", "\n")
                    elif not defer_output():
                        ui.tool_request(request.name, request.args)
                    result = session.tools.run(request).output
                    if use_live_work_ui() and monitor.active:
                        monitor.write_response(result, None, "\n")
                    elif defer_output():
                        show(f"{request_text}\n{result}")
                    else:
                        ui.tool_result(result)
                finally:
                    if use_live_work_ui():
                        _clear_monitor(monitor, refresh=False)
                        monitor.stop()
                continue
            if not ensure_engine():
                continue
            push_snapshot()
            response = ask_model(prompt)
            if response is None:
                continue
            tasks.update_from_text(response)
            auto_save_session()
    finally:
        monitor.stop()


def _ask_session(
    session: ToolChatSession,
    ui: ChatUI,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    context_length: int,
    monitor: LiveStatusMonitor | None = None,
    stop_checker: Callable[[], bool] | None = None,
) -> str:
    if monitor is not None:
        monitor.start()
    stream = (
        monitor.response_stream()
        if monitor is not None and getattr(monitor, "active", False)
        else ui.response_stream()
    )

    def on_event(event: dict[str, object]) -> None:
        phase = str(event.get("phase") or "")
        if phase == "tool":
            tool = str(event.get("tool") or "")
            args = event.get("args")
            stream.finish()
            if monitor is not None:
                monitor.set(status_label(tool))
            if isinstance(args, dict):
                if monitor is not None and getattr(monitor, "active", False):
                    monitor.write_response(format_tool_request_text(tool, args), "dim", "\n")
                else:
                    ui.tool_request(tool, args)
            return
        if phase and monitor is not None:
            monitor.set(phase)

    interrupt = None if stop_checker is not None else EscInterrupt()
    try:
        if interrupt is not None:
            interrupt.start()

        def should_stop() -> bool:
            return bool(interrupt and interrupt.should_stop()) or bool(stop_checker and stop_checker())

        return session.ask(
            prompt,
            on_token=stream.write,
            on_event=on_event,
            should_stop=should_stop,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            context_length=context_length,
        )
    finally:
        if interrupt is not None:
            interrupt.stop()
        stream.finish()
        if monitor is not None:
            _clear_monitor(monitor, refresh=False)
            monitor.stop()


def _clear_monitor(monitor: object, refresh: bool = True) -> None:
    clear = getattr(monitor, "clear")
    try:
        clear(refresh=refresh)
    except TypeError:
        clear()


def _live_status_text(
    device: str,
    context_length: int,
    kv_cache_precision: str = "auto",
) -> str:
    return format_live_status(
        device,
        context_length,
        kv_cache_precision=kv_cache_precision,
    )


def _chat_window_text(
    history: list[tuple[str, str]],
    display_messages: list[tuple[int, str]] | None = None,
    max_turns: int = 12,
    raw: bool = False,
) -> str:
    display_messages = display_messages or []
    if not history and not display_messages:
        return "No messages yet."
    lines: list[str] = []
    start_index = max(0, len(history) - max_turns)
    visible_history = history[start_index:]
    messages_by_position: dict[int, list[str]] = {}
    for position, message in display_messages:
        if position >= start_index:
            messages_by_position.setdefault(position, []).append(message)

    def append_messages(position: int) -> None:
        for message in messages_by_position.get(position, []):
            lines.append("openvino:")
            lines.append(_chat_content(message, raw))
            lines.append("")

    append_messages(start_index)
    for offset, (role, content) in enumerate(visible_history, start=start_index):
        if role == "user":
            lines.append("> " + _chat_content(content, raw))
        else:
            lines.append(_assistant_chat_content(content, raw))
        lines.append("")
        append_messages(offset + 1)
    return "\n".join(lines).strip()


def _chat_content(text: str, raw: bool) -> str:
    clean = _ANSI_ESCAPE.sub("", text)
    if raw:
        return clean
    thinking, answer = split_thinking(clean)
    parts = []
    if thinking:
        parts.append(f"{tui_mod.GRAY}{thinking}\x1b[0m")
    if answer:
        parts.append(
            tui_mod._render_terminal_markup(answer).rstrip("\n")
            if tui_mod._has_terminal_markup(answer)
            else answer
        )
    return "\n".join(parts).strip()


def _assistant_chat_content(text: str, raw: bool) -> str:
    clean = _ANSI_ESCAPE.sub("", text)
    if raw:
        return f"{tui_mod.GREEN}> \x1b[0m{clean}"
    thinking, answer = split_thinking(clean)
    parts = []
    if thinking:
        parts.append(f"{tui_mod.GRAY}{thinking}\x1b[0m")
    if answer:
        rendered = (
            tui_mod._render_terminal_markup(answer).rstrip("\n")
            if tui_mod._has_terminal_markup(answer)
            else answer
        )
        parts.append(f"{tui_mod.GREEN}> \x1b[0m{rendered}")
    return "\n".join(parts).strip()


def _last_assistant_message(history: list[tuple[str, str]]) -> str:
    return next((content for role, content in reversed(history) if role == "assistant"), "")


def _copy_to_clipboard(text: str) -> bool:
    commands = []
    if os.name == "nt":
        commands.append(["clip"])
    elif shutil.which("pbcopy"):
        commands.append(["pbcopy"])
    elif shutil.which("wl-copy"):
        commands.append(["wl-copy"])
    elif shutil.which("xclip"):
        commands.append(["xclip", "-selection", "clipboard"])
    for command in commands:
        try:
            subprocess.run(command, input=text, text=True, check=True, capture_output=True, timeout=5)
            return True
        except Exception:
            continue
    return False


def _stats_text(
    sessions: ChatSessionStore,
    history: list[tuple[str, str]],
    model_dir: Path,
    loaded: bool,
    tools: ToolRegistry,
    context_length: int,
) -> str:
    names = sessions.list_sessions()
    saved_messages = 0
    model_counts: dict[str, int] = {}
    for name in names:
        try:
            metadata = sessions.metadata(name)
        except Exception:
            try:
                saved_messages += len(sessions.load(name))
            except Exception:
                continue
        else:
            saved_messages += int(metadata.get("message_count") or 0)
            model = str(metadata.get("model") or "").strip()
            if model:
                model_counts[model] = model_counts.get(model, 0) + 1
    current_messages = len(history)
    lines = [
        f"sessions={len(names)}",
        f"messages={saved_messages + current_messages}",
        f"current_messages={current_messages}",
        f"active_model={model_name_from_dir(model_dir)}",
        f"loaded={'yes' if loaded else 'no'}",
        f"ctx={context_length}",
        f"models_available={_available_models_summary()}",
        f"tool_changes={len(getattr(tools, '_changes', []))}",
    ]
    if model_counts:
        lines.append("session_models=" + ", ".join(f"{name}:{count}" for name, count in sorted(model_counts.items())))
    return "\n".join(lines)


def _export_markdown(path: Path, history: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# OpenVINO Chat", ""]
    for role, content in history:
        lines.append(f"## {role}")
        lines.append("")
        lines.append(content)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _handle_system_command(prompt: str, session: ToolChatSession, cwd: Path) -> str:
    command = prompt.strip()
    lower = command.lower()
    if lower in {"/system", "/system show"}:
        return session.system_prompt_template
    if lower == "/system reset":
        session.system_prompt_template = TOOL_SYSTEM_PROMPT
        return "system reset"
    if lower.startswith("/system set "):
        _, _, text = command.partition("/system set ")
        session.system_prompt_template = _decode_system_text(text)
        return "system set"
    if lower.startswith("/system append "):
        _, _, text = command.partition("/system append ")
        addition = _decode_system_text(text)
        session.system_prompt_template = session.system_prompt_template.rstrip() + "\n" + addition
        return "system appended"
    if lower.startswith("/system save"):
        _, _, text = command.partition(" ")
        _, _, path_text = text.partition(" ")
        target = _resolve_user_path(path_text.strip() or "openvino-system-prompt.txt", cwd)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(session.system_prompt_template, encoding="utf-8")
        return f"system saved={target}"
    if lower.startswith("/system load "):
        _, _, path_text = command.partition("/system load ")
        source = _resolve_user_path(path_text.strip(), cwd)
        session.system_prompt_template = source.read_text(encoding="utf-8")
        return f"system loaded={source}"
    _, _, text = command.partition(" ")
    if text.strip():
        session.system_prompt_template = _decode_system_text(text)
        return "system set"
    return session.system_prompt_template


def _decode_system_text(text: str) -> str:
    return text.strip().replace("\\n", "\n")


def _resolve_user_path(path_text: str, cwd: Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return cwd / path


def _help_text() -> str:
    return (
        _format_command_specs("OpenVINO Chat commands")
        + "\n\nKeys:"
        + "\n  Esc                         Stop current generation."
        + "\n  PageUp / PageDown           Scroll chat history."
        + "\n  Mouse wheel                 Scroll chat history."
        + "\n  Ctrl+Home / Ctrl+End        Oldest / latest message."
    )


def _commands_text() -> str:
    return _format_command_specs("Command Palette")


def _format_command_specs(title: str) -> str:
    lines = [title, ""]
    groups = []
    for spec in COMMAND_SPECS:
        if spec.group not in groups:
            groups.append(spec.group)
    for group in groups:
        lines.append(f"{group}:")
        for spec in COMMAND_SPECS:
            if spec.group == group:
                lines.append(f"  {spec.usage:<28} {spec.description}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _project_status(cwd: Path) -> str:
    lines = [f"cwd={cwd}"]
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=5,
        )
        if branch.returncode == 0 and branch.stdout.strip():
            lines.append(f"branch={branch.stdout.strip()}")
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=5,
        )
        if status.returncode == 0:
            dirty = status.stdout.strip()
            lines.append("dirty=yes" if dirty else "dirty=no")
            if dirty:
                lines.append(dirty)
    except Exception:
        lines.append("git=unavailable")
    return "\n".join(lines)


def _resolve_model(value: str) -> Path:
    key = value.lower()
    if key in MODEL_DIRS:
        return MODEL_DIRS[key]
    return Path(value).expanduser()


def _available_models_summary() -> str:
    return ", ".join(f"{name}: {_model_install_state(path)}" for name, path in MODEL_DIRS.items())


def _model_list(active_model_dir: Path, loaded: bool) -> str:
    lines = [
        "Available models",
        f"active: {active_model_dir}",
        f"loaded: {'yes' if loaded else 'no'}",
        f"root: {MODEL_ROOT}",
        "",
    ]
    for name, path in MODEL_DIRS.items():
        marker = "*" if path == active_model_dir else " "
        state = _model_install_state(path)
        size = _model_dir_size_text(path)
        repo = MODEL_REPOS.get(name, "-")
        active = " active" if path == active_model_dir else ""
        loaded_text = " loaded" if path == active_model_dir and loaded else ""
        lines.append(f"{marker} {name}: {state}{active}{loaded_text}")
        lines.append(f"  repo: {repo}")
        lines.append(f"  size: {size}")
        lines.append(f"  path: {path}")
    return "\n".join(lines)


def _model_install_state(path: Path) -> str:
    return "installed" if path.exists() else "missing"


def _model_dir_size_text(path: Path) -> str:
    if not path.exists():
        return "-"
    if path.is_file():
        return human_bytes(path.stat().st_size)
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return human_bytes(total)
