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
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openvino_chat.agent import ToolChatSession
from openvino_chat.benchmarks import BenchmarkStore
from openvino_chat.api import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    api_status,
    format_api_status,
    run_api_server,
    start_api_process,
    stop_api_process,
)
from openvino_chat.download import (
    delete_named_model,
    download_named_model,
    is_hf_repo_reference,
    is_openvino_model_dir,
)
from openvino_chat.engine import (
    OpenVinoChatEngine,
    load_engine,
    model_name_from_dir,
    normalize_kv_cache_precision,
)
from openvino_chat.knowledge import KnowledgeStore
from openvino_chat.perf import estimate_model_memory, format_live_status, format_perf_status, get_cpu_usage, get_gpu_usage, get_ram_usage, human_bytes
from openvino_chat.sessions import ChatSessionStore
from openvino_chat.settings import (
    CONFIG_PATH,
    DEFAULT_AUTO_COMPACT,
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_DUCK_MODE,
    DEFAULT_GENERATION_EFFORT,
    DEFAULT_KNOWLEDGE_MODE,
    DEFAULT_MODEL_DIR,
    DEFAULT_THINKING_EFFORT,
    EXPORT_DIR,
    GENERATION_EFFORTS,
    MODEL_DIRS,
    MODEL_REPOS,
    MODEL_ROOT,
    REPORT_DIR,
    coerce_thinking_effort,
    discover_model_dirs,
    generation_settings,
    model_repo_for_path,
    normalize_generation_effort,
    normalize_knowledge_mode,
    normalize_auto_compact,
    normalize_duck_mode,
    normalize_thinking_effort,
    package_install_command,
    resolve_thinking_effort,
    thinking_efforts_for_model,
)
from openvino_chat import tui as tui_mod
from openvino_chat.tasks import TaskList, has_visible_tasks
from openvino_chat.tools import ToolRegistry, parse_slash_tool
from openvino_chat.ui import (
    ChatUI,
    LiveStatusMonitor,
    format_tool_request_text,
    sanitize_tool_artifacts,
    split_thinking,
    status_label,
)
from openvino_chat.visuals import (
    QUACK_PORTRAIT,
    QUACK_PORTRAIT_SMALL,
    extract_visual_panel,
    render_big_text,
    render_chart,
    render_tilt_text,
)


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
        self._buffer.append_system(value)
        self._invalidate()

    def print_plain(self, text="", end="\n") -> None:
        value = str(text)
        if end and not value.endswith(end):
            value = value + end
        self._buffer.append_system(value)
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
    duck_mode: bool = False,
) -> str:
    name = model_name_from_dir(model_dir)
    accent = tui_mod.ORANGE if duck_mode else tui_mod.CYAN
    if duck_mode:
        terminal = shutil.get_terminal_size(fallback=(80, 30))
        portrait = (
            QUACK_PORTRAIT
            if terminal.columns >= 72 and terminal.lines >= 46
            else QUACK_PORTRAIT_SMALL
        )
        stars = _quack_welcome_portrait(portrait)
    else:
        stars = f"{accent}OpenVINO Chat{tui_mod.RESET}"
    meta = (
        f"model {name} | device {device} | loaded {'yes' if loaded else 'no'} | "
        f"ctx {context_length} | kv {kv_cache_precision}"
    )
    hint = (
        f"{tui_mod.DIM}Type / for commands  |  Drag select  |  "
        f"F6 mouse scroll  |  Esc stop{tui_mod.RESET}"
    )
    return f"{stars}\n{meta}\n{hint}\n"


def _quack_welcome_portrait(portrait: str = QUACK_PORTRAIT) -> str:
    light = f"{tui_mod.YELLOW}{tui_mod.BOLD}"
    dark = f"{tui_mod.ORANGE}{tui_mod.BOLD}"
    dark_chars = frozenset("@%#*+=")
    rendered: list[str] = []
    plain_lines = portrait.splitlines()
    for line in plain_lines:
        chunks: list[str] = []
        active = ""
        for char in line.rstrip():
            color = dark if char in dark_chars else light
            if color != active:
                chunks.append(color)
                active = color
            chunks.append(char)
        chunks.append(tui_mod.RESET)
        rendered.append("".join(chunks))
    width = max((len(line.rstrip()) for line in plain_lines), default=0)
    rendered.append(f"{dark}{'OpenVINO Quack'.center(width)}{tui_mod.RESET}")
    rendered.append(f"{light}{'LOUD MODE // ON'.center(width)}{tui_mod.RESET}")
    return "\n".join(rendered)


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
    CommandSpec("Chat", "/rewind", "/rewind", "Undo one turn or command (repeatable)."),
    CommandSpec("Chat", "/redo", "/redo", "Reapply one rewind (repeatable)."),
    CommandSpec("Chat", "/compact", "/compact [status|auto on|auto off]", "Compact older context."),
    CommandSpec("Chat", "/reset", "/reset", "Clear current chat memory."),
    CommandSpec("Chat", "/clear", "/clear", "Clear screen and redraw banner."),
    CommandSpec("Chat", "/archive", "/archive", "Save current session and quit."),
    CommandSpec("Chat", "/exit", "/exit", "Quit."),
    CommandSpec("UI", "/ui", "/ui", "Show UI layout."),
    CommandSpec("UI", "/sidepanel", "/sidepanel [on|off]", "Show or hide responsive side panel."),
    CommandSpec("UI", "/chart", "/chart a=2 b=4", "Show bar chart in visual panel."),
    CommandSpec("UI", "/big", "/big <text>", "Show block letters in visual panel."),
    CommandSpec("UI", "/tilt", "/tilt <text>", "Show slanted text in visual panel."),
    CommandSpec("Models", "/model", "/model", "Open model picker."),
    CommandSpec("System Prompt", "/system", "/system", "Show current system prompt."),
    CommandSpec("Personality", "/duck", "/duck [on|off]", "Toggle loud Quack personality for every task."),
    CommandSpec("Reasoning", "/effort", "/effort [low|medium|high|custom]", "Set model sampling effort."),
    CommandSpec("Reasoning", "/thinking", "/thinking", "Set model-native thinking mode."),
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
    CommandSpec("Knowledge", "/knowledge", "/knowledge", "Manage local documents and web mode."),
    CommandSpec("API", "/api", "/api", "Show local OpenAI API status."),
    CommandSpec("Workspace", "/workspace", "/workspace", "Show workspace and cwd."),
    CommandSpec("Workspace", "/cd", "/cd <path>", "Change tool cwd inside workspace."),
    CommandSpec("Workspace", "/project", "/project", "Show git project status."),
    CommandSpec("Workspace", "/permissions", "/permissions", "Open permission picker."),
    CommandSpec("Tools", "/tools", "/tools", "List tools."),
    CommandSpec("Tools", "/pwd", "/pwd", "Print tool cwd."),
    CommandSpec("Tools", "/ls", "/ls [path]", "List files."),
    CommandSpec("Tools", "/read", "/read <path>", "Read file."),
    CommandSpec("Tools", "/scan", "/scan [path]", "List project files."),
    CommandSpec("Tools", "/grep", "/grep <pattern> [-- <path>]", "Search files."),
    CommandSpec("Tools", "/write", "/write <path> <text>", "Write file."),
    CommandSpec("Tools", "/append", "/append <path> <text>", "Append file."),
    CommandSpec("Tools", "/shell", "/shell <command>", "Run shell command."),
    CommandSpec("Tools", "/storage", "/storage [path]", "Show disk usage."),
    CommandSpec("Tools", "/startup", "/startup", "List startup applications."),
    CommandSpec("Tools", "/web", "/web <query>", "Search web."),
    CommandSpec("Tools", "/fetch", "/fetch <url>", "Fetch webpage."),
    CommandSpec("Tools", "/diff", "/diff", "Show tracked tool file changes."),
    CommandSpec("Tools", "/undo", "/undo [tool]", "Undo last tracked tool file change."),
    CommandSpec("Tasks", "/task", "/task", "Show task list."),
    CommandSpec("Tasks", "/plan", "/plan <goal>", "Create task plan from model."),
    CommandSpec("Tasks", "/review", "/review", "Review current git/tool diff."),
    CommandSpec("Sessions", "/session", "/session", "Open session picker."),
    CommandSpec("Sessions", "/sessions", "/sessions", "List saved sessions."),
    CommandSpec("Sessions", "/new", "/new [name]", "Start new empty session."),
    CommandSpec("Sessions", "/save", "/save [name]", "Save chat history."),
    CommandSpec("Sessions", "/load", "/load <name>", "Load saved history."),
    CommandSpec("Sessions", "/delete", "/delete [name]", "Delete current or named session."),
    CommandSpec("Sessions", "/export", "/export [path]", "Export chat as markdown."),
)

ADVANCED_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec("Chat", "/raw on", "/raw on", "Show raw model protocol text."),
    CommandSpec("Chat", "/raw off", "/raw off", "Render thoughts, tools, and Markdown."),
    CommandSpec("Chat", "/compact status", "/compact status", "Show context compaction state."),
    CommandSpec("UI", "/ui window", "/ui window", "Full terminal chat window."),
    CommandSpec("UI", "/ui statusline", "/ui statusline", "Bottom statusline."),
    CommandSpec("UI", "/ui side", "/ui side", "Side live panel."),
    CommandSpec("Models", "/model use", "/model use <name|path>", "Select model."),
    CommandSpec("Models", "/model import", "/model import <path|owner/repo>", "Select local model or download OpenVINO model from Hugging Face."),
    CommandSpec("Models", "/model load", "/model load [name|path]", "Load current or selected model."),
    CommandSpec("Models", "/model list", "/model list", "List configured models."),
    CommandSpec("Models", "/model unload", "/model unload", "Unload current model."),
    CommandSpec("Models", "/model download", "/model download <name|owner/repo>", "Install built-in or Hugging Face OpenVINO model."),
    CommandSpec("Models", "/model delete", "/model delete <name>", "Delete model."),
    CommandSpec("System Prompt", "/system set", "/system set <text>", "Replace system prompt."),
    CommandSpec("System Prompt", "/system show", "/system show", "Show current system prompt."),
    CommandSpec("System Prompt", "/system append", "/system append <text>", "Append to system prompt."),
    CommandSpec("System Prompt", "/system reset", "/system reset", "Restore default system prompt."),
    CommandSpec("System Prompt", "/system save", "/system save [path]", "Save system prompt."),
    CommandSpec("System Prompt", "/system load", "/system load <path>", "Load system prompt."),
    CommandSpec("Context and Performance", "/config set", "/config set <key> <value>", "Update config."),
    CommandSpec("Context and Performance", "/compact auto", "/compact auto <on|off>", "Configure automatic compaction."),
    CommandSpec("Knowledge", "/knowledge mode", "/knowledge mode <offline|auto|web>", "Set knowledge mode."),
    CommandSpec("Knowledge", "/knowledge add", "/knowledge add <path>", "Index a document or folder."),
    CommandSpec("Knowledge", "/knowledge search", "/knowledge search <query>", "Search indexed documents."),
    CommandSpec("Knowledge", "/knowledge setup", "/knowledge setup", "Install OpenVINO embedding and reranking models."),
    CommandSpec("Knowledge", "/knowledge list", "/knowledge list", "List indexed document sources."),
    CommandSpec("Knowledge", "/knowledge reindex", "/knowledge reindex", "Rebuild local document index."),
    CommandSpec("Knowledge", "/knowledge clear", "/knowledge clear", "Clear local document index."),
    CommandSpec("API", "/api start", "/api start [port]", "Start lazy local API server."),
    CommandSpec("API", "/api status", "/api status", "Show local API server status."),
    CommandSpec("API", "/api stop", "/api stop", "Stop local API server."),
    CommandSpec("Workspace", "/workspace set", "/workspace set <path>", "Set workspace root."),
    CommandSpec("Workspace", "/permissions ask", "/permissions ask", "Ask before tool actions."),
    CommandSpec("Workspace", "/permissions allow", "/permissions allow", "Always allow tool actions."),
    CommandSpec("Tasks", "/task add", "/task add <text>", "Add task."),
    CommandSpec("Tasks", "/task done", "/task done <n>", "Mark task done."),
    CommandSpec("Tasks", "/task clear", "/task clear", "Clear tasks."),
    CommandSpec("Tasks", "/task list", "/task list", "List tasks."),
)

SLASH_COMMAND_POPUP_LIMIT = 15
REWIND_HISTORY_LIMIT = 50
SESSION_TIMELINE_EXCLUDED_COMMANDS = {
    "/archive",
    "/delete",
    "/exit",
    "/load",
    "/new",
    "/quit",
    "/save",
    "/session",
    "/sessions",
}
SLASH_TOP_COMMANDS = (
    "/help",
    "/model",
    "/session",
    "/rewind",
    "/redo",
    "/status",
    "/tools",
    "/permissions",
    "/ctx",
    "/compact",
    "/kv",
    "/effort",
    "/duck",
    "/system",
    "/exit",
)

