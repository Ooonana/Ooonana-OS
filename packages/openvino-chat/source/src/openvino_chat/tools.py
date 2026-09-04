from __future__ import annotations

import json
import html
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import unified_diff
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable


ToolChange = tuple[Path, str | None, str]
ToolCheckpoint = tuple[ToolChange, ...]
MAX_HTTP_BYTES = 2 * 1024 * 1024


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
            "description": (
                "Run one PowerShell command in the workspace. Requires permission."
                if os.name == "nt"
                else "Run one POSIX shell command in the workspace. Requires permission."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": (
                            "PowerShell command."
                            if os.name == "nt"
                            else "POSIX shell command."
                        ),
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "storage",
            "description": "Report total, used, and free disk storage for a drive or path.",
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
            "name": "startup_apps",
            "description": "List configured operating-system startup or login applications without running a shell command.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
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
            "name": "luci_history",
            "description": (
                "Search the user's private Luci computer-activity history. Use only for "
                "questions about what the user previously did, saw, heard, opened, or worked on."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "One of: status, search, transcript, usage, filter.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Words or description for search/transcript.",
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Relative range such as 30m, 24h, 7d, or 2w. Defaults to 24h.",
                    },
                    "app": {
                        "type": "string",
                        "description": "Exact application name for filter.",
                    },
                    "semantic": {
                        "type": "boolean",
                        "description": "Use semantic search instead of exact text search.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results from 1 to 50. Defaults to 10.",
                    },
                },
                "required": ["action"],
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

_TOOL_DEFINITIONS_BY_NAME = {
    str(item["function"]["name"]): item
    for item in TOOL_DEFINITIONS
}

_LOCAL_READ_TOOLS = {"pwd", "ls", "read", "scan", "grep"}
_LOCAL_WRITE_TOOLS = _LOCAL_READ_TOOLS | {"write", "append", "diff", "undo"}
_WEB_TOOLS = {"web_search", "web_fetch"}
_HISTORY_TOOLS = {"luci_history"}


def select_tool_definitions(
    message: str,
    knowledge_mode: str = "auto",
) -> list[dict[str, Any]]:
    """Return small, intent-matched tool schema set for current model turn."""
    text = str(message or "").lower()
    mode = str(knowledge_mode or "auto").strip().lower()
    if mode not in {"offline", "auto", "web"}:
        mode = "auto"
    selected: set[str] = set()
    if re.search(r"\b(all|available|list|show|use)\s+tools?\b", text):
        selected.update(_TOOL_DEFINITIONS_BY_NAME)
    explicit_web = re.search(
        r"\b(web|online|internet|website|url|browse|google)\b|"
        r"\b(search|look up|research)\s+(the\s+)?(web|online|internet)\b|https?://",
        text,
    )
    live_fact = re.search(
        r"\b(latest|newest|news|today|tonight|currently|right now|weather|forecast|"
        r"price|stock|exchange rate|schedule|score|election|release date|recent release)\b|"
        r"\bcurrent\s+(president|prime minister|ceo|version|law|regulation|price|score)\b",
        text,
    )
    if mode == "web" or (mode == "auto" and (explicit_web or live_fact)):
        selected.update(_WEB_TOOLS)
    if re.search(r"\b(storage|disk|drive|free space|space left|capacity)\b", text):
        selected.add("storage")
    if re.search(r"\b(startup|start-up|autorun|login items?|boot apps?)\b", text):
        selected.add("startup_apps")
    if re.search(
        r"\b(luci|personal history|computer history|screen history|activity history)\b|"
        r"\b(what|which|where|when)\b.{0,32}\b(i|me|my)\b.{0,40}"
        r"\b(did|saw|see|heard|hear|opened|used|worked|read|watched)\b|"
        r"\bwhat did i (do|work on|open|see|hear|use|read|watch)\b|"
        r"(어제|전에|지난번|과거에).{0,24}(뭘|무엇을|봤|했|들었|열었|작업)",
        text,
    ):
        selected.update(_HISTORY_TOOLS)
    if re.search(r"\b(where|where am i|working directory|current directory|cwd|pwd)\b", text):
        selected.add("pwd")
    if re.search(
        r"\b(file|folder|directory|workspace|repo|repository|project|source|code|script|"
        r"read|open|list|scan|find|grep|search files?|inspect)\b",
        text,
    ):
        selected.update(_LOCAL_READ_TOOLS)
    if re.search(
        r"\b(create|make|write|append|edit|change|modify|fix|implement|refactor|delete|remove|"
        r"rename|move|copy|patch|undo|revert)\b",
        text,
    ):
        selected.update(_LOCAL_WRITE_TOOLS)
    if re.search(
        r"\b(shell|powershell|terminal|command|run|execute|install|uninstall|build|compile|test|"
        r"git|process|service|environment|operating system|system info|cpu|gpu|ram|memory|date|time)\b",
        text,
    ):
        selected.update({"pwd", "shell"})
    if re.search(r"\b(diff|changes|changed)\b", text):
        selected.add("diff")
    if re.search(r"\b(undo|revert)\b", text):
        selected.add("undo")
    if re.search(r"\b(where am i|working directory|current directory|cwd|pwd)\b", text) and not re.search(
        r"\b(file|folder|list|scan|find|grep|search|inspect|read|open)\b",
        text,
    ):
        selected.difference_update(_LOCAL_READ_TOOLS - {"pwd"})
    if mode == "offline":
        selected.difference_update(_WEB_TOOLS)
    return [
        definition
        for definition in TOOL_DEFINITIONS
        if definition["function"]["name"] in selected
    ]


