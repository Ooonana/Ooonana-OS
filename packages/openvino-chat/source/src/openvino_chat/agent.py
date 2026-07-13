from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from openvino_chat.tools import TOOL_DEFINITIONS, ToolRegistry, format_tool_result, parse_tool_requests


TOOL_SYSTEM_PROMPT = """You are {model_name} running inside OpenVINO Chat as a local assistant.
Use provided tools whenever facts depend on the computer, workspace, or current web information.
Inspect before changing files. Never invent tool output. If a tool fails, use its error to correct the next action.
This computer runs Windows and PowerShell. Use storage for disk-space questions; never use df.
After tools finish, answer the user's request directly and cite concrete results. Do not expose tool-call syntax.
For plans, use markdown checkboxes like "- [ ] step" and "- [x] done" so the task panel can track progress."""

FALLBACK_TOOL_PROTOCOL = """
When using a tool, output exactly one JSON object and no text after it:
{"tool":"tool_name","args":{"argument":"value"}}
Available tool names: pwd, ls, read, scan, grep, write, append, shell, storage, web_search, web_fetch, diff, undo.
""".strip()


class ToolChatSession:
    def __init__(
        self,
        engine: Any,
        tools: ToolRegistry | None = None,
        max_tool_rounds: int = 8,
    ) -> None:
        self.engine = engine
        self.tools = tools or ToolRegistry()
        self.max_tool_rounds = max_tool_rounds
        self.history: list[tuple[str, str]] = []
        self.system_prompt_template = TOOL_SYSTEM_PROMPT
        self.tools_enabled = True

    def reset(self) -> None:
        self.history.clear()

    def ask(
        self,
        message: str,
        on_token=None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        **generation_kwargs: Any,
    ) -> str:
        native_messages = self._native_messages(message)
        pending = self._format_native(native_messages)
        using_native_template = pending is not None
        if pending is None:
            pending = self._build_prompt(message, generation_kwargs)
        for round_index in range(self.max_tool_rounds + 1):
            if using_native_template and round_index:
                formatted = self._format_native(native_messages)
                if formatted is not None:
                    pending = formatted
            pending = self._fit_pending_prompt(pending, generation_kwargs)
            if on_event is not None:
                phase = "thinking" if round_index == 0 else "generating"
                on_event({"phase": phase})
            stream = _ToolSafeStreamer(on_token) if on_token is not None else None
            response = self.engine.generate(
                pending,
                on_token=stream.push if stream is not None else None,
                **generation_kwargs,
            )
            requests = parse_tool_requests(response) if self.tools_enabled else []
            if not requests:
                if stream is not None:
                    stream.finish(show_buffered=True)
                    if not stream.raw:
                        on_token(response)
                elif on_token is not None:
                    on_token(response)
                self.history.append(("user", message))
                self.history.append(("assistant", response))
                return response
            if stream is not None:
                stream.finish(show_buffered=False)
            results: list[tuple[str, str, str]] = []
            for request_index, request in enumerate(requests):
                if on_event is not None:
                    on_event({"phase": "tool", "tool": request.name, "args": request.args})
                call_id = f"call_{round_index}_{request_index}"
                results.append((call_id, request.name, format_tool_result(self.tools.run(request))))
            if using_native_template:
                native_messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {"name": request.name, "arguments": request.args},
                            }
                            for (call_id, _name, _result), request in zip(results, requests)
                        ],
                    }
                )
                native_messages.extend(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": result,
                    }
                    for call_id, name, result in results
                )
            else:
                result_text = "\n\n".join(result for _call_id, _name, result in results)
                pending = (
                    pending
                    + "\n\nassistant: "
                    + response
                    + "\n\n"
                    + result_text
                    + "\n\nassistant: Use the tool result above. Continue the task or answer now."
                )
        self.history.append(("user", message))
        self.history.append(("assistant", response))
        return response

    def _build_prompt(
        self,
        message: str,
        generation_kwargs: dict[str, Any] | None = None,
    ) -> str:
        model_name = getattr(self.engine, "model_name", "the current model")
        system_prompt = self.system_prompt_template.replace("{model_name}", str(model_name))
        if self.tools_enabled:
            system_prompt += "\n\n" + FALLBACK_TOOL_PROTOCOL
        generation_kwargs = generation_kwargs or {}
        input_budget = _input_token_budget(generation_kwargs)
        if input_budget is None:
            return _compose_prompt(system_prompt, self.history[-12:], message, omitted=False)

        history = list(self.history[-64:])
        omitted = len(history) < len(self.history)
        prompt = _compose_prompt(system_prompt, history, message, omitted)
        while history and self._count_tokens(prompt) > input_budget:
            _drop_oldest_turn(history)
            omitted = True
            prompt = _compose_prompt(system_prompt, history, message, omitted)
        if self._count_tokens(prompt) <= input_budget:
            return prompt

        overhead = self._count_tokens(_compose_prompt("", [], "", omitted))
        available = max(16, input_budget - overhead)
        system_budget = min(
            self._count_tokens(system_prompt),
            max(32, available // 3),
        )
        fitted_system = _truncate_to_tokens(system_prompt, system_budget, self._count_tokens)
        message_budget = max(16, available - self._count_tokens(fitted_system))
        fitted_message = _truncate_to_tokens(message, message_budget, self._count_tokens)
        prompt = _compose_prompt(fitted_system, [], fitted_message, omitted=True)
        while self._count_tokens(prompt) > input_budget and message_budget > 16:
            overflow = self._count_tokens(prompt) - input_budget
            message_budget = max(16, message_budget - overflow - 4)
            fitted_message = _truncate_to_tokens(message, message_budget, self._count_tokens)
            prompt = _compose_prompt(fitted_system, [], fitted_message, omitted=True)
        return prompt

    def _native_messages(self, message: str) -> list[dict[str, Any]]:
        model_name = getattr(self.engine, "model_name", "the current model")
        system_prompt = self.system_prompt_template.replace("{model_name}", str(model_name))
        history = self.history[-24:]
        if len(history) < len(self.history):
            system_prompt += "\n\nOlder conversation was omitted to fit context."
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": role, "content": content} for role, content in history)
        messages.append({"role": "user", "content": message})
        return messages

    def _format_native(self, messages: list[dict[str, Any]]) -> str | None:
        formatter = getattr(self.engine, "format_chat", None)
        if not callable(formatter):
            return None
        try:
            tools = TOOL_DEFINITIONS if self.tools_enabled else None
            formatted = formatter(messages, tools=tools)
            return str(formatted) if formatted else None
        except Exception:
            return None

    def _fit_pending_prompt(
        self,
        prompt: str,
        generation_kwargs: dict[str, Any],
    ) -> str:
        input_budget = _input_token_budget(generation_kwargs)
        if input_budget is None or self._count_tokens(prompt) <= input_budget:
            return prompt
        return _truncate_to_tokens(prompt, input_budget, self._count_tokens)

    def _count_tokens(self, text: str) -> int:
        counter = getattr(self.engine, "count_tokens", None)
        if callable(counter):
            try:
                return max(0, int(counter(text)))
            except Exception:
                pass
        if not text:
            return 0
        return max(1, (len(text.encode("utf-8")) + 2) // 3)


def _compose_prompt(
    system_prompt: str,
    history: list[tuple[str, str]],
    message: str,
    omitted: bool,
) -> str:
    lines = [system_prompt, ""]
    if omitted:
        lines.extend(["[Older conversation omitted to fit context.]", ""])
    for role, content in history:
        lines.append(f"{role}: {content}")
    lines.append(f"user: {message}")
    lines.append("assistant:")
    return "\n".join(lines)


def _input_token_budget(generation_kwargs: dict[str, Any]) -> int | None:
    raw_context = generation_kwargs.get("context_length")
    if raw_context is None:
        return None
    context_length = max(2, int(raw_context))
    max_new_tokens = max(1, int(generation_kwargs.get("max_new_tokens", 4096)))
    reserve = min(
        max_new_tokens,
        max(32, min(1024, context_length // 4)),
        max(1, context_length // 2),
    )
    return max(1, context_length - reserve)


def _drop_oldest_turn(history: list[tuple[str, str]]) -> None:
    if len(history) >= 2 and history[0][0] == "user" and history[1][0] == "assistant":
        del history[:2]
    elif history:
        del history[0]


def _truncate_to_tokens(
    text: str,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> str:
    if max_tokens <= 0 or not text:
        return ""
    if count_tokens(text) <= max_tokens:
        return text
    marker = "\n...[truncated to fit context]...\n"
    if count_tokens(marker) >= max_tokens:
        marker = "...[truncated]..."
    best = marker
    low = 0
    high = len(text)
    while low <= high:
        keep = (low + high) // 2
        head = (keep + 1) // 2
        tail = keep // 2
        candidate = text[:head] + marker + (text[-tail:] if tail else "")
        if count_tokens(candidate) <= max_tokens:
            best = candidate
            low = keep + 1
        else:
            high = keep - 1
    return best


class _ToolSafeStreamer:
    def __init__(self, emit: Callable[[str], None]) -> None:
        self.emit = emit
        self.raw = ""
        self.emitted = 0

    def push(self, token: str) -> None:
        if not token:
            return
        self.raw += token
        safe = _safe_visible_prefix(self.raw)
        if len(safe) <= self.emitted:
            return
        self.emit(safe[self.emitted :])
        self.emitted = len(safe)

    def finish(self, show_buffered: bool) -> None:
        if not show_buffered or len(self.raw) <= self.emitted:
            return
        self.emit(self.raw[self.emitted :])
        self.emitted = len(self.raw)


def _safe_visible_prefix(text: str) -> str:
    lower = text.lower()
    tool_markers = ("<tool_call>", "<|tool_call>")
    marker_indexes = [index for marker in tool_markers if (index := lower.find(marker)) >= 0]
    if marker_indexes:
        return text[: min(marker_indexes)]
    partial = max(_partial_marker_length(lower, marker) for marker in tool_markers)
    if partial:
        return text[:-partial]
    gemma_call = re.search(r"\bcall:[A-Za-z_][\w.-]*\s*\{", text, flags=re.IGNORECASE)
    if gemma_call is not None:
        return text[: gemma_call.start()]
    gemma_partial = re.search(
        r"\bcall(?::[A-Za-z_][\w.-]*)?\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if gemma_partial is not None:
        return text[: gemma_partial.start()]
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return ""
    close_indexes = [
        index
        for marker in ("</think>", "<think/>", "<think />", "</thinking>", "</analysis>", "<channel|>")
        if (index := lower.find(marker)) >= 0
    ]
    close_index = min(close_indexes, default=-1)
    if close_index >= 0:
        close_marker = next(
            marker
            for marker in ("</think>", "<think/>", "<think />", "</thinking>", "</analysis>", "<channel|>")
            if lower.startswith(marker, close_index)
        )
        visible_end = close_index + len(close_marker)
        rest = text[visible_end:]
        if rest.lstrip().startswith("{"):
            return text[:visible_end] + rest[: len(rest) - len(rest.lstrip())]
    return text


def _partial_marker_length(text: str, marker: str) -> int:
    for size in range(min(len(text), len(marker) - 1), 0, -1):
        if text.endswith(marker[:size]):
            return size
    return 0
