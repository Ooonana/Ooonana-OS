#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDER="$ROOT/scripts/build-openvino-chat-package.sh"
SOURCE="$ROOT/packages/openvino-chat/source"
PAYLOAD="$ROOT/packages/openvino-chat/rootfs"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$BUILDER" ]] || fail "missing executable OpenVINO package builder"
[[ -f "$SOURCE/pyproject.toml" ]] || fail "missing vendored pyproject"
[[ -f "$SOURCE/src/openvino_chat/cli.py" ]] || fail "missing vendored CLI"
[[ -f "$SOURCE/src/openvino_chat/benchmarks.py" ]] || fail "missing benchmark support"
[[ -f "$SOURCE/src/openvino_chat/compaction.py" ]] || fail "missing context compaction"
[[ -f "$SOURCE/src/openvino_chat/knowledge.py" ]] || fail "missing local knowledge support"
[[ -f "$SOURCE/src/openvino_chat/gui.py" ]] || fail "missing browser GUI"
[[ -f "$SOURCE/src/openvino_chat/web/openvino.html" ]] || fail "missing browser GUI assets"
[[ -f "$SOURCE/scripts/browser-bridge.sh" ]] || fail "missing Linux browser bridge"
[[ -x "$PAYLOAD/usr/bin/openvino" ]] || fail "missing OpenVINO launcher"
[[ -x "$PAYLOAD/usr/bin/ooonana-openvino-setup" ]] || fail "missing runtime setup"
[[ -f "$PAYLOAD/usr/bin/ooonana-openvino-launch" ]] || fail "missing GUI launcher"

source_text="$(<"$SOURCE/src/openvino_chat/cli.py")"
settings_text="$(<"$SOURCE/src/openvino_chat/settings.py")"
pyproject_text="$(<"$SOURCE/pyproject.toml")"
assert_contains "$source_text" 'choices=["GPU", "CPU"]'
assert_contains "$settings_text" '"ornith"'
assert_contains "$settings_text" 'DEFAULT_CONTEXT_LENGTH = 4096'
assert_contains "$pyproject_text" 'version = "0.2.0"'
assert_contains "$pyproject_text" 'pywebview>=6; sys_platform == '\''win32'\'''
assert_contains "$(<"$SOURCE/scripts/setup-linux.sh")" 'OPENVINO_MODEL_ROOT'
assert_contains "$(<"$SOURCE/scripts/setup-linux.sh")" 'OPENVINO_CHAT_CONFIG'
linux_paths="$(OPENVINO_HOME=/tmp/ov-runtime OPENVINO_MODEL_ROOT=/tmp/ov-models OPENVINO_CHAT_CONFIG=/tmp/ov-config/custom.json bash "$SOURCE/scripts/setup-linux.sh" --dry-run)"
assert_contains "$linux_paths" 'models: /tmp/ov-models'
assert_contains "$linux_paths" 'config: /tmp/ov-config/custom.json'

PYTHONPATH="$SOURCE/src" python3 - <<'PY'
import os
import ast
import tempfile
from pathlib import Path

from openvino_chat.api import _api_url, _health_payload
from openvino_chat.perf import _parse_linux_meminfo
from openvino_chat.tools import TOOL_DEFINITIONS, _parse_search_results
from openvino_chat.media import extract_media_paths, model_media_capabilities
from openvino_chat.sessions import CrashRecoveryStore
from openvino_chat.settings import canonical_model_name
from openvino_chat.cli import _parser
from openvino_chat.cli import _chat
from unittest.mock import patch