def validate_tool_request(
    request: ToolRequest,
    definitions: list[dict[str, Any]] | None = None,
) -> tuple[ToolRequest | None, str | None]:
    """Validate model arguments before any tool or permission callback runs."""
    available = {
        str(item.get("function", {}).get("name")): item
        for item in (definitions or TOOL_DEFINITIONS)
        if isinstance(item, dict) and isinstance(item.get("function"), dict)
    }
    definition = available.get(request.name)
    if definition is None:
        return None, f"unknown tool: {request.name}"
    if not isinstance(request.args, dict):
        return None, "args must be an object"
    parameters = definition["function"].get("parameters") or {}
    properties = parameters.get("properties") or {}
    missing = [name for name in parameters.get("required", []) if name not in request.args]
    if missing:
        return None, "missing required argument(s): " + ", ".join(missing)
    if parameters.get("additionalProperties") is False:
        unknown = [name for name in request.args if name not in properties]
        if unknown:
            return None, "unknown argument(s): " + ", ".join(unknown)
    for name, value in request.args.items():
        expected = properties.get(name, {}).get("type")
        if expected == "string" and not isinstance(value, str):
            return None, f"argument {name} must be string"
        if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            return None, f"argument {name} must be integer"
        if expected == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            return None, f"argument {name} must be number"
        if expected == "boolean" and not isinstance(value, bool):
            return None, f"argument {name} must be boolean"
    return ToolRequest(request.name, dict(request.args)), None


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
        startup_provider: Callable[[], str] | None = None,
        history_provider: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self.cwd = (cwd or Path.cwd()).resolve()
        self.workspace_root = (workspace_root or self.cwd).resolve()
        self.permission_mode = permission_mode
        self.approval_callback = approval_callback
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        self.web_searcher = web_searcher or self._web_search
        self.web_fetcher = web_fetcher or self._web_fetch
        self.startup_provider = startup_provider or _startup_apps
        self.history_provider = history_provider or _luci_history
        self._changes: list[ToolChange] = []

    def checkpoint(self) -> ToolCheckpoint:
        return tuple(self._changes)

    def restore_checkpoint(self, checkpoint: ToolCheckpoint) -> None:
        target = list(checkpoint)
        common = 0
        for current_change, target_change in zip(self._changes, target):
            if current_change != target_change:
                break
            common += 1

        for path, before, _after in reversed(self._changes[common:]):
            self._restore_file(path, before)
        for path, _before, after in target[common:]:
            self._restore_file(path, after)
        self._changes[:] = target

    @staticmethod
    def _restore_file(path: Path, content: str | None) -> None:
        if content is None:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

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
            "startup_apps": self._startup_apps_tool,
            "web_search": self._web_search_tool,
            "web_fetch": self._web_fetch_tool,
            "luci_history": self._luci_history_tool,
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
            _shell_invocation(command),
            cwd=self.cwd,
            shell=False,
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

    def _startup_apps_tool(self, _args: dict[str, Any]) -> str:
        return self.startup_provider()

    def _web_search_tool(self, args: dict[str, Any]) -> str:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("missing query")
        return self.web_searcher(query)

    def _web_fetch_tool(self, args: dict[str, Any]) -> str:
        url = str(args.get("url") or "").strip()
        if not url:
            raise ValueError("missing url")
        _validate_http_url(url)
        return self.web_fetcher(url)

    def _luci_history_tool(self, args: dict[str, Any]) -> str:
        return self.history_provider(args)

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
        url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
        matches = _parse_search_results(self._http_get(url))
        lines = []
        for title, result_url, snippet in matches[:5]:
            lines.append(f"{title}\n{snippet}\n{result_url}" if snippet else f"{title}\n{result_url}")
        return "\n\n".join(lines) if lines else "no results"

    def _web_fetch(self, url: str) -> str:
        return _strip_html(self._http_get(url))

    def _http_get(self, url: str) -> str:
        _validate_http_url(url)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OpenVINO-Chat/0.1)"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            _validate_http_url(response.geturl())
            return response.read(MAX_HTTP_BYTES + 1)[:MAX_HTTP_BYTES].decode(
                "utf-8", errors="replace"
            )

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
        return name in {"shell", "write", "append", "undo"}

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


