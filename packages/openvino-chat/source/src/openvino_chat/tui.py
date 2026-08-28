"""Persistent full-screen TUI for openvino-chat.

A single long-lived prompt_toolkit ``Application`` owns the screen for the
whole REPL session. The existing ``_repl`` loop runs on a worker thread and
looks exactly like it always did: it calls ``_input_with_status`` each turn,
dispatches slash commands / model generation, then loops. The TUI acts as a
mediator — when the worker asks for input, the TUI's accept handler delivers
the typed text and the worker proceeds; the app never exits between turns.

Model streaming tokens, tool-call notices and slash-command output all flow
into a thread-safe :class:`ChatBuffer` rendered by the chat region.
"""

from __future__ import annotations

import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from openvino_chat.tasks import has_visible_tasks

# Module-level flag consulted by ``cli._can_use_fullscreen_picker`` so pickers
# fall back to inline listing while the persistent TUI owns the screen.
_TUI_ACTIVE = False


def is_tui_active() -> bool:
    return _TUI_ACTIVE


def _set_tui_active(value: bool) -> None:
    global _TUI_ACTIVE
    _TUI_ACTIVE = value


GREEN = "\x1b[32m"
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GRAY = "\x1b[90m"
CYAN = "\x1b[36m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
RED = "\x1b[31m"

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class _MutableRegion:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.final: str | None = None

    def append(self, text: str) -> None:
        if self.final is None and text:
            self.parts.append(text)

    def replace(self, text: str) -> None:
        self.final = text
        self.parts.clear()

    def render(self) -> str:
        return self.final if self.final is not None else "".join(self.parts)


@dataclass(frozen=True)
class ChatBufferCheckpoint:
    epoch: int
    segment_count: int


@dataclass(frozen=True)
class ChatBufferState:
    segments: tuple[str, ...]


