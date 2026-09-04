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
[[ -x "$PAYLOAD/usr/bin/openvino" ]] || fail "missing OpenVINO launcher"
[[ -x "$PAYLOAD/usr/bin/ooonana-openvino-setup" ]] || fail "missing runtime setup"

source_text="$(<"$SOURCE/src/openvino_chat/cli.py")"
settings_text="$(<"$SOURCE/src/openvino_chat/settings.py")"
pyproject_text="$(<"$SOURCE/pyproject.toml")"
assert_contains "$source_text" 'choices=["GPU", "CPU"]'
assert_contains "$settings_text" '"ornith"'
assert_contains "$pyproject_text" 'version = "0.1.5"'

PYTHONPATH="$SOURCE/src" python3 - <<'PY'
import os

from openvino_chat.api import _api_url, _health_payload
from openvino_chat.perf import _parse_linux_meminfo
from openvino_chat.tools import TOOL_DEFINITIONS, _parse_search_results

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
assert_contains "$setup_text" "pip install --no-cache-dir --upgrade /tmp/ooonana-openvino-src"
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
built="$(bash "$BUILDER" --out-dir "$tmp/repo" --version 0.1.5)"
assert_contains "$built" "openvino-chat.pkg"
[[ -f "$tmp/repo/openvino-chat.pkg" ]] || fail "missing package metadata"
[[ -f "$tmp/repo/archives/openvino-chat-0.1.5.tar.gz" ]] || fail "missing package archive"

metadata="$(<"$tmp/repo/openvino-chat.pkg")"
assert_contains "$metadata" 'OOONANA_PKG_ID="openvino-chat"'
assert_contains "$metadata" 'OOONANA_PKG_DEPS="bubblewrap xz curl ca-certificates coreutils"'
assert_contains "$metadata" "Offline Ooonana AI"
assert_contains "$metadata" "intel gpu cpu"

contents="$(tar -tzf "$tmp/repo/archives/openvino-chat-0.1.5.tar.gz")"
assert_contains "$contents" "./usr/bin/openvino"
assert_contains "$contents" "./usr/bin/ooonana-openvino-setup"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/cli.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/benchmarks.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/compaction.py"
assert_contains "$contents" "./usr/lib/ooonana/openvino-chat/src/openvino_chat/knowledge.py"
assert_contains "$contents" "./usr/share/applications/ooonana-openvino.desktop"
assert_contains "$(<"$ROOT/packages/openvino-chat/rootfs/usr/share/applications/ooonana-openvino.desktop")" "Icon=/usr/share/ooonana/logo.png"

printf 'ok openvino-chat-package\n'
