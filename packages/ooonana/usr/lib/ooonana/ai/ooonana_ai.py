#!/usr/bin/env python3
"""Ooonana AI terminal client backed by NVIDIA NIM."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import readline  # noqa: F401 - enables line editing in interactive mode
except ImportError:
    pass


VERSION = "0.1.0"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
CONFIG_PATH = Path(os.environ.get("OOONANA_AI_CONFIG", "~/.config/ooonana/ai.env")).expanduser()
DEFAULT_MAX_CONTEXT_BYTES = 12000

IDENTITY_PROMPT = """\
You are Ooonana, the built-in AI assistant for Ooonana OS.
Your name is Ooonana. Say you are Ooonana when identity matters.
You are not Gemini, Claude, ChatGPT, or NIM; NVIDIA NIM is only your model provider.
You live in a Linux terminal and help the user understand, build, debug, and operate the whole Ooonana Linux environment.
Use the provided environment snapshot as authoritative current context.
Prefer concrete shell commands, file paths, and short explanations.
Do not pretend you executed commands; say when a command should be run by the user.
"""

POPULAR_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2-instruct",
    "meta/llama-3.3-70b-instruct",
    "openai/gpt-oss-120b",
]


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


def print_banner(model: str, mode: str = "chat") -> None:
    width = 64
    print(heading("=" * width))
    print(heading("Ooonana AI").ljust(width))
    print(f"mode: {mode} | provider: NVIDIA NIM | model: {model}")
    print(faint("identity: Ooonana | context: Linux + workspace"))
    print(heading("=" * width))


def print_status(model: str, config: dict[str, str]) -> None:
    print("Ooonana AI status")
    print("identity: Ooonana")
    print("provider: NVIDIA NIM")
    print(f"model: {model}")
    print(f"base_url: {config_value(config, 'OOONANA_NIM_BASE_URL', DEFAULT_BASE_URL)}")
    print(f"config_key: {'present' if api_key(config) else 'missing'}")
    print(f"cwd: {os.getcwd()}")


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
    for key in (
        "NVIDIA_API_KEY",
        "NVIDIA_NIM_API_KEY",
        "OOONANA_NIM_BASE_URL",
        "OOONANA_NIM_MODEL",
        "OOONANA_AI_MAX_TOKENS",
        "OOONANA_AI_TEMPERATURE",
        "OOONANA_AI_STREAM",
    ):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def config_value(config: dict[str, str], key: str, default: str) -> str:
    value = config.get(key, "").strip()
    return value if value else default


def api_key(config: dict[str, str]) -> str:
    return config.get("NVIDIA_NIM_API_KEY") or config.get("NVIDIA_API_KEY") or ""


def setup_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        old_umask = os.umask(0o077)
        try:
            path.write_text(
                textwrap.dedent(
                    f"""\
                    # Ooonana AI uses NVIDIA NIM's OpenAI-compatible chat API.
                    # Get a key from https://build.nvidia.com/settings/api-keys
                    NVIDIA_API_KEY=
                    OOONANA_NIM_BASE_URL={DEFAULT_BASE_URL}
                    OOONANA_NIM_MODEL={DEFAULT_MODEL}
                    OOONANA_MODEL_FAST=qwen/qwen3-next-80b-a3b-instruct
                    OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
                    OOONANA_MODEL_DEEP=nvidia/nemotron-3-super-120b-a12b
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


def build_messages(prompt: str, history: list[dict[str, str]] | None = None, include_env: bool = True) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": IDENTITY_PROMPT}]
    if include_env:
        messages.append({"role": "system", "content": "Current Linux environment snapshot:\n" + environment_snapshot()})
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


def request_payload(args: argparse.Namespace, config: dict[str, str], messages: list[dict[str, str]], stream: bool) -> dict[str, Any]:
    model = resolve_model(args.model, config)
    max_tokens = int(config_value(config, "OOONANA_AI_MAX_TOKENS", "1024"))
    temperature = float(config_value(config, "OOONANA_AI_TEMPERATURE", "0.2"))
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }


def model_aliases(config: dict[str, str]) -> dict[str, str]:
    aliases = {
        "default": config_value(config, "OOONANA_NIM_MODEL", DEFAULT_MODEL),
        "fast": config.get("OOONANA_MODEL_FAST", "qwen/qwen3-next-80b-a3b-instruct"),
        "code": config.get("OOONANA_MODEL_CODE", "qwen/qwen3-coder-480b-a35b-instruct"),
        "deep": config.get("OOONANA_MODEL_DEEP", "nvidia/nemotron-3-super-120b-a12b"),
    }
    return {key: value for key, value in aliases.items() if value}


