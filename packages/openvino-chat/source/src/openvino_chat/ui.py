from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable
from typing import Any

from openvino_chat.tasks import has_visible_tasks


class ChatUI:
    def __init__(self) -> None:
        self.duck_theme = False
        try:
            from rich.console import Console
            from rich.console import Group
            from rich.markdown import Markdown
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            self.console = None
            self.group_cls = None
            self.markdown_cls = None
            self.panel_cls = None
            self.table_cls = None
            self.text_cls = None
        else:
            self.console = Console()
            self.group_cls = Group
            self.markdown_cls = Markdown
            self.panel_cls = Panel
            self.table_cls = Table
            self.text_cls = Text

    @property
    def accent(self) -> str:
        return "#ff9f1c" if self.duck_theme else "cyan"

    @property
    def answer_style(self) -> str:
        return "#ff9f1c" if self.duck_theme else "green"

    def set_duck_theme(self, enabled: bool) -> None:
        self.duck_theme = bool(enabled)

    def banner(
        self,
        device: str,
        context_length: int | None = None,
        est_ram: str | None = None,
        model_name: str = "model",
        loaded: bool = False,
        models_summary: str | None = None,
    ) -> None:
        quick = "/help /model /effort /api /system /status /tools /ctx /kv /exit"
        if self.console and self.panel_cls and self.table_cls and self.group_cls and self.text_cls:
            grid = self.table_cls.grid(expand=True)
            for _ in range(4):
                grid.add_column(ratio=1)
            accent = self.accent
            grid.add_row(
                f"[dim]model[/dim]\n[bold {accent}]" + model_name + f"[/bold {accent}]",
                f"[dim]device[/dim]\n[bold {accent}]" + device + f"[/bold {accent}]",
                "[dim]loaded[/dim]\n" + (f"[bold {accent}]yes[/bold {accent}]" if loaded else "[yellow]no[/yellow]"),
                "[dim]ctx[/dim]\n" + (str(context_length) if context_length is not None else "-"),
            )
            parts = [grid]
            if models_summary:
                parts.append(self.text_cls("models: " + models_summary, style="dim"))
            parts.append(self.text_cls(quick, style="dim"))
            body = self.group_cls(*parts)
            title = "OpenVINO Quack" if self.duck_theme else "OpenVINO Chat"
            self.console.print(
                self.panel_cls(
                    body,
                    title=f"[bold {accent}]{title}[/bold {accent}]",
                    border_style=accent,
                )
            )
        else:
            bits = [
                f"model {model_name}",
                f"device {device}",
                f"loaded {'yes' if loaded else 'no'}",
            ]
            if context_length is not None:
                bits.append(f"ctx {context_length}")
            model_line = f"\nmodels: {models_summary}" if models_summary else ""
            print("  ".join(bits) + model_line + "\n" + quick)

    def user_prompt(self) -> str:
        return "> "

    def assistant_prefix(self, model_name: str = "Assistant") -> None:
        if self.console:
            self.print(f"[bold {self.answer_style}]>[/bold {self.answer_style}] ", end="")
        else:
            self.print("> ", end="")

    def print(self, text: Any = "", end: str = "\n") -> None:
        if self.console:
            self.console.print(text, end=end)
        else:
            print(text, end=end)

    def print_plain(self, text: str = "", end: str = "\n") -> None:
        if self.console:
            self.console.print(text, end=end, markup=False, highlight=False)
        else:
            print(text, end=end)

    def tool_result(self, text: str) -> None:
        if self.console and self.panel_cls:
            self.console.print(self.panel_cls(text, title="[dim]tool output[/dim]", border_style="dim"))
        else:
            print(text)

    def help(self, text: str) -> None:
        if self.console and self.panel_cls:
            self.console.print(
                self.panel_cls(
                    text,
                    title=f"[bold {self.accent}]Help[/bold {self.accent}]",
                    border_style=self.accent,
                )
            )
        else:
            print(text)

    def assistant_message(self, text: str, model_name: str = "Assistant") -> None:
        stream = self.response_stream()
        stream.write(text)
        stream.finish()

    def response_stream(self) -> "ResponseStream":
        return ResponseStream(self.console, answer_style=self.answer_style)

    @contextmanager
    def live_status(self, status_text: Callable[[], str], refresh_seconds: float = 3.0):
        monitor = self.status_monitor(status_text, refresh_seconds)
        monitor.start()
        try:
            yield monitor
        finally:
            monitor.stop()

    def status_monitor(
        self,
        status_text: Callable[[], str],
        refresh_seconds: float = 3.0,
        layout: str = "side",
        tasks_text: Callable[[], str] | None = None,
    ) -> "LiveStatusMonitor":
        return LiveStatusMonitor(
            status_text=status_text,
            console=self.console,
            refresh_seconds=refresh_seconds,
            layout=layout,
            tasks_text=tasks_text,
            accent=lambda: self.accent,
        )

    def tool_request(self, name: str, args: dict[str, Any]) -> None:
        self.print(format_tool_request(name, args))


