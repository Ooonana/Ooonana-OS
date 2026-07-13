from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from openvino_chat.agent import _ToolSafeStreamer
from openvino_chat.engine import OpenVinoChatEngine, load_engine
from openvino_chat.settings import API_DIR
from openvino_chat.tools import ToolRequest, parse_tool_requests
from openvino_chat.ui import split_thinking


DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 11435
API_STATE_PATH = API_DIR / "server.json"
API_LOG_PATH = API_DIR / "server.log"

EngineLoader = Callable[..., OpenVinoChatEngine]


@dataclass(frozen=True)
class GenerationResult:
    text: str
    reasoning: str
    tool_calls: list[ToolRequest]
    prompt_tokens: int
    completion_tokens: int


class ApiRuntime:
    def __init__(
        self,
        model_dir: Path,
        device: str = "GPU",
        context_length: int = 4096,
        kv_cache_precision: str = "auto",
        engine_loader: EngineLoader = load_engine,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.device = device.upper()
        self.context_length = max(2, int(context_length))
        self.kv_cache_precision = kv_cache_precision
        self.engine_loader = engine_loader
        self.model_id = self.model_dir.name
        self._engine: OpenVinoChatEngine | None = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._engine is not None

    @property
    def active_device(self) -> str:
        return self._engine.device if self._engine is not None else self.device

    def chat(
        self,
        body: dict[str, Any],
        on_token: Callable[[str], None] | None = None,
    ) -> GenerationResult:
        messages = _normalize_messages(body.get("messages"))
        tools = _normalize_tools(body.get("tools"))
        with self._lock:
            engine = self._ensure_engine()
            prompt = engine.format_chat(messages, tools=tools or None)
            if not prompt:
                prompt = _fallback_chat_prompt(messages, tools)
            raw = _generate(engine, str(prompt), body, self.context_length, on_token=on_token)
            return _generation_result(engine, str(prompt), raw)

    def complete(
        self,
        body: dict[str, Any],
        on_token: Callable[[str], None] | None = None,
    ) -> GenerationResult:
        prompt = body.get("prompt")
        if isinstance(prompt, list):
            if len(prompt) != 1 or not isinstance(prompt[0], str):
                raise ValueError("prompt must be one string")
            prompt = prompt[0]
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be a non-empty string")
        with self._lock:
            engine = self._ensure_engine()
            raw = _generate(engine, prompt, body, self.context_length, on_token=on_token)
            return _generation_result(engine, prompt, raw)

    def _ensure_engine(self) -> OpenVinoChatEngine:
        if self._engine is not None:
            return self._engine
        if not self.model_dir.exists():
            raise RuntimeError(f"model missing: {self.model_dir}")
        try:
            self._engine = self.engine_loader(
                self.model_dir,
                device=self.device,
                kv_cache_precision=self.kv_cache_precision,
            )
        except TypeError as exc:
            if "kv_cache_precision" not in str(exc):
                raise
            self._engine = self.engine_loader(self.model_dir, device=self.device)
        return self._engine


class OpenVinoApiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        runtime: ApiRuntime,
        api_key: str | None = None,
        instance_id: str | None = None,
    ) -> None:
        self.runtime = runtime
        self.api_key = api_key
        self.instance_id = instance_id or uuid.uuid4().hex
        super().__init__(server_address, OpenVinoApiHandler)