def resolve_model(model: str, config: dict[str, str]) -> str:
    aliases = model_aliases(config)
    selected = model or "default"
    return aliases.get(selected, selected)


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
    payload = request_payload(args, config, messages, stream=stream)
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
    if not path.exists():
        print("AI config missing: run ooonana ai setup")
        return 1
    if not api_key(config):
        print("AI config missing NVIDIA_API_KEY")
        print(f"config: {path}")
        print(f"model: {resolve_model('', config)}")
        return 1
    print("AI config: ok")
    print("provider: NVIDIA NIM")
    print(f"base_url: {config_value(config, 'OOONANA_NIM_BASE_URL', DEFAULT_BASE_URL)}")
    print(f"model: {resolve_model('', config)}")
    print("aliases:")
    for alias, model in model_aliases(config).items():
        print(f"  {alias}: {model}")
    print("identity: Ooonana")
    return 0


def cmd_env(_: argparse.Namespace) -> int:
    print(environment_snapshot(max_bytes=20000))
    return 0


def cmd_models(_: argparse.Namespace) -> int:
    print("Popular NVIDIA NIM model ids for Ooonana:")
    for model in POPULAR_MODELS:
        print(f"  {model}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    print_status(resolve_model(args.model, config), config)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    config = load_config(path)
    safe = dict(config)
    for key in ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"):
        if key in safe and safe[key]:
            safe[key] = (safe[key][:8] + "...redacted") if len(safe[key]) > 12 else "...redacted"
    print(f"config: {path}")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        raise OoonanaError("prompt required")
    messages = build_messages(prompt, include_env=not args.no_env)
    stream_default = config_value(config, "OOONANA_AI_STREAM", "1") != "0"
    stream = stream_default and not args.no_stream and not args.json
    model = resolve_model(args.model, config)
    if args.dry_run:
        payload = request_payload(args, config, messages, stream=stream)
        print(json.dumps(payload, indent=2))
        return 0
    if sys.stdout.isatty() and not args.json:
        print_banner(model, mode="ask")
    answer = call_nim(args, config, messages, stream=stream)
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
            /env               Print the Linux environment snapshot
            /status            Show provider, model, config, and cwd
            /model [MODEL]     Show or switch model for this chat
            /clear             Clear conversation history
            /save PATH         Save transcript as JSON
            /exit              Leave Ooonana AI
            """
        ).strip()
    )


def cmd_chat(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    model = resolve_model(args.model, config)
    history: list[dict[str, str]] = []
    transcript: list[dict[str, str]] = []

    print_banner(model, mode="chat")
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
            if command == "/env":
                print(environment_snapshot(max_bytes=20000))
                continue
            if command == "/status":
                print_status(model, config)
                continue
            if command == "/clear":
                history.clear()
                transcript.clear()
                print("history cleared")
                continue
            if command == "/model":
                if len(parts) == 1:
                    print(model)
                else:
                    model = resolve_model(parts[1], config)
                    print(f"model: {model}")
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
        messages = build_messages(stripped, history=history, include_env=True)
        try:
            answer = call_nim(local_args, config, messages, stream=not args.no_stream)
        except OoonanaError as exc:
            print(warn(str(exc)), file=sys.stderr)
            return 1
        history.append({"role": "user", "content": stripped})
        history.append({"role": "assistant", "content": answer})
        transcript.extend(history[-2:])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ooonana ai", description="Ooonana AI CLI for NVIDIA NIM")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="config env file")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("setup", help="create config file")
    subparsers.add_parser("doctor", help="check AI config")
    subparsers.add_parser("config", help="print resolved config without secrets")
    subparsers.add_parser("env", help="print Linux environment context")
    subparsers.add_parser("models", help="show useful NVIDIA NIM model ids")

    status = subparsers.add_parser("status", help="show UI/provider status")
    status.add_argument("--model", default="", help="override model id")

    ask = subparsers.add_parser("ask", help="ask one question")
    ask.add_argument("--model", default="", help="override model id")
    ask.add_argument("--no-env", action="store_true", help="do not include Linux environment snapshot")
    ask.add_argument("--no-stream", action="store_true", help="disable streaming output")
    ask.add_argument("--dry-run", action="store_true", help="print request JSON without calling NIM")
    ask.add_argument("--json", action="store_true", help="print JSON response")
    ask.add_argument("prompt", nargs=argparse.REMAINDER)

    code = subparsers.add_parser("code", help="alias for ask")
    code.add_argument("--model", default="", help="override model id")
    code.add_argument("--no-env", action="store_true", help="do not include Linux environment snapshot")
    code.add_argument("--no-stream", action="store_true", help="disable streaming output")
    code.add_argument("--dry-run", action="store_true", help="print request JSON without calling NIM")
    code.add_argument("--json", action="store_true", help="print JSON response")
    code.add_argument("prompt", nargs=argparse.REMAINDER)

    chat = subparsers.add_parser("chat", help="start interactive chat")
    chat.add_argument("--model", default="", help="override model id")
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
        if command == "status":
            return cmd_status(args)
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