@dataclass
class OperationStatus:
    label: str
    started_at: float

    def render(self, now: float | None = None) -> str:
        current = time.monotonic() if now is None else now
        elapsed = max(0, int(current - self.started_at))
        return f"{self.label} {elapsed}s"


class LiveStatusMonitor:
    def __init__(
        self,
        status_text: Callable[[], str],
        console: Any = None,
        refresh_seconds: float = 3.0,
        layout: str = "side",
        tasks_text: Callable[[], str] | None = None,
        accent: Callable[[], str] | None = None,
    ) -> None:
        self.status_text = status_text
        self.console = console
        self.refresh_seconds = refresh_seconds
        self.layout = layout
        self.tasks_text = tasks_text or (lambda: "no tasks")
        self.accent = accent or (lambda: "cyan")
        self.operation: OperationStatus | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._live = None
        self._response_segments: list[tuple[str, str | None]] = []

    def start(self) -> None:
        if self._live is not None:
            return
        self._stop.clear()
        if self.console is None:
            return
        if not getattr(self.console, "is_terminal", False):
            return
        from rich.live import Live

        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            screen=self.layout == "window",
        )
        self._live.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        if self._live is not None:
            self._live.stop()
            self._live = None

    @property
    def active(self) -> bool:
        return self._live is not None

    def set(self, label: str) -> None:
        self.operation = OperationStatus(label, time.monotonic())
        self.refresh()

    def update(self, label: str) -> None:
        if self.operation is None:
            self.set(label)
            return
        self.operation.label = label
        self.refresh()

    def clear(self, refresh: bool = True) -> None:
        self.operation = None
        if refresh:
            self.refresh()

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render(), refresh=True)

    def _loop(self) -> None:
        while not self._stop.wait(self.refresh_seconds):
            self.refresh()

    def _render(self) -> Any:
        from rich.console import Group
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        text = format_status_block(self.status_text())
        if self.operation is not None:
            text.append("\n")
            text.append(self.operation.render(), style=status_color(self.operation.label))
        response = _render_response_segments(self._response_segments, Group, Markdown, Text)
        if self.layout == "statusline":
            status_text = format_status_line(self.status_text())
            if self.operation is not None:
                if status_text.plain:
                    status_text.append(" | ", style="dim")
                status_text.append(self.operation.render(), style=status_color(self.operation.label))
            return Group(response, Panel(status_text, border_style=self.accent()))
        if self.layout == "window":
            status_text = format_status_line(self.status_text())
            if self.operation is not None:
                if status_text.plain:
                    status_text.append(" | ", style="dim")
                status_text.append(self.operation.render(), style=status_color(self.operation.label))
            task_text = self.tasks_text() or "no tasks"
            grid = Table.grid(expand=True)
            grid.add_column(ratio=1)
            if has_visible_tasks(task_text):
                grid.add_column(width=34)
                grid.add_row(response, Text(task_text, style="dim"))
            else:
                grid.add_row(response)
            return Group(grid, status_text)

        status_panel = Panel(text, title="Live", border_style=self.accent())
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(width=34)
        grid.add_row(response, status_panel)
        return grid

    def response_stream(self) -> "ResponseStream":
        self._response_segments.clear()
        return ResponseStream(
            writer=self.write_response,
            phase_callback=self.set,
            answer_style=self.accent(),
        )

    def write_response(self, text: str, style: str | None = None, end: str = "") -> None:
        if text:
            self._response_segments.append((text, style))
        if end:
            self._response_segments.append((end, style))
        self.refresh()