class OpenVinoApiHandler(BaseHTTPRequestHandler):
    server: OpenVinoApiServer
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._json_response(
                200,
                {
                    "status": "ok",
                    "instance_id": self.server.instance_id,
                    "model": self.server.runtime.model_id,
                    "loaded": self.server.runtime.loaded,
                    "device": self.server.runtime.active_device,
                },
            )
            return
        if not self._authorized():
            return
        if self.path.rstrip("/") == "":
            self._json_response(
                200,
                {
                    "status": "ok",
                    "instance_id": self.server.instance_id,
                    "model": self.server.runtime.model_id,
                    "loaded": self.server.runtime.loaded,
                    "device": self.server.runtime.active_device,
                },
            )
            return
        if self.path.rstrip("/") == "/v1/models":
            self._json_response(200, _models_payload(self.server.runtime))
            return
        self._error(404, "not_found", f"unknown endpoint: {self.path}")

    def do_POST(self) -> None:
        if not self._authorized():
            return
        try:
            body = self._read_json()
            if self.path.rstrip("/") == "/v1/chat/completions":
                if body.get("stream") is True:
                    self._stream_chat_request(body)
                else:
                    result = self.server.runtime.chat(body)
                    self._json_response(200, _chat_payload(self.server.runtime, result))
                return
            if self.path.rstrip("/") == "/v1/completions":
                if body.get("stream") is True:
                    self._stream_completion_request(body)
                else:
                    result = self.server.runtime.complete(body)
                    self._json_response(200, _completion_payload(self.server.runtime, result))
                return
            self._error(404, "not_found", f"unknown endpoint: {self.path}")
        except ValueError as exc:
            self._error(400, "invalid_request_error", str(exc))
        except Exception as exc:
            self._error(500, "server_error", str(exc))

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"api {self.address_string()} {fmt % args}", file=sys.stderr, flush=True)

    def _authorized(self) -> bool:
        required = self.server.api_key
        if not required:
            return True
        supplied = self.headers.get("Authorization", "")
        if supplied == f"Bearer {required}":
            return True
        self._error(401, "authentication_error", "invalid API key")
        return False

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0 or length > 10 * 1024 * 1024:
            raise ValueError("request body must be between 1 byte and 10 MB")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, error_type: str, message: str) -> None:
        self._json_response(
            status,
            {"error": {"message": message, "type": error_type, "code": error_type}},
        )

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _start_sse(self) -> None:
        self.close_connection = True
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _sse(self, payload: dict[str, Any] | str) -> None:
        value = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        self.wfile.write(f"data: {value}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _stream_chat_request(self, body: dict[str, Any]) -> None:
        self._start_sse()
        created = int(time.time())
        completion_id = "chatcmpl-" + uuid.uuid4().hex

        def chunk(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
            return {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": self.server.runtime.model_id,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
            }

        self._sse(chunk({"role": "assistant", "content": ""}))
        deltas = _ApiTokenDeltas(
            on_reasoning=lambda value: self._sse(chunk({"reasoning_content": value})),
            on_content=lambda value: self._sse(chunk({"content": value})),
        )
        tool_filter = _ToolSafeStreamer(deltas.push)
        result = self.server.runtime.chat(body, on_token=tool_filter.push)
        if tool_filter.raw:
            tool_filter.finish(show_buffered=not result.tool_calls)
            deltas.finish()
        else:
            if result.reasoning:
                self._sse(chunk({"reasoning_content": result.reasoning}))
            if result.text:
                self._sse(chunk({"content": result.text}))
        if result.tool_calls:
            self._sse(chunk({"tool_calls": _stream_tool_calls(result.tool_calls)}))
        finish = "tool_calls" if result.tool_calls else "stop"
        self._sse(chunk({}, finish))
        self._sse("[DONE]")

    def _stream_completion_request(self, body: dict[str, Any]) -> None:
        self._start_sse()
        created = int(time.time())
        completion_id = "cmpl-" + uuid.uuid4().hex

        streamed = False

        def emit(piece: str) -> None:
            nonlocal streamed
            streamed = True
            self._sse(
                {
                    "id": completion_id,
                    "object": "text_completion",
                    "created": created,
                    "model": self.server.runtime.model_id,
                    "choices": [{"index": 0, "text": piece, "finish_reason": None}],
                }
            )

        result = self.server.runtime.complete(body, on_token=emit)
        if not streamed and result.text:
            emit(result.text)
        self._sse(
            {
                "id": completion_id,
                "object": "text_completion",
                "created": created,
                "model": self.server.runtime.model_id,
                "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
            }
        )
        self._sse("[DONE]")


def run_api_server(
    model_dir: Path,
    host: str = DEFAULT_API_HOST,
    port: int = DEFAULT_API_PORT,
    device: str = "GPU",
    context_length: int = 4096,
    kv_cache_precision: str = "auto",
    api_key: str | None = None,
    engine_loader: EngineLoader = load_engine,
) -> int:
    _validate_bind(host, port, api_key)
    runtime = ApiRuntime(
        model_dir,
        device=device,
        context_length=context_length,
        kv_cache_precision=kv_cache_precision,
        engine_loader=engine_loader,
    )
    server = OpenVinoApiServer((host, port), runtime, api_key=api_key)
    bound_host, bound_port = server.server_address[:2]
    state = {
        "pid": os.getpid(),
        "instance_id": server.instance_id,
        "host": bound_host,
        "port": bound_port,
        "base_url": f"http://{bound_host}:{bound_port}/v1",
        "model": runtime.model_id,
        "model_dir": str(runtime.model_dir),
        "device": device,
        "context_length": context_length,
        "kv_cache_precision": kv_cache_precision,
        "started_at": int(time.time()),
    }
    API_DIR.mkdir(parents=True, exist_ok=True)
    API_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"OpenVINO API: {state['base_url']}", flush=True)
    print(f"model={runtime.model_id} loaded=no device={device}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        _remove_owned_state(server.instance_id)
    return 0


def start_api_process(
    model_dir: Path,
    host: str = DEFAULT_API_HOST,
    port: int = DEFAULT_API_PORT,
    device: str = "GPU",
    context_length: int = 4096,
    kv_cache_precision: str = "auto",
    api_key: str | None = None,
) -> dict[str, Any]:
    _validate_bind(host, port, api_key)
    current = api_status()
    if current.get("running"):
        return current
    API_DIR.mkdir(parents=True, exist_ok=True)
    if API_LOG_PATH.exists() and API_LOG_PATH.stat().st_size > 2 * 1024 * 1024:
        API_LOG_PATH.write_text("", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "openvino_chat",
        "--model-dir",
        str(model_dir),
        "serve",
        "--host",
        host,
        "--port",
        str(port),
        "--device",
        device,
        "--ctx",
        str(context_length),
        "--kv-cache",
        kv_cache_precision,
    ]
    log = API_LOG_PATH.open("a", encoding="utf-8")
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    if api_key:
        environment = os.environ.copy()
        environment["OPENVINO_CHAT_API_KEY"] = api_key
        kwargs["env"] = environment
    try:
        process = subprocess.Popen(command, **kwargs)
    finally:
        log.close()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        status = api_status()
        if status.get("running"):
            return status
        if process.poll() is not None:
            break
        time.sleep(0.1)
    if process.poll() is None:
        process.terminate()
    tail = _log_tail()
    raise RuntimeError("API server failed to start" + (f": {tail}" if tail else ""))


def stop_api_process() -> bool:
    status = api_status()
    if not status.get("running"):
        API_STATE_PATH.unlink(missing_ok=True)
        return False
    pid = int(status["pid"])
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
    else:
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _health_matches(status):
        time.sleep(0.1)
    API_STATE_PATH.unlink(missing_ok=True)
    return True


def api_status() -> dict[str, Any]:
    if not API_STATE_PATH.exists():
        return {"running": False}
    try:
        state = json.loads(API_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"running": False}
    if not isinstance(state, dict) or not _health_matches(state):
        return {**state, "running": False}
    return {**state, "running": True}


def format_api_status(status: dict[str, Any] | None = None) -> str:
    value = status or api_status()
    if not value.get("running"):
        return (
            "api: stopped\n"
            f"default: http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}/v1\n"
            "start: /api start\n"
            "server: openvino serve"
        )
    return "\n".join(
        [
            "api: running",
            f"url: {value.get('base_url')}",
            f"model: {value.get('model')}",
            f"device: {value.get('device')}",
            f"pid: {value.get('pid')}",
            f"log: {API_LOG_PATH}",
        ]
    )


def _normalize_messages(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("messages must be a non-empty array")
    messages: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict) or not isinstance(raw.get("role"), str):
            raise ValueError("each message must contain a role")
        message = dict(raw)
        message["content"] = _message_text(raw.get("content"))
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            message["tool_calls"] = [_normalize_tool_call(call) for call in calls]
        messages.append(message)
    return messages


def _message_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(part.get("text") or "")
            for part in value
            if isinstance(part, dict) and part.get("type") in {"text", "input_text"}
        )
    raise ValueError("message content must be text or text parts")


def _normalize_tool_call(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("function"), dict):
        raise ValueError("invalid assistant tool_call")
    call = dict(value)
    function = dict(call["function"])
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            decoded = json.loads(arguments)
        except json.JSONDecodeError:
            decoded = arguments
        else:
            arguments = decoded
    function["arguments"] = arguments
    call["function"] = function
    return call


def _normalize_tools(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tools must be an array")
    tools = []
    for tool in value:
        if not isinstance(tool, dict) or not isinstance(tool.get("function"), dict):
            raise ValueError("each tool must be an OpenAI function tool")
        tools.append(tool)
    return tools


def _fallback_chat_prompt(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    if tools:
        lines.append("Available tools: " + json.dumps(tools, ensure_ascii=False))
    for message in messages:
        lines.append(f"{message['role']}: {message.get('content', '')}")
    lines.append("assistant:")
    return "\n".join(lines)


def _generate(
    engine: OpenVinoChatEngine,
    prompt: str,
    body: dict[str, Any],
    context_length: int,
    on_token: Callable[[str], None] | None = None,
) -> str:
    max_tokens = body.get("max_completion_tokens", body.get("max_tokens", 512))
    try:
        max_tokens = max(1, min(int(max_tokens), context_length))
        temperature = float(body.get("temperature", 0.7))
        top_p = float(body.get("top_p", 0.9))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid generation parameter") from exc
    stop = body.get("stop")
    stop_values = [stop] if isinstance(stop, str) else stop if isinstance(stop, list) else []
    stop_values = [value for value in stop_values if isinstance(value, str) and value]
    chunks: list[str] = []

    def emit_token(token: str) -> None:
        chunks.append(token)
        if on_token is not None:
            on_token(token)

    def should_stop() -> bool:
        current = "".join(chunks)
        return any(marker in current for marker in stop_values)

    raw = engine.generate(
        prompt,
        on_token=emit_token if stop_values or on_token is not None else None,
        should_stop=should_stop if stop_values else None,
        max_new_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        context_length=context_length,
    )
    for marker in stop_values:
        if marker in raw:
            raw = raw.split(marker, 1)[0]
    return raw


def _generation_result(engine: OpenVinoChatEngine, prompt: str, raw: str) -> GenerationResult:
    calls = parse_tool_requests(raw)
    visible = _visible_before_tool_call(raw)
    reasoning, answer = split_thinking(visible)
    if not reasoning and not answer and not calls:
        answer = raw.strip()
    return GenerationResult(
        text=answer,
        reasoning=reasoning,
        tool_calls=calls,
        prompt_tokens=engine.count_tokens(prompt),
        completion_tokens=engine.count_tokens(raw),
    )


def _visible_before_tool_call(text: str) -> str:
    lower = text.lower()
    indexes = [
        index
        for marker in ("<|tool_call>", "<tool_call>")
        if (index := lower.find(marker)) >= 0
    ]
    import re

    gemma = re.search(r"\bcall:[A-Za-z_][\w.-]*\s*\{", text, flags=re.IGNORECASE)
    if gemma is not None:
        indexes.append(gemma.start())
    return text[: min(indexes)].strip() if indexes else text.strip()


def _models_payload(runtime: ApiRuntime) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": runtime.model_id,
                "object": "model",
                "created": 0,
                "owned_by": "openvino-local",
            }
        ],
    }