import openvino_chat
for path in Path(openvino_chat.__file__).parent.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
assert canonical_model_name("qwen") == "qwen3.5"
assert canonical_model_name("qwen38") == "qwen3.8"
assert _parser().parse_args(["chat", "--gui"]).gui is True
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    with patch("openvino_chat.cli._command_completer", return_value=None), patch(
        "openvino_chat.cli._can_use_persistent_tui", return_value=True
    ), patch(
        "openvino_chat.cli.tui_mod.run_persistent_repl", return_value=0
    ) as repl:
        assert _chat(root, "", "CPU", 128, None, None, 4096, "auto", lambda *a, **k: None, input, start_gui=True) == 0
        assert repl.call_args.kwargs["start_frontend"] == "browser"
        assert _chat(root / "missing", "", "CPU", 128, None, None, 4096, "auto", lambda *a, **k: None, input, start_gui=True) == 0
    first, second = root / "Photo.png", root / "photo.png"
    first.touch()
    second.touch()
    paths = extract_media_paths(f'"{first}" "{second}" "{first}"')
    assert len(paths) == (1 if os.name == "nt" else 2), paths
    assert model_media_capabilities(None, object()) == frozenset({"text"})
    recovery = CrashRecoveryStore(root / "recovery.json")
    recovery.schedule("session", "old draft")
    recovery.save_now("session", "new draft", pending=True)
    recovery.flush()
    assert recovery.load()["draft"] == "new draft"
    recovery.clear()
    recovery.flush()
    assert recovery.load() == {}

assert _api_url("::1", 11435, "/health") == "http://[::1]:11435/health"
assert _health_payload({}) is None
assert _parse_linux_meminfo("MemTotal: 100 kB\nMemAvailable: 40 kB\n") == (102400, 40960)
results = _parse_search_results(
    '<a class="result-link" href="https://example.com">Example</a>'
    '<td class="result-snippet">Safe result</td>'
)
assert results == [("Example", "https://example.com", "Safe result")]
shell_tool = next(item for item in TOOL_DEFINITIONS if item["function"]["name"] == "shell")
command_help = shell_tool["function"]["parameters"]["properties"]["command"]["description"]
assert command_help == ("PowerShell command." if os.name == "nt" else "POSIX shell command.")
PY

setup_dry="$("$PAYLOAD/usr/bin/ooonana-openvino-setup" --dry-run)"
assert_contains "$setup_dry" "Ubuntu Python venv + openvino-genai"
assert_contains "$setup_dry" "OOONANA_OPENVINO_SETUP_DRY_OK"

setup_text="$(<"$PAYLOAD/usr/bin/ooonana-openvino-setup")"
assert_contains "$setup_text" "/tmp/ooonana-openvino-src"
assert_contains "$setup_text" "--no-preserve=mode,ownership,timestamps,xattr"
assert_contains "$setup_text" "chmod -R u+rwX /tmp/ooonana-openvino-src"
assert_contains "$setup_text" "requirements-linux-runtime.lock /tmp/ooonana-openvino-src"
assert_contains "$setup_text" "--exclude='./dev/*'"

launcher_help="$("$PAYLOAD/usr/bin/openvino" --help)"
assert_contains "$launcher_help" "openvino chat [--device GPU|CPU]"
assert_contains "$launcher_help" "Inference works offline"

launcher_text="$(<"$PAYLOAD/usr/bin/openvino")"
assert_contains "$launcher_text" "--unshare-user"
assert_contains "$launcher_text" "--unshare-uts"
[[ "$launcher_text" != *"--unshare-all"* ]] || fail "runtime PID namespace would kill background API"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkfifo "$tmp/browser-request"
(IFS= read -r request < "$tmp/browser-request"; printf '%s\n' "$request" > "$tmp/browser-captured") &
browser_reader=$!
OOONANA_OPENVINO_BROWSER_FIFO="$tmp/browser-request" sh "$SOURCE/scripts/browser-bridge.sh" 'http://127.0.0.1:12345/openvino.html#token=test-token'
wait "$browser_reader"
assert_contains "$(<"$tmp/browser-captured")" 'http://127.0.0.1:12345/openvino.html#token=test-token'
if OOONANA_OPENVINO_BROWSER_FIFO="$tmp/browser-request" sh "$SOURCE/scripts/browser-bridge.sh" 'https://example.com/' 2>/dev/null; then
  fail "browser bridge accepted remote URL"
