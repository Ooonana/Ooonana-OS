#!/usr/bin/env python3
"""Ooonana AI terminal client backed by NVIDIA NIM or Google Gemini."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import platform
import re
import shlex
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4
from pathlib import Path
from typing import Any

try:
    import readline  # noqa: F401 - enables line editing in interactive mode
except ImportError:
    pass


VERSION = "0.1.0"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_PROVIDER = "nim"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
CONFIG_PATH = Path(os.environ.get("OOONANA_AI_CONFIG", "~/.config/ooonana/ai.env")).expanduser()
STATE_PATH = Path(os.environ.get("OOONANA_AI_STATE_DIR", "~/.local/state/ooonana/ai")).expanduser()
DEFAULT_MAX_CONTEXT_BYTES = 12000

IDENTITY_PROMPT = """\
You are Ooonana, the built-in AI assistant for Ooonana OS.
Identity:
- Your name is Ooonana.
- If asked who you are, answer as Ooonana.
- You are not Gemini, Claude, ChatGPT, Google, or NVIDIA NIM.
- NVIDIA NIM and Google Gemini are only model/API providers behind the terminal app.

Environment:
- You live in a Linux terminal and are designed for Ooonana OS, WSL, and shell-first workflows.
- Treat the provided Linux environment snapshot as authoritative current context.
- Notice hostname, OS release, current directory, available commands, workspace files, and package state.
- When the snapshot is incomplete or stale, say what command the user should run to confirm.

Behavior:
- Be practical, calm, and direct.
- Prefer concrete commands, file paths, config keys, and exact next steps.
- Keep answers concise by default, but expand when debugging, installing, or explaining architecture.
- For coding tasks, give runnable shell/Python snippets and mention where files should live.
- Never pretend you executed a command or saw a file if it was not in the provided context.
- Do not expose API keys or secrets. If config is shown, redact secret values.
- When using NVIDIA NIM, explain provider settings in OpenAI-compatible terms: base URL, model, bearer token, chat completions, streaming.
- When using Gemini, explain provider settings as Gemini API terms: API key, model, generateContent, streamGenerateContent, system instruction, contents.

Ooonana product direction:
- Help the user build Ooonana as its own AI CLI experience, not a thin rebrand.
- Preserve Ooonana naming and terminal style in examples.
- Keep the user interface CLI-first: commands, slash commands, compact tables, status lines, JSON when requested, and copyable shell snippets.
- Do not design for voice input, voice recognition, GUI dashboards, or web-first flows unless the user explicitly asks.
- Assume the user wants forward movement and practical implementation.

Agent/memory behavior:
- You may receive focused context from local Ooonana agents such as system, activity, and summarizer.
- Treat those agents as local context collectors, not separate people.
- Use history and activity context to understand what the user was doing lately, but do not reveal sensitive values.
- If asked to rewind, continue from the rewound conversation state and ignore later removed turns.

