from __future__ import annotations

import json
import html
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ToolRequest:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    output: str


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "pwd",
            "description": "Return the current working directory.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ls",
            "description": "List files and directories at a path inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path; defaults to current directory."}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path."}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan",
            "description": "Recursively list workspace files. Use before editing an unfamiliar project.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Starting path; defaults to current directory."}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search text files for a literal case-insensitive string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to find."},
                    "path": {"type": "string", "description": "File or directory; defaults to current directory."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Create or replace a text file inside the workspace. Requires permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Destination file path."},
                    "text": {"type": "string", "description": "Complete file contents."},
                },
                "required": ["path", "text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append",
            "description": "Append text to a file inside the workspace. Requires permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Destination file path."},
                    "text": {"type": "string", "description": "Text to append."},
                },
                "required": ["path", "text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run one PowerShell command in the workspace. Requires permission. Use Windows commands, not Unix-only commands.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "PowerShell command."}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "storage",
            "description": "Report total, used, and free disk storage for a Windows drive or path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Drive or path, such as C:/ or F:/"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information and return result titles, snippets, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Specific search query."}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch readable text from a specific HTTP or HTTPS URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full page URL."}},
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diff",
            "description": "Show file changes made by tools during this chat.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo",
            "description": "Undo the most recent file change made by a tool. Requires permission.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