fi
printf 'ram\n' >"$tmp/live-mode"
if setup_rejection="$(OOONANA_LIVE_MODE_FILE="$tmp/live-mode" sh "$PAYLOAD/usr/bin/ooonana-openvino-setup" 2>&1)"; then
  fail "OpenVINO setup accepted RAM-only live storage"
fi
assert_contains "$setup_rejection" 'OOONANA_PERSIST'
printf 'usb-temporary\n' >"$tmp/live-mode"
if setup_rejection="$(OOONANA_LIVE_MODE_FILE="$tmp/live-mode" sh "$PAYLOAD/usr/bin/ooonana-openvino-setup" 2>&1)"; then
  fail "OpenVINO setup accepted temporary live storage"
fi
assert_contains "$setup_rejection" 'vanish on reboot'
mkdir -p "$tmp/state/rootfs"
touch "$tmp/state/rootfs/.ooonana-openvino-ready"
if doctor="$(OOONANA_OPENVINO_STATE_DIR="$tmp/state" OOONANA_OPENVINO_PROJECT="$SOURCE" "$PAYLOAD/usr/bin/openvino" doctor)"; then
  fail "old unversioned runtime reported ready"
fi
assert_contains "$doctor" "runtime: outdated"
assert_contains "$doctor" "next: openvino setup"
assert_contains "$setup_text" 'APP-MANIFEST.sha256'
assert_contains "$setup_text" 'openvino-dependencies.lock'
assert_contains "$setup_text" 'requirements-linux-runtime.lock'
built="$(bash "$BUILDER" --out-dir "$tmp/repo" --version 0.2.0)"
assert_contains "$built" "openvino-chat.pkg"
[[ -f "$tmp/repo/openvino-chat.pkg" ]] || fail "missing package metadata"
[[ -f "$tmp/repo/archives/openvino-chat-0.2.0.tar.gz" ]] || fail "missing package archive"

metadata="$(<"$tmp/repo/openvino-chat.pkg")"
assert_contains "$metadata" 'OOONANA_PKG_ID="openvino-chat"'
assert_contains "$metadata" 'OOONANA_PKG_DEPS="bubblewrap xz curl ca-certificates coreutils"'
assert_contains "$metadata" "Offline Ooonana AI"
assert_contains "$metadata" "intel gpu cpu"

contents="$(tar -tzf "$tmp/repo/archives/openvino-chat-0.2.0.tar.gz")"
[[ "$contents" != *'__pycache__'* ]] || fail "OpenVINO contains Python cache"
[[ "$contents" != *'.pyc'* ]] || fail "OpenVINO contains Python bytecode"
[[ "$contents" != *'/.openvino/'* && "$contents" != *'/models/'* && "$contents" != *'.venv/'* ]] || fail "OpenVINO package contains user runtime or models"
assert_contains "$contents" "./usr/bin/openvino"
assert_contains "$contents" "./usr/bin/ooonana-openvino-setup"
assert_contains "$contents" "./usr/bin/ooonana-openvino-launch"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/cli.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/benchmarks.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/compaction.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/knowledge.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/gui.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/web/openvino.html"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/scripts/browser-bridge.sh"
assert_contains "$contents" "./usr/share/applications/ooonana-openvino.desktop"
assert_contains "$(<"$ROOT/packages/openvino-chat/rootfs/usr/share/applications/ooonana-openvino.desktop")" "Icon=/usr/share/ooonana/logo.png"
assert_contains "$(<"$ROOT/packages/openvino-chat/rootfs/usr/share/applications/ooonana-openvino.desktop")" "Exec=ooonana-openvino-launch"
assert_contains "$(sh "$PAYLOAD/usr/bin/ooonana-openvino-launch" --dry-run)" "OOONANA_OPENVINO_LAUNCH_OK"

printf 'ok openvino-chat-package\n'