EXACT_USAGE_COMMANDS = {
    "/chart": "/chart a=2 b=4",
    "/big": "/big <text>",
    "/tilt": "/tilt <text>",
    "/model download": "/model download <name|owner/repo>",
    "/model delete": "/model delete <name>",
    "/model use": "/model use <name|path>",
    "/model import": "/model import <path|owner/repo>",
    "/system set": "/system set <text>",
    "/system append": "/system append <text>",
    "/system load": "/system load <path>",
    "/config set": "/config set <key> <value>",
    "/compact auto": "/compact auto <on|off>",
    "/knowledge mode": "/knowledge mode <offline|auto|web>",
    "/knowledge add": "/knowledge add <path>",
    "/knowledge search": "/knowledge search <query>",
    "/workspace set": "/workspace set <path>",
    "/cd": "/cd <path>",
    "/read": "/read <path>",
    "/grep": "/grep <pattern> [-- <path>]",
    "/write": "/write <path> <text>",
    "/append": "/append <path> <text>",
    "/shell": "/shell <command>",
    "/web": "/web <query>",
    "/fetch": "/fetch <url>",
    "/plan": "/plan <goal>",
    "/task add": "/task add <text>",
    "/task done": "/task done <n>",
    "/load": "/load <name>",
}

TRANSIENT_UI_COMMANDS = {
    "/model",
    "/session",
    "/rewind",
    "/redo",
    "/permissions",
    "/permissions ask",
    "/permissions allow",
    "/kv",
    "/effort",
    "/thinking",
    "/duck",
    "/sidepanel",
    "/sidepanel on",
    "/sidepanel off",
    "/sidepannel",
    "/sidepannel on",
    "/sidepannel off",
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
    except Exception as exc:
        if exc.__class__.__name__ == "NoConsoleScreenBufferError":
            return input_fn(prompt_text)
        raise
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


def _prompt_style(duck_mode: bool = False):
    from prompt_toolkit.styles import Style

    if duck_mode:
        return Style.from_dict(
            {
                "bottom-toolbar": "noreverse bg:#160e05 #ffd166",
                "bottom-toolbar.secondary": "noreverse bg:#100a04 #e7a95a",
                "toolbar.title": "bold #ff9f1c",
                "toolbar.model": "bold #ffd08a",
                "toolbar.state": "#ffb347",
                "toolbar.label": "#ff9f1c",
                "toolbar.value": "#ffd166",
                "toolbar.sep": "#8a4b08",
                "input": "bg:#1a1007 #fff1dc",
                "input.prompt": "bold #ff9f1c",
                "text-area.prompt": "bold #ff9f1c",
                "separator": "#8a4b08",
                "task": "bg:#140c05 #ffdca0",
                "task.strip": "bg:#140c05 #ffdca0",
                "task.title": "bold #ff9f1c",
                "task.label": "#b99268",
                "task.value": "#ffd08a",
                "command-bar": "bg:#211308 #ffe7a8",
                "model-menu": "bg:#1c1107 #ffe7a8",
                "notice": "bg:#3a2108 #ffd08a",
                "operation.thinking": "#60a5fa",
                "operation.generating": "#facc15",
                "operation.tool": "#4ade80",
                "operation.loading": "#ff9f1c",
                "operation.default": "#d6b78f",
            }
        )
    return Style.from_dict(
        {
            "bottom-toolbar": "noreverse bg:#0c0c0f #71717a",
            "bottom-toolbar.secondary": "noreverse bg:#09090b #71717a",
            "toolbar.title": "bold #4ade80",
            "toolbar.model": "bold #e4e4e7",
            "toolbar.state": "#a3e635",
            "toolbar.label": "#38bdf8",
            "toolbar.value": "#9ca3af",
            "toolbar.sep": "#4b5563",
            "input": "bg:#111113 #f4f4f5",
            "input.prompt": "#d4d4d8",
            "text-area.prompt": "#d4d4d8",
            "separator": "#374151",
            "task": "bg:#0f0f12 #a1a1aa",
            "task.strip": "bg:#0f0f12 #a1a1aa",
            "task.title": "bold #38bdf8",
            "task.label": "#71717a",
            "task.value": "#a1a1aa",
            "command-bar": "bg:#18181b #e4e4e7",
            "model-menu": "bg:#141417 #e4e4e7",
            "notice": "bg:#17351f #bbf7d0",
            "operation.thinking": "#60a5fa",
            "operation.generating": "#facc15",
            "operation.tool": "#4ade80",
            "operation.loading": "#38bdf8",
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
    show_groups: bool | None = None,
) -> str:
    query = text.strip()
    if not query.startswith("/"):
        return ""
    usage_hint = _argument_usage_hint(text)
    matches = _slash_command_matches(query)
    if usage_hint is not None and (text.endswith(" ") or not matches):
        usage, description = usage_hint
        return f" usage: {usage}  {description}"
    if not matches:
        return " no matching slash commands"
    has_more = len(matches) > limit
    visible_limit = max(1, limit - 1) if has_more else limit
    selected = 0 if selected_index is None else max(0, min(selected_index, len(matches) - 1))
    start = 0
    if has_more:
        start = max(0, min(selected - visible_limit + 1, len(matches) - visible_limit))
    visible = matches[start : start + visible_limit]
    width = max(len(spec.command) for spec in visible)
    group_width = max(len(spec.group) for spec in visible)
    show_groups = query == "/" if show_groups is None else bool(show_groups and query == "/")
    lines = []
    for offset, spec in enumerate(visible):
        index = start + offset
        marker = ">" if selected == index else " "
        group = f"{spec.group:<{group_width}}  " if show_groups else ""
        lines.append(f"{marker} {spec.command:<{width}}  {group}{spec.description}")
    if has_more:
        above = start
        below = len(matches) - (start + len(visible))
        lines.append(f"  ... {above} above | {below} below")
    return "\n".join(lines)


def _slash_command_bar_height(text: str, limit: int = SLASH_COMMAND_POPUP_LIMIT) -> int:
    query = text.strip()
    if not query.startswith("/"):
        return 0
    usage_hint = _argument_usage_hint(text)
    matches = _slash_command_matches(query)
    if usage_hint is not None and (text.endswith(" ") or not matches):
        return 1
    if not matches:
        return 1
    return min(len(matches), limit)


def _argument_usage_hint(text: str) -> tuple[str, str] | None:
    query = text.strip().lower()
    for command in sorted(EXACT_USAGE_COMMANDS, key=len, reverse=True):
        if query == command or query.startswith(command + " "):
            description = next(
                (
                    spec.description
                    for spec in COMMAND_SPECS + ADVANCED_COMMAND_SPECS
                    if spec.command == command
                ),
                "Enter required value.",
            )
            return EXACT_USAGE_COMMANDS[command], description
    return None


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


def _command_matches(text: str, command: str) -> bool:
    value = text.strip().lower()
    expected = command.strip().lower()
    return value == expected or value.startswith(expected + " ")


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

    def input_width() -> int:
        columns = shutil.get_terminal_size((100, 30)).columns
        return max(1, columns - max(1, tui_mod._display_width(prompt_text)))

    def input_height() -> int:
        positions = tui_mod._visual_cursor_positions(input_area.text, input_width())
        terminal_rows = shutil.get_terminal_size((100, 30)).lines
        return max(1, min(max(row for row, _column in positions) + 1, max(1, min(8, terminal_rows // 3))))

    input_area = TextArea(
        prompt=prompt_text,
        multiline=True,
        wrap_lines=True,
        height=input_height,
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
    preferred_column: dict[str, int | None] = {"value": None}

    def reset_preferred(_buffer) -> None:
        preferred_column["value"] = None

    input_area.buffer.on_text_changed += reset_preferred

    @keys.add("enter")
    def _accept(event) -> None:
        event.app.exit(result=input_area.text)

    @keys.add("c-j")
    def _newline(_event) -> None:
        input_area.buffer.insert_text("\n")

    plain_input = Condition(lambda: not input_area.text.lstrip().startswith("/"))

    @keys.add("up", filter=plain_input, eager=True)
    def _input_up(_event) -> None:
        target, preferred = tui_mod._visual_cursor_target(
            input_area.text,
            input_area.buffer.cursor_position,
            input_width(),
            -1,
            preferred_column["value"],
        )
        preferred_column["value"] = preferred
        input_area.buffer.cursor_position = target

    @keys.add("down", filter=plain_input, eager=True)
    def _input_down(_event) -> None:
        target, preferred = tui_mod._visual_cursor_target(
            input_area.text,
            input_area.buffer.cursor_position,
            input_width(),
            1,
            preferred_column["value"],
        )
        preferred_column["value"] = preferred
        input_area.buffer.cursor_position = target

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
            input_area,
            toolbar,
        ]
    )
    app = Application(
        layout=Layout(body, focused_element=input_area),
        key_bindings=keys,
        full_screen=True,
        mouse_support=False,
        min_redraw_interval=0.03,
        max_render_postpone_time=0.03,
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
    catalog = _model_catalog()
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        items = [
            {
                "name": name,
                "state": _model_install_state(path),
                "size": _model_dir_size_text(path),
                "active": path == active_model_dir,
                "repo": _model_repo(name, path),
                "path": str(path),
                "effort": ", ".join(reversed(GENERATION_EFFORTS)),
                "thinking": ", ".join(reversed(thinking_efforts_for_model(path))),
            }
            for name, path in catalog.items()
        ]
        return mediator.request_model_picker(items, loaded)
    if not _can_use_fullscreen_picker():
        return ("list", None)

    entries = list(catalog.items())
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
            repo = _model_repo(name, path)
            lines.append(f"{marker} {name:<8} {exists:<9} {state_text:<10} {size:<10}{active}")
            lines.append(f"  repo: {repo}")
            lines.append("  effort: " + ", ".join(reversed(GENERATION_EFFORTS)))
            lines.append(
                "  thinking: " + ", ".join(reversed(thinking_efforts_for_model(path)))
            )
            lines.append(f"  path: {path}")
        return "\n".join(lines)

    return _run_picker(render, state, len(entries), selected, enter_action="load")


def _kv_picker(current: str) -> str | None:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        return mediator.request_kv_picker(current)
    return None


def _thinking_picker(current: str, supported: tuple[str, ...]) -> str | None:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        return mediator.request_thinking_picker(current, tuple(reversed(supported)))
    return None


def _effort_picker(current: str) -> str | None:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        picker = getattr(mediator, "request_effort_picker", None)
        if callable(picker):
            return picker(current, tuple(reversed(GENERATION_EFFORTS)))
    return None


def _custom_sampling_defaults(
    model_dir: Path,
    thinking_effort: str,
    current: dict[str, float | int] | None = None,
) -> dict[str, float | int]:
    values: dict[str, float | int] = {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 0.0,
        "repetition_penalty": 1.0,
    }
    values.update(
        generation_settings(
            model_name_from_dir(model_dir),
            "general",
            thinking_effort,
            generation_effort="medium",
        )
    )
    values.update(current or {})
    return _normalize_custom_sampling(values)


def _custom_sampling_picker(
    values: dict[str, float | int],
) -> dict[str, float | int] | None:
    mediator = tui_mod.active_mediator()
    if mediator is None:
        return None
    editor = getattr(mediator, "request_sampling_editor", None)
    return editor(values) if callable(editor) else None


def _duck_picker(current: bool) -> str | None:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        picker = getattr(mediator, "request_duck_picker", None)
        if callable(picker):
            return picker("on" if current else "off")
    return None


def _permission_picker(current: str) -> str | None:
    mediator = tui_mod.active_mediator()
    if mediator is not None:
        return mediator.request_permission_picker(current)
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
    state: dict[str, object] | None = None,
) -> Path:
    metadata = {
        "model": model_name,
        "device": device,
    }
    try:
        return sessions.save(name, history, metadata=metadata, state=state)
    except TypeError:
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
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_config(config: dict[str, str]) -> Path:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(config, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def _configured_kv_precision() -> str:
    try:
        return normalize_kv_cache_precision(_load_config().get("kv_cache_precision", "auto"))
    except ValueError:
        return "auto"


def _configured_thinking_effort() -> str:
    try:
        return normalize_thinking_effort(
            _load_config().get("thinking_effort", DEFAULT_THINKING_EFFORT)
        )
    except ValueError:
        return DEFAULT_THINKING_EFFORT


def _configured_generation_effort() -> str:
    try:
        return normalize_generation_effort(
            _load_config().get("generation_effort", DEFAULT_GENERATION_EFFORT)
        )
    except ValueError:
        return DEFAULT_GENERATION_EFFORT


SAMPLING_FIELDS = (
    "temperature",
    "top_p",
    "top_k",
    "min_p",
    "presence_penalty",
    "repetition_penalty",
)


def _normalize_custom_sampling(values: object) -> dict[str, float | int]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, float | int] = {}
    for key in SAMPLING_FIELDS:
        if key not in values:
            continue
        raw = values[key]
        try:
            value: float | int = int(raw) if key == "top_k" else float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be numeric") from None
        if key == "temperature" and not 0.0 <= value <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if key in {"top_p", "min_p"} and not 0.0 <= value <= 1.0:
            raise ValueError(f"{key} must be between 0 and 1")
        if key == "top_k" and not 1 <= value <= 1000:
            raise ValueError("top_k must be between 1 and 1000")
        if key == "presence_penalty" and not -2.0 <= value <= 2.0:
            raise ValueError("presence_penalty must be between -2 and 2")
        if key == "repetition_penalty" and not 0.01 <= value <= 2.0:
            raise ValueError("repetition_penalty must be between 0.01 and 2")
        result[key] = value
    return result


def _sampling_config_key(model_dir: Path) -> str:
    return "sampling." + Path(model_dir).name.casefold()


def _configured_custom_sampling(model_dir: Path) -> dict[str, float | int]:
    raw = _load_config().get(_sampling_config_key(model_dir), "")
    if not raw:
        return {}
    try:
        return _normalize_custom_sampling(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_custom_sampling(model_dir: Path, values: dict[str, float | int]) -> None:
    config = _load_config()
    config[_sampling_config_key(model_dir)] = json.dumps(values, separators=(",", ":"))
    _save_config(config)


def _parse_custom_sampling(
    text: str,
    baseline: dict[str, float | int],
) -> dict[str, float | int]:
    values = dict(baseline)
    for item in text.split():
        if "=" not in item:
            raise ValueError("custom values use name=value")
        key, raw = item.split("=", 1)
        key = key.strip().lower()
        if key not in SAMPLING_FIELDS:
            raise ValueError(f"unknown sampling value: {key}")
        values[key] = raw.strip()
    return _normalize_custom_sampling(values)


def _configured_duck_mode() -> bool:
    # Quack is an explicit per-session personality, never a startup preference.
    return DEFAULT_DUCK_MODE


def _thinking_effort_for_model(value: str, model_dir: Path) -> str:
    return coerce_thinking_effort(value, thinking_efforts_for_model(model_dir))


def _configured_auto_compact() -> bool:
    try:
        return normalize_auto_compact(
            _load_config().get("auto_compact", str(DEFAULT_AUTO_COMPACT))
        )
    except ValueError:
        return DEFAULT_AUTO_COMPACT


def _configured_context_length() -> int:
    try:
        value = int(_load_config().get("context_length", str(DEFAULT_CONTEXT_LENGTH)))
    except (TypeError, ValueError):
        return DEFAULT_CONTEXT_LENGTH
    return value if value >= 128 else DEFAULT_CONTEXT_LENGTH


def _configured_knowledge_mode() -> str:
    try:
        return normalize_knowledge_mode(
            _load_config().get("knowledge_mode", DEFAULT_KNOWLEDGE_MODE)
        )
    except ValueError:
        return DEFAULT_KNOWLEDGE_MODE


def _knowledge_store() -> KnowledgeStore:
    base = _config_path().parent / "knowledge"
    index_path = Path(os.environ.get("OPENVINO_CHAT_KNOWLEDGE_INDEX", base / "index.json"))
    models_dir = Path(os.environ.get("OPENVINO_CHAT_KNOWLEDGE_MODELS", base / "models"))
    return KnowledgeStore(index_path=index_path, models_dir=models_dir)


def _configured_model_dir() -> Path:
    value = _load_config().get("model", "").strip()
    return _resolve_model(value) if value else DEFAULT_MODEL_DIR


def _save_active_model(model_dir: Path) -> None:
    value = next(
        (name for name, path in _model_catalog().items() if path == model_dir),
        str(model_dir),
    )
    config = _load_config()
    config["model"] = value
    _save_config(config)


def _model_load_timing_key(model_dir: Path, device: str, kv_cache_precision: str) -> str:
    return f"load_seconds.{model_dir.name.lower()}.{device.lower()}.{kv_cache_precision.lower()}"


def _model_load_expected_seconds(
    model_dir: Path,
    device: str,
    kv_cache_precision: str,
    model_bytes: int,
) -> float:
    raw = _load_config().get(_model_load_timing_key(model_dir, device, kv_cache_precision))
    try:
        saved = float(raw) if raw is not None else 0.0
    except ValueError:
        saved = 0.0
    if saved >= 1.0:
        return saved
    return max(20.0, model_bytes / (20 * 1024 * 1024) + 45.0)


def _record_model_load_seconds(
    model_dir: Path,
    device: str,
    kv_cache_precision: str,
    seconds: float,
) -> None:
    if seconds < 1.0:
        return
    config = _load_config()
    key = _model_load_timing_key(model_dir, device, kv_cache_precision)
    try:
        previous = float(config.get(key, "0"))
    except ValueError:
        previous = 0.0
    measured = seconds if previous < 1.0 else (previous + seconds) / 2
    config[key] = f"{measured:.2f}"
    _save_config(config)


def _update_status_monitor(monitor: object, label: str) -> None:
    update = getattr(monitor, "update", None)
    if callable(update):
        update(label)
    else:
        getattr(monitor, "set")(label)


def _model_load_progress_loop(
    monitor: object,
    stop: threading.Event,
    started_at: float,
    expected_seconds: float,
) -> None:
    while not stop.wait(0.5):
        elapsed = max(0.0, time.monotonic() - started_at)
        percent = min(95, max(1, int(elapsed / max(expected_seconds, 1.0) * 100)))
        _update_status_monitor(monitor, f"loading model ~{percent}%")


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


def _knowledge_status_text(store: KnowledgeStore, mode: str) -> str:
    sources = store.list_sources()
    return "\n".join(
        [
            f"knowledge={mode}",
            f"documents={len(sources)}",
            f"chunks={store.chunk_count}",
            f"embeddings={'ready' if store.embedding_ready else 'lexical fallback'}",
            f"reranker={'ready' if store.reranker_ready else 'not installed'}",
            f"index={store.index_path}",
            "usage: /knowledge mode <offline|auto|web> | add <path> | search <query> | list | setup | reindex | clear",
        ]
    )


def _doctor_text(model_dir: Path, session_dir: Path, cwd: Path) -> str:
    lines = [
        f"python={sys.executable}",
        f"cwd={cwd}",
        f"model_dir={model_dir}",
        f"model_exists={model_dir.exists()}",
        f"model_valid={_validate_model_dir(model_dir)}",
        f"session_dir={session_dir}",
        f"session_dir_exists={session_dir.exists()}",
        f"benchmark_file={BenchmarkStore().path}",
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
    for name, path in _model_catalog().items():
        lines.append(f"model.{name}.exists={path.exists()}")
    return "\n".join(lines)


def _validate_model_dir(model_dir: Path) -> bool:
    return is_openvino_model_dir(model_dir)


def _model_path_error(model_dir: Path) -> str | None:
    if not model_dir.exists():
        return f"model missing: {model_dir}"
    if not _validate_model_dir(model_dir):
        return (
            f"model invalid: {model_dir}\n"
            "expected openvino_model.xml or openvino_language_model.xml"
        )
    return None


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
    temperature: float | None,
    top_p: float | None,
    context_length: int,
    model_dir: Path | None = None,
    kv_cache_precision: str = "auto",
    store: BenchmarkStore | None = None,
) -> str:
    chunks: list[str] = []
    first_token_at: float | None = None
    start = time.perf_counter()

    def on_token(token: str) -> None:
        nonlocal first_token_at
        if first_token_at is None:
            first_token_at = time.perf_counter()
        chunks.append(token)

    engine.generate(
        "Say hello in five words.",
        on_token=on_token,
        max_new_tokens=min(max_new_tokens, 64),
        temperature=temperature,
        top_p=top_p,
        context_length=context_length,
    )
    elapsed = max(time.perf_counter() - start, 0.000001)
    text = "".join(chunks)
    metrics = getattr(engine, "last_metrics", None)
    tokens = int(getattr(metrics, "output_tokens", 0)) or (
        len(text.split()) if text else len(chunks)
    )
    seconds = float(getattr(metrics, "elapsed_seconds", elapsed))
    ttft = getattr(metrics, "ttft_seconds", None)
    if ttft is None and first_token_at is not None:
        ttft = first_token_at - start
    lines = [
        f"tokens={tokens}",
        f"seconds={seconds:.3f}",
        f"tokens_per_sec={tokens / max(seconds, 0.000001):.2f}",
    ]
    if ttft is not None:
        lines.append(f"ttft={float(ttft):.3f}s")
    if metrics is not None and model_dir is not None:
        benchmark_store = store or BenchmarkStore()
        try:
            profile = benchmark_store.record(
                model_dir,
                engine.device,
                kv_cache_precision,
                context_length,
                metrics,
            )
            lines.append(benchmark_store.format_profile(profile))
        except (OSError, TypeError, ValueError) as exc:
            lines.append(f"profile_saved=failed ({exc})")
    return "\n".join(lines)


@dataclass
class ReplSnapshot:
    submitted_prompt: str
    model_dir: Path
    engine_loaded: bool
    config_existed: bool
    config: dict[str, str]
    context_length: int
    max_new_tokens: int
    kv_cache_precision: str
    thinking_effort: str
    generation_effort: str
    sampling_overrides: dict[str, float | int]
    duck_mode: bool
    knowledge_mode: str
    auto_compact_enabled: bool
    compaction_summary: str
    compacted_history_count: int
    compaction_count: int
    history_length: int
    history_backup: tuple[tuple[str, str], ...] | None
    display_messages_length: int
    display_messages_backup: tuple[tuple[int, str], ...] | None
    system_prompt_template: str
    system_prompt_is_default: bool
    tools_enabled: bool
    workspace_root: Path
    cwd: Path
    permission_mode: str
    active_session: str
    ui_layout: str
    raw_output: bool
    tasks: list[tuple[str, bool]]
    tool_checkpoint: object
    knowledge_checkpoint: str
    tui_checkpoint: object | None
    tui_backup: object | None
    transcript_backup: str | None = None


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
    model_dir = args.model_dir or _configured_model_dir()
    command = args.command or "chat"
    context_length = getattr(args, "context_length", None) or _configured_context_length()

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
                context_length=context_length,
                kv_cache_precision=args.kv_cache_precision or _configured_kv_precision(),
                api_key=args.api_key,
                engine_loader=engine_loader,
                knowledge_mode=_configured_knowledge_mode(),
                knowledge_store=_knowledge_store(),
                duck_mode=_configured_duck_mode(),
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
            context_length,
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
            temperature=getattr(args, "temperature", None),
            top_p=getattr(args, "top_p", None),
            context_length=context_length,
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
    download_parser.add_argument("model", help="built-in name or Hugging Face owner/repo")

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("model", help="model name shown by openvino models")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default=DEFAULT_API_HOST)
    serve_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    serve_parser.add_argument("--device", default="GPU", choices=["GPU", "CPU"])
    serve_parser.add_argument("--ctx", "--context-length", dest="context_length", type=int, default=None)
    serve_parser.add_argument("--kv-cache", dest="kv_cache_precision", choices=["auto", "u4", "u8", "f16"])
    serve_parser.add_argument("--api-key", default=os.environ.get("OPENVINO_CHAT_API_KEY"))

    api_parser = subparsers.add_parser("api")
    api_parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "stop"])
    api_parser.add_argument("--host", default=DEFAULT_API_HOST)
    api_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    api_parser.add_argument("--device", default="GPU", choices=["GPU", "CPU"])
    api_parser.add_argument("--ctx", "--context-length", dest="context_length", type=int, default=None)
    api_parser.add_argument("--kv-cache", dest="kv_cache_precision", choices=["auto", "u4", "u8", "f16"])
    api_parser.add_argument("--api-key", default=os.environ.get("OPENVINO_CHAT_API_KEY"))

    chat_parser = subparsers.add_parser("chat")
    chat_parser.add_argument("prompt", nargs="*")
    chat_parser.add_argument("--device", default="GPU", choices=["GPU", "CPU"])
    chat_parser.add_argument("--max-new-tokens", type=int, default=4096)
    chat_parser.add_argument("--ctx", "--context-length", dest="context_length", type=int, default=None)
    chat_parser.add_argument("--temperature", type=float, default=None)
    chat_parser.add_argument("--top-p", type=float, default=None)
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
    try:
        path = downloader(model, model_dir)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ImportError:
        print("missing package: install with " + package_install_command(), file=sys.stderr)
        return 3
    except (OSError, RuntimeError) as exc:
        print(f"download failed: {exc}", file=sys.stderr)
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
    temperature: float | None,
    top_p: float | None,
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
        startup_effort = _thinking_effort_for_model(
            _configured_thinking_effort(),
            model_dir,
        )
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
            status_text=lambda: _live_status_text(
                device,
                context_length,
                kv_cache_precision,
                startup_effort,
                generation_effort=_configured_generation_effort(),
                duck_mode=_configured_duck_mode(),
            ),
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
    return _interactive_stdio()


def _interactive_stdio() -> bool:
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
    temperature: float | None,
    top_p: float | None,
    context_length: int,
) -> int:
    ui = ChatUI()
    session = ToolChatSession(
        engine,
        ToolRegistry(cwd=Path.cwd(), permission_mode="allow"),
        thinking_effort=_thinking_effort_for_model(
            _configured_thinking_effort(),
            Path(getattr(engine, "model_dir", None) or DEFAULT_MODEL_DIR),
        ),
        generation_effort=_configured_generation_effort(),
        duck_mode=_configured_duck_mode(),
        knowledge_mode=_configured_knowledge_mode(),
        knowledge_store=_knowledge_store(),
        auto_compact_enabled=_configured_auto_compact(),
        sampling_overrides=(
            _configured_custom_sampling(
                Path(getattr(engine, "model_dir", None) or DEFAULT_MODEL_DIR)
            )
            if _configured_generation_effort() == "custom"
            else {}
        ),
    )
    ui.set_duck_theme(session.duck_mode)
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
    temperature: float | None,
    top_p: float | None,
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
        mediator = tui_mod.active_mediator()
        if mediator is not None:
            return mediator.request_tool_approval(request.name, request.args)
        prompt_text = f"Allow {request.name}? [y/N] "
        answer = input_fn(prompt_text).strip().lower()
        return answer in {"y", "yes", "allow"}

    registry = ToolRegistry(
        cwd=Path.cwd(),
        permission_mode="ask",
        approval_callback=approve_tool,
    )
    knowledge = _knowledge_store()
    session = ToolChatSession(
        engine,
        registry,
        thinking_effort=_thinking_effort_for_model(
            _configured_thinking_effort(),
            model_dir,
        ),
        generation_effort=_configured_generation_effort(),
        duck_mode=_configured_duck_mode(),
        knowledge_mode=_configured_knowledge_mode(),
        knowledge_store=knowledge,
        auto_compact_enabled=_configured_auto_compact(),
        sampling_overrides=(
            _configured_custom_sampling(model_dir)
            if _configured_generation_effort() == "custom"
            else {}
        ),
    )

    def sync_duck_ui() -> None:
        target = getattr(ui, "_inner", ui)
        setter = getattr(target, "set_duck_theme", None)
        if callable(setter):
            setter(session.duck_mode)
        mediator = tui_mod.active_mediator()
        if mediator is not None:
            mediator.set_duck_theme(session.duck_mode)
            if not session.duck_mode:
                mediator.clear_visual_panel()

    sync_duck_ui()
    if session.duck_mode and _configured_thinking_effort() != "off":
        config = _load_config()
        config["thinking_effort"] = "off"
        _save_config(config)
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
    redo_snapshots: list[ReplSnapshot] = []
    snapshot_started = False
    current_submitted_prompt = ""
    ui_layout = "window"
    side_panel_enabled = True
    raw_output = False
    tasks = TaskList()
    display_messages: list[tuple[int, str]] = []
    tui_before_prompt: object | None = None
    benchmark_store = BenchmarkStore()
    context_meter = {"tokens": 0, "percent": 0}

    def sync_thinking_effort_to_model() -> bool:
        next_effort = _thinking_effort_for_model(session.thinking_effort, model_dir)
        if next_effort == session.thinking_effort:
            return False
        session.set_thinking_effort(next_effort)
        config = _load_config()
        config["thinking_effort"] = next_effort
        _save_config(config)
        return True

    def sync_sampling_to_model() -> None:
        values = (
            _configured_custom_sampling(model_dir)
            if session.generation_effort == "custom"
            else {}
        )
        session.set_sampling_overrides(values)

    def active_device() -> str:
        return engine.device if engine is not None else device

    def refresh_context_meter(message: str = "") -> None:
        try:
            status = session.context_status(
                message,
                {
                    "context_length": context_length,
                    "max_new_tokens": max_new_tokens,
                },
            )
        except Exception:
            return
        context_meter["tokens"] = int(status.get("tokens", 0))
        context_meter["percent"] = int(status.get("percent", 0))

    def live_text() -> str:
        return _live_status_text(
            active_device(),
            context_length,
            kv_cache_precision,
            session.thinking_effort,
            generation_effort=session.generation_effort,
            duck_mode=session.duck_mode,
            model_name=model_name_from_dir(model_dir),
            loaded=engine is not None,
            context_used=context_meter["tokens"],
            auto_compact=session.auto_compact_enabled,
        )

    refresh_context_meter()

    def defer_output() -> bool:
        if tui_mod.active_mediator() is not None:
            return False
        return input_fn is builtins.input and ui_layout == "window"

    def use_live_work_ui() -> bool:
        return not defer_output()

    def show(text: object = "", *, plain: bool = False) -> None:
        value = str(text)
        if defer_output() and _interactive_stdio():
            display_messages.append((len(session.history), value))
            return
        if plain:
            ui.print_plain(value)
        else:
            ui.print(value)

    def notify(text: str, seconds: float = 4.0) -> None:
        mediator = tui_mod.active_mediator()
        show_notice = getattr(mediator, "show_notice", None)
        if callable(show_notice):
            show_notice(text, seconds=seconds)
        else:
            show(text)

    def unload_engine() -> bool:
        nonlocal engine
        old_engine = engine
        was_loaded = engine is not None
        session.engine = None
        engine = None
        del old_engine
        gc.collect()
        return was_loaded

    def take_snapshot(
        *,
        preserve_history: bool = False,
        preserve_transcript: bool = False,
        submitted_prompt: str | None = None,
    ) -> ReplSnapshot:
        buffer = _tui_buffer()
        tui_backup = None
        if preserve_transcript and buffer is not None and tui_before_prompt is not None:
            try:
                tui_backup = buffer.capture_checkpoint(tui_before_prompt)
            except (AttributeError, ValueError):
                tui_backup = None
        return ReplSnapshot(
            submitted_prompt=(
                current_submitted_prompt
                if submitted_prompt is None
                else submitted_prompt
            ),
            model_dir=model_dir,
            engine_loaded=engine is not None,
            config_existed=_config_path().exists(),
            config=dict(_load_config()),
            context_length=context_length,
            max_new_tokens=max_new_tokens,
            kv_cache_precision=kv_cache_precision,
            thinking_effort=session.thinking_effort,
            generation_effort=session.generation_effort,
            sampling_overrides=dict(session.sampling_overrides),
            duck_mode=session.duck_mode,
            knowledge_mode=session.knowledge_mode,
            auto_compact_enabled=session.auto_compact_enabled,
            compaction_summary=session.compaction_summary,
            compacted_history_count=session.compacted_history_count,
            compaction_count=session.compaction_count,
            history_length=len(session.history),
            history_backup=tuple(session.history) if preserve_history else None,
            display_messages_length=len(display_messages),
            display_messages_backup=(
                tuple(display_messages) if preserve_transcript else None
            ),
            system_prompt_template=session.system_prompt_template,
            system_prompt_is_default=session.system_prompt_is_default,
            tools_enabled=session.tools_enabled,
            workspace_root=session.tools.workspace_root,
            cwd=session.tools.cwd,
            permission_mode=session.tools.permission_mode,
            active_session=active_session,
            ui_layout=ui_layout,
            raw_output=raw_output,
            tasks=[(item.text, item.done) for item in tasks.items],
            tool_checkpoint=session.tools.checkpoint(),
            knowledge_checkpoint=knowledge.checkpoint(),
            tui_checkpoint=tui_before_prompt,
            tui_backup=tui_backup,
        )

    def commit_snapshot(snapshot: ReplSnapshot) -> None:
        nonlocal snapshot_started
        if snapshot_started and snapshots:
            snapshots[-1] = snapshot
        else:
            snapshots.append(snapshot)
            del snapshots[:-REWIND_HISTORY_LIMIT]
        redo_snapshots.clear()
        snapshot_started = True

    def push_snapshot(
        *,
        preserve_history: bool = False,
        preserve_transcript: bool = False,
    ) -> None:
        commit_snapshot(
            take_snapshot(
                preserve_history=preserve_history,
                preserve_transcript=preserve_transcript,
            )
        )

    def snapshot_transcript(snapshot: ReplSnapshot) -> str | None:
        if snapshot.transcript_backup is not None:
            return sanitize_tool_artifacts(snapshot.transcript_backup)
        state = snapshot.tui_backup
        if state is None and snapshot.tui_checkpoint is not None:
            buffer = _tui_buffer()
            if buffer is not None:
                try:
                    state = buffer.capture_checkpoint(snapshot.tui_checkpoint)
                except (AttributeError, ValueError):
                    state = None
        segments = getattr(state, "segments", None)
        if segments is None:
            return None
        return sanitize_tool_artifacts("".join(str(part) for part in segments))

    def serialize_snapshot(
        snapshot: ReplSnapshot,
        current_transcript: str | None,
    ) -> dict[str, object]:
        data: dict[str, object] = {
            "submitted_prompt": snapshot.submitted_prompt,
            "model_dir": str(snapshot.model_dir),
            "config_existed": snapshot.config_existed,
            "config": snapshot.config,
            "context_length": snapshot.context_length,
            "max_new_tokens": snapshot.max_new_tokens,
            "kv_cache_precision": snapshot.kv_cache_precision,
            "thinking_effort": snapshot.thinking_effort,
            "generation_effort": snapshot.generation_effort,
            "sampling_overrides": snapshot.sampling_overrides,
            "duck_mode": snapshot.duck_mode,
            "knowledge_mode": snapshot.knowledge_mode,
            "auto_compact_enabled": snapshot.auto_compact_enabled,
            "compaction_summary": snapshot.compaction_summary,
            "compacted_history_count": snapshot.compacted_history_count,
            "compaction_count": snapshot.compaction_count,
            "history_length": snapshot.history_length,
            "display_messages_length": snapshot.display_messages_length,
            "system_prompt_template": snapshot.system_prompt_template,
            "system_prompt_is_default": snapshot.system_prompt_is_default,
            "tools_enabled": snapshot.tools_enabled,
            "workspace_root": str(snapshot.workspace_root),
            "cwd": str(snapshot.cwd),
            "permission_mode": snapshot.permission_mode,
            "ui_layout": snapshot.ui_layout,
            "raw_output": snapshot.raw_output,
            "tasks": snapshot.tasks,
        }
        if snapshot.history_backup is not None:
            data["history_backup"] = list(snapshot.history_backup)
        if snapshot.display_messages_backup is not None:
            data["display_messages_backup"] = list(snapshot.display_messages_backup)
        transcript = snapshot_transcript(snapshot)
        if transcript is not None:
            if current_transcript is not None and current_transcript.startswith(transcript):
                data["transcript_length"] = len(transcript)
            else:
                data["transcript"] = transcript
        return data

    def deserialize_snapshot(
        data: object,
        current_transcript: str | None,
        session_name: str,
    ) -> ReplSnapshot | None:
        if not isinstance(data, dict):
            return None

        def integer(key: str, fallback: int) -> int:
            try:
                return int(data.get(key, fallback))
            except (TypeError, ValueError):
                return fallback

        def history_value(key: str) -> tuple[tuple[str, str], ...] | None:
            raw = data.get(key)
            if not isinstance(raw, list):
                return None
            pairs = []
            for item in raw:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pairs.append((str(item[0]), str(item[1])))
            return tuple(pairs)

        def display_value() -> tuple[tuple[int, str], ...] | None:
            raw = data.get("display_messages_backup")
            if not isinstance(raw, list):
                return None
            pairs = []
            for item in raw:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                try:
                    position = int(item[0])
                except (TypeError, ValueError):
                    continue
                pairs.append((position, str(item[1])))
            return tuple(pairs)

        baseline = take_snapshot(submitted_prompt=str(data.get("submitted_prompt") or ""))
        try:
            thinking = normalize_thinking_effort(
                str(data.get("thinking_effort") or baseline.thinking_effort)
            )
        except ValueError:
            thinking = baseline.thinking_effort
        try:
            saved_generation_effort = normalize_generation_effort(
                str(data.get("generation_effort") or baseline.generation_effort)
            )
        except ValueError:
            saved_generation_effort = baseline.generation_effort
        try:
            saved_sampling_overrides = _normalize_custom_sampling(
                data.get("sampling_overrides", baseline.sampling_overrides)
            )
        except ValueError:
            saved_sampling_overrides = baseline.sampling_overrides
        try:
            saved_duck_mode = normalize_duck_mode(
                data.get("duck_mode", baseline.duck_mode)
            )
        except ValueError:
            saved_duck_mode = baseline.duck_mode
        try:
            saved_knowledge_mode = normalize_knowledge_mode(
                str(data.get("knowledge_mode") or baseline.knowledge_mode)
            )
        except ValueError:
            saved_knowledge_mode = baseline.knowledge_mode
        try:
            saved_auto_compact = normalize_auto_compact(
                data.get("auto_compact_enabled", baseline.auto_compact_enabled)
            )
        except ValueError:
            saved_auto_compact = baseline.auto_compact_enabled
        config_value = data.get("config")
        saved_config = (
            {str(key): str(value) for key, value in config_value.items()}
            if isinstance(config_value, dict)
            else baseline.config
        )
        task_value = data.get("tasks")
        saved_tasks = []
        if isinstance(task_value, list):
            for item in task_value:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    saved_tasks.append((str(item[0]), bool(item[1])))
        transcript = data.get("transcript")
        if not isinstance(transcript, str):
            transcript = None
        if transcript is None and current_transcript is not None:
            length = integer("transcript_length", -1)
            if 0 <= length <= len(current_transcript):
                transcript = current_transcript[:length]
        saved_system_prompt = str(
            data.get("system_prompt_template") or baseline.system_prompt_template
        )
        saved_prompt_default = data.get("system_prompt_is_default")
        if not isinstance(saved_prompt_default, bool):
            saved_prompt_default = (
                saved_system_prompt.startswith(
                    "You are {model_name}, local OpenVINO Chat assistant."
                )
                and "Tool map:" in saved_system_prompt
                and "Tool rules:" in saved_system_prompt
            )
        return ReplSnapshot(
            submitted_prompt=str(data.get("submitted_prompt") or ""),
            model_dir=Path(str(data.get("model_dir") or baseline.model_dir)),
            engine_loaded=False,
            config_existed=bool(data.get("config_existed", baseline.config_existed)),
            config=saved_config,
            context_length=integer("context_length", baseline.context_length),
            max_new_tokens=integer("max_new_tokens", baseline.max_new_tokens),
            kv_cache_precision=str(data.get("kv_cache_precision") or baseline.kv_cache_precision),
            thinking_effort=thinking,
            generation_effort=saved_generation_effort,
            sampling_overrides=saved_sampling_overrides,
            duck_mode=saved_duck_mode,
            knowledge_mode=saved_knowledge_mode,
            auto_compact_enabled=saved_auto_compact,
            compaction_summary=str(data.get("compaction_summary") or ""),
            compacted_history_count=integer(
                "compacted_history_count", baseline.compacted_history_count
            ),
            compaction_count=integer("compaction_count", baseline.compaction_count),
            history_length=integer("history_length", baseline.history_length),
            history_backup=history_value("history_backup"),
            display_messages_length=integer(
                "display_messages_length", baseline.display_messages_length
            ),
            display_messages_backup=display_value(),
            system_prompt_template=saved_system_prompt,
            system_prompt_is_default=saved_prompt_default,
            tools_enabled=bool(data.get("tools_enabled", baseline.tools_enabled)),
            workspace_root=Path(str(data.get("workspace_root") or baseline.workspace_root)),
            cwd=Path(str(data.get("cwd") or baseline.cwd)),
            permission_mode=str(data.get("permission_mode") or baseline.permission_mode),
            active_session=session_name,
            ui_layout=str(data.get("ui_layout") or baseline.ui_layout),
            raw_output=bool(data.get("raw_output", baseline.raw_output)),
            tasks=saved_tasks,
            tool_checkpoint=session.tools.checkpoint(),
            knowledge_checkpoint=knowledge.checkpoint(),
            tui_checkpoint=None,
            tui_backup=None,
            transcript_backup=(
                sanitize_tool_artifacts(transcript) if transcript is not None else None
            ),
        )

    def session_state() -> dict[str, object]:
        buffer = _tui_buffer()
        transcript = (
            sanitize_tool_artifacts(buffer.render()) if buffer is not None else None
        )
        runtime = take_snapshot(submitted_prompt="")
        timeline = []
        for snapshot in snapshots:
            command = snapshot.submitted_prompt.strip().lower().split(" ", 1)[0]
            if command in SESSION_TIMELINE_EXCLUDED_COMMANDS:
                continue
            timeline.append(serialize_snapshot(snapshot, transcript))
        runtime_data = serialize_snapshot(runtime, transcript)
        if transcript is not None:
            runtime_data.pop("transcript", None)
            runtime_data["transcript_length"] = len(transcript)
        state: dict[str, object] = {
            "version": 1,
            "runtime": runtime_data,
            "timeline": timeline[-REWIND_HISTORY_LIMIT:],
            "display_messages": display_messages,
        }
        if transcript is not None:
            state["transcript"] = transcript
        return state

    def legacy_timeline(
        history: list[tuple[str, str]],
        session_name: str,
    ) -> list[ReplSnapshot]:
        result = []
        for index, (role, content) in enumerate(history):
            if role != "user":
                continue
            snapshot = take_snapshot(submitted_prompt=content)
            snapshot.engine_loaded = False
            snapshot.history_length = index
            snapshot.history_backup = None
            snapshot.display_messages_length = 0
            snapshot.display_messages_backup = None
            snapshot.active_session = session_name
            snapshot.tui_checkpoint = None
            snapshot.tui_backup = None
            snapshot.transcript_backup = None
            result.append(snapshot)
        return result[-REWIND_HISTORY_LIMIT:]

    def restore_snapshot(snapshot: ReplSnapshot) -> None:
        nonlocal model_dir, context_length, max_new_tokens, kv_cache_precision, estimate, active_session, raw_output
        duck_theme_changed = snapshot.duck_mode != session.duck_mode
        if engine is not None and (
            snapshot.model_dir != model_dir
            or snapshot.kv_cache_precision != kv_cache_precision
            or not snapshot.engine_loaded
        ):
            unload_engine()
        model_dir = snapshot.model_dir
        context_length = snapshot.context_length
        max_new_tokens = snapshot.max_new_tokens
        kv_cache_precision = snapshot.kv_cache_precision
        if snapshot.config_existed:
            _save_config(dict(snapshot.config))
        else:
            _config_path().unlink(missing_ok=True)
        estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
        if snapshot.history_backup is not None:
            session.history = list(snapshot.history_backup)
        else:
            del session.history[snapshot.history_length :]
        session.set_duck_mode(snapshot.duck_mode)
        session.set_thinking_effort(
            _thinking_effort_for_model(snapshot.thinking_effort, model_dir)
        )
        session.set_generation_effort(snapshot.generation_effort)
        session.set_sampling_overrides(snapshot.sampling_overrides)
        sync_duck_ui()
        session.set_knowledge_mode(snapshot.knowledge_mode)
        session.set_auto_compact(snapshot.auto_compact_enabled)
        session.restore_compaction_state(
            snapshot.compaction_summary,
            snapshot.compacted_history_count,
            snapshot.compaction_count,
        )
        if snapshot.display_messages_backup is not None:
            display_messages[:] = list(snapshot.display_messages_backup)
        else:
            del display_messages[snapshot.display_messages_length :]
        if snapshot.system_prompt_is_default:
            session.reset_system_prompt()
        else:
            session.system_prompt_template = snapshot.system_prompt_template
        session.tools_enabled = snapshot.tools_enabled
        session.tools.workspace_root = snapshot.workspace_root
        session.tools.cwd = snapshot.cwd
        session.tools.permission_mode = snapshot.permission_mode
        session.tools.restore_checkpoint(snapshot.tool_checkpoint)
        knowledge.restore_checkpoint(snapshot.knowledge_checkpoint)
        active_session = snapshot.active_session
        raw_output = snapshot.raw_output
        tasks.clear()
        for text, done in snapshot.tasks:
            tasks.add(text, done=done)
        set_ui_layout(snapshot.ui_layout)
        buffer = _tui_buffer()
        if buffer is not None:
            restored = False
            if duck_theme_changed:
                redraw_tui_history()
                restored = True
            elif snapshot.transcript_backup is not None:
                buffer.replace(snapshot.transcript_backup.rstrip() + "\n")
                restored = True
            elif snapshot.tui_checkpoint is not None:
                try:
                    restored = buffer.restore_checkpoint(
                        snapshot.tui_checkpoint,
                        snapshot.tui_backup,
                    )
                except AttributeError:
                    restored = False
            if not restored:
                redraw_tui_history()
            _invalidate_buffer()
        refresh_context_meter()
        if snapshot.engine_loaded and engine is None:
            ensure_engine()

    def ensure_engine() -> bool:
        nonlocal engine, device
        if engine is not None:
            return True
        load_started = time.monotonic()
        progress_stop = threading.Event()
        progress_thread: threading.Thread | None = None
        if use_live_work_ui():
            monitor.start()
            monitor.set("loading model ~0%")
            expected_seconds = _model_load_expected_seconds(
                model_dir,
                device,
                kv_cache_precision,
                estimate.model_bytes,
            )
            progress_thread = threading.Thread(
                target=_model_load_progress_loop,
                args=(monitor, progress_stop, load_started, expected_seconds),
                name="openvino-load-progress",
                daemon=True,
            )
            progress_thread.start()
        try:
            engine = _load_engine_for_cli(
                engine_loader,
                model_dir,
                device,
                kv_cache_precision,
            )
            session.set_engine(engine)
            device = engine.device
            load_seconds = time.monotonic() - load_started
            _record_model_load_seconds(model_dir, device, kv_cache_precision, load_seconds)
            if use_live_work_ui():
                _update_status_monitor(monitor, "loading model 100%")
            show(
                f"model loaded: {model_name_from_dir(model_dir)} "
                f"({engine.device}) in {load_seconds:.1f}s"
            )
            return True
        except RuntimeError as exc:
            show(str(exc))
            return False
        finally:
            progress_stop.set()
            if progress_thread is not None:
                progress_thread.join(timeout=1)
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
        refresh_context_meter(prompt_text)
        try:
            response = _ask_session(
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
            metrics = getattr(engine, "last_metrics", None)
            if metrics is not None and engine is not None:
                try:
                    benchmark_store.record(
                        model_dir,
                        engine.device,
                        kv_cache_precision,
                        context_length,
                        metrics,
                    )
                except Exception:
                    pass
            mediator = tui_mod.active_mediator()
            if (
                mediator is not None
                and session.duck_mode
                and mediator.can_show_visual_panel()
            ):
                visual = extract_visual_panel(response)
                if visual is not None:
                    mediator.set_visual_panel(*visual)
            return response
        except Exception as exc:
            show(f"generation failed: {exc}")
            return None
        finally:
            refresh_context_meter()

    _mediator = tui_mod.active_mediator()
    if _mediator is not None:
        _mediator.status_text = live_text
        _mediator.tasks_text = tasks.format
        _mediator.set_side_panel(side_panel_enabled)
        if getattr(_mediator, "chat_buffer", None) is not None:
            _welcome = _build_tui_welcome_text(
                device,
                context_length,
                estimate,
                model_dir,
                engine is not None,
                kv_cache_precision,
                session.duck_mode,
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
                session.duck_mode,
            ).rstrip()
        ]
        if include_history and (session.history or display_messages):
            parts.append(
                _chat_window_text(
                    session.history,
                    display_messages,
                    raw=raw_output,
                    duck_mode=session.duck_mode,
                )
            )
        buffer.replace("\n\n".join(part for part in parts if part).rstrip() + "\n")
        _invalidate_buffer()

    def set_ui_layout(layout: str) -> None:
        nonlocal monitor, ui_layout
        ui_layout = layout
        monitor.stop()
        monitor = ui.status_monitor(live_text, refresh_seconds=3.0, layout=ui_layout, tasks_text=tasks.format)

    def compaction_kwargs() -> dict[str, object]:
        return {
            "context_length": context_length,
            "max_new_tokens": max_new_tokens,
        }

    def compaction_status_text() -> str:
        status = session.context_status("", compaction_kwargs())
        return "\n".join(
            [
                f"auto_compact={'on' if session.auto_compact_enabled else 'off'}",
                f"context_tokens={status['tokens']} / {context_length} ({status['percent']}%)",
                f"compact_threshold={status['threshold']}",
                f"compacted_messages={session.compacted_history_count} / {len(session.history)}",
                f"compactions={session.compaction_count}",
            ]
        )

    def auto_save_session() -> str | None:
        nonlocal active_session
        if not session.history:
            return None
        name = active_session if active_session != "default" else _auto_session_name(session.history)
        try:
            _save_session(
                sessions,
                name,
                session.history,
                model_name_from_dir(model_dir),
                active_device(),
                state=session_state(),
            )
        except (OSError, TypeError, ValueError) as exc:
            show(f"session save failed: {exc}")
            return None
        active_session = name
        return name

    def load_saved_session(name: str) -> bool:
        nonlocal active_session, snapshot_started
        try:
            loaded_history = sessions.load(name)
            load_state = getattr(sessions, "load_state", None)
            state = load_state(name) if callable(load_state) else {}
        except (OSError, TypeError, ValueError) as exc:
            show(f"session load failed: {exc}")
            return False
        if not isinstance(state, dict):
            state = {}

        saved_display = []
        for item in state.get("display_messages", []):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                position = int(item[0])
            except (TypeError, ValueError):
                continue
            saved_display.append((position, str(item[1])))
        display_messages[:] = saved_display
        session.history = loaded_history
        session.restore_compaction_state("", 0, 0)
        active_session = name

        current_transcript = state.get("transcript")
        if not isinstance(current_transcript, str):
            current_transcript = None
        elif current_transcript:
            current_transcript = sanitize_tool_artifacts(current_transcript)

        runtime = deserialize_snapshot(
            state.get("runtime"),
            current_transcript,
            name,
        )
        if runtime is not None:
            runtime.history_backup = tuple(loaded_history)
            runtime.display_messages_backup = tuple(saved_display)
            restore_snapshot(runtime)
        else:
            buffer = _tui_buffer()
            if buffer is not None and current_transcript is not None:
                buffer.replace(current_transcript.rstrip() + "\n")
                _invalidate_buffer()
            else:
                redraw_tui_history()

        restored_timeline = []
        timeline = state.get("timeline")
        if isinstance(timeline, list):
            for item in timeline:
                snapshot = deserialize_snapshot(item, current_transcript, name)
                if snapshot is not None:
                    restored_timeline.append(snapshot)
        if not restored_timeline:
            restored_timeline = legacy_timeline(loaded_history, name)
        snapshots[:] = restored_timeline[-REWIND_HISTORY_LIMIT:]
        redo_snapshots.clear()
        snapshot_started = False
        active_session = name
        mediator = tui_mod.active_mediator()
        if mediator is not None:
            mediator.clear_visual_panel()
        refresh_context_meter()
        return True

    try:
        while True:
            snapshot_started = False
            try:
                prompt = _input_with_status(
                    input_fn,
                    ui.user_prompt(),
                    live_text,
                    layout=ui_layout,
                    chat_text=lambda: _chat_window_text(
                        session.history,
                        display_messages,
                        raw=raw_output,
                        duck_mode=session.duck_mode,
                    ),
                    tasks_text=tasks.format,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                if tui_mod.active_mediator() is None:
                    print()
                auto_save_session()
                return 0
            current_submitted_prompt = prompt
            if prompt.lower() in {"exit", "quit", ":q", "/exit", "/quit"}:
                saved = auto_save_session()
                if session.history and saved is None:
                    continue
                return 0
            buffer = _tui_buffer()
            tui_before_prompt = buffer.checkpoint() if buffer is not None else None
            if prompt:
                if buffer is not None and prompt.lower() not in TRANSIENT_UI_COMMANDS:
                    buffer.append_user(prompt)
                    _invalidate_buffer()
                if prompt.lower() not in {"/rewind", "/redo"}:
                    push_snapshot()
            usage = _exact_usage_message(prompt)
            if usage:
                show(usage, plain=True)
                continue
            if prompt.lower() == "/archive":
                name = auto_save_session()
                if session.history and name is None:
                    show("archive failed; session remains open")
                    continue
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
                push_snapshot(preserve_transcript=True)
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
            if _command_matches(prompt, "/sidepanel") or _command_matches(
                prompt, "/sidepannel"
            ):
                requested = prompt.strip().split(maxsplit=1)
                if len(requested) == 1:
                    show(
                        f"sidepanel={'on' if side_panel_enabled else 'off'}\n"
                        "usage: /sidepanel [on|off]",
                        plain=True,
                    )
                    continue
                value = requested[1].strip().lower()
                if value not in {"on", "off"}:
                    show("usage: /sidepanel [on|off]", plain=True)
                    continue
                side_panel_enabled = value == "on"
                mediator = tui_mod.active_mediator()
                if mediator is not None:
                    mediator.set_side_panel(side_panel_enabled)
                    mediator.show_notice(f"Side panel: {value}")
                else:
                    show(f"sidepanel={value}")
                continue
            if prompt.lower() in {"/task", "/tasks"} or prompt.lower().startswith(("/task ", "/tasks ")):
                snapshot = take_snapshot()
                before = [(item.text, item.done) for item in tasks.items]
                result = tasks.handle_command(prompt)
                if [(item.text, item.done) for item in tasks.items] != before:
                    commit_snapshot(snapshot)
                show(result, plain=True)
                continue
            if _command_matches(prompt, "/plan"):
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
                push_snapshot(preserve_transcript=True)
                buffer = _tui_buffer()
                if buffer is not None:
                    display_messages.clear()
                    mediator = tui_mod.active_mediator()
                    if mediator is not None:
                        mediator.clear_visual_panel()
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
                push_snapshot(preserve_history=True, preserve_transcript=True)
                session.reset()
                refresh_context_meter()
                mediator = tui_mod.active_mediator()
                if mediator is not None:
                    mediator.clear_visual_panel()
                redraw_tui_history()
                show("memory reset")
                continue
            if prompt.lower() == "/rewind":
                if not snapshots:
                    notify("nothing to rewind")
                    continue
                target = snapshots[-1]
                next_redo = take_snapshot(
                    preserve_history=True,
                    preserve_transcript=True,
                    submitted_prompt=target.submitted_prompt,
                )
                try:
                    restore_snapshot(target)
                except OSError as exc:
                    notify(f"rewind failed: {exc}")
                    continue
                snapshots.pop()
                redo_snapshots.append(next_redo)
                del redo_snapshots[:-REWIND_HISTORY_LIMIT]
                notify(
                    f"rewound | prompt restored | older: {len(snapshots)} | "
                    f"redo: {len(redo_snapshots)}"
                )
                mediator = tui_mod.active_mediator()
                queue_prefill = getattr(mediator, "queue_input_prefill", None)
                if callable(queue_prefill):
                    queue_prefill(target.submitted_prompt)
                continue
            if prompt.lower() == "/redo":
                if not redo_snapshots:
                    notify("nothing to redo")
                    continue
                target = redo_snapshots[-1]
                rewind_snapshot = take_snapshot(
                    preserve_history=True,
                    preserve_transcript=True,
                    submitted_prompt=target.submitted_prompt,
                )
                try:
                    restore_snapshot(target)
                except OSError as exc:
                    notify(f"redo failed: {exc}")
                    continue
                redo_snapshots.pop()
                snapshots.append(rewind_snapshot)
                del snapshots[:-REWIND_HISTORY_LIMIT]
                notify(
                    f"redone | rewind: {len(snapshots)} | "
                    f"newer: {len(redo_snapshots)}"
                )
                continue
            if prompt.lower() == "/compact status":
                show(compaction_status_text())
                continue
            if _command_matches(prompt, "/compact auto"):
                _, _, requested = prompt.lower().partition("/compact auto")
                requested = requested.strip()
                if requested not in {"on", "off"}:
                    show("usage: /compact auto <on|off>")
                    continue
                enabled = requested == "on"
                session.set_auto_compact(enabled)
                config = _load_config()
                config["auto_compact"] = requested
                _save_config(config)
                show(compaction_status_text())
                continue
            if prompt.lower() == "/compact":
                if not ensure_engine():
                    continue
                if use_live_work_ui():
                    monitor.start()
                    monitor.set("compacting")
                try:
                    result = session.compact(
                        "",
                        compaction_kwargs(),
                        on_event=(
                            lambda event: monitor.set("compacting")
                            if event.get("phase") == "compacting"
                            else None
                        ),
                    )
                finally:
                    if use_live_work_ui():
                        _clear_monitor(monitor, refresh=False)
                        monitor.stop()
                refresh_context_meter()
                if result.compacted:
                    show(
                        f"compacted={result.turns_compacted} turns | "
                        f"tokens={result.before_tokens}->{result.after_tokens} | "
                        f"summary={result.summary_tokens}"
                    )
                    auto_save_session()
                else:
                    show(f"compact skipped: {result.reason}")
                continue
            if _command_matches(prompt, "/compact"):
                show("usage: /compact [status|auto on|auto off]")
                continue
            if prompt.lower() == "/status":
                compact_status = session.context_status("", compaction_kwargs())
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
                            f"effort={session.generation_effort}",
                            f"thinking={session.thinking_effort}",
                            f"duck={'on' if session.duck_mode else 'off'}",
                            f"auto_compact={'on' if session.auto_compact_enabled else 'off'}",
                            f"context_used={compact_status['tokens']} ({compact_status['percent']}%)",
                            f"compactions={session.compaction_count}",
                            f"knowledge={session.knowledge_mode}",
                            f"knowledge_chunks={knowledge.chunk_count}",
                            f"workspace={session.tools.workspace_root}",
                            f"cwd={session.tools.cwd}",
                            "loaded=yes" if engine is not None else "loaded=no",
                            f"models_available={_available_models_summary()}",
                        ]
                    )
                )
                continue
            if prompt.lower() == "/knowledge":
                show(_knowledge_status_text(knowledge, session.knowledge_mode))
                continue
            if prompt.lower().startswith("/knowledge "):
                _, _, rest = prompt.partition(" ")
                action, _, value = rest.strip().partition(" ")
                action = action.lower()
                value = value.strip()
                if action == "mode":
                    try:
                        next_mode = normalize_knowledge_mode(value)
                    except ValueError as exc:
                        show(str(exc))
                        continue
                    if next_mode != session.knowledge_mode:
                        push_snapshot()
                        session.set_knowledge_mode(next_mode)
                        config = _load_config()
                        config["knowledge_mode"] = next_mode
                        _save_config(config)
                    show(f"knowledge={session.knowledge_mode}")
                    continue
                if action == "add":
                    target = _resolve_user_path(value, session.tools.cwd)
                    if use_live_work_ui():
                        monitor.start()
                        monitor.set("indexing documents")
                    try:
                        result = knowledge.add(target)
                    except (OSError, ValueError) as exc:
                        show(f"knowledge failed: {exc}")
                    else:
                        show(
                            f"indexed_files={result.files}\n"
                            f"indexed_chunks={result.chunks}\n"
                            f"semantic={'yes' if result.semantic else 'no'}"
                        )
                    finally:
                        if use_live_work_ui():
                            _clear_monitor(monitor, refresh=False)
                            monitor.stop()
                    continue
                if action == "search":
                    matches = knowledge.search(value, limit=5)
                    if not matches:
                        show("no relevant local knowledge")
                    else:
                        show(
                            "\n\n".join(
                                f"{index}. {match.source} ({match.score:.3f})\n{match.text}"
                                for index, match in enumerate(matches, 1)
                            ),
                            plain=True,
                        )
                    continue
                if action == "list":
                    sources = knowledge.list_sources()
                    show("\n".join(sources) if sources else "no indexed documents", plain=True)
                    continue
                if action == "setup":
                    if use_live_work_ui():
                        monitor.start()
                        monitor.set("downloading RAG models")
                    try:
                        status = knowledge.setup()
                        reindexed = knowledge.reindex() if knowledge.chunk_count else None
                    except Exception as exc:
                        show(f"knowledge setup failed: {exc}")
                    else:
                        lines = [
                            f"embedding={'ready' if status.embedding_ready else 'missing'}",
                            f"reranker={'ready' if status.reranker_ready else 'missing'}",
                        ]
                        if reindexed is not None:
                            lines.append(f"reindexed_chunks={reindexed.chunks}")
                        show("\n".join(lines))
                    finally:
                        if use_live_work_ui():
                            _clear_monitor(monitor, refresh=False)
                            monitor.stop()
                    continue
                if action == "reindex":
                    result = knowledge.reindex()
                    show(
                        f"indexed_files={result.files}\n"
                        f"indexed_chunks={result.chunks}\n"
                        f"semantic={'yes' if result.semantic else 'no'}"
                    )
                    continue
                if action == "clear":
                    push_snapshot()
                    knowledge.clear()
                    show("knowledge cleared")
                    continue
                show("usage: /knowledge mode <offline|auto|web> | add <path> | search <query> | list | setup | reindex | clear")
                continue
            if prompt.lower() == "/doctor":
                show(_doctor_text(model_dir, sessions.root, session.tools.cwd))
                continue
            if _command_matches(prompt, "/config"):
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
                show(
                    _bench_engine(
                        engine,
                        max_new_tokens,
                        temperature,
                        top_p,
                        context_length,
                        model_dir=model_dir,
                        kv_cache_precision=kv_cache_precision,
                        store=benchmark_store,
                    )
                )
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
            if _command_matches(prompt, "/ctx"):
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
                    if next_context_length != context_length:
                        push_snapshot()
                        context_length = next_context_length
                        max_new_tokens = min(max_new_tokens, context_length)
                        config = _load_config()
                        config["context_length"] = str(context_length)
                        _save_config(config)
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
            if _command_matches(prompt, "/effort"):
                raw_requested = prompt[len("/effort") :].strip()
                requested, _, custom_args = raw_requested.partition(" ")
                requested = requested.lower()
                if not requested:
                    selected = _effort_picker(session.generation_effort)
                    if selected is None:
                        show(
                            _generation_effort_status(
                                model_dir,
                                session.generation_effort,
                                session.thinking_effort,
                                session.sampling_overrides,
                            )
                            + "\nusage: /effort [low|medium|high|custom]"
                        )
                        continue
                    requested = selected
                next_sampling: dict[str, float | int] = {}
                if requested == "custom":
                    baseline = _custom_sampling_defaults(
                        model_dir,
                        session.thinking_effort,
                        _configured_custom_sampling(model_dir)
                        or session.sampling_overrides,
                    )
                    try:
                        if custom_args.strip():
                            next_sampling = _parse_custom_sampling(custom_args, baseline)
                        else:
                            selected_sampling = _custom_sampling_picker(baseline)
                            if selected_sampling is None:
                                show(
                                    "usage: /effort custom "
                                    "temperature=<0..2> top_p=<0..1> top_k=<1..1000> "
                                    "min_p=<0..1> presence_penalty=<-2..2> "
                                    "repetition_penalty=<0.01..2>"
                                )
                                continue
                            next_sampling = _normalize_custom_sampling(selected_sampling)
                    except ValueError as exc:
                        show(str(exc))
                        continue
                try:
                    next_effort = normalize_generation_effort(requested)
                except ValueError as exc:
                    show(str(exc))
                    continue
                changed = (
                    next_effort != session.generation_effort
                    or next_sampling != session.sampling_overrides
                )
                if changed:
                    push_snapshot()
                    session.set_generation_effort(next_effort)
                    session.set_sampling_overrides(next_sampling)
                    config = _load_config()
                    config["generation_effort"] = next_effort
                    _save_config(config)
                    if next_effort == "custom":
                        _save_custom_sampling(model_dir, next_sampling)
                show(
                    _generation_effort_status(
                        model_dir,
                        session.generation_effort,
                        session.thinking_effort,
                        session.sampling_overrides,
                    )
                )
                monitor.refresh()
                continue
            if _command_matches(prompt, "/duck"):
                requested = prompt[len("/duck") :].strip().lower()
                if not requested:
                    selected = _duck_picker(session.duck_mode)
                    if selected is None:
                        show(
                            f"duck={'on' if session.duck_mode else 'off'}\n"
                            "usage: /duck [on|off]"
                        )
                        continue
                    requested = selected
                try:
                    enabled = normalize_duck_mode(requested)
                except ValueError as exc:
                    show(str(exc))
                    continue
                changed = enabled != session.duck_mode
                if changed:
                    push_snapshot()
                    session.set_duck_mode(enabled)
                if changed:
                    sync_duck_ui()
                    redraw_tui_history()
                message = (
                    "Quack mode: ON. Everything is Quack territory. QUACK QUACK QUACK."
                    if enabled
                    else "Quack mode: off. Native thinking remains off; use /thinking to change it."
                )
                mediator = tui_mod.active_mediator()
                if mediator is not None:
                    mediator.show_notice(message)
                else:
                    show(message)
                monitor.refresh()
                continue
            if _command_matches(prompt, "/thinking"):
                if session.duck_mode:
                    mediator = tui_mod.active_mediator()
                    message = "Quack mode keeps native thinking off. QUACK."
                    if mediator is not None:
                        mediator.show_notice(message)
                    else:
                        show(message)
                    continue
                requested = prompt[len("/thinking") :].strip().lower()
                supported = thinking_efforts_for_model(model_dir)
                if not requested:
                    selected = _thinking_picker(session.thinking_effort, supported)
                    if selected is None:
                        show(
                            f"thinking={session.thinking_effort}\n"
                            f"supported={', '.join(reversed(supported))}\n"
                            "usage: /thinking or /thinking <mode>"
                        )
                        continue
                    requested = selected
                try:
                    next_effort = resolve_thinking_effort(requested, supported)
                except ValueError as exc:
                    show(str(exc))
                    continue
                if next_effort != session.thinking_effort:
                    push_snapshot()
                    session.set_thinking_effort(next_effort)
                    config = _load_config()
                    config["thinking_effort"] = next_effort
                    _save_config(config)
                show(
                    f"thinking={session.thinking_effort}\n"
                    f"supported={', '.join(reversed(supported))}\n"
                    "control=model-native; applies on next message"
                )
                monitor.refresh()
                continue
            if _command_matches(prompt, "/max-tokens"):
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
                    if next_max_tokens != max_new_tokens:
                        push_snapshot()
                        max_new_tokens = next_max_tokens
                show(f"max_new_tokens={max_new_tokens}\nctx={context_length}")
                continue
            if prompt.lower() == "/api" or prompt.lower().startswith("/api "):
                parts = prompt.split()
                action = parts[1].lower() if len(parts) > 1 else "status"
                if action not in {"status", "start", "stop"} or len(parts) > 3:
                    show("usage: /api [start [port]|stop|status]")
                    continue
                if action != "start" and len(parts) > 2:
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
                if not 1 <= api_port <= 65535:
                    show("API port must be between 1 and 65535")
                    continue
                push_snapshot(preserve_transcript=True)
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
                show("tools: pwd, ls, read, scan, grep, write, append, shell, storage, startup_apps, web_search, web_fetch, diff, undo, chart, big, tilt")
                continue
            if prompt.lower().startswith("/chart "):
                _, _, data = prompt.partition(" ")
                try:
                    rendered = render_chart(data)
                    mediator = tui_mod.active_mediator()
                    if (
                        mediator is not None
                        and session.duck_mode
                        and mediator.can_show_visual_panel()
                    ):
                        mediator.set_visual_panel("chart", rendered)
                    else:
                        show(rendered)
                except ValueError as exc:
                    show(str(exc))
                continue
            if prompt.lower().startswith("/big "):
                _, _, text = prompt.partition(" ")
                rendered = render_big_text(text)
                mediator = tui_mod.active_mediator()
                if (
                    mediator is not None
                    and session.duck_mode
                    and mediator.can_show_visual_panel()
                ):
                    mediator.set_visual_panel("big", rendered)
                else:
                    show(rendered)
                continue
            if prompt.lower().startswith("/tilt "):
                _, _, text = prompt.partition(" ")
                rendered = render_tilt_text(text)
                mediator = tui_mod.active_mediator()
                if (
                    mediator is not None
                    and session.duck_mode
                    and mediator.can_show_visual_panel()
                ):
                    mediator.set_visual_panel("tilt", rendered)
                else:
                    show(rendered)
                continue
            if prompt.lower() in {"/model", "/models pick"}:
                action, value = _model_picker(active_model_dir=model_dir, loaded=engine is not None)
                if action == "list":
                    show(_model_list(model_dir, engine is not None))
                    continue
                if action == "cancel":
                    continue
                if action == "unload":
                    push_snapshot(preserve_transcript=True)
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
                    deleting_active = _catalog_model_path(value) == model_dir
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
                    model_error = _model_path_error(next_model_dir)
                    if model_error:
                        show(model_error)
                        continue
                    push_snapshot(preserve_history=True, preserve_transcript=True)
                    switched = next_model_dir != model_dir
                    if switched:
                        unload_engine()
                        session.reset()
                        model_dir = next_model_dir
                        sync_thinking_effort_to_model()
                        sync_sampling_to_model()
                        _save_active_model(model_dir)
                        estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                    ensure_engine()
                    if switched:
                        redraw_tui_history()
                    continue
            if prompt.lower() in {"/model list", "/models"}:
                show(_model_list(model_dir, engine is not None))
                continue
            if _command_matches(prompt, "/model load"):
                _, _, value = prompt.partition("/model load ")
                pushed = False
                if value.strip():
                    next_model_dir = _resolve_model(value.strip())
                    model_error = _model_path_error(next_model_dir)
                    if model_error:
                        show(model_error)
                        continue
                    if next_model_dir != model_dir:
                        push_snapshot(preserve_history=True, preserve_transcript=True)
                        pushed = True
                        unload_engine()
                        session.reset()
                        model_dir = next_model_dir
                        sync_thinking_effort_to_model()
                        sync_sampling_to_model()
                        _save_active_model(model_dir)
                        estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
                if not pushed:
                    push_snapshot()
                ensure_engine()
                if pushed:
                    redraw_tui_history()
                continue
            if prompt.lower() == "/model unload":
                push_snapshot(preserve_transcript=True)
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
                deleting_active = _catalog_model_path(model_name) == model_dir
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
            if _command_matches(prompt, "/model use") or _command_matches(
                prompt, "/model import"
            ) or (
                _command_matches(prompt, "/model") and prompt.lower() not in {"/model list"}
            ):
                if prompt.lower().startswith("/model use "):
                    _, _, value = prompt.partition("/model use ")
                elif prompt.lower().startswith("/model import "):
                    _, _, value = prompt.partition("/model import ")
                else:
                    _, _, value = prompt.partition(" ")
                value = value.strip()
                local_candidate = Path(value).expanduser()
                if (
                    prompt.lower().startswith("/model import ")
                    and not local_candidate.exists()
                    and is_hf_repo_reference(value)
                ):
                    try:
                        next_model_dir = download_with_status(value)
                    except Exception as exc:
                        show(str(exc))
                        continue
                else:
                    next_model_dir = _resolve_model(value)
                model_error = _model_path_error(next_model_dir)
                if model_error:
                    show(model_error)
                    continue
                push_snapshot(preserve_history=True, preserve_transcript=True)
                unload_engine()
                session.reset()
                model_dir = next_model_dir
                sync_thinking_effort_to_model()
                sync_sampling_to_model()
                _save_active_model(model_dir)
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
                snapshot = take_snapshot()
                try:
                    session.tools.set_workspace(Path(path.strip()))
                except ValueError as exc:
                    show(str(exc))
                    continue
                commit_snapshot(snapshot)
                show(f"workspace={session.tools.workspace_root}")
                continue
            if prompt.lower().startswith("/cd "):
                _, _, path = prompt.partition(" ")
                snapshot = take_snapshot()
                try:
                    session.tools.set_cwd(Path(path.strip()))
                except ValueError as exc:
                    show(str(exc))
                    continue
                commit_snapshot(snapshot)
                show(f"cwd={session.tools.cwd}")
                continue
            if prompt.lower() == "/permissions":
                selected = _permission_picker(session.tools.permission_mode)
                if selected is not None and selected != session.tools.permission_mode:
                    push_snapshot()
                    session.tools.permission_mode = selected
                mediator = tui_mod.active_mediator()
                if mediator is not None:
                    mediator.show_notice(f"Permission mode: {session.tools.permission_mode}")
                else:
                    show(f"permissions={session.tools.permission_mode}")
                continue
            if prompt.lower() in {"/permissions ask", "/permissions allow"}:
                next_permission = prompt.rsplit(" ", 1)[1]
                if next_permission != session.tools.permission_mode:
                    push_snapshot()
                    session.tools.permission_mode = next_permission
                mediator = tui_mod.active_mediator()
                if mediator is not None:
                    mediator.show_notice(f"Permission mode: {session.tools.permission_mode}")
                else:
                    show(f"permissions={session.tools.permission_mode}")
                continue
            if prompt.lower() == "/project":
                show(_project_status(session.tools.cwd))
                continue
            if _command_matches(prompt, "/export"):
                _, _, path_text = prompt.partition(" ")
                target = Path(path_text.strip() or (EXPORT_DIR / "openvino-chat.md"))
                if not target.is_absolute():
                    target = session.tools.cwd / target
                _export_markdown(target, session.history)
                show(f"exported={target}")
                continue
            if _command_matches(prompt, "/system"):
                snapshot = take_snapshot()
                before = session.system_prompt_template
                try:
                    result = _handle_system_command(prompt, session, session.tools.cwd)
                except OSError as exc:
                    show(f"system failed: {exc}")
                    continue
                if session.system_prompt_template != before:
                    commit_snapshot(snapshot)
                show(result)
                continue
            if prompt.lower() == "/session":
                try:
                    action, value = _session_picker(
                        store=sessions,
                        active_session=active_session,
                    )
                except (OSError, ValueError) as exc:
                    show(f"session picker failed: {exc}")
                    continue
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
                    saved = auto_save_session()
                    if session.history and saved is None:
                        continue
                    push_snapshot(preserve_history=True, preserve_transcript=True)
                    active_session = _auto_session_name([])
                    session.reset()
                    redraw_tui_history()
                    show(f"new session: {active_session}")
                    continue
                if action == "delete" and value:
                    try:
                        sessions.delete(value)
                    except (OSError, ValueError) as exc:
                        show(f"session delete failed: {exc}")
                        continue
                    show(f"deleted={value}")
                    continue
                if action == "load" and value:
                    saved = auto_save_session()
                    if session.history and saved is None:
                        continue
                    if load_saved_session(value):
                        show(f"loaded={active_session}")
                    continue
            if prompt.lower() == "/delete":
                name = active_session
                if name == "default" and session.history:
                    saved = auto_save_session()
                    name = saved or name
                if name != "default":
                    try:
                        sessions.delete(name)
                    except (OSError, ValueError) as exc:
                        show(f"session delete failed: {exc}")
                        continue
                    show(f"deleted session={name}")
                else:
                    show("nothing to delete")
                return 0
            if prompt.lower() == "/sessions":
                try:
                    names = sessions.list_sessions()
                except OSError as exc:
                    show(f"session list failed: {exc}")
                    continue
                show("\n".join(names) if names else "no saved sessions")
                continue
            if _command_matches(prompt, "/new"):
                _, _, name = prompt.partition(" ")
                saved = auto_save_session()
                if session.history and saved is None:
                    continue
                push_snapshot(preserve_history=True, preserve_transcript=True)
                active_session = name.strip() or "default"
                session.reset()
                redraw_tui_history()
                show(f"new session: {active_session}")
                continue
            if _command_matches(prompt, "/save"):
                _, _, name = prompt.partition(" ")
                requested_session = name.strip() or active_session
                try:
                    path = _save_session(
                        sessions,
                        requested_session,
                        session.history,
                        model_name_from_dir(model_dir),
                        active_device(),
                        state=session_state(),
                    )
                except (OSError, TypeError, ValueError) as exc:
                    show(f"session save failed: {exc}")
                    continue
                active_session = requested_session
                show(f"saved={path}")
                continue
            if prompt.lower().startswith("/load "):
                _, _, name = prompt.partition(" ")
                saved = auto_save_session()
                if session.history and saved is None:
                    continue
                if load_saved_session(name.strip()):
                    show(f"loaded={active_session}")
                continue
            if prompt.lower().startswith("/delete "):
                _, _, name = prompt.partition(" ")
                try:
                    sessions.delete(name.strip())
                except (OSError, ValueError) as exc:
                    show(f"session delete failed: {exc}")
                    continue
                show(f"deleted={name.strip()}")
                continue
            if not prompt:
                continue
            request = parse_slash_tool(prompt)
            if request is not None:
                snapshot = take_snapshot(preserve_transcript=True)
                tool_checkpoint = session.tools.checkpoint()
                if use_live_work_ui():
                    monitor.start()
                try:
                    if use_live_work_ui():
                        _set_monitor_tool(monitor, request.name)
                    request_text = format_tool_request_text(request.name, request.args)
                    if use_live_work_ui() and monitor.active:
                        monitor.write_response(request_text, "dim", "\n")
                    elif not defer_output():
                        ui.tool_request(request.name, request.args)
                    tool_result = session.tools.run(request)
                    result = tool_result.output
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
                if tool_result.ok and (
                    session.tools.checkpoint() != tool_checkpoint
                    or request.name == "shell"
                ):
                    commit_snapshot(snapshot)
                continue
            if prompt.startswith("/"):
                show(f"unknown command: {prompt.split()[0]}\ntype / to list commands")
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
    temperature: float | None,
    top_p: float | None,
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
        if phase == "compacted":
            stream.finish()
            turns = int(event.get("turns") or 0)
            before = int(event.get("before_tokens") or 0)
            after = int(event.get("after_tokens") or 0)
            text = f"context compacted: {turns} turns | {before} -> {after} tokens"
            notice = getattr(monitor, "notice", None) if monitor is not None else None
            if callable(notice):
                notice(text)
            elif monitor is not None and getattr(monitor, "active", False):
                monitor.write_response(text, "dim", "\n")
            else:
                ui.print(text)
            return
        if phase == "tool":
            tool = str(event.get("tool") or "")
            args = event.get("args")
            stream.finish()
            if monitor is not None:
                _set_monitor_tool(monitor, tool)
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


