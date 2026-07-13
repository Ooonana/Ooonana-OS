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


class ChatBuffer:
    """Thread-safe append-only log of ANSI-styled chat segments."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._segments: list[str | _MutableRegion] = []
        self._dirty = True
        self._snapshot = ""

    def append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._segments.append(text)
            self._dirty = True

    def append_line(self, text: str = "") -> None:
        self.append(text + "\n")

    def append_user(self, prompt: str) -> None:
        self.append(f"> {prompt}\n")

    def begin_assistant(self) -> None:
        self.append(f"{GREEN}> {RESET}")

    def append_tool(self, name: str, args_text: str) -> None:
        self.append(f"\n{DIM}tool: {name} {args_text}{RESET}\n")

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

    def replace(self, text: str) -> None:
        with self._lock:
            self._segments[:] = [text] if text else []
            self._dirty = True

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

    def __init__(self, buffer: ChatBuffer, invalidate: Callable[[], None]) -> None:
        from openvino_chat.ui import ResponseStream

        self.buffer = buffer
        self.invalidate = invalidate
        self.fragments: list[tuple[str, str | None]] = []
        self.region: int | None = None
        self.inner = ResponseStream(writer=self._write)

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


def response_stream(buffer: ChatBuffer, invalidate: Callable[[], None]):
    return TuiResponseStream(buffer, invalidate)


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
    return "".join(rendered)


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

    def clear(self, refresh: bool = True) -> None:
        self.mediator.clear_operation(refresh=refresh)

    def refresh(self) -> None:
        self.mediator.invalidate()

    def response_stream(self):
        return response_stream(self.buffer, self.mediator.invalidate)

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
        self._slash_index = 0
        self._slash_navigation = False
        self._slash_query = ""
        self._chat_view_height = 0
        self._chat_view_width = 0
        self._chat_scroll_lines = 0

    # -- worker side -------------------------------------------------------

    def request_prompt(self, prompt_text: str) -> str:
        # Mark generation complete so the input bar accepts the next prompt.
        self._busy.set()
        self._interrupted.clear()
        self._prompt_text = prompt_text
        if self._input_area is not None:
            try:
                self._set_input_prompt(prompt_text)
                self._input_area.text = ""
            except Exception:
                pass
        self._request_event.set()
        self._prompt_event.clear()
        # Wake the app so it can re-render the (now-cleared) input bar.
        self.invalidate()
        self._prompt_event.wait()
        self._request_event.clear()
        if self._interrupted.is_set():
            raise KeyboardInterrupt
        return self._prompt_value

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

    def clear_operation(self, refresh: bool = True) -> None:
        self._operation_label = None
        self._operation_started = 0.0
        if refresh:
            self.invalidate()

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
        self._set_input_prompt("")
        if self._input_area is not None:
            self._input_area.text = ""
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
        lines = ["Models  Up/Down select  Enter load  i install  d delete  u unload  Esc close", ""]
        if not self._model_menu_items:
            return "\n".join(lines + ["  no configured models"])
        for index, item in enumerate(self._model_menu_items):
            marker = ">" if index == self._model_menu_index else " "
            active = " active" if item.get("active") else ""
            loaded = " loaded" if item.get("active") and self._model_menu_loaded else ""
            row = (
                f"{marker} {str(item['name']):<8} {str(item['state']):<9} "
                f"{str(item['size']):>9}{active}{loaded}"
            )
            lines.append(f"{GREEN}{row}{RESET}" if index == self._model_menu_index else row)
        selected = self._model_menu_items[self._model_menu_index]
        lines.extend(
            [
                "",
                f"repo: {selected.get('repo', '-')}",
                f"path: {selected.get('path', '-')}",
            ]
        )
        return "\n".join(lines)

    def _model_menu_height(self) -> int:
        return max(3, len(self._model_menu_items) + 5)

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
        if self._input_area is not None:
            self._input_area.text = ""
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
        lines = ["Sessions  Up/Down select  Enter resume  d delete  n new  s save  Esc close", ""]
        if not self._session_menu_items:
            return "\n".join(lines + ["  no saved sessions", "", "Press n to start new session"])

        count = len(self._session_menu_items)
        visible = 8
        start = max(0, min(self._session_menu_index - visible // 2, count - visible))
        end = min(count, start + visible)
        if start:
            lines.append(f"  ... {start} above")
        for index in range(start, end):
            item = self._session_menu_items[index]
            marker = ">" if index == self._session_menu_index else " "
            active = " active" if item.get("active") else ""
            row = f"{marker} {item['name']}{active}"
            lines.append(f"{GREEN}{row}{RESET}" if index == self._session_menu_index else row)
        if end < count:
            lines.append(f"  ... {count - end} below")

        selected = self._session_menu_items[self._session_menu_index]
        preview = str(selected.get("preview") or "(empty)")
        lines.extend(["", "Preview:"])
        lines.extend(f"  {line}" for line in preview.splitlines()[:4])
        return "\n".join(lines)

    def _session_menu_height(self) -> int:
        if not self._session_menu_items:
            return 5
        visible_rows = min(8, len(self._session_menu_items))
        overflow_rows = int(len(self._session_menu_items) > 8) * 2
        preview_rows = min(4, len(str(self._session_menu_items[self._session_menu_index].get("preview") or "").splitlines()))
        return 4 + visible_rows + overflow_rows + preview_rows

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
        if self._input_area is not None:
            self._input_area.text = ""
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
        lines = ["KV cache  Up/Down select  Enter apply  Esc close", ""]
        for index, value in enumerate(self._kv_menu_values):
            marker = ">" if index == self._kv_menu_index else " "
            active = " current" if value == self._kv_menu_current else ""
            row = f"{marker} {value:<5} {descriptions[value]}{active}"
            lines.append(f"{GREEN}{row}{RESET}" if index == self._kv_menu_index else row)
        lines.extend(["", "Changing precision unloads current model. Next prompt reloads it."])
        return "\n".join(lines)

    # -- main thread side --------------------------------------------------

    def invalidate(self) -> None:
        if self._app is not None:
            try:
                self._app.invalidate()
            except Exception:
                pass

    def _render_chat_tail(self) -> str:
        """Return chat tail fitting last rendered window dimensions."""
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
        terminal = shutil.get_terminal_size((100, 30))
        max_rows = self._chat_view_height or max(1, terminal.lines - 5)
        width = self._chat_view_width or max(20, terminal.columns)
        return self.chat_buffer.render_tail(max_rows, width)

    def _render_chat_source(self) -> str:
        terminal = shutil.get_terminal_size((100, 30))
        max_rows = self._chat_view_height or max(1, terminal.lines - 5)
        width = self._chat_view_width or max(20, terminal.columns)
        return self.chat_buffer.render_tail(
            max_rows + self._chat_scroll_lines + 2,
            width,
        )

    def _move_chat_scroll(self, rows: int) -> None:
        max_scroll = max(0, self.chat_buffer.render().count("\n"))
        self._chat_scroll_lines = max(
            0,
            min(max_scroll, self._chat_scroll_lines + rows),
        )
        self.invalidate()

    def _chat_page_size(self) -> int:
        terminal = shutil.get_terminal_size((100, 30))
        return max(1, (self._chat_view_height or terminal.lines - 5) - 1)

    def _set_input_prompt(self, prompt_text: str) -> None:
        if prompt_text:
            self._prompt_text = prompt_text

    def _status_fragments(self) -> list[tuple[str, str]]:
        with self._status_lock:
            text = self._status_value
        frags: list[tuple[str, str]] = [("class:toolbar.title", " openvino "), ("", " ")]
        for index, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            if index:
                frags.append(("class:toolbar.sep", " | "))
            if ": " in line:
                label, value = line.split(": ", 1)
            elif "=" in line:
                label, value = line.split("=", 1)
            else:
                label, value = line.replace("_", " "), None
            frags.append(("class:toolbar.label", label.replace("_", " ")))
            if value is not None:
                frags.append(("class:toolbar.sep", ": "))
                frags.append(("class:toolbar.value", value))
        if self._operation_label:
            elapsed = max(0, int(time.monotonic() - self._operation_started))
            dots = "." * (((max(elapsed, 1) - 1) % 3) + 1)
            frags.append(("class:toolbar.sep", " | "))
            frags.append((self._operation_style(self._operation_label), f"{self._operation_label}{dots} {elapsed}s"))
        elif not self._busy.is_set():
            frags.append(("class:toolbar.sep", " | "))
            frags.append(("class:toolbar.value", "working..."))
        if self._chat_scroll_lines:
            frags.append(("class:toolbar.sep", " | "))
            frags.append(("class:toolbar.label", "history"))
            frags.append(("class:toolbar.sep", ": "))
            frags.append(("class:toolbar.value", f"{self._chat_scroll_lines} lines up"))
        return frags

    @staticmethod
    def _operation_style(label: str) -> str:
        if label == "thinking":
            return "class:operation.thinking"
        if label == "generating":
            return "class:operation.generating"
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

        selected = self._slash_index if self._slash_navigation else None
        return _slash_command_bar(text, selected_index=selected)

    def _slash_command_bar_height(self, text: str) -> int:
        from openvino_chat.cli import _slash_command_bar_height

        return _slash_command_bar_height(text)

    def _slash_matches(self) -> list[Any]:
        if self._input_area is None:
            return []
        from openvino_chat.cli import _slash_command_matches

        return _slash_command_matches(self._input_area.text)

    def _slash_menu_active(self) -> bool:
        return (
            not self._model_menu_active
            and not self._session_menu_active
            and not self._kv_menu_active
            and bool(self._slash_matches())
        )

    def _move_slash_selection(self, amount: int) -> None:
        matches = self._slash_matches()
        if not matches:
            return
        if not self._slash_navigation:
            self._slash_index = 0 if amount > 0 else len(matches) - 1
            self._slash_navigation = True
        else:
            self._slash_index = (self._slash_index + amount) % len(matches)
        self.invalidate()

    def _apply_slash_selection(self) -> bool:
        if not self._slash_navigation:
            return False
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
        from prompt_toolkit.data_structures import Point
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import (
            ConditionalContainer,
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
            prompt=lambda: self._prompt_text,
            multiline=False,
            wrap_lines=True,
            height=1,
            style="class:input",
            completer=self.completer,
            complete_while_typing=True,
        )

        def _input_changed(_buffer) -> None:
            query = self._input_area.text
            if query != self._slash_query:
                self._slash_query = query
                self._slash_index = 0
                self._slash_navigation = False
            self.invalidate()

        self._input_area.buffer.on_text_changed += _input_changed

        def _chat_cursor() -> Point:
            source = self._render_chat_source()
            line = max(0, source.count("\n") - self._chat_scroll_lines)
            return Point(x=0, y=line)

        def _chat_height_dim() -> Dimension:
            return Dimension(weight=1)

        chat_window = Window(
            FormattedTextControl(
                lambda: ANSI(self._render_chat_source()),
                get_cursor_position=_chat_cursor,
            ),
            width=Dimension(weight=1),
            height=_chat_height_dim,
            wrap_lines=True,
            always_hide_cursor=True,
        )
        self._chat_window = chat_window

        def _tasks_visible() -> bool:
            try:
                return has_visible_tasks(self.tasks_text())
            except Exception:
                return False

        task_window = Window(
            FormattedTextControl(lambda: ANSI(_strip(self.tasks_text()))),
            wrap_lines=True,
            always_hide_cursor=True,
            width=Dimension(preferred=32, max=40),
            style="class:task",
        )

        vertical_separator = Window(width=1, char="|", style="class:separator", always_hide_cursor=True)
        input_separator = Window(height=1, char="-", style="class:separator", always_hide_cursor=True)

        def _bar_text() -> str:
            try:
                return self._slash_command_bar(self._input_area.text)
            except Exception:
                return ""

        command_bar = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(_strip(_bar_text()))),
                height=lambda: self._slash_command_bar_height(self._input_area.text),
                style="class:command-bar",
                always_hide_cursor=True,
            ),
            filter=Condition(
                lambda: not self._model_menu_active
                and not self._session_menu_active
                and not self._kv_menu_active
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
                wrap_lines=True,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._session_menu_active),
        )

        kv_menu = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ANSI(self._kv_menu_text())),
                height=8,
                wrap_lines=True,
                always_hide_cursor=True,
                style="class:model-menu",
            ),
            filter=Condition(lambda: self._kv_menu_active),
        )

        toolbar = Window(
            FormattedTextControl(self._status_fragments),
            height=1,
            style="class:bottom-toolbar",
            always_hide_cursor=True,
        )

        task_side = ConditionalContainer(
            VSplit([vertical_separator, task_window]),
            filter=Condition(_tasks_visible),
        )
        content = VSplit([chat_window, task_side], height=Dimension(weight=1))

        body = HSplit(
            [
                content,
                model_menu,
                session_menu,
                kv_menu,
                command_bar,
                input_separator,
                self._input_area,
                toolbar,
            ]
        )

        keys = KeyBindings()
        model_menu_active = Condition(lambda: self._model_menu_active)
        session_menu_active = Condition(lambda: self._session_menu_active)
        kv_menu_active = Condition(lambda: self._kv_menu_active)
        menus_inactive = ~(model_menu_active | session_menu_active | kv_menu_active)

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

        @keys.add("escape", filter=menus_inactive)
        def _stop_generation(_event) -> None:
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

        @keys.add("pageup", filter=menus_inactive)
        def _chat_page_up(_event) -> None:
            self._move_chat_scroll(self._chat_page_size())

        @keys.add("pagedown", filter=menus_inactive)
        def _chat_page_down(_event) -> None:
            self._move_chat_scroll(-self._chat_page_size())

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

        slash_menu_active = Condition(self._slash_menu_active)

        @keys.add("down", filter=slash_menu_active)
        def _slash_down(_event) -> None:
            self._move_slash_selection(1)

        @keys.add("up", filter=slash_menu_active)
        def _slash_up(_event) -> None:
            self._move_slash_selection(-1)

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

        app = Application(
            layout=Layout(body, focused_element=self._input_area),
            key_bindings=keys,
            full_screen=True,
            mouse_support=True,
            refresh_interval=self.refresh_interval,
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


def _strip(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text or "")


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