def split_thinking(text: str) -> tuple[str, str]:
    stripped = text.strip()
    match = re.match(
        r"^(?:<(?:think|thinking|analysis)>)?(.*?)(?:</(?:think|thinking|analysis)>|<(?:think|thinking|analysis)\s*/>)\s*(.*)$",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match is None:
        match = re.match(
            r"^(?:<\|channel>(?:thought|analysis)\s*)?(.*?)<channel\|>\s*(.*)$",
            stripped,
            flags=re.DOTALL | re.IGNORECASE,
        )
    if match is None:
        open_only = re.match(
            r"^(?:<(?:think|thinking|analysis)>|<\|channel>(?:thought|analysis))\s*(.*)$",
            stripped,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if open_only is not None:
            return open_only.group(1).strip(), ""
    if match is None:
        return "", stripped
    return match.group(1).strip(), match.group(2).strip()


_TOOL_PROTOCOL_TAG = re.compile(
    r"\\?<\s*(?P<closing>/?)\s*(?:\|\s*)?tool\\?_call(?:\s*\|)?\s*\\?>",
    flags=re.IGNORECASE,
)
_NATIVE_PROTOCOL_TAG = re.compile(
    r"\\?<\s*/?\s*(?:function(?:=[^>]*)?|parameter(?:=[^>]*)?)\s*\\?>",
    flags=re.IGNORECASE,
)


def sanitize_tool_artifacts(text: str) -> str:
    """Remove model protocol wrappers that must never become chat text."""
    canonical = _TOOL_PROTOCOL_TAG.sub(
        lambda match: "</tool_call>" if match.group("closing") else "<tool_call>",
        text,
    )
    canonical = re.sub(
        r"<tool_call>.*?</tool_call>",
        "",
        canonical,
        flags=re.DOTALL | re.IGNORECASE,
    )
    canonical = re.sub(r"</?tool_call>", "", canonical, flags=re.IGNORECASE)
    return _NATIVE_PROTOCOL_TAG.sub("", canonical)


def status_color(label: str) -> str:
    if label.startswith(("loading model", "downloading model", "compacting")):
        return "cyan"
    return {
        "thinking": "blue",
        "generating": "yellow",
        "running command": "green",
        "searching web": "green",
        "searching history": "green",
        "running tool": "green",
    }.get(label, "white")


def status_label(tool_name: str) -> str:
    if tool_name == "shell":
        return "running command"
    if tool_name in {"web_search", "web_fetch"}:
        return "searching web"
    if tool_name == "luci_history":
        return "searching history"
    return "running tool"


def format_status_line(status_text: str) -> Any:
    from rich.text import Text

    text = Text()
    for index, line in enumerate(line for line in status_text.splitlines() if line.strip()):
        if index:
            text.append(" | ", style="dim")
        _append_status_item(text, line)
    return text


def format_status_block(status_text: str) -> Any:
    from rich.text import Text

    text = Text()
    for index, line in enumerate(line for line in status_text.splitlines() if line.strip()):
        if index:
            text.append("\n")
        _append_status_item(text, line)
    return text


def format_tool_request(name: str, args: dict[str, Any]) -> str:
    return f"[dim]{format_tool_request_text(name, args)}[/dim]"


def format_tool_request_text(name: str, args: dict[str, Any]) -> str:
    encoded = json.dumps(args, ensure_ascii=False)
    return f"tool: {name} {encoded}"


def _append_status_item(text: Any, line: str) -> None:
    label, value = _split_status_item(line)
    if value is None:
        text.append(label, style="cyan")
        return
    text.append(label, style="cyan")
    text.append(": ")
    text.append(value)


def _split_status_item(line: str) -> tuple[str, str | None]:
    clean = line.strip()
    if ": " in clean:
        label, value = clean.split(": ", 1)
        return label.replace("_", " "), value
    if "=" in clean:
        label, value = clean.split("=", 1)
        return label.replace("_", " "), value
    return clean.replace("_", " "), None


def _render_response_segments(segments: list[tuple[str, str | None]], group_cls: Any, markdown_cls: Any, text_cls: Any) -> Any:
    if _needs_code_coloring(segments):
        text = text_cls()
        for segment, style in segments:
            if style is None:
                text.append_text(format_code_colored_text(_strip_code_fences(segment)))
            else:
                text.append(segment, style=_rich_style(style))
        return text
    if not _needs_markdown(segments):
        text = text_cls()
        for segment, style in segments:
            text.append(segment, style=_rich_style(style))
        return text

    renderables = []
    pending_plain = text_cls()
    pending_markdown = []

    def flush_plain() -> None:
        nonlocal pending_plain
        if pending_plain.plain:
            renderables.append(pending_plain)
            pending_plain = text_cls()

    def flush_markdown() -> None:
        if pending_markdown:
            renderables.append(markdown_cls("".join(pending_markdown), code_theme="monokai"))
            pending_markdown.clear()

    for segment, style in segments:
        if style is None:
            flush_plain()
            pending_markdown.append(segment)
            continue
        flush_markdown()
        pending_plain.append(segment, style=_rich_style(style))
    flush_markdown()
    flush_plain()
    return group_cls(*renderables) if renderables else text_cls()


def _rich_style(style: str | None) -> str | None:
    return "bright_black" if style == "thinking" else style


def _needs_markdown(segments: list[tuple[str, str | None]]) -> bool:
    text = "".join(segment for segment, style in segments if style is None)
    return any(marker in text for marker in ("```", "**", "__", "`", "### ", "## ", "# ", "- ", "1. "))


def format_code_colored_text(text: str) -> Any:
    from rich.text import Text

    result = Text()
    for line in text.splitlines(keepends=True):
        body = line[:-1] if line.endswith("\n") else line
        newline = "\n" if line.endswith("\n") else ""
        result.append(body, style=_code_line_style(body))
        if newline:
            result.append(newline)
    return result


def _code_line_style(line: str) -> str | None:
    stripped = line.lstrip()
    if stripped.startswith("+") and not stripped.startswith("+++"):
        return "green"
    if stripped.startswith("-") and not stripped.startswith("---"):
        return "red"
    if stripped.startswith("@@"):
        return "cyan"
    if stripped.startswith(("#", "//", "/*", "* ")):
        return "dim"
    keyword_prefixes = (
        "def ",
        "class ",
        "function ",
        "import ",
        "from ",
        "return ",
        "if ",
        "elif ",
        "else",
        "for ",
        "while ",
        "try",
        "except ",
        "catch ",
        "const ",
        "let ",
        "var ",
        "async ",
        "await ",
        "public ",
        "private ",
        "protected ",
    )
    return "cyan" if stripped.startswith(keyword_prefixes) else None


def _needs_code_coloring(segments: list[tuple[str, str | None]]) -> bool:
    text = "".join(segment for segment, style in segments if style is None)
    lines = text.splitlines()
    has_diff_add = any(line.lstrip().startswith("+") and not line.lstrip().startswith("+++") for line in lines)
    has_diff_remove = any(line.lstrip().startswith("-") and not line.lstrip().startswith("---") for line in lines)
    script_lines = [line for line in lines if _code_line_style(line) == "cyan"]
    has_script = len(script_lines) >= 2 or any(
        line.lstrip().startswith(("def ", "class ", "function ", "import ", "from "))
        or any(symbol in line for symbol in ("(", ")", "{", "}", ";"))
        for line in script_lines
    )
    return (has_diff_add and has_diff_remove) or has_script


def _strip_code_fences(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "".join(lines)


class ResponseStream:
    def __init__(
        self,
        console: Any = None,
        writer: Callable[[str, str | None, str], None] | None = None,
        phase_callback: Callable[[str], None] | None = None,
        answer_style: str = "green",
    ) -> None:
        self.console = console
        self.writer = writer
        self.phase_callback = phase_callback
        self.answer_style = answer_style
        self.buffer = ""
        self.started = False
        self.thinking = False
        self.wrote = False
        self.answer_started = False
        self.thought_started = False
        self.line_ended = True
        self._reported_phase: str | None = None

    def write(self, token: str) -> None:
        if not token:
            return
        self.buffer += token
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)
        if self.thinking:
            self._leave_thinking()
        if self.started and not self.line_ended:
            self._print("", end="\n")
        self.started = False
        self.thinking = False
        self.answer_started = False
        self.thought_started = False
        self.line_ended = True
        self._reported_phase = None

    def _drain(self, final: bool) -> None:
        while self.buffer:
            tag = self._next_complete_tag(self.buffer)
            if tag is None:
                safe_len = len(self.buffer) if final else _safe_text_length(self.buffer)
                if safe_len <= 0:
                    return
                self._emit(self.buffer[:safe_len])
                self.buffer = self.buffer[safe_len:]
                continue
            index, marker = tag
            if index:
                if marker.lower() in _THINK_CLOSE_MARKERS and not self.thinking:
                    self.thinking = True
                    self._emit(self.buffer[:index])
                    self._leave_thinking()
                else:
                    self._emit(self.buffer[:index])
            self.buffer = self.buffer[index + len(marker):]
            if marker.lower() in _THINK_OPEN_MARKERS:
                self.thinking = True
                self._report_phase("thinking")
            else:
                self._leave_thinking()

    def _emit(self, text: str) -> None:
        if not text:
            return
        if self.thinking:
            self._report_phase("thinking")
            self._print(text, style="thinking", end="")
            self.thought_started = True
            self.started = True
            self.line_ended = text.endswith("\n")
            self.wrote = True
            return
        if not self.answer_started:
            self._report_phase("generating")
            if self.started and not self.line_ended:
                self._print("", end="\n")
            self._print("> ", style=self.answer_style, end="")
            self.answer_started = True
        self._print(text, end="")
        self.started = True
        self.line_ended = text.endswith("\n")
        self.wrote = True

    def _leave_thinking(self) -> None:
        if self.thought_started and not self.line_ended:
            self._print("", style="thinking", end="\n")
            self.line_ended = True
        self.thinking = False

    def _report_phase(self, phase: str) -> None:
        if self.phase_callback is None or phase == self._reported_phase:
            return
        self._reported_phase = phase
        self.phase_callback(phase)

    def _print(self, text: str, style: str | None = None, end: str = "") -> None:
        if self.writer is not None:
            self.writer(text, style, end)
            return
        if self.console is not None:
            rich_style = "bright_black" if style == "thinking" else style
            self.console.print(text, style=rich_style, end=end, highlight=False, markup=False)
        else:
            print(text, end=end)

    @staticmethod
    def _next_complete_tag(text: str) -> tuple[int, str] | None:
        candidates = []
        lower = text.lower()
        for marker in (*_THINK_OPEN_MARKERS, *_THINK_CLOSE_MARKERS):
            index = lower.find(marker)
            if index >= 0:
                candidates.append((index, marker))
        return min(candidates, default=None, key=lambda item: item[0])


def _safe_text_length(text: str) -> int:
    keep = 0
    lower = text.lower()
    for marker in (*_THINK_OPEN_MARKERS, *_THINK_CLOSE_MARKERS):
        for size in range(1, min(len(marker), len(text))):
            if lower.endswith(marker[:size]):
                keep = max(keep, size)
    return len(text) - keep


_THINK_OPEN_MARKERS = (
    "<think>",
    "<thinking>",
    "<analysis>",
    "<|channel>thought",
    "<|channel>analysis",
)
_THINK_CLOSE_MARKERS = (
    "</think>",
    "<think/>",
    "<think />",
    "</thinking>",
    "<thinking/>",
    "<thinking />",
    "</analysis>",
    "<analysis/>",
    "<analysis />",
    "<channel|>",
)