def _set_monitor_tool(monitor: object, name: str) -> None:
    set_tool = getattr(monitor, "set_tool", None)
    if callable(set_tool):
        set_tool(name)
        return
    monitor.set(status_label(name))


def _generation_effort_status(
    model_dir: Path,
    effort: str,
    thinking_effort: str,
    sampling_overrides: dict[str, float | int] | None = None,
) -> str:
    model_name = model_name_from_dir(model_dir)

    def rendered(profile: str) -> str:
        values = generation_settings(
            model_name,
            profile,
            thinking_effort,
            generation_effort=effort,
        )
        if effort == "custom":
            values.update(sampling_overrides or {})
        order = (
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "presence_penalty",
            "repetition_penalty",
        )
        return ", ".join(f"{key}={values[key]}" for key in order if key in values)

    lines = [
        f"effort={effort}",
        f"thinking={thinking_effort}",
        (
            "control=manual sampling; saved for this model"
            if effort == "custom"
            else "control=sampling preset; explicit generation options override it"
        ),
    ]
    general = rendered("general")
    coding = rendered("coding")
    if effort == "medium" and coding != general:
        lines.extend([f"general={general}", f"coding={coding}"])
    else:
        lines.append(f"sampling={general}")
    return "\n".join(lines)


def _live_status_text(
    device: str,
    context_length: int,
    kv_cache_precision: str = "auto",
    thinking_effort: str = DEFAULT_THINKING_EFFORT,
    generation_effort: str = DEFAULT_GENERATION_EFFORT,
    duck_mode: bool = DEFAULT_DUCK_MODE,
    model_name: str | None = None,
    loaded: bool | None = None,
    context_used: int | None = None,
    auto_compact: bool | None = None,
) -> str:
    identity: list[str] = []
    if model_name:
        identity.append(f"model: {model_name}")
    if loaded is not None:
        identity.append(f"state: {'ready' if loaded else 'lazy'}")
    metrics = format_live_status(
        device,
        context_length,
        kv_cache_precision=kv_cache_precision,
    )
    if context_used is not None:
        used = max(0, int(context_used))
        percent = min(999, int(used * 100 / max(1, context_length)))
        metrics = re.sub(
            r"(?m)^ctx:\s*.*$",
            f"ctx: {used}/{context_length} ({percent}%)",
            metrics,
            count=1,
        )
    modes = [metrics, f"effort: {generation_effort}", f"think: {thinking_effort}"]
    if auto_compact is not None:
        modes.append(f"compact: {'auto' if auto_compact else 'off'}")
    if duck_mode:
        modes.append("quack: loud")
    return "\n".join(identity + modes)