def _chat_payload(runtime: ApiRuntime, result: GenerationResult) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": result.text or None}
    if result.reasoning:
        message["reasoning_content"] = result.reasoning
    if result.tool_calls:
        message["tool_calls"] = _openai_tool_calls(result.tool_calls)
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": runtime.model_id,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if result.tool_calls else "stop",
            }
        ],
        "usage": _usage(result),
    }


def _completion_payload(runtime: ApiRuntime, result: GenerationResult) -> dict[str, Any]:
    return {
        "id": "cmpl-" + uuid.uuid4().hex,
        "object": "text_completion",
        "created": int(time.time()),
        "model": runtime.model_id,
        "choices": [{"index": 0, "text": result.text, "finish_reason": "stop"}],
        "usage": _usage(result),
    }


def _usage(result: GenerationResult) -> dict[str, int]:
    return {
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.prompt_tokens + result.completion_tokens,
    }


def _openai_tool_calls(calls: list[ToolRequest]) -> list[dict[str, Any]]:
    return [
        {
            "id": "call_" + uuid.uuid4().hex,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": json.dumps(call.args, ensure_ascii=False, separators=(",", ":")),
            },
        }
        for call in calls
    ]


def _stream_tool_calls(calls: list[ToolRequest]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            **call,
        }
        for index, call in enumerate(_openai_tool_calls(calls))
    ]