class ChatBuffer:
    """Thread-safe append-only log of ANSI-styled chat segments."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._segments: list[str | _MutableRegion] = []
        self._dirty = True
        self._snapshot = ""
        self._epoch = 0

    def append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._segments.append(text)
            self._dirty = True

    def append_line(self, text: str = "") -> None:
        self.append(text + "\n")

    def append_user(self, prompt: str) -> None:
        with self._lock:
            tail = next(
                (text for segment in reversed(self._segments) if (text := _segment_text(segment))),
                "",
            )
            spacer = "" if not tail or tail.endswith("\n\n") else "\n" if tail.endswith("\n") else "\n\n"
            self._segments.append(f"{spacer}> {prompt}\n")
            self._dirty = True

    def begin_assistant(self) -> None:
        self.append(f"{GREEN}> {RESET}")

    def append_system(self, text: str) -> None:
        value = str(text)
        if not value:
            return
        with self._lock:
            tail = next(
                (part for segment in reversed(self._segments) if (part := _segment_text(segment))),
                "",
            )
            spacer = "" if not tail or tail.endswith("\n\n") else "\n" if tail.endswith("\n") else "\n\n"
            suffix = "" if value.endswith("\n") else "\n"
            self._segments.append(
                f"{spacer}{CYAN}openvino:{RESET} {value}{suffix}"
            )
            self._dirty = True

    def append_tool(self, name: str, args_text: str) -> None:
        self.append(f"\n{GRAY}[tool] {name}  {args_text}{RESET}\n")

    def append_status(self, label: str) -> None:
        self.append(f"\n{CYAN}[{label}]{RESET} ")

    def append_styled(self, text: str, style: str | None = None, end: str = "") -> None:
        value = text + end
        if not value:
            return
        self.append(_styled(value, style))

    def begin_region(self) -> int:
        with self._lock:
            self._segments.append(_MutableRegion())
            self._dirty = True
            return len(self._segments) - 1

    def append_region(self, index: int, text: str) -> None:
        if not text:
            return
        with self._lock:
            if 0 <= index < len(self._segments):
                region = self._segments[index]
                if isinstance(region, _MutableRegion):
                    region.append(text)
                else:
                    self._segments[index] = region + text
                self._dirty = True

    def update_region(self, index: int, text: str) -> None:
        with self._lock:
            if 0 <= index < len(self._segments):
                region = self._segments[index]
                if isinstance(region, _MutableRegion):
                    region.replace(text)
                else:
                    self._segments[index] = text
                self._dirty = True

    def clear(self) -> None:
        with self._lock:
            self._segments.clear()
            self._dirty = True
            self._epoch += 1

    def replace(self, text: str) -> None:
        with self._lock:
            self._segments[:] = [text] if text else []
            self._dirty = True
            self._epoch += 1

    def checkpoint(self) -> ChatBufferCheckpoint:
        with self._lock:
            return ChatBufferCheckpoint(self._epoch, len(self._segments))

    def capture_checkpoint(self, checkpoint: ChatBufferCheckpoint) -> ChatBufferState:
        with self._lock:
            if checkpoint.epoch != self._epoch:
                raise ValueError("chat checkpoint expired")
            segments = tuple(
                _segment_text(segment)
                for segment in self._segments[: checkpoint.segment_count]
            )
            return ChatBufferState(segments)

    def restore_checkpoint(
        self,
        checkpoint: ChatBufferCheckpoint,
        state: ChatBufferState | None = None,
    ) -> bool:
        with self._lock:
            if state is not None:
                self._segments[:] = list(state.segments)
                self._epoch = checkpoint.epoch
            elif checkpoint.epoch == self._epoch and checkpoint.segment_count <= len(self._segments):
                del self._segments[checkpoint.segment_count :]
            else:
                return False
            self._dirty = True
            self._snapshot = ""
            return True

    def render(self) -> str:
        with self._lock:
            if self._dirty:
                self._snapshot = "".join(_segment_text(segment) for segment in self._segments)
                self._dirty = False
            return self._snapshot

    def render_tail(self, max_rows: int, width: int | None = None) -> str:
        """Return transcript tail fitting visible rows, including wrapped lines."""
        if not max_rows or max_rows <= 0:
            return self.render()
        with self._lock:
            parts: list[str] = []
            logical_lines = 0
            visible_chars = 0
            target_chars = max_rows * max(int(width or 1), 1)
            for segment in reversed(self._segments):
                text = _segment_text(segment)
                parts.append(text)
                logical_lines += text.count("\n")
                visible_chars += len(_ANSI_ESCAPE.sub("", text))
                if logical_lines >= max_rows + 2 or visible_chars >= target_chars * 2:
                    break
        rendered = "".join(reversed(parts))
        return _fit_visible_tail(rendered, max_rows, int(width or 0))


def _segment_text(segment: str | _MutableRegion) -> str:
    return segment.render() if isinstance(segment, _MutableRegion) else segment


def _fit_visible_tail(text: str, max_rows: int, width: int) -> str:
    lines = text.split("\n")
    if width <= 0:
        return "\n".join(lines[-max_rows:])
    remaining = max_rows
    selected: list[str] = []
    for line in reversed(lines):
        rows = max(1, (_display_width(line) + width - 1) // width)
        if rows <= remaining:
            selected.append(line)
            remaining -= rows
        elif remaining > 0:
            selected.append(_plain_display_tail(line, remaining * width))
            remaining = 0
        if remaining <= 0:
            break
    return "\n".join(reversed(selected))


def _display_width(text: str) -> int:
    from prompt_toolkit.utils import get_cwidth

    return sum(max(0, get_cwidth(char)) for char in _ANSI_ESCAPE.sub("", text))


def _visual_cursor_positions(text: str, width: int) -> list[tuple[int, int]]:
    """Map every buffer cursor offset to its soft-wrapped screen row/column."""
    from prompt_toolkit.utils import get_cwidth

    width = max(1, int(width))
    row = 0
    column = 0
    positions = [(row, column)]
    for index, char in enumerate(text):
        if char == "\n":
            row += 1
            column = 0
            positions.append((row, column))
            continue
        char_width = 4 - (column % 4) if char == "\t" else max(0, get_cwidth(char))
        if char_width and column and column + char_width > width:
            row += 1
            column = 0
            positions[index] = (row, column)
        column += char_width
        positions.append((row, min(column, width)))
    return positions


def _visual_cursor_target(
    text: str,
    cursor_position: int,
    width: int,
    row_delta: int,
    preferred_column: int | None = None,
) -> tuple[int, int]:
    positions = _visual_cursor_positions(text, width)
    cursor_position = max(0, min(int(cursor_position), len(text)))
    current_row, current_column = positions[cursor_position]
    preferred = current_column if preferred_column is None else preferred_column
    last_row = max(row for row, _column in positions)
    target_row = max(0, min(last_row, current_row + row_delta))
    if target_row == current_row:
        return cursor_position, preferred
    candidates = [
        (index, column)
        for index, (row, column) in enumerate(positions)
        if row == target_row
    ]
    target, _column = min(
        candidates,
        key=lambda item: (abs(item[1] - preferred), abs(item[0] - cursor_position)),
    )
    return target, preferred


def _plain_display_tail(text: str, max_width: int) -> str:
    from prompt_toolkit.utils import get_cwidth

    plain = _ANSI_ESCAPE.sub("", text)
    width = 0
    selected: list[str] = []
    for char in reversed(plain):
        char_width = max(0, get_cwidth(char))
        if width + char_width > max_width:
            break
        selected.append(char)
        width += char_width
    return "".join(reversed(selected))


def _plain_display_head(text: str, max_width: int) -> str:
    from prompt_toolkit.utils import get_cwidth

    plain = _ANSI_ESCAPE.sub("", text)
    width = 0
    selected: list[str] = []
    for char in plain:
        char_width = max(0, get_cwidth(char))
        if width + char_width > max_width:
            break
        selected.append(char)
        width += char_width
    if len(selected) < len(plain) and max_width >= 3:
        while selected and width + 3 > max_width:
            removed = selected.pop()
            width -= max(0, get_cwidth(removed))
        selected.extend("...")
    return "".join(selected)


def _ansi_visual_rows(text: str, width: int) -> list[list[tuple[str, str]]]:
    """Turn ANSI text into terminal-width rows while preserving styles."""
    rows: list[list[tuple[str, str]]] = [[]]
    _append_ansi_visual_rows(rows, text, width)
    return rows


def _append_ansi_visual_rows(
    rows: list[list[tuple[str, str]]],
    text: str,
    width: int,
) -> None:
    from prompt_toolkit.formatted_text import ANSI, to_formatted_text
    from prompt_toolkit.utils import get_cwidth

    width = max(1, width)
    if not rows:
        rows.append([])
    column = sum(max(0, get_cwidth(char)) for _style, value in rows[-1] for char in value)

    def append(style: str, value: str) -> None:
        if not value:
            return
        row = rows[-1]
        if row and row[-1][0] == style:
            previous_style, previous_text = row[-1]
            row[-1] = (previous_style, previous_text + value)
        else:
            row.append((style, value))

    for fragment in to_formatted_text(ANSI(text or "")):
        style, value = fragment[0], fragment[1]
        for char in value:
            if char == "\r":
                continue
            if char == "\n":
                rows.append([])
                column = 0
                continue
            if char == "\t":
                spaces = 4 - (column % 4)
                for _ in range(spaces):
                    if column >= width:
                        rows.append([])
                        column = 0
                    append(style, " ")
                    column += 1
                continue
            char_width = max(0, get_cwidth(char))
            if char_width and column and column + char_width > width:
                rows.append([])
                column = 0
            append(style, char)
            column += char_width


def _join_visual_rows(rows: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        fragments.extend(row)
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


class TuiStream:
    """Drop-in for ``ResponseStream`` that appends tokens into ChatBuffer.

    Mirrors the package's ``> `` green marker + streaming-text behaviour but
    writes into the buffer instead of console.print, so the chat region shows
    live token output.
    """

    def __init__(self, buffer: ChatBuffer, on_write: Callable[[], None] | None = None, on_finish: Callable[[], None] | None = None) -> None:
        self.buffer = buffer
        self.started = False
        self._on_write = on_write
        self._on_finish = on_finish

    def write(self, token: str) -> None:
        if not token:
            return
        if not self.started:
            self.buffer.begin_assistant()
            self.started = True
        self.buffer.append(token)
        if self._on_write is not None:
            self._on_write()

    def finish(self) -> None:
        if self.started:
            self.buffer.append("\n")
        self.started = False
        if self._on_finish is not None:
            self._on_finish()


def _styled(text: str, style: str | None) -> str:
    ansi = {
        "dim": DIM,
        "thinking": GRAY,
        "bright_black": GRAY,
        "green": GREEN,
        "blue": BLUE,
        "yellow": YELLOW,
        "red": RED,
    }.get(style or "")
    return f"{ansi}{text}{RESET}" if ansi else text


class TuiResponseStream:
    """Stream plain tokens immediately, then replace response with rendered Markdown."""

    def __init__(
        self,
        buffer: ChatBuffer,
        invalidate: Callable[[], None],
        phase_callback: Callable[[str], None] | None = None,
    ) -> None:
        from openvino_chat.ui import ResponseStream

        self.buffer = buffer
        self.invalidate = invalidate
        self.fragments: list[tuple[str, str | None]] = []
        self.region: int | None = None
        self.inner = ResponseStream(writer=self._write, phase_callback=phase_callback)

    def write(self, token: str) -> None:
        self.inner.write(token)

    def finish(self) -> None:
        self.inner.finish()
        if self.region is not None:
            self.buffer.update_region(self.region, _render_response_fragments(self.fragments, final=True))
            self.invalidate()
        self.fragments.clear()
        self.region = None

    def _write(self, text: str, style: str | None, end: str) -> None:
        if self.region is None:
            self.region = self.buffer.begin_region()
        value = text + end
        self.fragments.append((value, style))
        self.buffer.append_region(self.region, _styled(value, style))
        self.invalidate()


def response_stream(
    buffer: ChatBuffer,
    invalidate: Callable[[], None],
    phase_callback: Callable[[str], None] | None = None,
):
    return TuiResponseStream(buffer, invalidate, phase_callback=phase_callback)


def _render_response_fragments(
    fragments: list[tuple[str, str | None]],
    final: bool,
) -> str:
    rendered: list[str] = []
    index = 0
    while index < len(fragments):
        style = fragments[index][1]
        parts = []
        while index < len(fragments) and fragments[index][1] == style:
            parts.append(fragments[index][0])
            index += 1
        text = "".join(parts)
        if final and style is None and _has_terminal_markup(text):
            rendered.append(_render_terminal_markup(text))
        else:
            rendered.append(_styled(text, style))
    result = "".join(rendered)
    if final:
        from openvino_chat.ui import sanitize_tool_artifacts

        result = sanitize_tool_artifacts(result)
    return result


def _has_terminal_markup(text: str) -> bool:
    markers = ("```", "**", "__", "`", "# ", "## ", "### ", "- ", "* ", "1. ")
    if any(marker in text for marker in markers):
        return True
    lines = text.splitlines()
    has_add = any(line.lstrip().startswith("+") and not line.lstrip().startswith("+++") for line in lines)
    has_remove = any(line.lstrip().startswith("-") and not line.lstrip().startswith("---") for line in lines)
    if has_add and has_remove:
        return True
    from openvino_chat.ui import _needs_code_coloring

    return _needs_code_coloring([(text, None)])


def _render_terminal_markup(text: str) -> str:
    import io

    from rich.console import Console
    from rich.markdown import Markdown
    from openvino_chat.ui import _needs_code_coloring, format_code_colored_text

    width = max(40, min(100, shutil.get_terminal_size((100, 30)).columns - 4))
    sink = io.StringIO()
    console = Console(
        file=sink,
        record=True,
        force_terminal=True,
        color_system="truecolor",
        width=width,
    )
    if "```" not in text and _needs_code_coloring([(text, None)]):
        console.print(format_code_colored_text(text.rstrip()), end="")
    else:
        console.print(Markdown(text.rstrip(), code_theme="monokai"), end="")
    rendered = console.export_text(styles=True)
    return rendered + ("\n" if text.endswith("\n") and not rendered.endswith("\n") else "")


class TuiStatusMonitor:
    """Status/stream facade that never leaves prompt_toolkit's screen."""

    def __init__(self, buffer: ChatBuffer, mediator: "_TuiInputMediator") -> None:
        self.buffer = buffer
        self.mediator = mediator
        self.active = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False
        self.mediator.clear_operation()

    def set(self, label: str) -> None:
        self.mediator.set_operation(label)

    def update(self, label: str) -> None:
        self.mediator.update_operation(label)

    def clear(self, refresh: bool = True) -> None:
        self.mediator.clear_operation(refresh=refresh)

    def refresh(self) -> None:
        self.mediator.invalidate()

    def response_stream(self):
        return response_stream(
            self.buffer,
            self.mediator.invalidate,
            phase_callback=self.set,
        )

    def write_response(self, text: str, style: str | None = None, end: str = "") -> None:
        value = text + end
        if style is None and _has_terminal_markup(value):
            self.buffer.append(_render_terminal_markup(value))
        else:
            self.buffer.append_styled(text, style, end)
        self.mediator.invalidate()