Jarvis-class direction:
- Aim for a local-first personal AI with a CLI-first terminal interface: provider router, memory, tool execution, permission gates, and system awareness.
- Do not claim to be AGI. Be honest about capabilities and ask before risky system actions.
- Never rename yourself Jarvis; Ooonana is the assistant identity.
"""

AGENTS = {
    "system": "Collects OS, WSL, command, package, and workspace context.",
    "activity": "Collects recent shell and Ooonana CLI activity with secrets redacted.",
    "summarizer": "Turns system and activity context into a compact working summary.",
}

POPULAR_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2-instruct",
    "meta/llama-3.3-70b-instruct",
    "openai/gpt-oss-120b",
]

GEMINI_POPULAR_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

PROVIDER_LABELS = {
    "nim": "NVIDIA NIM",
    "gemini": "Google Gemini",
}

DEFAULT_MODEL_ALIASES = {
    "nim": {
        "fast": "qwen/qwen3-next-80b-a3b-instruct",
        "code": "qwen/qwen3-coder-480b-a35b-instruct",
        "deep": "nvidia/nemotron-3-super-120b-a12b",
    },
    "gemini": {
        "fast": "gemini-2.5-flash-lite",
        "code": "gemini-2.5-flash",
        "deep": "gemini-2.5-pro",
    },
}


class OoonanaError(Exception):
    pass


def color(text: str, code: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def heading(text: str) -> str:
    return color(text, "1;36")


def warn(text: str) -> str:
    return color(text, "33")


def faint(text: str) -> str:
    return color(text, "2")


def print_banner(model: str, provider: str = DEFAULT_PROVIDER, mode: str = "chat") -> None:
    width = 64
    print(heading("=" * width))
    print(heading("Ooonana AI").ljust(width))
    print(f"mode: {mode} | provider: {provider_label(provider)} | model: {model}")
    print(faint("identity: Ooonana | context: Linux + workspace"))
    print(heading("=" * width))


def print_status(model: str, provider: str, config: dict[str, str], state: Path | None = None) -> None:
    print("Ooonana AI status")
    print("identity: Ooonana")
    print(f"provider: {provider_label(provider)}")
    print(f"model: {model}")
    print(f"base_url: {provider_base_url(config, provider)}")
    print(f"config_key: {'present' if provider_api_key(config, provider) else 'missing'}")
    print(f"cwd: {os.getcwd()}")
    print(f"state_dir: {state or STATE_PATH}")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        try:
            value = shlex.split(raw_value, comments=False, posix=True)[0] if raw_value else ""
        except ValueError:
            value = raw_value.strip("\"'")
        values[key] = value
    return values


def load_config(path: Path) -> dict[str, str]:
    values = parse_env_file(path)
    fixed_keys = {
        "NVIDIA_API_KEY",
        "NVIDIA_NIM_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OOONANA_AI_PROVIDER",
        "OOONANA_NIM_BASE_URL",
        "OOONANA_NIM_MODEL",
        "OOONANA_GEMINI_BASE_URL",
        "OOONANA_GEMINI_MODEL",
        "OOONANA_MODEL_FAST",
        "OOONANA_MODEL_CODE",
        "OOONANA_MODEL_DEEP",
        "OOONANA_GEMINI_MODEL_FAST",
        "OOONANA_GEMINI_MODEL_CODE",
        "OOONANA_GEMINI_MODEL_DEEP",
        "OOONANA_AI_MAX_TOKENS",
        "OOONANA_AI_TEMPERATURE",
        "OOONANA_AI_STREAM",
    }
    for key, value in os.environ.items():
        if value and (key in fixed_keys or key.startswith("OOONANA_MODEL_") or key.startswith("OOONANA_GEMINI_MODEL_")):
            values[key] = value
    return values


def config_value(config: dict[str, str], key: str, default: str) -> str:
    value = config.get(key, "").strip()
    return value if value else default


def api_key(config: dict[str, str]) -> str:
    return config.get("NVIDIA_NIM_API_KEY") or config.get("NVIDIA_API_KEY") or ""


def gemini_api_key(config: dict[str, str]) -> str:
    return config.get("GOOGLE_API_KEY") or config.get("GEMINI_API_KEY") or ""


def provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider)


def selected_provider(config: dict[str, str], override: str = "") -> str:
    provider = (override or config.get("OOONANA_AI_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if provider == "auto":
        if gemini_api_key(config) and not api_key(config):
            return "gemini"
        return DEFAULT_PROVIDER
    if provider not in PROVIDER_LABELS:
        raise OoonanaError("provider must be nim, gemini, or auto")
    return provider


def provider_api_key(config: dict[str, str], provider: str) -> str:
    if provider == "gemini":
        return gemini_api_key(config)
    return api_key(config)


def provider_base_url(config: dict[str, str], provider: str) -> str:
    if provider == "gemini":
        return config_value(config, "OOONANA_GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL)
    return config_value(config, "OOONANA_NIM_BASE_URL", DEFAULT_BASE_URL)


def missing_key_message(provider: str) -> str:
    if provider == "gemini":
        return "AI config missing GEMINI_API_KEY or GOOGLE_API_KEY"
    return "AI config missing NVIDIA_API_KEY"


def setup_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        old_umask = os.umask(0o077)
        try:
            path.write_text(
                textwrap.dedent(
                    f"""\
                    # Ooonana AI uses NVIDIA NIM or Google Gemini.
                    # Get a key from https://build.nvidia.com/settings/api-keys
                    # Get a Gemini key from https://aistudio.google.com/app/apikey
                    OOONANA_AI_PROVIDER=nim
                    NVIDIA_API_KEY=
                    GEMINI_API_KEY=
                    OOONANA_NIM_BASE_URL={DEFAULT_BASE_URL}
                    OOONANA_NIM_MODEL={DEFAULT_MODEL}
                    OOONANA_GEMINI_BASE_URL={DEFAULT_GEMINI_BASE_URL}
                    OOONANA_GEMINI_MODEL={DEFAULT_GEMINI_MODEL}
                    OOONANA_MODEL_FAST=qwen/qwen3-next-80b-a3b-instruct
                    OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
                    OOONANA_MODEL_DEEP=nvidia/nemotron-3-super-120b-a12b
                    OOONANA_GEMINI_MODEL_FAST=gemini-2.5-flash-lite
                    OOONANA_GEMINI_MODEL_CODE=gemini-2.5-flash
                    OOONANA_GEMINI_MODEL_DEEP=gemini-2.5-pro
                    OOONANA_AI_MAX_TOKENS=1024
                    OOONANA_AI_TEMPERATURE=0.2
                    OOONANA_AI_STREAM=1
                    """
                ),
                encoding="utf-8",
            )
        finally:
            os.umask(old_umask)
    path.chmod(0o600)
    print(f"AI config: {path}")


def write_env_updates(path: Path, updates: dict[str, str]) -> None:
    if not path.exists():
        setup_config(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    changed: list[str] = []
    for line in lines:
        stripped = line.strip()
        probe = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        if stripped.startswith("#") or "=" not in probe:
            changed.append(line)
            continue
        key = probe.split("=", 1)[0].strip()
        if key in remaining:
            changed.append(f"{key}={shlex.quote(remaining.pop(key))}")
        else:
            changed.append(line)
    if remaining:
        if changed and changed[-1].strip():
            changed.append("")
        for key, value in remaining.items():
            changed.append(f"{key}={shlex.quote(value)}")
    path.write_text("\n".join(changed) + "\n", encoding="utf-8")
    path.chmod(0o600)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def state_dir(args: argparse.Namespace) -> Path:
    return Path(args.state_dir).expanduser()


def history_path(args: argparse.Namespace) -> Path:
    return state_dir(args) / "history.jsonl"


def sessions_dir(args: argparse.Namespace) -> Path:
    return state_dir(args) / "sessions"


def session_path(args: argparse.Namespace, session_id: str) -> Path:
    return sessions_dir(args) / f"{session_id}.jsonl"


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def redact_secret_text(text: str) -> str:
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=([^ \t]+)", r"\1=REDACTED", text)
    text = re.sub(r"(?i)(bearer)\s+[-._~+/A-Za-z0-9=]+", r"\1 REDACTED", text)
    text = re.sub(r"nvapi-[A-Za-z0-9_.-]+", "nvapi-REDACTED", text)
    return text


def read_tail(path: Path, limit: int = 30) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [redact_secret_text(line.strip()) for line in lines if line.strip()][-limit:]


def shell_history_snapshot(limit: int = 30) -> str:
    candidates = [
        Path(os.environ.get("HISTFILE", "")).expanduser() if os.environ.get("HISTFILE") else None,
        Path("~/.bash_history").expanduser(),
        Path("~/.zsh_history").expanduser(),
        Path("~/.local/share/powershell/PSReadLine/ConsoleHost_history.txt").expanduser(),
    ]
    seen: set[Path] = set()
    lines: list[str] = []
    for candidate in candidates:
        if candidate is None or candidate in seen:
            continue
        seen.add(candidate)
        tail = read_tail(candidate, limit)
        if tail:
            lines.append(f"[{candidate}]")
            lines.extend(tail)
    return "\n".join(lines[-limit * 2 :]) if lines else "no shell history found"


def ooonana_history_snapshot(args: argparse.Namespace, limit: int = 12) -> str:
    records = read_jsonl(history_path(args))[-limit:]
    if not records:
        return "no Ooonana AI history yet"
    lines: list[str] = []
    for record in records:
        user = str(record.get("user", "")).replace("\n", " ")[:160]
        assistant = str(record.get("assistant", "")).replace("\n", " ")[:160]
        lines.append(f"{record.get('time', '')} {record.get('mode', '')} user: {user}")
        if assistant:
            lines.append(f"{record.get('time', '')} {record.get('mode', '')} ooonana: {assistant}")
    return "\n".join(lines)


def record_exchange(
    args: argparse.Namespace,
    *,
    session_id: str,
    mode: str,
    model: str,
    user: str,
    assistant: str,
) -> dict[str, Any]:
    record = {
        "time": now_iso(),
        "session": session_id,
        "mode": mode,
        "model": model,
        "cwd": os.getcwd(),
        "user": user,
        "assistant": assistant,
    }
    append_jsonl(history_path(args), record)
    append_jsonl(session_path(args, session_id), record)
    return record


def records_to_messages(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for record in records:
        user = str(record.get("user", "")).strip()
        assistant = str(record.get("assistant", "")).strip()
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})
    return messages


def run_capture(command: list[str], timeout: float = 1.5) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def first_existing(paths: list[str]) -> str:
    for path in paths:
        if Path(path).exists():
            return path
    return ""


def read_small(path: str, limit: int = 4000) -> str:
    try:
        data = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return data[:limit].strip()


def command_status(names: list[str]) -> str:
    lines = []
    for name in names:
        found = run_capture(["sh", "-lc", f"command -v {shlex.quote(name)} || true"])
        lines.append(f"{name}: {found or 'missing'}")
    return "\n".join(lines)


def workspace_snapshot(root: str, max_files: int = 80) -> str:
    root_path = Path(root)
    lines = [f"cwd: {root_path}"]

    git_status = run_capture(["git", "status", "-sb"], timeout=2.0)
    if git_status.startswith("fatal:"):
        git_status = "unavailable from this WSL worktree"
    if git_status:
        lines.append("[git]")
        lines.append(git_status[:3000])

    names: list[str] = []
    skip_dirs = {".git", "node_modules", ".venv", "__pycache__", "build", "dist"}
    try:
        for current, dirs, files in os.walk(root_path):
            dirs[:] = [name for name in sorted(dirs) if name not in skip_dirs and not name.startswith(".cache")]
            rel_dir = Path(current).relative_to(root_path)
            depth = 0 if str(rel_dir) == "." else len(rel_dir.parts)
            if depth > 3:
                dirs[:] = []
                continue
            for file_name in sorted(files):
                if file_name.endswith((".pyc", ".iso", ".ext4", ".img")):
                    continue
                rel_file = (rel_dir / file_name) if str(rel_dir) != "." else Path(file_name)
                names.append(str(rel_file))
                if len(names) >= max_files:
                    raise StopIteration
    except StopIteration:
        names.append("[truncated]")
    except OSError as exc:
        lines.append(f"files unavailable: {exc}")

    if names:
        lines.append("[files]")
        lines.extend(names)
    return "\n".join(lines)


def environment_snapshot(max_bytes: int | None = None) -> str:
    os_release = read_small(first_existing(["/etc/os-release", "/usr/lib/os-release"]))
    if os_release:
        os_release = "\n".join(
            line for line in os_release.splitlines() if line.startswith(("NAME=", "ID=", "PRETTY_NAME=", "VERSION_ID="))
        )

    sections = [
        ("identity", "assistant_name: Ooonana\nos_name: Ooonana OS"),
        ("host", f"hostname: {socket.gethostname()}\nplatform: {platform.platform()}\nuname: {run_capture(['uname', '-a'])}"),
        ("os-release", os_release or "missing"),
        ("process", f"user: {run_capture(['id'])}\ncwd: {os.getcwd()}\nshell: {os.environ.get('SHELL', 'unknown')}\nterm: {os.environ.get('TERM', 'unknown')}"),
        ("storage", run_capture(["df", "-h", "/"])),
        ("commands", command_status(["bash", "sh", "python3", "git", "curl", "apt-get", "systemctl", "qemu-system-x86_64", "wsl.exe"])),
        ("workspace", workspace_snapshot(os.getcwd())),
        ("path", os.environ.get("PATH", "")),
    ]

    rendered = "\n\n".join(f"[{title}]\n{body}" for title, body in sections if body)
    if max_bytes is None:
        try:
            max_bytes = int(os.environ.get("OOONANA_ENV_CONTEXT_BYTES", str(DEFAULT_MAX_CONTEXT_BYTES)))
        except ValueError:
            max_bytes = DEFAULT_MAX_CONTEXT_BYTES
    encoded = rendered.encode("utf-8")
    if len(encoded) <= max_bytes:
        return rendered
    return encoded[:max_bytes].decode("utf-8", errors="ignore") + "\n[truncated]"


def agent_context(agent: str, args: argparse.Namespace | None = None, max_bytes: int = 12000) -> str:
    if agent == "system":
        return environment_snapshot(max_bytes=max_bytes)
    if agent == "activity":
        activity = "[recent shell history]\n" + shell_history_snapshot()
        if args is not None:
            activity += "\n\n[recent Ooonana AI history]\n" + ooonana_history_snapshot(args)
        return activity
    if agent == "summarizer":
        parts = [
            "[summary task]",
            "Summarize what the user has been doing recently and identify likely next actions.",
            "Use only the context below. Redact secrets. Keep it compact and operational.",
            "",
            "[system]",
            environment_snapshot(max_bytes=max_bytes // 2),
        ]
        if args is not None:
            parts.extend(["", "[activity]", agent_context("activity", args, max_bytes=max_bytes // 2)])
        return "\n".join(parts)
    raise OoonanaError(f"unknown agent: {agent}")


def build_messages(
    prompt: str,
    history: list[dict[str, str]] | None = None,
    include_env: bool = True,
    agent: str = "",
    args: argparse.Namespace | None = None,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": IDENTITY_PROMPT}]
    if include_env:
        messages.append({"role": "system", "content": "Current Linux environment snapshot:\n" + environment_snapshot()})
    if agent:
        messages.append({"role": "system", "content": f"Ooonana local agent context ({agent}):\n" + agent_context(agent, args)})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


def completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def active_provider(args: argparse.Namespace, config: dict[str, str]) -> str:
    return selected_provider(config, getattr(args, "provider", ""))


def max_tokens(config: dict[str, str]) -> int:
    return int(config_value(config, "OOONANA_AI_MAX_TOKENS", "1024"))


def temperature(config: dict[str, str]) -> float:
    return float(config_value(config, "OOONANA_AI_TEMPERATURE", "0.2"))


def request_payload(args: argparse.Namespace, config: dict[str, str], messages: list[dict[str, str]], stream: bool) -> dict[str, Any]:
    provider = active_provider(args, config)
    if provider == "gemini":
        return gemini_request_payload(args, config, messages, stream=stream, include_meta=True)
    return nim_request_payload(args, config, messages, stream=stream, include_meta=True)


def nim_request_payload(
    args: argparse.Namespace,
    config: dict[str, str],
    messages: list[dict[str, str]],
    stream: bool,
    include_meta: bool = False,
) -> dict[str, Any]:
    model = resolve_model(args.model, config, "nim")
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens(config),
        "temperature": temperature(config),
        "stream": stream,
    }
    if include_meta:
        payload = {"provider": "nim", **payload}
    return payload


def gemini_role(role: str) -> str:
    return "model" if role == "assistant" else "user"


def gemini_request_payload(
    args: argparse.Namespace,
    config: dict[str, str],
    messages: list[dict[str, str]],
    stream: bool,
    include_meta: bool = False,
) -> dict[str, Any]:
    model = resolve_model(args.model, config, "gemini")
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(content)
            continue
        contents.append({"role": gemini_role(role), "parts": [{"text": content}]})
    payload: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": "\n\n".join(system_parts)}]},
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens(config),
            "temperature": temperature(config),
        },
    }
    if include_meta:
        payload = {"provider": "gemini", "model": model, **payload}
    return payload


def model_default_env_key(provider: str) -> str:
    if provider == "gemini":
        return "OOONANA_GEMINI_MODEL"
    return "OOONANA_NIM_MODEL"


def model_default(config: dict[str, str], provider: str) -> str:
    if provider == "gemini":
        return config_value(config, "OOONANA_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    return config_value(config, "OOONANA_NIM_MODEL", DEFAULT_MODEL)


def model_alias_env_key(alias: str, provider: str = "nim") -> str:
    normalized = normalize_model_alias(alias)
    if normalized == "default":
        return model_default_env_key(provider)
    prefix = "OOONANA_GEMINI_MODEL_" if provider == "gemini" else "OOONANA_MODEL_"
    return prefix + normalized.upper().replace("-", "_")


def model_aliases(config: dict[str, str], provider: str = "nim") -> dict[str, str]:
    aliases: dict[str, str] = {"default": model_default(config, provider)}
    for alias, default_model in DEFAULT_MODEL_ALIASES[provider].items():
        aliases[alias] = config.get(model_alias_env_key(alias, provider), default_model)
    prefix = "OOONANA_GEMINI_MODEL_" if provider == "gemini" else "OOONANA_MODEL_"
    extras: list[tuple[str, str]] = []
    for key, value in config.items():
        if not key.startswith(prefix) or not value:
            continue
        alias = key.removeprefix(prefix).lower().replace("_", "-")
        if alias not in aliases:
            extras.append((alias, value))
    for alias, value in sorted(extras):
        aliases[alias] = value
    return {key: value for key, value in aliases.items() if value}


def resolve_model(model: str, config: dict[str, str], provider: str = "nim") -> str:
    aliases = model_aliases(config, provider)
    selected = (model or "default").strip()
    return aliases.get(selected.lower(), selected)


def print_model_aliases(config: dict[str, str], provider: str) -> None:
    print("aliases:")
    for alias, model in model_aliases(config, provider).items():
        print(f"  {alias}: {model}")


def print_model_catalog(config: dict[str, str], provider: str) -> None:
    print_model_aliases(config, provider)
    print("popular:")
    models = GEMINI_POPULAR_MODELS if provider == "gemini" else POPULAR_MODELS
    for model in models:
        print(f"  {model}")


def gemini_url(base_url: str, model: str, stream: bool) -> str:
    base = base_url.rstrip("/")
    suffix = "streamGenerateContent?alt=sse" if stream else "generateContent"
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    quoted_model = urllib.parse.quote(model, safe="")
    return f"{base}/models/{quoted_model}:{suffix}"


def extract_gemini_text(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        text = part.get("text")
        if text:
            chunks.append(text)
    return "".join(chunks)


def read_gemini_streaming_response(response: Any) -> str:
    chunks: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        text = extract_gemini_text(event)
        if text:
            chunks.append(text)
            print(text, end="", flush=True)
    print()
    return "".join(chunks)


def call_model(args: argparse.Namespace, config: dict[str, str], messages: list[dict[str, str]], stream: bool) -> str:
    provider = active_provider(args, config)
    if os.environ.get("OOONANA_AI_MOCK") == "1":
        response = mock_response(messages)
        if stream:
            for char in response:
                print(char, end="", flush=True)
                time.sleep(0.001)
            print()
        return response
    if provider == "gemini":
        return call_gemini(args, config, messages, stream)
    return call_nim(args, config, messages, stream)


def call_gemini(args: argparse.Namespace, config: dict[str, str], messages: list[dict[str, str]], stream: bool) -> str:
    key = gemini_api_key(config)
    if not key:
        raise OoonanaError("AI config missing GEMINI_API_KEY or GOOGLE_API_KEY: run ooonana ai setup")
    model = resolve_model(args.model, config, "gemini")
    payload = gemini_request_payload(args, config, messages, stream=stream, include_meta=False)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        gemini_url(provider_base_url(config, "gemini"), model, stream),
        data=body,
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": f"ooonana-ai/{VERSION}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=float(os.environ.get("OOONANA_AI_TIMEOUT", "120"))) as response:
            if stream:
                return read_gemini_streaming_response(response)
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OoonanaError(f"Google Gemini HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OoonanaError(f"Google Gemini connection failed: {exc.reason}") from exc

    text = extract_gemini_text(data)
    if not text:
        raise OoonanaError("Google Gemini response did not include text content")
    return text


def normalize_model_alias(alias: str) -> str:
    normalized = alias.strip().lower().replace("_", "-")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", normalized):
        raise OoonanaError("model alias must start with a letter and use letters, numbers, or dashes")
    return normalized


def mock_response(messages: list[dict[str, str]]) -> str:
    last = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
    return f"Ooonana mock response. I see this Linux environment and your prompt was: {last}"


def call_nim(args: argparse.Namespace, config: dict[str, str], messages: list[dict[str, str]], stream: bool) -> str:
    if os.environ.get("OOONANA_AI_MOCK") == "1":
        response = mock_response(messages)
        if stream:
            for char in response:
                print(char, end="", flush=True)
                time.sleep(0.001)
            print()
        return response

    key = api_key(config)
    if not key:
        raise OoonanaError("AI config missing NVIDIA_API_KEY: run ooonana ai setup")

    base_url = config_value(config, "OOONANA_NIM_BASE_URL", DEFAULT_BASE_URL)
    payload = nim_request_payload(args, config, messages, stream=stream, include_meta=False)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        completions_url(base_url),
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": f"ooonana-ai/{VERSION}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=float(os.environ.get("OOONANA_AI_TIMEOUT", "120"))) as response:
            if stream:
                return read_streaming_response(response)
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OoonanaError(f"NVIDIA NIM HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OoonanaError(f"NVIDIA NIM connection failed: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise OoonanaError("NVIDIA NIM response did not include chat content") from exc


def read_streaming_response(response: Any) -> str:
    chunks: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        delta = event.get("choices", [{}])[0].get("delta", {})
        text = delta.get("content") or ""
        if text:
            chunks.append(text)
            print(text, end="", flush=True)
    print()
    return "".join(chunks)


def cmd_doctor(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    config = load_config(path)
    provider = active_provider(args, config)
    if not path.exists():
        print("AI config missing: run ooonana ai setup")
        return 1
    if not provider_api_key(config, provider):
        print(missing_key_message(provider))
        print(f"config: {path}")
        print(f"provider: {provider_label(provider)}")
        print(f"model: {resolve_model('', config, provider)}")
        return 1
    print("AI config: ok")
    print(f"provider: {provider_label(provider)}")
    print(f"base_url: {provider_base_url(config, provider)}")
    print(f"model: {resolve_model('', config, provider)}")
    print("aliases:")
    for alias, model in model_aliases(config, provider).items():
        print(f"  {alias}: {model}")
    print("identity: Ooonana")
    return 0


def cmd_env(_: argparse.Namespace) -> int:
    print(environment_snapshot(max_bytes=20000))
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    provider = active_provider(args, config)
    print(f"Ooonana {provider_label(provider)} models:")
    print_model_catalog(config, provider)
    return 0


def cmd_provider(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    config = load_config(path)
    action = args.action
    if action == "show":
        provider = active_provider(args, config)
        print(f"active: {provider}")
        print(f"label: {provider_label(provider)}")
        print(f"base_url: {provider_base_url(config, provider)}")
        print(f"key: {'present' if provider_api_key(config, provider) else 'missing'}")
        print(f"config: {path}")
        return 0
    if action == "set":
        if args.value not in PROVIDER_LABELS:
            raise OoonanaError("provider must be nim or gemini")
        write_env_updates(path, {"OOONANA_AI_PROVIDER": args.value})
        print(f"provider: {args.value}")
        print(f"config: {path}")
        return 0
    raise OoonanaError("usage: ooonana-ai provider [show|set nim|set gemini]")
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    config = load_config(path)
    provider = active_provider(args, config)
    action = args.action
    values = args.values

    if action in ("show", ""):
        print(f"provider: {provider}")
        print(f"active: {resolve_model('', config, provider)}")
        print(f"config: {path}")
        print_model_aliases(config, provider)
        print("change default: ooonana-ai model set code")
        return 0

    if action == "list":
        print_model_catalog(config, provider)
        return 0

    if action in ("set", "use"):
        if len(values) != 1:
            raise OoonanaError("usage: ooonana-ai model set MODEL_OR_ALIAS")
        model = resolve_model(values[0], config, provider)
        write_env_updates(path, {model_default_env_key(provider): model})
        print(f"default model: {model}")
        print(f"config: {path}")
        return 0

    if action == "alias":
        if len(values) != 2:
            raise OoonanaError("usage: ooonana-ai model alias NAME MODEL_OR_ALIAS")
        alias = normalize_model_alias(values[0])
        if alias == "default":
            raise OoonanaError("use model set to change default")
        model = resolve_model(values[1], config, provider)
        write_env_updates(path, {model_alias_env_key(alias, provider): model})
        print(f"alias {alias}: {model}")
        print(f"config: {path}")
        return 0

    raise OoonanaError("usage: ooonana-ai model [show|list|set|use|alias]")


def cmd_agents(_: argparse.Namespace) -> int:
    print("Ooonana local agents:")
    for name, description in AGENTS.items():
        print(f"  {name:<10} {description}")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    agent = args.name
    if agent not in AGENTS:
        raise OoonanaError(f"unknown agent: {agent}")
    context = agent_context(agent, args, max_bytes=args.max_bytes)
    if args.ask:
        config = load_config(Path(args.config).expanduser())
        prompt = args.prompt or f"Summarize the {agent} context for the user."
        messages = build_messages(prompt, include_env=False, agent=agent, args=args)
        answer = call_model(args, config, messages, stream=not args.no_stream)
        if not args.no_stream:
            return 0
        print(answer)
        return 0
    print(context)
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    records = read_jsonl(history_path(args))
    if getattr(args, "clear", False):
        history_path(args).unlink(missing_ok=True)
        print("history cleared")
        return 0
    records = records[-getattr(args, "limit", 20) :]
    if getattr(args, "json", False):
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return 0
    if not records:
        print("no Ooonana AI history yet")
        return 0
    for index, record in enumerate(records, start=1):
        user = str(record.get("user", "")).replace("\n", " ")[:120]
        assistant = str(record.get("assistant", "")).replace("\n", " ")[:120]
        print(f"{index:>2}. {record.get('time', '')} {record.get('mode', '')} {record.get('model', '')}")
        print(f"    user: {user}")
        if assistant:
            print(f"    ooonana: {assistant}")
    return 0


def cmd_sessions(args: argparse.Namespace) -> int:
    directory = sessions_dir(args)
    if not directory.exists():
        print("no Ooonana AI sessions yet")
        return 0
    rows: list[tuple[str, int, str]] = []
    for path in sorted(directory.glob("*.jsonl")):
        records = read_jsonl(path)
        last = records[-1].get("time", "") if records else ""
        rows.append((path.stem, len(records), str(last)))
    if not rows:
        print("no Ooonana AI sessions yet")
        return 0
    for session_id, count, last in rows[-args.limit :]:
        print(f"{session_id} turns={count} last={last}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    provider = active_provider(args, config)
    print_status(resolve_model(args.model, config, provider), provider, config, state_dir(args))
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    prompt = "Reply with exactly: Ooonana online"
    messages = build_messages(prompt, include_env=False)
    answer = call_model(args, config, messages, stream=False).strip()
    print(answer)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    config = load_config(path)
    safe = dict(config)
    for key in ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if key in safe and safe[key]:
            safe[key] = (safe[key][:8] + "...redacted") if len(safe[key]) > 12 else "...redacted"
    print(f"config: {path}")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    provider = active_provider(args, config)
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        raise OoonanaError("prompt required")
    active_agent = "" if args.no_agent else args.agent
    messages = build_messages(prompt, include_env=not args.no_env, agent=active_agent, args=args)
    stream_default = config_value(config, "OOONANA_AI_STREAM", "1") != "0"
    stream = stream_default and not args.no_stream and not args.json
    model = resolve_model(args.model, config, provider)
    session_id = args.session or f"ask-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    if args.dry_run:
        payload = request_payload(args, config, messages, stream=stream)
        print(json.dumps(payload, indent=2))
        return 0
    if sys.stdout.isatty() and not args.json:
        print_banner(model, provider, mode="ask")
    answer = call_model(args, config, messages, stream=stream)
    if not args.no_history:
        record_exchange(args, session_id=session_id, mode="ask", model=model, user=prompt, assistant=answer)
    if args.json:
        print(json.dumps({"model": model, "content": answer}))
    elif not stream:
        print(answer)
    return 0


def print_chat_help() -> None:
    print(
        textwrap.dedent(
            """\
            /help              Show commands
            /agents            List local context agents
            /agent [NAME|none] Show or switch active agent
            /env               Print the Linux environment snapshot
            /history           Show recent Ooonana AI history
            /rewind [N]        Remove the latest N turns from this chat context
            /status            Show provider, model, config, and cwd
            /provider          Show or switch provider
            /models            List aliases and popular model ids
            /model [MODEL]     Show or switch model for this chat
            /model set MODEL   Persist default model in config
            /model alias N M   Save alias N for model M
            /clear             Clear conversation history
            /save PATH         Save transcript as JSON
            /exit              Leave Ooonana AI
            """
        ).strip()
    )


def cmd_chat(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    provider = active_provider(args, config)
    model = resolve_model(args.model, config, provider)
    session_id = args.session or f"chat-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    session_records = read_jsonl(session_path(args, session_id))
    history = records_to_messages(session_records)
    transcript = list(session_records)
    active_agent = "" if args.no_agent else args.agent

    print_banner(model, provider, mode="chat")
    print(f"session: {session_id}")
    print(f"agent: {active_agent or 'none'}")
    print("type /help for commands, /exit to leave")

    while True:
        try:
            prompt = input(color("ooonana ai> ", "1;35"))
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        stripped = prompt.strip()
        if not stripped:
            continue
        if stripped.startswith("/"):
            parts = shlex.split(stripped)
            command = parts[0]
            if command in ("/exit", "/quit"):
                return 0
            if command == "/help":
                print_chat_help()
                continue
            if command == "/agents":
                cmd_agents(args)
                continue
            if command == "/agent":
                if len(parts) == 1:
                    print(f"active agent: {active_agent or 'none'}")
                    print("available: " + ", ".join(AGENTS))
                elif parts[1] == "none":
                    active_agent = ""
                    print("active agent: none")
                elif parts[1] in AGENTS:
                    active_agent = parts[1]
                    print(f"active agent: {active_agent}")
                else:
                    print(f"unknown agent: {parts[1]}")
                continue
            if command == "/env":
                print(environment_snapshot(max_bytes=20000))
                continue
            if command == "/status":
                print_status(model, provider, config, state_dir(args))
                continue
            if command == "/provider":
                if len(parts) == 1:
                    print(f"active provider: {provider}")
                    print("available: nim, gemini")
                    continue
                if len(parts) == 3 and parts[1] == "set":
                    if parts[2] not in PROVIDER_LABELS:
                        print("usage: /provider set nim|gemini")
                        continue
                    provider = parts[2]
                    write_env_updates(Path(args.config).expanduser(), {"OOONANA_AI_PROVIDER": provider})
                    config = load_config(Path(args.config).expanduser())
                    model = resolve_model("", config, provider)
                    print(f"provider: {provider}")
                    continue
                print("usage: /provider [set nim|gemini]")
                continue
            if command == "/models":
                print_model_catalog(config, provider)
                continue
            if command == "/history":
                cmd_history(args)
                continue
            if command == "/rewind":
                count = 1
                if len(parts) > 1:
                    try:
                        count = max(1, int(parts[1]))
                    except ValueError:
                        print("usage: /rewind [N]")
                        continue
                removed = min(count, len(session_records))
                if removed:
                    del session_records[-removed:]
                    history = records_to_messages(session_records)
                    transcript = list(session_records)
                    write_jsonl(session_path(args, session_id), session_records)
                print(f"rewound {removed} turn(s)")
                continue
            if command == "/clear":
                history.clear()
                transcript.clear()
                session_records.clear()
                write_jsonl(session_path(args, session_id), session_records)
                print("history cleared")
                continue
            if command == "/model":
                if len(parts) == 1:
                    print(f"active: {model}")
                    continue
                if parts[1] in ("set", "use"):
                    if len(parts) != 3:
                        print("usage: /model set MODEL_OR_ALIAS")
                        continue
                    model = resolve_model(parts[2], config, provider)
                    write_env_updates(Path(args.config).expanduser(), {model_default_env_key(provider): model})
                    config = load_config(Path(args.config).expanduser())
                    print(f"default model: {model}")
                    continue
                if parts[1] == "alias":
                    if len(parts) != 4:
                        print("usage: /model alias NAME MODEL_OR_ALIAS")
                        continue
                    try:
                        alias = normalize_model_alias(parts[2])
                        if alias == "default":
                            raise OoonanaError("use /model set to change default")
                        resolved = resolve_model(parts[3], config, provider)
                        write_env_updates(Path(args.config).expanduser(), {model_alias_env_key(alias, provider): resolved})
                        config = load_config(Path(args.config).expanduser())
                        print(f"alias {alias}: {resolved}")
                    except OoonanaError as exc:
                        print(str(exc))
                    continue
                if len(parts) == 2:
                    model = resolve_model(parts[1], config, provider)
                    print(f"model: {model}")
                else:
                    print("usage: /model [MODEL] | /model set MODEL | /model alias NAME MODEL")
                continue
            if command == "/save":
                if len(parts) != 2:
                    print("usage: /save PATH")
                    continue
                Path(parts[1]).write_text(json.dumps(transcript, indent=2), encoding="utf-8")
                print(f"saved: {parts[1]}")
                continue
            print("unknown command")
            continue

        local_args = argparse.Namespace(**vars(args))
        local_args.model = model
        local_args.provider = provider
        messages = build_messages(stripped, history=history, include_env=True, agent=active_agent, args=args)
        try:
            answer = call_model(local_args, config, messages, stream=not args.no_stream)
        except OoonanaError as exc:
            print(warn(str(exc)), file=sys.stderr)
            return 1
        if args.no_stream:
            print(answer)
        record = record_exchange(args, session_id=session_id, mode="chat", model=model, user=stripped, assistant=answer)
        session_records.append(record)
        history.append({"role": "user", "content": stripped})
        history.append({"role": "assistant", "content": answer})
        transcript.append(record)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ooonana ai", description="Ooonana AI CLI for NVIDIA NIM and Google Gemini")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="config env file")
    parser.add_argument("--state-dir", default=str(STATE_PATH), help="history/session state directory")
    parser.add_argument("--provider", default="", choices=("nim", "gemini", "auto", ""), help="provider override")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("setup", help="create config file")
    subparsers.add_parser("doctor", help="check AI config")
    subparsers.add_parser("config", help="print resolved config without secrets")
    subparsers.add_parser("env", help="print Linux environment context")
    subparsers.add_parser("models", help="show useful provider model ids")
    provider = subparsers.add_parser("provider", help="show or change provider")
    provider.add_argument("action", nargs="?", default="show", choices=("show", "set"), help="provider action")
    provider.add_argument("value", nargs="?", default="", choices=("nim", "gemini", ""), help="provider name")
    model = subparsers.add_parser("model", help="show or change default model")
    model.add_argument("action", nargs="?", default="show", choices=("show", "list", "set", "use", "alias"), help="model action")
    model.add_argument("values", nargs="*", help="model id or alias values")
    subparsers.add_parser("agents", help="list local context agents")

    agent = subparsers.add_parser("agent", help="run or inspect a local context agent")
    agent.add_argument("name", choices=sorted(AGENTS), help="agent name")
    agent.add_argument("--ask", action="store_true", help="ask provider to summarize this agent context")
    agent.add_argument("--prompt", default="", help="custom summarization prompt")
    agent.add_argument("--model", default="", help="override model id")
    agent.add_argument("--no-stream", action="store_true", help="disable streaming output")
    agent.add_argument("--max-bytes", type=int, default=12000, help="max context bytes to print/submit")

    history = subparsers.add_parser("history", help="show persistent Ooonana AI history")
    history.add_argument("--limit", type=int, default=20, help="number of turns to show")
    history.add_argument("--json", action="store_true", help="print JSON history")
    history.add_argument("--clear", action="store_true", help="clear global history")

    sessions = subparsers.add_parser("sessions", help="list persistent chat sessions")
    sessions.add_argument("--limit", type=int, default=20, help="number of sessions to show")

    status = subparsers.add_parser("status", help="show UI/provider status")
    status.add_argument("--model", default="", help="override model id")

    ping = subparsers.add_parser("ping", help="send a tiny live check to active provider")
    ping.add_argument("--model", default="", help="override model id")

    ask = subparsers.add_parser("ask", help="ask one question")
    ask.add_argument("--model", default="", help="override model id")
    ask.add_argument("--no-env", action="store_true", help="do not include Linux environment snapshot")
    ask.add_argument("--agent", choices=sorted(AGENTS), default="activity", help="local context agent to include")
    ask.add_argument("--no-agent", action="store_true", help="do not include local agent context")
    ask.add_argument("--session", default="", help="session id for saved history")
    ask.add_argument("--no-history", action="store_true", help="do not save this exchange")
    ask.add_argument("--no-stream", action="store_true", help="disable streaming output")
    ask.add_argument("--dry-run", action="store_true", help="print request JSON without calling provider")
    ask.add_argument("--json", action="store_true", help="print JSON response")
    ask.add_argument("prompt", nargs=argparse.REMAINDER)

    code = subparsers.add_parser("code", help="alias for ask")
    code.add_argument("--model", default="", help="override model id")
    code.add_argument("--no-env", action="store_true", help="do not include Linux environment snapshot")
    code.add_argument("--agent", choices=sorted(AGENTS), default="activity", help="local context agent to include")
    code.add_argument("--no-agent", action="store_true", help="do not include local agent context")
    code.add_argument("--session", default="", help="session id for saved history")
    code.add_argument("--no-history", action="store_true", help="do not save this exchange")
    code.add_argument("--no-stream", action="store_true", help="disable streaming output")
    code.add_argument("--dry-run", action="store_true", help="print request JSON without calling provider")
    code.add_argument("--json", action="store_true", help="print JSON response")
    code.add_argument("prompt", nargs=argparse.REMAINDER)

    chat = subparsers.add_parser("chat", help="start interactive chat")
    chat.add_argument("--model", default="", help="override model id")
    chat.add_argument("--agent", choices=sorted(AGENTS), default="activity", help="local context agent to include")
    chat.add_argument("--no-agent", action="store_true", help="do not include local agent context")
    chat.add_argument("--session", default="", help="session id to create/resume")
    chat.add_argument("--no-stream", action="store_true", help="disable streaming output")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "chat"
    try:
        if command == "setup":
            setup_config(Path(args.config).expanduser())
            return 0
        if command == "doctor":
            return cmd_doctor(args)
        if command == "config":
            return cmd_config(args)
        if command == "env":
            return cmd_env(args)
        if command == "models":
            return cmd_models(args)
        if command == "provider":
            return cmd_provider(args)
        if command == "model":
            return cmd_model(args)
        if command == "agents":
            return cmd_agents(args)
        if command == "agent":
            return cmd_agent(args)
        if command == "history":
            return cmd_history(args)
        if command == "sessions":
            return cmd_sessions(args)
        if command == "status":
            return cmd_status(args)
        if command == "ping":
            return cmd_ping(args)
        if command in ("ask", "code"):
            return cmd_ask(args)
        if command == "chat":
            return cmd_chat(args)
    except OoonanaError as exc:
        print(f"ooonana ai: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