class ToolRegistry:
    def __init__(
        self,
        cwd: Path | None = None,
        workspace_root: Path | None = None,
        permission_mode: str = "ask",
        approval_callback: Callable[[ToolRequest], bool] | None = None,
        timeout_seconds: int = 30,
        max_output_chars: int = 4000,
        web_searcher: Callable[[str], str] | None = None,
        web_fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.cwd = (cwd or Path.cwd()).resolve()
        self.workspace_root = (workspace_root or self.cwd).resolve()
        self.permission_mode = permission_mode
        self.approval_callback = approval_callback
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        self.web_searcher = web_searcher or self._web_search
        self.web_fetcher = web_fetcher or self._web_fetch
        self._changes: list[tuple[Path, str | None, str]] = []

    def set_workspace(self, path: Path) -> None:
        root = path.resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"workspace not found: {path}")
        self.workspace_root = root
        self.cwd = root

    def set_cwd(self, path: Path) -> None:
        resolved = self._resolve(path)
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"directory not found: {path}")
        self.cwd = resolved

    def run(self, request: ToolRequest) -> ToolResult:
        return self.run_name(request.name, request.args)

    def run_name(self, name: str, args: dict[str, Any]) -> ToolResult:
        handlers = {
            "pwd": self._pwd,
            "ls": self._ls,
            "read": self._read,
            "scan": self._scan,
            "grep": self._grep,
            "write": self._write,
            "append": self._append,
            "shell": self._shell,
            "storage": self._storage,
            "web_search": self._web_search_tool,
            "web_fetch": self._web_fetch_tool,
            "diff": self._diff,
            "undo": self._undo,
        }
        handler = handlers.get(name)
        if handler is None:
            return ToolResult(name, False, f"unknown tool: {name}")
        try:
            request = ToolRequest(name, args)
            if self._needs_permission(name) and not self._approved(request):
                return ToolResult(name, False, "permission denied")
            return ToolResult(name, True, self._cap(handler(args)))
        except Exception as exc:
            return ToolResult(name, False, self._cap(str(exc)))

    def _pwd(self, _args: dict[str, Any]) -> str:
        return str(self.cwd)

    def _ls(self, args: dict[str, Any]) -> str:
        path = self._resolve(args.get("path") or ".")
        entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        return "\n".join(item.name + ("/" if item.is_dir() else "") for item in entries)

    def _read(self, args: dict[str, Any]) -> str:
        path = self._resolve(args.get("path") or "")
        return path.read_text(encoding="utf-8", errors="replace")

    def _scan(self, args: dict[str, Any]) -> str:
        path = self._resolve(args.get("path") or ".")
        if path.is_file():
            return self._relative(path)
        lines = []
        for item in sorted(path.rglob("*"), key=lambda p: str(p).lower()):
            if self._skip_path(item):
                continue
            lines.append(self._relative(item) + ("/" if item.is_dir() else ""))
            if len(lines) >= 200:
                lines.append("... truncated")
                break
        return "\n".join(lines)

    def _grep(self, args: dict[str, Any]) -> str:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("missing query")
        path = self._resolve(args.get("path") or ".")
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        matches = []
        for file_path in sorted(files, key=lambda p: str(p).lower()):
            if self._skip_path(file_path):
                continue
            for line_number, line in enumerate(
                file_path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                if query.lower() in line.lower():
                    matches.append(f"{self._relative(file_path)}:{line_number}:{line}")
                    if len(matches) >= 100:
                        return "\n".join(matches + ["... truncated"])
        return "\n".join(matches) if matches else "no matches"

    def _write(self, args: dict[str, Any]) -> str:
        path = self._resolve(args.get("path") or "")
        text = str(args.get("text") or "")
        before = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._changes.append((path, before, text))
        return f"wrote={self._relative(path)}"

    def _append(self, args: dict[str, Any]) -> str:
        path = self._resolve(args.get("path") or "")
        text = str(args.get("text") or "")
        before = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
        after = path.read_text(encoding="utf-8", errors="replace")
        self._changes.append((path, before, after))
        return f"appended={self._relative(path)}"

    def _shell(self, args: dict[str, Any]) -> str:
        command = str(args.get("command") or "").strip()
        if not command:
            raise ValueError("missing command")
        if _is_destructive_shell_command(command):
            raise ValueError("blocked destructive command")
        completed = subprocess.run(
            command,
            cwd=self.cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            output = f"exit={completed.returncode}\n{output}"
        return output.strip()

    def _storage(self, args: dict[str, Any]) -> str:
        path = self._resolve(args.get("path") or self.cwd.anchor or ".", allow_outside=True)
        usage = shutil.disk_usage(path)
        return (
            f"path={path}\n"
            f"total={_human_bytes(usage.total)}\n"
            f"used={_human_bytes(usage.used)}\n"
            f"free={_human_bytes(usage.free)}"
        )

    def _web_search_tool(self, args: dict[str, Any]) -> str:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("missing query")
        return self.web_searcher(query)

    def _web_fetch_tool(self, args: dict[str, Any]) -> str:
        url = str(args.get("url") or "").strip()
        if not url:
            raise ValueError("missing url")
        return self.web_fetcher(url)

    def _diff(self, _args: dict[str, Any]) -> str:
        if not self._changes:
            return "no tracked tool changes"
        parts = []
        for path, before, after in self._changes:
            before_lines = [] if before is None else before.splitlines()
            after_lines = after.splitlines()
            parts.extend(
                unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=str(self._relative(path)) + ".before",
                    tofile=str(self._relative(path)) + ".after",
                    lineterm="",
                )
            )
        return "\n".join(parts)

    def _undo(self, _args: dict[str, Any]) -> str:
        if not self._changes:
            return "nothing to undo"
        path, before, _after = self._changes.pop()
        if before is None:
            path.unlink(missing_ok=True)
            return f"removed={self._relative(path)}"
        path.write_text(before, encoding="utf-8")
        return f"restored={self._relative(path)}"

    def _web_search(self, query: str) -> str:
        url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        html = self._http_get(url)
        matches = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.DOTALL,
        )
        lines = []
        for raw_url, raw_title in matches[:5]:
            title = _strip_html(raw_title)
            result_url = urllib.parse.unquote(raw_url)
            lines.append(f"{title}\n{result_url}")
        return "\n\n".join(lines) if lines else "no results"

    def _web_fetch(self, url: str) -> str:
        return _strip_html(self._http_get(url))

    def _http_get(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "openvino-chat/0.1"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    def _resolve(self, path: Any, allow_outside: bool = False) -> Path:
        candidate = Path(str(path))
        if not candidate.is_absolute():
            candidate = self.cwd / candidate
        resolved = candidate.resolve()
        if not allow_outside and not _is_relative_to(resolved, self.workspace_root):
            raise ValueError(f"outside workspace: {resolved}")
        return resolved

    def _cap(self, text: str) -> str:
        return text[: self.max_output_chars]

    def _needs_permission(self, name: str) -> bool:
        return name in {"shell", "write", "append"}

    def _approved(self, request: ToolRequest) -> bool:
        if self.permission_mode == "allow":
            return True
        if self.approval_callback is None:
            return False
        return self.approval_callback(request)

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace_root))
        except ValueError:
            return str(path)

    def _skip_path(self, path: Path) -> bool:
        parts = set(path.parts)
        return bool(parts & {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"})


def parse_slash_tool(text: str) -> ToolRequest | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    command, _, rest = stripped[1:].partition(" ")
    rest = rest.strip()
    if command == "pwd":
        return ToolRequest("pwd", {})
    if command == "ls":
        return ToolRequest("ls", {"path": rest or "."})
    if command == "read":
        return ToolRequest("read", {"path": rest})
    if command == "scan":
        return ToolRequest("scan", {"path": rest or "."})
    if command == "grep":
        query, _, path = rest.partition(" -- ")
        return ToolRequest("grep", {"query": query.strip(), "path": path.strip() or "."})
    if command == "write":
        path, _, text = rest.partition(" ")
        return ToolRequest("write", {"path": path, "text": text})
    if command == "append":
        path, _, text = rest.partition(" ")
        return ToolRequest("append", {"path": path, "text": text})
    if command == "shell":
        return ToolRequest("shell", {"command": rest})
    if command == "storage":
        return ToolRequest("storage", {"path": rest or "."})
    if command in {"web", "search"}:
        return ToolRequest("web_search", {"query": rest})
    if command in {"fetch", "web_fetch"}:
        return ToolRequest("web_fetch", {"url": rest})
    if command == "diff":
        return ToolRequest("diff", {})
    if command == "undo" and rest in {"", "tool"}:
        return ToolRequest("undo", {})
    return None


def parse_tool_requests(text: str) -> list[ToolRequest]:
    requests: list[ToolRequest] = []
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    candidates.extend(_json_objects_in_text(text))
    candidates = list(dict.fromkeys(candidates))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        requests.extend(_requests_from_payload(payload))
    requests.extend(_native_tool_requests(text))
    requests.extend(_gemma_tool_requests(text))
    unique: list[ToolRequest] = []
    seen: set[tuple[str, str]] = set()
    for request in requests:
        key = (request.name, json.dumps(request.args, sort_keys=True, default=str))
        if key not in seen:
            seen.add(key)
            unique.append(request)
    return unique


def format_tool_result(result: ToolResult) -> str:
    status = "ok" if result.ok else "error"
    return f"tool: {result.name}\nstatus: {status}\noutput:\n{result.output}"


def _requests_from_payload(payload: Any) -> list[ToolRequest]:
    if isinstance(payload, list):
        return [request for item in payload for request in _requests_from_payload(item)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("tool_calls"), list):
        return _requests_from_payload(payload["tool_calls"])
    function = payload.get("function")
    if isinstance(function, dict):
        payload = function
    name = payload.get("tool") or payload.get("name")
    args = payload.get("args", payload.get("arguments", {})) or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if isinstance(name, str) and isinstance(args, dict):
        return [ToolRequest(name.strip(), args)]
    return []


def _native_tool_requests(text: str) -> list[ToolRequest]:
    requests: list[ToolRequest] = []
    for call in re.findall(r"<tool_call\b[^>]*>(.*?)</tool_call>", text, flags=re.DOTALL | re.IGNORECASE):
        stripped = call.strip()
        if stripped.startswith("{"):
            try:
                requests.extend(_requests_from_payload(json.loads(stripped)))
            except json.JSONDecodeError:
                pass
        for match in re.finditer(
            r"<function\s*=\s*([^>\s]+)\s*>(.*?)</function>",
            call,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            args: dict[str, Any] = {}
            for parameter in re.finditer(
                r"<parameter\s*=\s*([^>\s]+)\s*>(.*?)</parameter>",
                match.group(2),
                flags=re.DOTALL | re.IGNORECASE,
            ):
                args[parameter.group(1).strip()] = _decode_tool_argument(parameter.group(2))
            requests.append(ToolRequest(match.group(1).strip(), args))
    return requests


def _gemma_tool_requests(text: str) -> list[ToolRequest]:
    requests: list[ToolRequest] = []
    for match in re.finditer(r"\bcall:([A-Za-z_][\w.-]*)\s*", text, flags=re.IGNORECASE):
        brace_index = match.end()
        if brace_index >= len(text) or text[brace_index] != "{":
            continue
        payload = _braced_text_at(text, brace_index)
        if payload is None:
            continue
        args = _parse_gemma_arguments(payload)
        if args is not None:
            requests.append(ToolRequest(match.group(1), args))
    return requests


def _braced_text_at(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _parse_gemma_arguments(payload: str) -> dict[str, Any] | None:
    text = payload.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    body = text[1:-1].strip()
    if not body:
        return {}

    arguments: dict[str, Any] = {}
    for field in _split_gemma_fields(body):
        separator = _gemma_top_level_colon(field)
        if separator < 0:
            return None
        key = field[:separator].strip().strip("'\"")
        if not re.fullmatch(r"[A-Za-z_][\w.-]*", key):
            return None
        arguments[key] = _parse_gemma_value(field[separator + 1 :].strip())
    return arguments


def _split_gemma_fields(text: str) -> list[str]:
    fields: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    gemma_quote = False
    index = 0
    while index < len(text):
        if text.startswith('<|"|>', index):
            gemma_quote = not gemma_quote
            index += 5
            continue
        char = text[index]
        if gemma_quote:
            index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            fields.append(text[start:index].strip())
            start = index + 1
        index += 1
    fields.append(text[start:].strip())
    return [field for field in fields if field]


def _gemma_top_level_colon(text: str) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    gemma_quote = False
    index = 0
    while index < len(text):
        if text.startswith('<|"|>', index):
            gemma_quote = not gemma_quote
            index += 5
            continue
        char = text[index]
        if gemma_quote:
            index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth = max(0, depth - 1)
        elif char == ":" and depth == 0:
            return index
        index += 1
    return -1


def _parse_gemma_value(text: str) -> Any:
    value = text.strip()
    marker = '<|"|>'
    if value.startswith(marker) and value.endswith(marker) and len(value) >= len(marker) * 2:
        return value[len(marker) : -len(marker)]
    if value.startswith("{") and value.endswith("}"):
        nested = _parse_gemma_arguments(value)
        return nested if nested is not None else value
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        return [] if not body else [_parse_gemma_value(item) for item in _split_gemma_fields(body)]
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"null", "none"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _decode_tool_argument(value: str) -> Any:
    clean = html.unescape(value.strip())
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return clean


def _json_objects_in_text(text: str) -> list[str]:
    objects: list[str] = []
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])
                start = None
    return objects


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<style.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = cleaned.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_destructive_shell_command(command: str) -> bool:
    lowered = command.lower()
    dangerous = [
        "remove-item",
        "rm -rf",
        "rmdir /s",
        "del /s",
        "format ",
        "diskpart",
        "git reset --hard",
        "git clean -fd",
    ]
    return any(pattern in lowered for pattern in dangerous)