class _TuiInputMediator:
    """Bridges the worker-driven REPL loop and the persistent Application.

    - ``request_prompt()`` is called by the worker thread (the existing
      ``_input_with_status`` path, redirected here in TUI mode). It blocks
      until the TUI's accept handler delivers a prompt, then returns it.
    - ``run_until_exit()`` is called on the main thread; it owns
      ``app.run()`` for the session lifetime and returns the exit code.
    - The accept handler also surfaces ctrl-c / ctrl-d as ``KeyboardInterrupt``
      / an exit prompt respectively.
    """

    def __init__(
        self,
        status_text: Callable[[], str],
        tasks_text: Callable[[], str],
        chat_buffer: ChatBuffer,
        completer: Any = None,
        refresh_interval: float = 0.15,
    ) -> None:
        self.status_text = status_text
        self.tasks_text = tasks_text
        self.chat_buffer = chat_buffer
        self.completer = completer
        self.refresh_interval = refresh_interval

        self._exit_code: int | None = None
        self._prompt_event = threading.Event()  # set when a prompt is ready
        self._prompt_value: str = ""
        self._request_event = threading.Event()  # set when worker wants input
        self._busy = threading.Event()
        self._busy.set()  # start not-busy so the first prompt is accepted
        self._interrupted = threading.Event()
        self._input_area: Any = None
        self._app: Any = None
        self._prompt_text = "> "
        self._status_lock = threading.Lock()
        self._status_value = "status: updating"
        self._status_stop = threading.Event()
        self._status_thread: threading.Thread | None = None
        self._operation_label: str | None = None
        self._operation_started = 0.0
        self._model_menu_active = False
        self._model_menu_items: list[dict[str, Any]] = []
        self._model_menu_index = 0
        self._model_menu_loaded = False
        self._model_menu_result: tuple[str, str | None] = ("cancel", None)
        self._model_menu_event = threading.Event()
        self._session_menu_active = False
        self._session_menu_items: list[dict[str, Any]] = []
        self._session_menu_index = 0
        self._session_menu_result: tuple[str, str | None] = ("cancel", None)
        self._session_menu_event = threading.Event()
        self._kv_menu_active = False
        self._kv_menu_values = ["auto", "u4", "u8", "f16"]
        self._kv_menu_current = "auto"
        self._kv_menu_index = 0
        self._kv_menu_result: str | None = None
        self._kv_menu_event = threading.Event()
        self._thinking_menu_active = False
        self._thinking_menu_values = ["on", "off"]
        self._thinking_menu_current = "on"
        self._thinking_menu_index = 0
        self._thinking_menu_result: str | None = None
        self._thinking_menu_event = threading.Event()
        self._thinking_menu_kind = "thinking"
        self._permission_menu_active = False
        self._permission_menu_values = ["ask", "allow"]
        self._permission_menu_current = "ask"
        self._permission_menu_index = 0
        self._permission_menu_result: str | None = None
        self._permission_menu_event = threading.Event()
        self._approval_menu_active = False
        self._approval_request_name = ""
        self._approval_request_args: dict[str, Any] = {}
        self._approval_result = False
        self._approval_event = threading.Event()
        self._notice_text_value = ""
        self._notice_until = 0.0
        self._notice_lock = threading.Lock()
        self._slash_index = 0
        self._slash_navigation = False
        self._slash_query = ""
        self._input_preferred_column: int | None = None
        self._moving_input_cursor = False
        self._chat_view_height = 0
        self._chat_view_width = 0
        self._chat_scroll_lines = 0
        self._chat_render_snapshot = ""
        self._chat_rows_text = ""
        self._chat_rows_width = 0
        self._chat_rows: list[list[tuple[str, str]]] = [[]]
        self._mouse_scroll_enabled = False
        self._queued_input_prefill: str | None = None
        self._prefill_lock = threading.Lock()

    # -- worker side -------------------------------------------------------

    def request_prompt(self, prompt_text: str) -> str:
        # Mark generation complete so the input bar accepts the next prompt.
        self._busy.set()
        self._interrupted.clear()
        self._prompt_text = prompt_text
        self._request_event.set()
        self._prompt_event.clear()
        # Wake the app so it can re-render the (now-cleared) input bar.
        self.invalidate()
        self._schedule_queued_input_prefill()
        self._prompt_event.wait()
        self._request_event.clear()
        if self._interrupted.is_set():
            raise KeyboardInterrupt
        return self._prompt_value

    def queue_input_prefill(self, text: str) -> None:
        """Queue editable input without mutating prompt_toolkit from worker thread."""
        with self._prefill_lock:
            self._queued_input_prefill = str(text)
        self.invalidate()

    def _apply_queued_input_prefill(self) -> bool:
        if self._input_area is None:
            return False
        with self._prefill_lock:
            value = self._queued_input_prefill
            self._queued_input_prefill = None
        if value is None:
            return False
        self._input_area.text = value
        self._input_area.buffer.cursor_position = len(value)
        self._input_preferred_column = None
        self._slash_query = value
        self._slash_index = 0
        self._slash_navigation = False
        try:
            if self._app is not None:
                self._app.layout.focus(self._input_area)
        except (AttributeError, ValueError):
            pass
        self.invalidate()
        return True

    def _schedule_queued_input_prefill(self) -> None:
        with self._prefill_lock:
            pending = self._queued_input_prefill is not None
        if not pending or self._app is None:
            return
        loop = getattr(self._app, "loop", None)
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._apply_queued_input_prefill)
        except RuntimeError:
            pass

    def notify_busy(self) -> None:
        """Called by the worker right before running a turn's dispatch."""
        self._busy.clear()
        self.invalidate()

    def should_stop(self) -> bool:
        return self._interrupted.is_set()

    def set_operation(self, label: str) -> None:
        self._operation_label = label
        self._operation_started = time.monotonic()
        self.invalidate()

    def update_operation(self, label: str) -> None:
        if self._operation_label is None:
            self.set_operation(label)
            return
        self._operation_label = label
        self.invalidate()

    def clear_operation(self, refresh: bool = True) -> None:
        self._operation_label = None
        self._operation_started = 0.0
        if refresh:
            self.invalidate()

    def show_notice(self, text: str, seconds: float = 3.0) -> None:
        with self._notice_lock:
            self._notice_text_value = text.strip()
            self._notice_until = time.monotonic() + max(0.1, seconds)
        self.invalidate()

    def _notice_text(self) -> str:
        with self._notice_lock:
            if time.monotonic() >= self._notice_until:
                self._notice_text_value = ""
            return self._notice_text_value

    def request_exit(self, code: int = 0) -> None:
        self._exit_code = code

    def request_model_picker(
        self,
        items: list[dict[str, Any]],
        loaded: bool,
    ) -> tuple[str, str | None]:
        self._model_menu_items = list(items)
        self._model_menu_loaded = loaded
        self._model_menu_index = next(
            (index for index, item in enumerate(items) if item.get("active")),
            0,
        )
        self._model_menu_result = ("cancel", None)
        self._model_menu_event.clear()
        self._model_menu_active = True
        self._busy.set()
        self.invalidate()
        self._model_menu_event.wait()
        return self._model_menu_result

    def _move_model_selection(self, amount: int) -> None:
        if not self._model_menu_items:
            return
        self._model_menu_index = max(
            0,
            min(len(self._model_menu_items) - 1, self._model_menu_index + amount),
        )
        self.invalidate()

    def _finish_model_picker(self, action: str) -> None:
        value = None
        if action not in {"cancel", "unload"} and self._model_menu_items:
            value = str(self._model_menu_items[self._model_menu_index]["name"])
        self._model_menu_result = (action, value)
        self._model_menu_active = False
        self._busy.clear()
        self._model_menu_event.set()
        self.invalidate()

    def _model_menu_text(self) -> str:
        count = len(self._model_menu_items)
        position = f"  {self._model_menu_index + 1}/{count}" if count else ""
        lines = [
            _menu_header(
                f"Models{position}",
                "Enter load  i install  d delete  u unload  Esc close",
            ),
            "",
        ]
        if not self._model_menu_items:
            return "\n".join(lines + ["  no configured models"])
        visible = max(1, self._model_menu_height() - 7)
        start, end = _picker_bounds(count, self._model_menu_index, visible)
        _rows, columns = self._output_dimensions()
        name_width = max(8, min(30, columns - 33))
        for index in range(start, end):
            item = self._model_menu_items[index]
            marker = ">" if index == self._model_menu_index else " "
            active = " active" if item.get("active") else ""
            loaded = " loaded" if item.get("active") and self._model_menu_loaded else ""
            name = _plain_display_head(str(item["name"]), name_width)
            row = (
                f"{marker} {name:<{name_width}} {str(item['state']):<9} "
                f"{str(item['size']):>9}{active}{loaded}"
            )
            lines.append(_selected_row(row, index == self._model_menu_index))
        selected = self._model_menu_items[self._model_menu_index]
        detail_width = max(8, columns - 9)
        lines.extend(
            [
                "",
                f"{GRAY}repo:{RESET} {_plain_display_head(str(selected.get('repo', '-')), detail_width)}",
                f"{GRAY}effort:{RESET} {selected.get('effort', 'on, off')}",
                f"{GRAY}thinking:{RESET} {selected.get('thinking', 'on, off')}",
                f"{GRAY}path:{RESET} {_plain_display_head(str(selected.get('path', '-')), detail_width)}",
            ]
        )
        return "\n".join(lines)

    def _model_menu_height(self) -> int:
        if not self._model_menu_items:
            return self._popup_height(3)
        return self._popup_height(min(15, len(self._model_menu_items) + 7), minimum=8)

    def request_session_picker(
        self,
        items: list[dict[str, Any]],
    ) -> tuple[str, str | None]:
        self._session_menu_items = list(items)
        self._session_menu_index = next(
            (index for index, item in enumerate(items) if item.get("active")),
            0,
        )
        self._session_menu_result = ("cancel", None)
        self._session_menu_event.clear()
        self._session_menu_active = True
        self._busy.set()
        self.invalidate()
        self._session_menu_event.wait()
        return self._session_menu_result

    def _move_session_selection(self, amount: int) -> None:
        if not self._session_menu_items:
            return
        self._session_menu_index = max(
            0,
            min(len(self._session_menu_items) - 1, self._session_menu_index + amount),
        )
        self.invalidate()

    def _finish_session_picker(self, action: str) -> None:
        value = None
        if action not in {"cancel", "new", "save"} and self._session_menu_items:
            value = str(self._session_menu_items[self._session_menu_index]["name"])
        self._session_menu_result = (action, value)
        self._session_menu_active = False
        self._busy.clear()
        self._session_menu_event.set()
        self.invalidate()

    def _session_menu_text(self) -> str:
        count = len(self._session_menu_items)
        position = f"  {self._session_menu_index + 1}/{count}" if count else ""
        lines = [
            _menu_header(
                f"Sessions{position}",
                "Enter resume  d delete  n new  s save  Esc close",
            ),
            "",
        ]
        if not self._session_menu_items:
            return "\n".join(lines + ["  no saved sessions", "", "Press n to start new session"])

        preview_rows = 2 if self._session_menu_height() >= 10 else 1
        visible = max(1, self._session_menu_height() - 4 - preview_rows)
        start, end = _picker_bounds(count, self._session_menu_index, visible)
        for index in range(start, end):
            item = self._session_menu_items[index]
            marker = ">" if index == self._session_menu_index else " "
            active = " active" if item.get("active") else ""
            row = f"{marker} {item['name']}{active}"
            lines.append(_selected_row(row, index == self._session_menu_index))

        selected = self._session_menu_items[self._session_menu_index]
        preview = str(selected.get("preview") or "(empty)")
        preview_lines = preview.splitlines() or ["(empty)"]
        lines.extend(["", f"{GRAY}Preview:{RESET} {preview_lines[0]}"])
        lines.extend(f"         {line}" for line in preview_lines[1:preview_rows])
        return "\n".join(lines)

    def _session_menu_height(self) -> int:
        if not self._session_menu_items:
            return self._popup_height(5, minimum=4)
        preview_rows = min(
            2,
            max(
                1,
                len(
                    str(
                        self._session_menu_items[self._session_menu_index].get("preview")
                        or "(empty)"
                    ).splitlines()
                ),
            ),
        )
        requested = 4 + min(8, len(self._session_menu_items)) + preview_rows
        return self._popup_height(requested, minimum=6)

    def request_kv_picker(self, current: str) -> str | None:
        self._kv_menu_current = current
        self._kv_menu_index = next(
            (index for index, value in enumerate(self._kv_menu_values) if value == current),
            0,
        )
        self._kv_menu_result = None
        self._kv_menu_event.clear()
        self._kv_menu_active = True
        self._busy.set()
        self.invalidate()
        self._kv_menu_event.wait()
        return self._kv_menu_result

    def _move_kv_selection(self, amount: int) -> None:
        self._kv_menu_index = max(
            0,
            min(len(self._kv_menu_values) - 1, self._kv_menu_index + amount),
        )
        self.invalidate()

    def _finish_kv_picker(self, accept: bool) -> None:
        self._kv_menu_result = self._kv_menu_values[self._kv_menu_index] if accept else None
        self._kv_menu_active = False
        self._busy.clear()
        self._kv_menu_event.set()
        self.invalidate()

    def _kv_menu_text(self) -> str:
        descriptions = {
            "auto": "OpenVINO default; safest compatibility",
            "u4": "smallest cache; largest context; may reduce accuracy",
            "u8": "balanced memory and accuracy",
            "f16": "largest cache; highest fidelity",
        }
        lines = [_menu_header("KV cache", "Enter apply  Esc close"), ""]
        for index, value in enumerate(self._kv_menu_values):
            marker = ">" if index == self._kv_menu_index else " "
            active = " current" if value == self._kv_menu_current else ""
            row = f"{marker} {value:<5} {descriptions[value]}{active}"
            lines.append(_selected_row(row, index == self._kv_menu_index))
        lines.extend(["", "Changing precision unloads current model. Next prompt reloads it."])
        return "\n".join(lines)

    def request_thinking_picker(
        self,
        current: str,
        values: tuple[str, ...] | None = None,
    ) -> str | None:
        self._thinking_menu_kind = "thinking"
        return self._request_thinking_menu(current, values)

    def request_effort_picker(
        self,
        current: str,
        values: tuple[str, ...] | None = None,
    ) -> str | None:
        self._thinking_menu_kind = "effort"
        return self._request_thinking_menu(current, values)

    def _request_thinking_menu(
        self,
        current: str,
        values: tuple[str, ...] | None,
    ) -> str | None:
        if values:
            self._thinking_menu_values = list(values)
        self._thinking_menu_current = current
        self._thinking_menu_index = next(
            (index for index, value in enumerate(self._thinking_menu_values) if value == current),
            0,
        )
        self._thinking_menu_result = None
        self._thinking_menu_event.clear()
        self._thinking_menu_active = True
        self._busy.set()
        self.invalidate()
        self._thinking_menu_event.wait()
        return self._thinking_menu_result

    def _move_thinking_selection(self, amount: int) -> None:
        self._thinking_menu_index = max(
            0,
            min(len(self._thinking_menu_values) - 1, self._thinking_menu_index + amount),
        )
        self.invalidate()

    def _finish_thinking_picker(self, accept: bool) -> None:
        self._thinking_menu_result = (
            self._thinking_menu_values[self._thinking_menu_index] if accept else None
        )
        self._thinking_menu_active = False
        self._busy.clear()
        self._thinking_menu_event.set()
        self.invalidate()

    def _thinking_menu_text(self) -> str:
        if self._thinking_menu_kind == "effort":
            descriptions = {
                "low": "Precise model-card preset; lower randomness",
                "medium": "Choose model-card preset from task type",
                "high": "General reasoning preset; broader sampling",
            }
            title = "Generation effort"
            detail = "Changes sampling. /thinking controls model-native reasoning."
        else:
            descriptions = {
                "on": "Use model-native reasoning output",
                "off": "Disable reasoning through model chat template",
                "low": "Brief focused native reasoning",
                "medium": "Balanced native reasoning depth",
                "xhigh": "Maximum native reasoning depth",
            }
            title = "Thinking mode"
            detail = (
                "Graded thinking comes from this model chat template."
                if "xhigh" in self._thinking_menu_values
                else "This model chat template supports only native on/off control."
            )
        lines = [_menu_header(title, "Enter apply  Esc close"), ""]
        for index, value in enumerate(self._thinking_menu_values):
            marker = ">" if index == self._thinking_menu_index else " "
            active = " current" if value == self._thinking_menu_current else ""
            row = f"{marker} {value:<6} {descriptions.get(value, 'Model-native mode')}{active}"
            lines.append(_selected_row(row, index == self._thinking_menu_index))
        lines.extend(["", detail])
        return "\n".join(lines)

    def request_permission_picker(self, current: str) -> str | None:
        self._permission_menu_current = current
        self._permission_menu_index = next(
            (index for index, value in enumerate(self._permission_menu_values) if value == current),
            0,
        )
        self._permission_menu_result = None
        self._permission_menu_event.clear()
        self._permission_menu_active = True
        self._busy.set()
        self.invalidate()
        self._permission_menu_event.wait()
        return self._permission_menu_result

    def _move_permission_selection(self, amount: int) -> None:
        self._permission_menu_index = max(
            0,
            min(len(self._permission_menu_values) - 1, self._permission_menu_index + amount),
        )
        self.invalidate()

    def _finish_permission_picker(self, accept: bool) -> None:
        self._permission_menu_result = (
            self._permission_menu_values[self._permission_menu_index] if accept else None
        )
        self._permission_menu_active = False
        self._busy.clear()
        self._permission_menu_event.set()
        self.invalidate()

    def _permission_menu_text(self) -> str:
        descriptions = {
            "ask": "Confirm write, shell, and risky tool actions",
            "allow": "Run tool actions without confirmation",
        }
        lines = [_menu_header("Permissions", "Enter apply  Esc close"), ""]
        for index, value in enumerate(self._permission_menu_values):
            marker = ">" if index == self._permission_menu_index else " "
            active = " current" if value == self._permission_menu_current else ""
            row = f"{marker} {value:<5} {descriptions[value]}{active}"
            lines.append(_selected_row(row, index == self._permission_menu_index))
        return "\n".join(lines)

    def request_tool_approval(self, name: str, args: dict[str, Any]) -> bool:
        self._approval_request_name = str(name)
        self._approval_request_args = dict(args)
        self._approval_result = False
        self._approval_event.clear()
        self._approval_menu_active = True
        self._busy.set()
        self.invalidate()
        self._approval_event.wait()
        return self._approval_result

    def _finish_tool_approval(self, approved: bool) -> None:
        self._approval_result = approved
        self._approval_menu_active = False
        self._set_input_prompt("")
        if self._input_area is not None:
            self._input_area.text = ""
        self._busy.clear()
        self._approval_event.set()
        self.invalidate()

    def _tool_approval_menu_text(self) -> str:
        try:
            import json

            args = json.dumps(self._approval_request_args, ensure_ascii=False)
        except Exception:
            args = repr(self._approval_request_args)
        if len(args) > 180:
            args = args[:177] + "..."
        return "\n".join(
            [
                _menu_header("Permission Required", "Enter/y allow  Esc/n deny"),
                "",
                f"{YELLOW}[tool]{RESET} {BOLD}{self._approval_request_name}{RESET}",
                f"{GRAY}{args}{RESET}",
                "",
                "This action can change files or run a command.",
            ]
        )

    # -- main thread side --------------------------------------------------

    def _output_dimensions(self) -> tuple[int, int]:
        """Return live application rows/columns, including resize changes."""
        try:
            output = getattr(self._app, "output", None)
            size = output.get_size() if output is not None else None
            rows = int(getattr(size, "rows", 0))
            columns = int(getattr(size, "columns", 0))
            if rows > 0 and columns > 0:
                return rows, columns
        except Exception:
            pass
        terminal = shutil.get_terminal_size((100, 30))
        return max(1, terminal.lines), max(20, terminal.columns)

    def _popup_height(self, desired: int, minimum: int = 3) -> int:
        rows, _columns = self._output_dimensions()
        available = max(minimum, rows - 4)
        return min(available, max(minimum, desired))

    def _slash_popup_limit(self) -> int:
        rows, _columns = self._output_dimensions()
        return max(3, min(15, rows - 4))

    def invalidate(self) -> None:
        if self._app is not None:
            try:
                self._app.invalidate()
            except Exception:
                pass

    def _render_chat_tail(self) -> str:
        """Return chat tail fitting last rendered window dimensions."""
        self._update_chat_dimensions()
        rows, columns = self._output_dimensions()
        max_rows = self._chat_view_height or max(1, rows - 6)
        width = self._chat_view_width or columns
        return self.chat_buffer.render_tail(max_rows, width)

    def _update_chat_dimensions(self) -> None:
        try:
            win = getattr(self, "_chat_window", None)
            info = getattr(win, "render_info", None) if win is not None else None
            rendered_h = getattr(info, "window_height", None) if info is not None else None
            rendered_w = getattr(info, "window_width", None) if info is not None else None
        except Exception:
            rendered_h = None
            rendered_w = None
        if rendered_h:
            self._chat_view_height = int(rendered_h)
        if rendered_w:
            self._chat_view_width = int(rendered_w)

    def _chat_dimensions(self) -> tuple[int, int]:
        self._update_chat_dimensions()
        rows, columns = self._output_dimensions()
        max_rows = self._chat_view_height or max(1, rows - 6)
        width = self._chat_view_width or columns
        return max_rows, width

    def _render_chat_view(self) -> list[tuple[str, str]]:
        max_rows, width = self._chat_dimensions()
        rows = self._chat_visual_rows(width)
        max_scroll = max(0, len(rows) - max_rows)
        self._chat_scroll_lines = min(self._chat_scroll_lines, max_scroll)
        end = max(0, len(rows) - self._chat_scroll_lines)
        start = max(0, end - max_rows)
        selected = rows[start:end]
        self._chat_render_snapshot = "\n".join(
            "".join(value for _style, value in row) for row in selected
        )
        return _join_visual_rows(selected)

    def _chat_visual_rows(self, width: int) -> list[list[tuple[str, str]]]:
        text = self.chat_buffer.render()
        if width != self._chat_rows_width:
            self._chat_rows = _ansi_visual_rows(text, width)
        elif text != self._chat_rows_text:
            if text.startswith(self._chat_rows_text):
                _append_ansi_visual_rows(
                    self._chat_rows,
                    text[len(self._chat_rows_text) :],
                    width,
                )
            else:
                self._chat_rows = _ansi_visual_rows(text, width)
        self._chat_rows_text = text
        self._chat_rows_width = width
        return self._chat_rows

    def _render_chat_source(self) -> str:
        return "\n".join(
            "".join(value for _style, value in row)
            for row in self._chat_visual_rows(self._chat_dimensions()[1])
        )

    def _move_chat_scroll(self, rows: int) -> None:
        max_rows, width = self._chat_dimensions()
        visual_rows = self._chat_visual_rows(width)
        max_scroll = max(0, len(visual_rows) - max_rows)
        self._chat_scroll_lines = max(
            0,
            min(max_scroll, self._chat_scroll_lines + rows),
        )
        self.invalidate()

    def _chat_page_size(self) -> int:
        return max(1, self._chat_dimensions()[0] - 1)

    def _set_input_prompt(self, prompt_text: str) -> None:
        self._prompt_text = prompt_text

    def _input_content_width(self) -> int:
        try:
            info = getattr(getattr(self._input_area, "window", None), "render_info", None)
            rendered = int(getattr(info, "window_width", 0)) if info is not None else 0
            if rendered > 0:
                return rendered
        except Exception:
            pass
        _rows, columns = self._output_dimensions()
        return max(1, columns - max(1, _display_width(self._prompt_text)))

    def _input_height(self) -> int:
        text = str(getattr(self._input_area, "text", "") or "")
        positions = _visual_cursor_positions(text, self._input_content_width())
        visual_rows = max(row for row, _column in positions) + 1
        terminal_rows, _columns = self._output_dimensions()
        maximum = max(1, min(8, terminal_rows // 3))
        return max(1, min(visual_rows, maximum))

    def _move_input_visual_row(self, amount: int) -> None:
        if self._input_area is None:
            return
        buffer = self._input_area.buffer
        target, preferred = _visual_cursor_target(
            self._input_area.text,
            buffer.cursor_position,
            self._input_content_width(),
            amount,
            self._input_preferred_column,
        )
        self._input_preferred_column = preferred
        if target == buffer.cursor_position:
            return
        self._moving_input_cursor = True
        try:
            buffer.cursor_position = target
        finally:
            self._moving_input_cursor = False
        self.invalidate()

    def _status_items(self) -> list[tuple[str, str | None]]:
        with self._status_lock:
            text = self._status_value
        items: list[tuple[str, str | None]] = []
        for index, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            if ": " in line:
                label, value = line.split(": ", 1)
            elif "=" in line:
                label, value = line.split("=", 1)
            else:
                label, value = line.replace("_", " "), None
            items.append((label.replace("_", " "), value))
        if self._operation_label:
            elapsed = max(0, int(time.monotonic() - self._operation_started))
            operation = f"{self._operation_label} {elapsed}s"
            for index, (label, _value) in enumerate(items):
                if label.lower().strip() == "state":
                    items[index] = (label, operation)
                    break
            else:
                insert_at = 1 if items and items[0][0].lower().strip() == "model" else 0
                items.insert(insert_at, ("state", operation))
        return items

    def _status_fragments(self) -> list[tuple[str, str]]:
        """Single-row status used by legacy prompt and focused tests."""
        frags = self._format_status_row(self._status_items(), title=True, compact=False)
        self._append_activity(frags, compact=False)
        return frags

    def _status_primary_fragments(self) -> list[tuple[str, str]]:
        items = self._status_items()
        primary_names = self._status_primary_names()
        primary = [item for item in items if item[0].lower() in primary_names]
        if not primary and len(items) > 1:
            primary = items[:1]
        _rows, columns = self._output_dimensions()
        return self._format_status_row(primary, title=True, compact=columns < 110)

    def _status_secondary_fragments(self) -> list[tuple[str, str]]:
        items = self._status_items()
        primary_names = self._status_primary_names()
        secondary = [item for item in items if item[0].lower() not in primary_names]
        _rows, columns = self._output_dimensions()
        compact = columns < 110
        frags = self._format_status_row(secondary, title=False, compact=compact)
        self._append_activity(frags, compact=compact)
        if not frags:
            return [("class:toolbar.value", " metrics updating")]
        return frags

    def _status_primary_names(self) -> set[str]:
        _rows, columns = self._output_dimensions()
        names = {"model", "state", "device", "ctx", "kv", "think"}
        if columns < 68:
            names.remove("think")
        return names

    def _format_status_row(
        self,
        items: list[tuple[str, str | None]],
        *,
        title: bool,
        compact: bool,
    ) -> list[tuple[str, str]]:
        frags: list[tuple[str, str]] = []
        if title:
            frags.extend([("class:toolbar.title", " openvino "), ("", " ")])
        _rows, columns = self._output_dimensions()
        very_compact = columns < 68
        for label, value in items:
            if frags and not (title and len(frags) == 2):
                frags.append(("class:toolbar.sep", " | "))
            normalized = label.lower().strip()
            shown_label = _compact_status_label(normalized) if compact else label
            if compact and normalized in {"model", "state", "device"} and value is not None:
                style = {
                    "model": "class:toolbar.model",
                    "state": (
                        self._operation_style(self._operation_label)
                        if self._operation_label
                        else "class:toolbar.state"
                    ),
                    "device": "class:toolbar.value",
                }[normalized]
                frags.append((style, value))
                continue
            frags.append(("class:toolbar.label", shown_label))
            if value is not None:
                frags.append(("class:toolbar.sep", ": "))
                shown_value = (
                    _compact_status_value(normalized, value, very_compact)
                    if compact
                    else value
                )
                value_style = (
                    self._operation_style(self._operation_label)
                    if normalized == "state" and self._operation_label
                    else "class:toolbar.value"
                )
                frags.append((value_style, shown_value))
        return frags

    def _append_activity(self, frags: list[tuple[str, str]], *, compact: bool) -> None:
        if not self._operation_label and not self._busy.is_set():
            if frags:
                frags.append(("class:toolbar.sep", " | "))
            frags.append(("class:toolbar.value", "working..."))
        if self._chat_scroll_lines:
            if frags:
                frags.append(("class:toolbar.sep", " | "))
            frags.append(("class:toolbar.label", "history"))
            frags.append(("class:toolbar.sep", " "))
            history = f"{self._chat_scroll_lines} up" if compact else f"{self._chat_scroll_lines} rows up"
            frags.append(("class:toolbar.value", history))

    def _task_lines(self) -> list[str]:
        try:
            text = _strip(self.tasks_text()).strip()
        except Exception:
            return []
        if not has_visible_tasks(text):
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _task_progress(self) -> tuple[int, int, str]:
        lines = self._task_lines()
        done = sum("[x]" in line.lower() for line in lines)
        next_task = next((line for line in lines if "[x]" not in line.lower()), lines[-1] if lines else "")
        next_task = re.sub(r"^\d+\.\s*\[[ xX]\]\s*", "", next_task).strip()
        return done, len(lines), next_task

    def _show_task_side(self) -> bool:
        _rows, columns = self._output_dimensions()
        return bool(self._task_lines()) and columns >= 96

    def _show_task_strip(self) -> bool:
        _rows, columns = self._output_dimensions()
        return bool(self._task_lines()) and columns < 96

    def _task_panel_text(self) -> str:
        lines = self._task_lines()
        done, total, _next_task = self._task_progress()
        rendered = [f"{CYAN}{BOLD} Tasks{RESET}  {GRAY}{done}/{total} done{RESET}", ""]
        pending_highlighted = False
        for line in lines:
            if "[x]" in line.lower():
                rendered.append(f"{GRAY}{line}{RESET}")
            elif not pending_highlighted:
                rendered.append(f"{BOLD}{line}{RESET}")
                pending_highlighted = True
            else:
                rendered.append(line)
        return "\n".join(rendered)

    def _task_strip_fragments(self) -> list[tuple[str, str]]:
        done, total, next_task = self._task_progress()
        _rows, columns = self._output_dimensions()
        available = max(8, columns - 24)
        next_task = _plain_display_head(next_task, available)
        return [
            ("class:task.title", " tasks "),
            ("class:task.value", f" {done}/{total}"),
            ("class:toolbar.sep", " | "),
            ("class:task.label", "next "),
            ("class:task.value", next_task),
        ]

    @staticmethod
    def _operation_style(label: str) -> str:
        if label == "thinking":
            return "class:operation.thinking"
        if label == "generating":
            return "class:operation.generating"
        if label.startswith(("loading model", "downloading model", "compacting")):
            return "class:operation.loading"
        if label in {"running command", "running tool", "searching web"}:
            return "class:operation.tool"
        return "class:operation.default"

    def _start_status_updates(self) -> None:
        if self._status_thread is not None:
            return
        self._status_stop.clear()
        self._status_thread = threading.Thread(target=self._status_loop, name="openvino-status", daemon=True)
        self._status_thread.start()

    def _stop_status_updates(self) -> None:
        self._status_stop.set()
        if self._status_thread is not None:
            self._status_thread.join(timeout=1)
            self._status_thread = None

    def _status_loop(self) -> None:
        while not self._status_stop.is_set():
            try:
                value = self.status_text()
            except Exception:
                value = "status: unavailable"
            with self._status_lock:
                self._status_value = value
            self.invalidate()
            if self._status_stop.wait(1.0):
                return

    def _slash_command_bar(self, text: str) -> str:
        from openvino_chat.cli import _slash_command_bar

        _rows, columns = self._output_dimensions()
        return _slash_command_bar(
            text,
            limit=self._slash_popup_limit(),
            selected_index=self._slash_index,
            show_groups=columns >= 90,
        )

    def _slash_command_bar_height(self, text: str) -> int:
        from openvino_chat.cli import _slash_command_bar_height

        return _slash_command_bar_height(text, limit=self._slash_popup_limit())

    def _slash_matches(self) -> list[Any]:
        if self._input_area is None:
            return []
        from openvino_chat.cli import _slash_command_matches

        return _slash_command_matches(self._input_area.text)

    def _slash_menu_active(self) -> bool:
        return (
            not self._any_menu_active()
            and bool(self._slash_matches())
        )

    def _any_menu_active(self) -> bool:
        return any(
            (
                self._model_menu_active,
                self._session_menu_active,
                self._kv_menu_active,
                self._thinking_menu_active,
                self._permission_menu_active,
                self._approval_menu_active,
            )
        )

    def _handle_chat_mouse(self, mouse_event: Any) -> Any:
        from prompt_toolkit.mouse_events import MouseEventType

        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._move_chat_scroll(3)
            return None
        if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._move_chat_scroll(-3)
            return None
        return NotImplemented

    def _toggle_mouse_scroll(self) -> None:
        self._mouse_scroll_enabled = not self._mouse_scroll_enabled
        if self._mouse_scroll_enabled:
            self.show_notice("Mouse wheel scroll enabled; hold Shift to select text")
        else:
            self.show_notice("Text selection enabled; use PageUp/PageDown for history")

    def _move_slash_selection(self, amount: int) -> None:
        matches = self._slash_matches()
        if not matches:
            return
        if not self._slash_navigation:
            self._slash_navigation = True
        self._slash_index = (self._slash_index + amount) % len(matches)
        self.invalidate()

    def _apply_slash_selection(self) -> bool:
        matches = self._slash_matches()
        if not matches:
            self._slash_navigation = False
            return False
        selected = matches[min(self._slash_index, len(matches) - 1)]
        from openvino_chat.cli import EXACT_USAGE_COMMANDS

        needs_argument = "<" in selected.usage or selected.command in EXACT_USAGE_COMMANDS
        value = selected.command + (" " if needs_argument else "")
        self._input_area.text = value
        self._input_area.buffer.cursor_position = len(value)
        self._slash_navigation = False
        self.invalidate()
        return needs_argument

    def build_app(self) -> Any:
        from prompt_toolkit.application import Application
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import (
            ConditionalContainer,
            Float,
            FloatContainer,
            HSplit,
            Layout,
            VSplit,
            Window,
        )
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.widgets import TextArea
        from openvino_chat.cli import _prompt_style

        self._input_area = TextArea(
            multiline=True,
            wrap_lines=True,
            height=self._input_height,
            style="class:input",
            completer=self.completer,
            complete_while_typing=True,
            read_only=Condition(lambda: not self._busy.is_set()),
        )

        def _input_changed(_buffer) -> None:
            query = self._input_area.text
            if query != self._slash_query:
                self._slash_query = query
                self._slash_index = 0
                self._slash_navigation = False
            self._input_preferred_column = None
            self.invalidate()

        self._input_area.buffer.on_text_changed += _input_changed

        def _cursor_changed(_buffer) -> None:
            if not self._moving_input_cursor:
                self._input_preferred_column = None

        self._input_area.buffer.on_cursor_position_changed += _cursor_changed

        def _chat_text() -> Any:
            return self._render_chat_view()

        def _chat_height_dim() -> Dimension:
            return Dimension(weight=1)

        chat_window = Window(
            FormattedTextControl(_chat_text),
            width=Dimension(weight=1),
            height=_chat_height_dim,
            wrap_lines=False,
            always_hide_cursor=True,
        )
        chat_window._mouse_handler = self._handle_chat_mouse
        self._chat_window = chat_window

        task_window = Window(
            FormattedTextControl(lambda: ANSI(self._task_panel_text())),
            wrap_lines=False,
            always_hide_cursor=True,
            width=Dimension(min=26, preferred=34, max=42),
            style="class:task",
        )

        vertical_separator = Window(width=1, char="|", style="class:separator", always_hide_cursor=True)
        def _bar_text() -> str:
            try:
                return _style_command_bar(self._slash_command_bar(self._input_area.text))
            except Exception:
                return ""

        command_bar = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(_bar_text())),
                height=lambda: self._slash_command_bar_height(self._input_area.text),
                style="class:command-bar",
                always_hide_cursor=True,
            ),
            filter=Condition(
                lambda: not self._any_menu_active()
                and bool(_bar_text())
            ),
        )

        model_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._model_menu_text())),
                height=self._model_menu_height,
                wrap_lines=False,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._model_menu_active),
        )

        session_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._session_menu_text())),
                height=self._session_menu_height,
                wrap_lines=False,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._session_menu_active),
        )

        kv_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._kv_menu_text())),
                height=lambda: self._popup_height(8, minimum=5),
                wrap_lines=False,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._kv_menu_active),
        )

        thinking_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._thinking_menu_text())),
                height=lambda: self._popup_height(
                    len(self._thinking_menu_values) + 4,
                    minimum=5,
                ),
                wrap_lines=False,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._thinking_menu_active),
        )

        permission_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._permission_menu_text())),
                height=lambda: self._popup_height(4, minimum=4),
                wrap_lines=False,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._permission_menu_active),
        )

        approval_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._tool_approval_menu_text())),
                height=lambda: self._popup_height(6, minimum=5),
                wrap_lines=False,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._approval_menu_active),
        )

        notice = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: [("class:notice", f" {self._notice_text()}")]),
                height=1,
                style="class:notice",
                always_hide_cursor=True,
            ),
            filter=Condition(lambda: bool(self._notice_text()) and not self._any_menu_active()),
        )

        primary_toolbar = Window(
            FormattedTextControl(self._status_primary_fragments),
            height=1,
            style="class:bottom-toolbar",
            always_hide_cursor=True,
        )
        secondary_toolbar = Window(
            FormattedTextControl(self._status_secondary_fragments),
            height=1,
            style="class:bottom-toolbar.secondary",
            always_hide_cursor=True,
        )

        task_side = ConditionalContainer(
            VSplit([vertical_separator, task_window]),
            filter=Condition(self._show_task_side),
        )
        task_strip = ConditionalContainer(
            Window(
                FormattedTextControl(self._task_strip_fragments),
                height=1,
                style="class:task.strip",
                always_hide_cursor=True,
            ),
            filter=Condition(self._show_task_strip),
        )
        content = VSplit([chat_window, task_side], height=Dimension(weight=1))

        prompt_window = Window(
            FormattedTextControl(lambda: [("class:input.prompt", self._prompt_text)]),
            width=lambda: Dimension.exact(max(1, _display_width(self._prompt_text))),
            height=self._input_height,
            style="class:input",
            always_hide_cursor=True,
        )
        input_container = ConditionalContainer(
            VSplit([prompt_window, self._input_area]),
            filter=Condition(lambda: not self._any_menu_active()),
        )
        body = HSplit(
            [
                content,
                task_strip,
                notice,
                command_bar,
                input_container,
                primary_toolbar,
                secondary_toolbar,
            ]
        )
        root = FloatContainer(
            content=body,
            floats=[
                Float(content=model_menu, bottom=2, left=1, right=1),
                Float(content=session_menu, bottom=2, left=1, right=1),
                Float(content=kv_menu, bottom=2, left=1, right=1),
                Float(content=thinking_menu, bottom=2, left=1, right=1),
                Float(content=permission_menu, bottom=2, left=1, right=1),
                Float(content=approval_menu, bottom=2, left=1, right=1),
            ],
        )

        keys = KeyBindings()
        model_menu_active = Condition(lambda: self._model_menu_active)
        session_menu_active = Condition(lambda: self._session_menu_active)
        kv_menu_active = Condition(lambda: self._kv_menu_active)
        thinking_menu_active = Condition(lambda: self._thinking_menu_active)
        permission_menu_active = Condition(lambda: self._permission_menu_active)
        approval_menu_active = Condition(lambda: self._approval_menu_active)
        menus_inactive = ~(
            model_menu_active
            | session_menu_active
            | kv_menu_active
            | thinking_menu_active
            | permission_menu_active
            | approval_menu_active
        )
        slash_menu_active = Condition(self._slash_menu_active)
        plain_input = menus_inactive & ~slash_menu_active

        @keys.add("enter", filter=menus_inactive)
        def _accept(_event) -> None:
            if not self._busy.is_set():
                # A turn is running; ignore further Enter presses.
                return
            if self._apply_slash_selection():
                return
            text = self._input_area.text
            self._input_area.text = ""
            self._chat_scroll_lines = 0
            self._prompt_value = text
            self.notify_busy()
            self._prompt_event.set()

        @keys.add("c-j", filter=menus_inactive)
        def _insert_newline(_event) -> None:
            if self._busy.is_set():
                self._input_area.buffer.insert_text("\n")

        @keys.add("up", filter=plain_input, eager=True)
        def _input_up(_event) -> None:
            self._move_input_visual_row(-1)

        @keys.add("down", filter=plain_input, eager=True)
        def _input_down(_event) -> None:
            self._move_input_visual_row(1)

        @keys.add("escape", filter=menus_inactive)
        def _stop_generation(_event) -> None:
            if self._busy.is_set() and self._slash_menu_active():
                self._input_area.text = ""
                self._slash_navigation = False
                self._slash_index = 0
                self.invalidate()
                return
            if not self._busy.is_set():
                self._interrupted.set()
                self.set_operation("stopping")

        @keys.add("c-c", filter=menus_inactive)
        def _interrupt(_event) -> None:
            self._interrupted.set()
            self._prompt_value = ""
            self._prompt_event.set()

        @keys.add("c-d", filter=menus_inactive)
        def _eof(_event) -> None:
            self._prompt_value = "/exit"
            self._prompt_event.set()

        @keys.add("pageup", filter=menus_inactive, eager=True)
        def _chat_page_up(_event) -> None:
            self._move_chat_scroll(self._chat_page_size())

        @keys.add("pagedown", filter=menus_inactive, eager=True)
        def _chat_page_down(_event) -> None:
            self._move_chat_scroll(-self._chat_page_size())

        @keys.add("c-up", filter=menus_inactive, eager=True)
        def _chat_line_up(_event) -> None:
            self._move_chat_scroll(3)

        @keys.add("c-down", filter=menus_inactive, eager=True)
        def _chat_line_down(_event) -> None:
            self._move_chat_scroll(-3)

        @keys.add("<scroll-up>", filter=menus_inactive)
        def _chat_wheel_up(_event) -> None:
            self._move_chat_scroll(3)

        @keys.add("<scroll-down>", filter=menus_inactive)
        def _chat_wheel_down(_event) -> None:
            self._move_chat_scroll(-3)

        @keys.add("c-home", filter=menus_inactive)
        def _chat_oldest(_event) -> None:
            self._move_chat_scroll(10**9)

        @keys.add("c-end", filter=menus_inactive)
        def _chat_latest(_event) -> None:
            self._chat_scroll_lines = 0
            self.invalidate()

        @keys.add("f6")
        def _toggle_mouse_mode(_event) -> None:
            self._toggle_mouse_scroll()

        @keys.add("down", filter=slash_menu_active)
        @keys.add("c-n", filter=slash_menu_active)
        def _slash_down(_event) -> None:
            self._move_slash_selection(1)

        @keys.add("up", filter=slash_menu_active)
        @keys.add("c-p", filter=slash_menu_active)
        def _slash_up(_event) -> None:
            self._move_slash_selection(-1)

        @keys.add("tab", filter=slash_menu_active)
        def _slash_complete(_event) -> None:
            self._apply_slash_selection()

        @keys.add("down", filter=model_menu_active)
        def _model_down(_event) -> None:
            self._move_model_selection(1)

        @keys.add("up", filter=model_menu_active)
        def _model_up(_event) -> None:
            self._move_model_selection(-1)

        @keys.add("home", filter=model_menu_active)
        def _model_home(_event) -> None:
            self._model_menu_index = 0
            self.invalidate()

        @keys.add("end", filter=model_menu_active)
        def _model_end(_event) -> None:
            self._model_menu_index = max(0, len(self._model_menu_items) - 1)
            self.invalidate()

        @keys.add("pageup", filter=model_menu_active)
        def _model_page_up(_event) -> None:
            self._move_model_selection(-max(1, self._model_menu_height() - 5))

        @keys.add("pagedown", filter=model_menu_active)
        def _model_page_down(_event) -> None:
            self._move_model_selection(max(1, self._model_menu_height() - 5))

        @keys.add("enter", filter=model_menu_active)
        def _model_load(_event) -> None:
            self._finish_model_picker("load")

        @keys.add("i", filter=model_menu_active)
        def _model_install(_event) -> None:
            self._finish_model_picker("download")

        @keys.add("d", filter=model_menu_active)
        def _model_delete(_event) -> None:
            self._finish_model_picker("delete")

        @keys.add("u", filter=model_menu_active)
        def _model_unload(_event) -> None:
            self._finish_model_picker("unload")

        @keys.add("escape", filter=model_menu_active)
        @keys.add("c-c", filter=model_menu_active)
        def _model_cancel(_event) -> None:
            self._finish_model_picker("cancel")

        @keys.add("down", filter=session_menu_active)
        def _session_down(_event) -> None:
            self._move_session_selection(1)

        @keys.add("up", filter=session_menu_active)
        def _session_up(_event) -> None:
            self._move_session_selection(-1)

        @keys.add("home", filter=session_menu_active)
        def _session_home(_event) -> None:
            self._session_menu_index = 0
            self.invalidate()

        @keys.add("end", filter=session_menu_active)
        def _session_end(_event) -> None:
            self._session_menu_index = max(0, len(self._session_menu_items) - 1)
            self.invalidate()

        @keys.add("pageup", filter=session_menu_active)
        def _session_page_up(_event) -> None:
            self._move_session_selection(-max(1, self._session_menu_height() - 5))

        @keys.add("pagedown", filter=session_menu_active)
        def _session_page_down(_event) -> None:
            self._move_session_selection(max(1, self._session_menu_height() - 5))

        @keys.add("enter", filter=session_menu_active)
        def _session_load(_event) -> None:
            self._finish_session_picker("load")

        @keys.add("d", filter=session_menu_active)
        def _session_delete(_event) -> None:
            self._finish_session_picker("delete")

        @keys.add("n", filter=session_menu_active)
        def _session_new(_event) -> None:
            self._finish_session_picker("new")

        @keys.add("s", filter=session_menu_active)
        def _session_save(_event) -> None:
            self._finish_session_picker("save")

        @keys.add("escape", filter=session_menu_active)
        @keys.add("c-c", filter=session_menu_active)
        def _session_cancel(_event) -> None:
            self._finish_session_picker("cancel")

        @keys.add("down", filter=kv_menu_active)
        def _kv_down(_event) -> None:
            self._move_kv_selection(1)

        @keys.add("up", filter=kv_menu_active)
        def _kv_up(_event) -> None:
            self._move_kv_selection(-1)

        @keys.add("enter", filter=kv_menu_active)
        def _kv_apply(_event) -> None:
            self._finish_kv_picker(True)

        @keys.add("escape", filter=kv_menu_active)
        @keys.add("c-c", filter=kv_menu_active)
        def _kv_cancel(_event) -> None:
            self._finish_kv_picker(False)

        @keys.add("down", filter=thinking_menu_active)
        def _thinking_down(_event) -> None:
            self._move_thinking_selection(1)

        @keys.add("up", filter=thinking_menu_active)
        def _thinking_up(_event) -> None:
            self._move_thinking_selection(-1)

        @keys.add("enter", filter=thinking_menu_active)
        def _thinking_apply(_event) -> None:
            self._finish_thinking_picker(True)

        @keys.add("escape", filter=thinking_menu_active)
        @keys.add("c-c", filter=thinking_menu_active)
        def _thinking_cancel(_event) -> None:
            self._finish_thinking_picker(False)

        @keys.add("down", filter=permission_menu_active)
        def _permission_down(_event) -> None:
            self._move_permission_selection(1)

        @keys.add("up", filter=permission_menu_active)
        def _permission_up(_event) -> None:
            self._move_permission_selection(-1)

        @keys.add("enter", filter=permission_menu_active)
        def _permission_apply(_event) -> None:
            self._finish_permission_picker(True)

        @keys.add("escape", filter=permission_menu_active)
        @keys.add("c-c", filter=permission_menu_active)
        def _permission_cancel(_event) -> None:
            self._finish_permission_picker(False)

        @keys.add("enter", filter=approval_menu_active)
        @keys.add("y", filter=approval_menu_active)
        def _approval_allow(_event) -> None:
            self._finish_tool_approval(True)

        @keys.add("escape", filter=approval_menu_active)
        @keys.add("c-c", filter=approval_menu_active)
        @keys.add("n", filter=approval_menu_active)
        def _approval_deny(_event) -> None:
            self._finish_tool_approval(False)

        app = Application(
            layout=Layout(root, focused_element=self._input_area),
            key_bindings=keys,
            full_screen=True,
            mouse_support=Condition(lambda: self._mouse_scroll_enabled),
            refresh_interval=self.refresh_interval,
            min_redraw_interval=0.03,
            max_render_postpone_time=0.03,
            style=_prompt_style(),
        )
        self._app = app
        return app

    def run_until_exit(self) -> int:
        _set_tui_active(True)
        self._start_status_updates()
        try:
            app = self._app or self.build_app()
            app.run()
            return int(self._exit_code) if self._exit_code is not None else 0
        finally:
            self._stop_status_updates()
            _set_tui_active(False)