class _ApiTokenDeltas:
    _OPEN_MARKERS = (
        "<think>",
        "<thinking>",
        "<analysis>",
        "<|channel>thought",
        "<|channel>analysis",
    )
    _CLOSE_MARKERS = (
        "</think>",
        "<think/>",
        "<think />",
        "</thinking>",
        "</analysis>",
        "<channel|>",
    )

    def __init__(
        self,
        on_reasoning: Callable[[str], None],
        on_content: Callable[[str], None],
    ) -> None:
        self.on_reasoning = on_reasoning
        self.on_content = on_content
        self.buffer = ""
        self.thinking = False

    def push(self, token: str) -> None:
        self.buffer += token
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)

    def _drain(self, final: bool) -> None:
        markers = (*self._OPEN_MARKERS, *self._CLOSE_MARKERS)
        while self.buffer:
            lower = self.buffer.lower()
            matches = [
                (index, marker)
                for marker in markers
                if (index := lower.find(marker)) >= 0
            ]
            if matches:
                index, marker = min(matches, key=lambda item: item[0])
                prefix = self.buffer[:index]
                is_close = marker in self._CLOSE_MARKERS
                if prefix:
                    if is_close and not self.thinking:
                        self.on_reasoning(prefix)
                    else:
                        self._emit(prefix)
                self.buffer = self.buffer[index + len(marker) :]
                self.thinking = not is_close
                continue
            if final:
                self._emit(self.buffer)
                self.buffer = ""
                return
            keep = max(_partial_suffix(lower, marker) for marker in markers)
            safe_length = len(self.buffer) - keep
            if safe_length <= 0:
                return
            self._emit(self.buffer[:safe_length])
            self.buffer = self.buffer[safe_length:]

    def _emit(self, text: str) -> None:
        if not text:
            return
        (self.on_reasoning if self.thinking else self.on_content)(text)


def _partial_suffix(text: str, marker: str) -> int:
    for size in range(min(len(text), len(marker) - 1), 0, -1):
        if text.endswith(marker[:size]):
            return size
    return 0


def _validate_bind(host: str, port: int, api_key: str | None) -> None:
    if not 1 <= int(port) <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if host not in {"127.0.0.1", "localhost", "::1"} and not api_key:
        raise ValueError("--api-key is required when binding outside localhost")


def _health_matches(state: dict[str, Any]) -> bool:
    host = str(state.get("host") or DEFAULT_API_HOST)
    if host in {"0.0.0.0", "::"}:
        host = DEFAULT_API_HOST
    port = state.get("port")
    instance_id = state.get("instance_id")
    if not port or not instance_id:
        return False
    try:
        with urllib.request.urlopen(f"http://{host}:{int(port)}/health", timeout=0.35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("instance_id") == instance_id
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return False


def _remove_owned_state(instance_id: str) -> None:
    try:
        state = json.loads(API_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if state.get("instance_id") == instance_id:
        API_STATE_PATH.unlink(missing_ok=True)


def _log_tail() -> str:
    try:
        lines = API_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return " | ".join(lines[-3:])