def _chat_window_text(
    history: list[tuple[str, str]],
    display_messages: list[tuple[int, str]] | None = None,
    max_turns: int = 12,
    raw: bool = False,
    duck_mode: bool = False,
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
            accent = tui_mod.ORANGE if duck_mode else tui_mod.CYAN
            label = "Quack" if duck_mode else "openvino"
            lines.append(f"{accent}{label}:{tui_mod.RESET}")
            lines.append(_chat_content(message, raw))
            lines.append("")

    append_messages(start_index)
    for offset, (role, content) in enumerate(visible_history, start=start_index):
        if role == "user":
            lines.append("> " + _chat_content(content, raw))
        else:
            lines.append(_assistant_chat_content(content, raw, duck_mode=duck_mode))
        lines.append("")
        append_messages(offset + 1)
    return "\n".join(lines).strip()


def _chat_content(text: str, raw: bool) -> str:
    clean = sanitize_tool_artifacts(_ANSI_ESCAPE.sub("", text))
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


def _assistant_chat_content(text: str, raw: bool, duck_mode: bool = False) -> str:
    clean = sanitize_tool_artifacts(_ANSI_ESCAPE.sub("", text))
    accent = tui_mod.ORANGE if duck_mode else tui_mod.GREEN
    if raw:
        return f"{accent}> \x1b[0m{clean}"
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
        parts.append(f"{accent}> \x1b[0m{rendered}")
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
        session.reset_system_prompt()
        return "system reset"
    if _command_matches(command, "/system set"):
        text = command[len("/system set ") :]
        session.system_prompt_template = _decode_system_text(text)
        return "system set"
    if _command_matches(command, "/system append"):
        text = command[len("/system append ") :]
        addition = _decode_system_text(text)
        session.system_prompt_template = session.system_prompt_template.rstrip() + "\n" + addition
        return "system appended"
    if _command_matches(command, "/system save"):
        _, _, text = command.partition(" ")
        _, _, path_text = text.partition(" ")
        target = _resolve_user_path(path_text.strip() or "openvino-system-prompt.txt", cwd)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(session.system_prompt_template, encoding="utf-8")
        return f"system saved={target}"
    if _command_matches(command, "/system load"):
        path_text = command[len("/system load ") :]
        source = _resolve_user_path(path_text.strip(), cwd)
        session.system_prompt_template = source.read_text(encoding="utf-8")
        return f"system loaded={source}"
    return "usage: /system [show|set <text>|append <text>|reset|save [path]|load <path>]"


def _decode_system_text(text: str) -> str:
    return text.strip().replace("\\n", "\n")


def _resolve_user_path(path_text: str, cwd: Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return cwd / path


def _help_text() -> str:
    return (
        _format_command_specs("OpenVINO Chat commands", COMMAND_SPECS + ADVANCED_COMMAND_SPECS)
        + "\n\nKeys:"
        + "\n  Esc                         Stop current generation."
        + "\n  PageUp / PageDown           Scroll chat history."
        + "\n  Ctrl+Up / Ctrl+Down         Scroll history by three rows."
        + "\n  Drag                         Select terminal text."
        + "\n  F6                           Toggle mouse-wheel history scrolling."
        + "\n  Shift+drag                   Select while mouse scrolling is enabled."
        + "\n  Ctrl+Home / Ctrl+End        Oldest / latest message."
        + "\n  Up/Down or Ctrl+N/Ctrl+P    Navigate slash command palette."
        + "\n  Tab / Enter / Esc           Complete / run / close palette."
        + "\n  Home/End or PageUp/PageDown Navigate model and session pickers."
    )


def _commands_text() -> str:
    return _format_command_specs("Command Palette")


def _format_command_specs(
    title: str,
    specs: tuple[CommandSpec, ...] = COMMAND_SPECS,
) -> str:
    lines = [title, ""]
    groups = []
    for spec in specs:
        if spec.group not in groups:
            groups.append(spec.group)
    for group in groups:
        lines.append(f"{group}:")
        for spec in specs:
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


def _model_catalog() -> dict[str, Path]:
    return discover_model_dirs(MODEL_ROOT, MODEL_DIRS)


def _catalog_model_path(value: str) -> Path | None:
    key = value.strip().casefold()
    return next(
        (path for name, path in _model_catalog().items() if name.casefold() == key),
        None,
    )


def _model_repo(name: str, path: Path) -> str:
    return (
        MODEL_REPOS.get(name.lower())
        or model_repo_for_path(path, MODEL_DIRS, MODEL_REPOS)
        or "-"
    )


def _resolve_model(value: str) -> Path:
    configured = _catalog_model_path(value)
    if configured is not None:
        return configured
    return Path(value).expanduser()


def _available_models_summary() -> str:
    return ", ".join(
        f"{name}: {_model_install_state(path)}"
        for name, path in _model_catalog().items()
    )


def _model_list(active_model_dir: Path, loaded: bool) -> str:
    lines = [
        "Available models",
        f"active: {active_model_dir}",
        f"loaded: {'yes' if loaded else 'no'}",
        f"root: {MODEL_ROOT}",
        "",
    ]
    for name, path in _model_catalog().items():
        marker = "*" if path == active_model_dir else " "
        state = _model_install_state(path)
        size = _model_dir_size_text(path)
        repo = _model_repo(name, path)
        active = " active" if path == active_model_dir else ""
        loaded_text = " loaded" if path == active_model_dir and loaded else ""
        lines.append(f"{marker} {name}: {state}{active}{loaded_text}")
        lines.append(f"  repo: {repo}")
        lines.append(f"  size: {size}")
        lines.append("  effort: " + ", ".join(reversed(GENERATION_EFFORTS)))
        lines.append(
            "  thinking: " + ", ".join(reversed(thinking_efforts_for_model(path)))
        )
        lines.append(f"  path: {path}")
    return "\n".join(lines)


def _model_install_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "installed" if _validate_model_dir(path) else "invalid"


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