def _picker_bounds(count: int, selected: int, visible: int) -> tuple[int, int]:
    visible = max(1, min(count, visible)) if count else 0
    start = max(0, min(selected - visible // 2, count - visible))
    return start, min(count, start + visible)


def _compact_status_label(label: str) -> str:
    return {
        "proc ram": "proc",
        "status": "status",
    }.get(label, label)


def _compact_status_value(label: str, value: str, very_compact: bool) -> str:
    clean = " ".join(value.split())
    if label == "ram":
        match = re.match(
            r"([\d.]+)\s*([KMGTP]?B)\s*/\s*([\d.]+)\s*([KMGTP]?B)\s*\(([^)]+)\)",
            clean,
            re.IGNORECASE,
        )
        if match:
            used, used_unit, total, total_unit, percent = match.groups()
            if very_compact:
                return percent
            if used_unit.lower() == total_unit.lower():
                return f"{used}/{total}{total_unit} {percent}"
            return f"{used}{used_unit}/{total}{total_unit} {percent}"
    if label == "proc ram":
        return re.sub(r"(?<=\d)\s+(?=[KMGTP]?B\b)", "", clean, flags=re.IGNORECASE)
    return clean


def _strip(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text or "")


def _menu_header(title: str, hints: str) -> str:
    return f"{CYAN}{BOLD}{title}{RESET}  {GRAY}{hints}{RESET}"


def _selected_row(row: str, selected: bool) -> str:
    return f"{GREEN}{BOLD}{row}{RESET}" if selected else row


def _style_command_bar(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("> "):
            lines.append(f"{GREEN}{BOLD}{line}{RESET}")
        elif line.startswith(" usage:"):
            lines.append(f"{CYAN}{line}{RESET}")
        elif line.lstrip().startswith("...") or line.startswith(" no matching"):
            lines.append(f"{GRAY}{line}{RESET}")
        else:
            lines.append(line)
    return "\n".join(lines)


def run_persistent_repl(
    repl_worker: Callable[[], int],
    status_text: Callable[[], str],
    tasks_text: Callable[[], str],
    chat_buffer: ChatBuffer,
    completer: Any = None,
) -> int:
    """Run the persistent TUI for a whole REPL session.

    Spawns ``repl_worker`` (the existing ``_repl`` while-loop) on a daemon
    thread and runs the persistent Application on the main thread. The worker
    must be wired so its ``_input_with_status`` calls route through
    ``active_mediator().request_prompt(...)``; this is set up in ``cli._repl``.

    Returns the worker's exit code (or 0).
    """
    mediator = _TuiInputMediator(status_text, tasks_text, chat_buffer, completer=completer)
    set_active_mediator(mediator)
    _set_tui_active(True)
    mediator.build_app()

    exit_code_box: dict[str, int] = {"code": 0}
    error_box: dict[str, str] = {}

    def _worker() -> None:
        try:
            exit_code_box["code"] = int(repl_worker() or 0)
        except (EOFError, KeyboardInterrupt):
            exit_code_box["code"] = 0
        except Exception as exc:
            exit_code_box["code"] = 1
            error_box["message"] = f"OpenVINO Chat error: {exc}"
        finally:
            # Ensure the app exits when the worker loop returns.
            mediator.request_exit(exit_code_box["code"])
            # Unblock the app in case it was waiting on a prompt accept.
            mediator._prompt_value = ""
            mediator._prompt_event.set()
            try:
                mediator._app.exit(result=exit_code_box["code"])
            except Exception:
                pass

    worker_thread = threading.Thread(target=_worker, name="openvino-repl", daemon=True)
    worker_thread.start()
    try:
        code = mediator.run_until_exit()
    finally:
        set_active_mediator(None)
        _set_tui_active(False)
    if error_box.get("message"):
        print(error_box["message"], file=sys.stderr)
    return code


_active_mediator: _TuiInputMediator | None = None


def set_active_mediator(mediator: _TuiInputMediator | None) -> None:
    global _active_mediator
    _active_mediator = mediator


def active_mediator() -> _TuiInputMediator | None:
    return _active_mediator