def _startup_apps() -> str:
    entries = _windows_startup_entries() if os.name == "nt" else _posix_startup_entries()
    if not entries:
        return "no startup apps found"
    rows = ["name | state | source | command"]
    seen: set[tuple[str, str]] = set()
    for name, state, source, command in sorted(entries, key=lambda item: item[0].lower()):
        key = (name.casefold(), command.casefold())
        if key in seen:
            continue
        seen.add(key)
        rows.append(" | ".join(_clean_startup_field(value) for value in (name, state, source, command)))
    return "\n".join(rows)


def _luci_history(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip().lower()
    if action not in {"status", "search", "transcript", "usage", "filter"}:
        raise ValueError("history action must be status, search, transcript, usage, or filter")

    command = [action]
    if action in {"search", "transcript"}:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError(f"{action} requires query")
        command.append(query)
    elif action == "filter":
        app = str(args.get("app") or "").strip()
        if not app:
            raise ValueError("filter requires app")
        command.extend(["--app", app])

    if action != "status":
        time_range = str(args.get("time_range") or "24h").strip().lower()
        if not re.fullmatch(r"(?:\d+[mhdw]|\d{10,}:\d{10,})", time_range):
            raise ValueError("time_range must resemble 30m, 24h, 7d, 2w, or fromMs:toMs")
        try:
            limit = int(args.get("limit", 10))
        except (TypeError, ValueError) as exc:
            raise ValueError("history limit must be integer") from exc
        if not 1 <= limit <= 50:
            raise ValueError("history limit must be between 1 and 50")
        if action == "search" and bool(args.get("semantic", False)):
            command.append("--semantic")
        command.extend(["--tr", time_range, "--limit", str(limit), "--json"])

    shim = _luci_shim()
    started_for_query = action != "status" and not _luci_is_running(shim)
    try:
        completed = _run_luci_process(shim, command)
    finally:
        if started_for_query:
            _stop_luci_process()
    output = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode:
        raise RuntimeError(output or f"Luci failed with exit code {completed.returncode}")
    return output or "no history results"


def _run_luci_process(shim: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    if os.name == "nt" and shim.suffix.lower() in {".cmd", ".bat"}:
        command_line = subprocess.list2cmdline([str(shim), *command])
        executable = os.environ.get("COMSPEC", "cmd.exe")
        process_args = [executable, "/d", "/s", "/c", command_line]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        process_args = [str(shim), *command]
        creation_flags = 0
    return subprocess.run(
        process_args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        creationflags=creation_flags,
        check=False,
    )


def _luci_is_running(shim: Path) -> bool:
    try:
        return _run_luci_process(shim, ["status"]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _stop_luci_process() -> None:
    if os.name != "nt":
        return
    for _attempt in range(3):
        subprocess.run(
            ["taskkill", "/IM", "Luci.exe", "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        time.sleep(0.4)


def _luci_shim() -> Path:
    for discovery in (
        Path.home() / ".luci" / "cli.json",
        Path.home() / ".luciMicrosoft" / "cli.json",
    ):
        try:
            data = json.loads(discovery.read_text(encoding="utf-8"))
            shim = Path(str(data.get("shim") or "")).expanduser()
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            continue
        if shim.is_file():
            return shim
    fallback = shutil.which("luci")
    if fallback:
        return Path(fallback)
    raise FileNotFoundError("Luci CLI not found. Install or start Luci, then retry.")


def _windows_startup_entries() -> list[tuple[str, str, str, str]]:
    try:
        import winreg
    except ImportError:
        return []

    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    approved_root = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
    locations = (
        (winreg.HKEY_CURRENT_USER, "HKCU Run", 0, "Run"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM Run", winreg.KEY_WOW64_64KEY, "Run"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM Run32", winreg.KEY_WOW64_32KEY, "Run32"),
    )
    entries: list[tuple[str, str, str, str]] = []
    for hive, source, view, approved_name in locations:
        try:
            key = winreg.OpenKey(hive, run_key, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with key:
            index = 0
            while True:
                try:
                    name, command, _kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                state = _windows_startup_state(
                    winreg,
                    hive,
                    approved_root + "\\" + approved_name,
                    name,
                    view,
                )
                entries.append((str(name), state, source, str(command)))

    startup_dirs = (
        (os.environ.get("APPDATA"), "User Startup"),
        (os.environ.get("PROGRAMDATA"), "All Users Startup"),
    )
    suffix = Path("Microsoft/Windows/Start Menu/Programs/Startup")
    for root, source in startup_dirs:
        if not root:
            continue
        folder = Path(root) / suffix
        if not folder.is_dir():
            continue
        for item in folder.iterdir():
            if item.is_file() and item.name.lower() != "desktop.ini":
                entries.append((item.stem, "configured", source, str(item)))
    return entries


def _windows_startup_state(winreg: Any, hive: Any, path: str, name: str, view: int) -> str:
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view) as key:
            raw, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return "configured"
    data = bytes(raw) if isinstance(raw, (bytes, bytearray)) else b""
    if not data:
        return "configured"
    return {2: "enabled", 3: "disabled"}.get(data[0], "configured")


def _posix_startup_entries() -> list[tuple[str, str, str, str]]:
    entries: list[tuple[str, str, str, str]] = []
    for folder in (Path.home() / ".config/autostart", Path("/etc/xdg/autostart")):
        if not folder.is_dir():
            continue
        for item in folder.glob("*.desktop"):
            values: dict[str, str] = {}
            for line in item.read_text(encoding="utf-8", errors="replace").splitlines():
                key, separator, value = line.partition("=")
                if separator and key in {"Name", "Exec", "Hidden"} and key not in values:
                    values[key] = value.strip()
            state = "disabled" if values.get("Hidden", "").lower() == "true" else "enabled"
            entries.append((values.get("Name", item.stem), state, str(folder), values.get("Exec", str(item))))
    return entries


def _clean_startup_field(value: object) -> str:
    return " ".join(str(value).replace("|", "/").split())


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
    if command in {"startup", "startup_apps"} and not rest:
        return ToolRequest("startup_apps", {})
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


def _shell_invocation(command: str) -> list[str]:
    if os.name == "nt":
        executable = shutil.which("pwsh") or shutil.which("powershell")
        if not executable:
            raise RuntimeError("PowerShell not found; install PowerShell 7 or Windows PowerShell")
        return [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command]
    executable = os.environ.get("SHELL") or shutil.which("bash") or shutil.which("sh")
    if not executable:
        raise RuntimeError("shell not found")
    return [executable, "-lc", command]


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<style.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class _DuckDuckGoLiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[list[str]] = []
        self._link_url: str | None = None
        self._link_text: list[str] = []
        self._snippet_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if tag.lower() == "a" and "result-link" in classes:
            self._link_url = values.get("href", "")
            self._link_text = []
        elif tag.lower() == "td" and "result-snippet" in classes:
            self._snippet_text = []

    def handle_data(self, data: str) -> None:
        if self._link_url is not None:
            self._link_text.append(data)
        if self._snippet_text is not None:
            self._snippet_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._link_url is not None:
            title = " ".join("".join(self._link_text).split())
            result_url = _duckduckgo_result_url(self._link_url)
            if title and result_url:
                self.results.append([title, result_url, ""])
            self._link_url = None
            self._link_text = []
        elif tag.lower() == "td" and self._snippet_text is not None:
            snippet = " ".join("".join(self._snippet_text).split())
            if self.results:
                self.results[-1][2] = snippet
            self._snippet_text = None


def _duckduckgo_result_url(value: str) -> str:
    url = html.unescape(str(value).strip())
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    redirect = urllib.parse.parse_qs(parsed.query).get("uddg")
    if redirect:
        url = redirect[0]
    try:
        _validate_http_url(url)
    except ValueError:
        return ""
    return url


def _parse_search_results(text: str) -> list[tuple[str, str, str]]:
    parser = _DuckDuckGoLiteParser()
    parser.feed(str(text))
    parser.close()
    return [tuple(result) for result in parser.results]


def _validate_http_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must use http or https")


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
