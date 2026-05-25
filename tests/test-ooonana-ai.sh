#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
AI_WRAPPER="$ROOT/packages/ooonana/usr/bin/ooonana-ai"
AI_APP="$ROOT/packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" != *"$needle"* ]] || fail "unexpected: $needle"
}

[[ -x "$CLI" ]] || fail "missing executable CLI"
[[ -x "$AI_WRAPPER" ]] || fail "missing executable AI wrapper"
[[ -f "$AI_APP" ]] || fail "missing AI app"
[[ "$(sed -n '1p' "$AI_WRAPPER")" == "#!/bin/sh" ]] || fail "AI wrapper must use /bin/sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
config="$tmp/ai.env"

setup="$(OOONANA_AI_CONFIG="$config" "$CLI" ai setup)"
assert_contains "$setup" "AI config:"
assert_contains "$(<"$config")" "NVIDIA_API_KEY="
assert_contains "$(<"$config")" "OOONANA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b"
assert_contains "$(<"$config")" "OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct"

doctor="$(OOONANA_AI_CONFIG="$config" "$CLI" ai doctor || true)"
assert_contains "$doctor" "AI config missing NVIDIA_API_KEY"

cat > "$config" <<'EOF'
NVIDIA_API_KEY=test-key
OOONANA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
OOONANA_NIM_MODEL=qwen/qwen3-coder-480b-a35b-instruct
OOONANA_AI_MAX_TOKENS=256
OOONANA_AI_TEMPERATURE=0.1
OOONANA_AI_STREAM=0
EOF

doctor_ok="$(OOONANA_AI_CONFIG="$config" "$CLI" ai doctor)"
assert_contains "$doctor_ok" "AI config: ok"
assert_contains "$doctor_ok" "provider: NVIDIA NIM"
assert_contains "$doctor_ok" "identity: Ooonana"
assert_contains "$doctor_ok" "code: qwen/qwen3-coder-480b-a35b-instruct"

config_out="$(OOONANA_AI_CONFIG="$config" "$CLI" ai config)"
assert_contains "$config_out" "redacted"
assert_not_contains "$config_out" "test-key"

dry_run="$(OOONANA_AI_CONFIG="$config" "$CLI" ai ask --dry-run "explain this machine")"
assert_contains "$dry_run" '"model": "qwen/qwen3-coder-480b-a35b-instruct"'
assert_contains "$dry_run" "You are Ooonana"
assert_contains "$dry_run" "Current Linux environment snapshot"
assert_contains "$dry_run" "assistant_name: Ooonana"
assert_contains "$dry_run" "[workspace]"
assert_not_contains "$dry_run" "test-key"

alias_dry_run="$(OOONANA_AI_CONFIG="$config" "$CLI" ai ask --model code --dry-run "write shell")"
assert_contains "$alias_dry_run" '"model": "qwen/qwen3-coder-480b-a35b-instruct"'

mock="$(OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$CLI" ai code --json "name yourself")"
assert_contains "$mock" '"content":'
assert_contains "$mock" "Ooonana mock response"

models="$("$CLI" ai models)"
assert_contains "$models" "qwen/qwen3-coder-480b-a35b-instruct"

status="$("$AI_WRAPPER" status --model code)"
assert_contains "$status" "Ooonana AI status"
assert_contains "$status" "provider: NVIDIA NIM"
assert_contains "$status" "qwen/qwen3-coder-480b-a35b-instruct"

ping="$(OOONANA_AI_MOCK=1 "$AI_WRAPPER" ping --model code)"
assert_contains "$ping" "Ooonana mock response"

chat_ui="$(printf '/status\n/exit\n' | OOONANA_AI_CONFIG="$config" "$AI_WRAPPER" chat --no-stream)"
assert_contains "$chat_ui" "Ooonana AI"
assert_contains "$chat_ui" "mode: chat"
assert_contains "$chat_ui" "ooonana ai>"

install_out="$(OOONANA_WSL_BIN_DIR="$tmp/bin" bash "$ROOT/scripts/install-ooonana-ai-wsl.sh")"
assert_contains "$install_out" "installed ooonana"
[[ -L "$tmp/bin/ooonana" ]] || fail "install script missing ooonana symlink"
[[ -L "$tmp/bin/ooonana-ai" ]] || fail "install script missing ooonana-ai symlink"
symlink_status="$(PATH="$tmp/bin:$PATH" OOONANA_AI_CONFIG="$config" ooonana-ai status --model code)"
assert_contains "$symlink_status" "Ooonana AI status"
assert_contains "$symlink_status" "qwen/qwen3-coder-480b-a35b-instruct"

printf 'ok ooonana-ai\n'
