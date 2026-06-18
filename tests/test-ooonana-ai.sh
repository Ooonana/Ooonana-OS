#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
AI_WRAPPER="$ROOT/packages/ooonana/usr/bin/ooonana-ai"
AI_DESKTOP_APP="$ROOT/packages/ooonana/usr/bin/ooonana-ai-app"
AI_LAUNCHER="$ROOT/packages/ooonana/usr/bin/ooonana-ai-launch"
AI_DESKTOP_FILE="$ROOT/packages/ooonana/usr/share/applications/ooonana-ai.desktop"
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
[[ -x "$AI_DESKTOP_APP" ]] || fail "missing executable AI desktop app"
[[ -x "$AI_LAUNCHER" ]] || fail "missing executable AI launcher"
[[ -f "$AI_DESKTOP_FILE" ]] || fail "missing AI desktop file"
[[ -f "$AI_APP" ]] || fail "missing AI app"
assert_contains "$(<"$AI_DESKTOP_APP")" 'xterm -title "Ooonana AI"'
assert_contains "$(<"$AI_DESKTOP_APP")" "yad --center --title \"Ooonana AI\""
assert_contains "$(<"$AI_DESKTOP_APP")" "OOONANA_AI_APP_GUI_OK"
assert_contains "$(<"$AI_DESKTOP_APP")" "show_home"
assert_contains "$(<"$AI_DESKTOP_APP")" "choose_action"
assert_contains "$(<"$AI_DESKTOP_APP")" "ask_gui"
assert_contains "$(<"$AI_DESKTOP_APP")" "chat_gui"
assert_contains "$(<"$AI_DESKTOP_APP")" "OOONANA_AI_CHAT_GUI_OK"
assert_contains "$(<"$AI_DESKTOP_APP")" "provider_model_gui"
assert_contains "$(<"$AI_DESKTOP_APP")" "render_status"
assert_contains "$(<"$AI_DESKTOP_APP")" "run_gui_text"
assert_contains "$(<"$AI_DESKTOP_APP")" "tools registry"
assert_contains "$(<"$AI_DESKTOP_APP")" "permissions_gui"
assert_contains "$(<"$AI_DESKTOP_APP")" "logs_gui"
assert_contains "$(<"$AI_DESKTOP_APP")" "desktop_control_gui"
assert_contains "$(<"$AI_DESKTOP_APP")" "if open_gui"
assert_contains "$(<"$AI_LAUNCHER")" "OOONANA_AI_LAUNCH_OK"
assert_contains "$(<"$AI_LAUNCHER")" "ooonana-ai-app"
assert_contains "$(<"$AI_DESKTOP_FILE")" "Exec=ooonana-ai-launch"
assert_contains "$(<"$AI_DESKTOP_APP")" "XTERM_FONT_ARGS='-fa monospace -fs 10'"
assert_contains "$(<"$AI_DESKTOP_APP")" '$XTERM_FONT_ARGS -title "Ooonana AI"'
assert_contains "$(<"$AI_DESKTOP_APP")" '$XTERM_FONT_ARGS -title "$title"'

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
config="$tmp/ai.env"
state="$tmp/state"
export OOONANA_AI_STATE_DIR="$state"

fake_app_bin="$tmp/fake-app-bin"
mkdir -p "$fake_app_bin"
cat > "$fake_app_bin/ooonana-ai" <<'EOF'
#!/bin/sh
printf 'FAKE_AI %s\n' "$*"
case "${1:-}" in
  status) printf 'Ooonana AI status\nprovider: fake\n' ;;
  tools) printf 'Ooonana CLI tool registry\n' ;;
  tasks) printf 'No tasks\n' ;;
  sessions) printf 'No sessions\n' ;;
  chat) printf 'fake chat opened\n' ;;
esac
EOF
chmod +x "$fake_app_bin/ooonana-ai"

app_oneshot="$(PATH="$fake_app_bin:$PATH" OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_ONESHOT=1 "$AI_DESKTOP_APP")"
assert_contains "$app_oneshot" "Ooonana AI native app"
assert_contains "$app_oneshot" "FAKE_AI status"
assert_contains "$app_oneshot" "Status panel"
assert_contains "$app_oneshot" "Quick actions"
assert_contains "$app_oneshot" "1  chat"
assert_contains "$app_oneshot" "6  setup"
assert_contains "$app_oneshot" "8  desktop"
assert_contains "$app_oneshot" "12 model"
assert_contains "$app_oneshot" "14 permissions"
assert_contains "$app_oneshot" "15 logs"
assert_contains "$app_oneshot" "16 desktop-control"

app_gui_dry="$("$AI_DESKTOP_APP" --dry-run)"
assert_contains "$app_gui_dry" "yad Ooonana AI dashboard"
assert_contains "$app_gui_dry" "status provider model tools tasks audit history desktop desktop-control permissions logs"
assert_contains "$app_gui_dry" "dashboard tabs: home actions ask provider-model logs"
assert_contains "$app_gui_dry" "dashboard sections: Home Ask Chat Tools Desktop Permissions Logs"
assert_contains "$app_gui_dry" "grouped actions: Prompt Health Config Tools Desktop Logs Safety Terminal"
assert_contains "$app_gui_dry" "icon command center"
assert_contains "$app_gui_dry" "persistent GUI loop"
assert_contains "$app_gui_dry" "gui chat: transcript prompt loop buttons ask status model provider tools clear save close"
assert_contains "$app_gui_dry" "gui controls: ask form provider/model action launcher desktop-control permissions logs"
assert_contains "$app_gui_dry" "permissions: shell actions gated"
assert_contains "$app_gui_dry" "OOONANA_AI_APP_GUI_OK"
assert_contains "$(<"$AI_DESKTOP_APP")" "--column Icon --column Action"
assert_contains "$(<"$AI_DESKTOP_APP")" "while :; do"
assert_contains "$(<"$AI_DESKTOP_APP")" "chat_gui || open_action_terminal chat"
assert_not_contains "$(<"$AI_DESKTOP_APP")" "Open interactive chat terminal"
launcher_dry="$("$AI_LAUNCHER" --dry-run)"
assert_contains "$launcher_dry" "OOONANA_AI_LAUNCH_OK"

app_tools="$(PATH="$fake_app_bin:$PATH" OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_COMMAND=tools "$AI_DESKTOP_APP")"
assert_contains "$app_tools" "Ooonana CLI tool registry"
assert_contains "$app_tools" "FAKE_AI tools"

app_desktop="$(PATH="$fake_app_bin:$PATH" OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_COMMAND=desktop "$AI_DESKTOP_APP")"
assert_contains "$app_desktop" "FAKE_AI tool desktop"
app_permissions="$(PATH="$fake_app_bin:$PATH" OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_COMMAND=permissions OOONANA_AI_APP_ONESHOT=1 "$AI_DESKTOP_APP")"
assert_contains "$app_permissions" "permissions: shell blocked unless --yes"
app_desktop_control="$(PATH="$fake_app_bin:$PATH" OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_COMMAND=desktop-control OOONANA_AI_APP_ONESHOT=1 "$AI_DESKTOP_APP")"
assert_contains "$app_desktop_control" "desktop-control: terminal browser files settings restart-i3"

setup="$(OOONANA_AI_CONFIG="$config" "$CLI" ai setup)"
assert_contains "$setup" "AI config:"
assert_contains "$(<"$config")" "NVIDIA_API_KEY="
assert_contains "$(<"$config")" "GEMINI_API_KEY="
assert_contains "$(<"$config")" "OOONANA_AI_PROVIDER=nim"
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

fallback_config="$tmp/fallback.env"
cp "$config" "$fallback_config"
fallback_provider="$(OOONANA_AI_APP="$tmp/missing.py" OOONANA_AI_CONFIG="$fallback_config" "$CLI" ai provider)"
assert_contains "$fallback_provider" "active: nim"
assert_contains "$fallback_provider" "key: present"
fallback_wrapper_provider="$(OOONANA_AI_APP="$tmp/missing.py" "$AI_WRAPPER" --config "$fallback_config" provider)"
assert_contains "$fallback_wrapper_provider" "active: nim"
assert_contains "$fallback_wrapper_provider" "key: present"
fallback_tools="$(OOONANA_AI_APP="$tmp/missing.py" OOONANA_AI_CONFIG="$fallback_config" "$CLI" ai tools)"
assert_contains "$fallback_tools" "Ooonana CLI tool registry"
assert_contains "$fallback_tools" "desktop"
assert_contains "$fallback_tools" "shell"
fallback_desktop="$(OOONANA_AI_APP="$tmp/missing.py" OOONANA_AI_CONFIG="$fallback_config" "$CLI" ai tool desktop)"
assert_contains "$fallback_desktop" "[desktop]"
assert_contains "$fallback_desktop" "display:"
assert_contains "$fallback_desktop" "i3-msg:"
fallback_status="$(OOONANA_AI_APP="$tmp/missing.py" OOONANA_AI_CONFIG="$fallback_config" "$CLI" ai status)"
assert_contains "$fallback_status" "Ooonana AI status"
assert_contains "$fallback_status" "python: missing"
fallback_provider_set="$(OOONANA_AI_APP="$tmp/missing.py" OOONANA_AI_CONFIG="$fallback_config" "$CLI" ai provider set gemini)"
assert_contains "$fallback_provider_set" "provider: gemini"
assert_contains "$(<"$fallback_config")" "OOONANA_AI_PROVIDER=gemini"

config_out="$(OOONANA_AI_CONFIG="$config" "$CLI" ai config)"
assert_contains "$config_out" "redacted"
assert_not_contains "$config_out" "test-key"

dry_run="$(OOONANA_AI_CONFIG="$config" "$CLI" ai ask --dry-run "explain this machine")"
assert_contains "$dry_run" '"model": "qwen/qwen3-coder-480b-a35b-instruct"'
assert_contains "$dry_run" "You are Ooonana"
assert_contains "$dry_run" "Current Linux environment snapshot"
assert_contains "$dry_run" "Ooonana local agent context (activity)"
assert_contains "$dry_run" "assistant_name: Ooonana"
assert_contains "$dry_run" "[workspace]"
assert_contains "$dry_run" "CLI-first terminal interface"
assert_contains "$dry_run" "Ooonana CLI tool registry"
assert_contains "$dry_run" "permission-gated shell/file actions"
assert_not_contains "$dry_run" "voice readiness"
assert_not_contains "$dry_run" "test-key"

alias_dry_run="$(OOONANA_AI_CONFIG="$config" "$CLI" ai ask --model code --dry-run "write shell")"
assert_contains "$alias_dry_run" '"model": "qwen/qwen3-coder-480b-a35b-instruct"'

mock="$(OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$CLI" ai code --json "name yourself")"
assert_contains "$mock" '"content":'
assert_contains "$mock" "Ooonana mock response"

models="$("$CLI" ai models)"
assert_contains "$models" "qwen/qwen3-coder-480b-a35b-instruct"

model_show="$(OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$AI_WRAPPER" model)"
assert_contains "$model_show" "active: qwen/qwen3-coder-480b-a35b-instruct"
assert_contains "$model_show" "aliases:"
assert_contains "$model_show" "code: qwen/qwen3-coder-480b-a35b-instruct"

model_set="$(OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$AI_WRAPPER" model set fast)"
assert_contains "$model_set" "default model: qwen/qwen3-next-80b-a3b-instruct"
assert_contains "$(<"$config")" "OOONANA_NIM_MODEL=qwen/qwen3-next-80b-a3b-instruct"

model_alias="$(OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$AI_WRAPPER" model alias tiny meta/llama-3.3-70b-instruct)"
assert_contains "$model_alias" "alias tiny: meta/llama-3.3-70b-instruct"
assert_contains "$(<"$config")" "OOONANA_MODEL_TINY=meta/llama-3.3-70b-instruct"

tiny_dry_run="$(OOONANA_AI_CONFIG="$config" "$AI_WRAPPER" --model tiny --dry-run "small answer")"
assert_contains "$tiny_dry_run" '"model": "meta/llama-3.3-70b-instruct"'

chat_model_ui="$(printf '/models\n/model set code\n/model\n/exit\n' | OOONANA_AI_CONFIG="$config" "$AI_WRAPPER" chat --no-stream)"
assert_contains "$chat_model_ui" "aliases:"
assert_contains "$chat_model_ui" "default model: qwen/qwen3-coder-480b-a35b-instruct"
assert_contains "$chat_model_ui" "active: qwen/qwen3-coder-480b-a35b-instruct"

gemini_config="$tmp/gemini.env"
cat > "$gemini_config" <<'EOF'
GEMINI_API_KEY=gemini-test-key
OOONANA_AI_PROVIDER=gemini
OOONANA_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
OOONANA_GEMINI_MODEL=gemini-2.5-flash
OOONANA_GEMINI_MODEL_DEEP=gemini-2.5-pro
OOONANA_AI_MAX_TOKENS=256
OOONANA_AI_TEMPERATURE=0.1
OOONANA_AI_STREAM=0
EOF

gemini_doctor="$(OOONANA_AI_CONFIG="$gemini_config" "$CLI" ai doctor)"
assert_contains "$gemini_doctor" "AI config: ok"
assert_contains "$gemini_doctor" "provider: Google Gemini"
assert_contains "$gemini_doctor" "model: gemini-2.5-flash"
assert_contains "$gemini_doctor" "deep: gemini-2.5-pro"

gemini_config_out="$(OOONANA_AI_CONFIG="$gemini_config" "$CLI" ai config)"
assert_contains "$gemini_config_out" "redacted"
assert_not_contains "$gemini_config_out" "gemini-test-key"

provider_show="$(OOONANA_AI_CONFIG="$gemini_config" "$AI_WRAPPER" provider)"
assert_contains "$provider_show" "active: gemini"
assert_contains "$provider_show" "key: present"

provider_set="$(OOONANA_AI_CONFIG="$gemini_config" "$AI_WRAPPER" provider set nim)"
assert_contains "$provider_set" "provider: nim"
assert_contains "$(<"$gemini_config")" "OOONANA_AI_PROVIDER=nim"
OOONANA_AI_CONFIG="$gemini_config" "$AI_WRAPPER" provider set gemini >/dev/null

gemini_model_set="$(OOONANA_AI_CONFIG="$gemini_config" "$AI_WRAPPER" model set deep)"
assert_contains "$gemini_model_set" "default model: gemini-2.5-pro"
assert_contains "$(<"$gemini_config")" "OOONANA_GEMINI_MODEL=gemini-2.5-pro"

gemini_dry_run="$(OOONANA_AI_CONFIG="$gemini_config" "$AI_WRAPPER" --provider gemini --dry-run "hello gemini")"
assert_contains "$gemini_dry_run" '"provider": "gemini"'
assert_contains "$gemini_dry_run" '"model": "gemini-2.5-pro"'
assert_contains "$gemini_dry_run" '"system_instruction"'
assert_contains "$gemini_dry_run" '"contents"'
assert_contains "$gemini_dry_run" "Current Linux environment snapshot"
assert_contains "$gemini_dry_run" "hello gemini"
assert_not_contains "$gemini_dry_run" "gemini-test-key"

gemini_mock="$(OOONANA_AI_CONFIG="$gemini_config" OOONANA_AI_MOCK=1 "$AI_WRAPPER" --provider gemini --no-stream "mock gemini")"
assert_contains "$gemini_mock" "Ooonana mock response"

gemini_chat_ui="$(printf '/provider\n/provider set nim\n/provider set gemini\n/models\n/model\n/exit\n' | OOONANA_AI_CONFIG="$gemini_config" "$AI_WRAPPER" chat --no-stream)"
assert_contains "$gemini_chat_ui" "active provider: gemini"
assert_contains "$gemini_chat_ui" "provider: nim"
assert_contains "$gemini_chat_ui" "provider: gemini"
assert_contains "$gemini_chat_ui" "gemini-2.5-flash"

agents="$("$AI_WRAPPER" agents)"
assert_contains "$agents" "system"
assert_contains "$agents" "activity"
assert_contains "$agents" "summarizer"
assert_contains "$agents" "tools"

activity="$("$AI_WRAPPER" agent activity)"
assert_contains "$activity" "recent shell history"
assert_contains "$activity" "recent Ooonana AI history"

tools="$("$AI_WRAPPER" tools)"
assert_contains "$tools" "processes"
assert_contains "$tools" "packages"
assert_contains "$tools" "files"
assert_contains "$tools" "desktop"
assert_contains "$tools" "shell"

desktop="$("$AI_WRAPPER" tool desktop)"
assert_contains "$desktop" "[desktop]"
assert_contains "$desktop" "display:"
assert_contains "$desktop" "i3-msg:"
assert_contains "$desktop" "xterm:"

processes="$("$AI_WRAPPER" tool processes)"
assert_contains "$processes" "PID"

files="$("$AI_WRAPPER" tool files "$tmp")"
assert_contains "$files" "ai.env"
assert_contains "$files" "gemini.env"

shell_blocked="$("$AI_WRAPPER" --state-dir "$state" tool shell echo hi)"
assert_contains "$shell_blocked" "blocked: add --yes"
audit_after_shell="$("$AI_WRAPPER" --state-dir "$state" audit)"
assert_contains "$audit_after_shell" "tool shell"
assert_contains "$audit_after_shell" "blocked"

task_add="$("$AI_WRAPPER" --state-dir "$state" task add "wire Jarvis-style tools into CLI")"
assert_contains "$task_add" "task:"
task_id="$(printf '%s\n' "$task_add" | awk '{print $2}')"
tasks_list="$("$AI_WRAPPER" --state-dir "$state" tasks)"
assert_contains "$tasks_list" "wire Jarvis-style tools into CLI"
task_done="$("$AI_WRAPPER" --state-dir "$state" task done "$task_id")"
assert_contains "$task_done" "done: $task_id"
task_plan="$("$AI_WRAPPER" task plan "inspect system safely")"
assert_contains "$task_plan" "1. inspect"
assert_contains "$task_plan" "2. propose"
assert_contains "$task_plan" "3. execute"

chat_tools_ui="$(printf '/tools\n/task plan inspect safely\n/audit\n/exit\n' | OOONANA_AI_CONFIG="$config" "$AI_WRAPPER" --state-dir "$state" chat --no-stream)"
assert_contains "$chat_tools_ui" "Ooonana CLI tool registry"
assert_contains "$chat_tools_ui" "1. inspect"
assert_contains "$chat_tools_ui" "tool shell"

status="$("$AI_WRAPPER" status --model code)"
assert_contains "$status" "Ooonana AI status"
assert_contains "$status" "provider: NVIDIA NIM"
assert_contains "$status" "qwen/qwen3-coder-480b-a35b-instruct"

ping="$(OOONANA_AI_MOCK=1 "$AI_WRAPPER" ping --model code)"
assert_contains "$ping" "Ooonana mock response"

help="$("$AI_WRAPPER" help)"
assert_contains "$help" "Ooonana AI CLI for NVIDIA NIM"
assert_contains "$help" "ask"
assert_contains "$help" "chat"

direct_message="$(OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$AI_WRAPPER" "hello from the wrapper")"
assert_contains "$direct_message" "Ooonana mock response"
assert_contains "$direct_message" "hello from the wrapper"

history_after_direct="$("$AI_WRAPPER" --state-dir "$state" history)"
assert_contains "$history_after_direct" "hello from the wrapper"

direct_option_message="$(OOONANA_AI_CONFIG="$config" "$AI_WRAPPER" --model code --dry-run "write shell")"
assert_contains "$direct_option_message" '"model": "qwen/qwen3-coder-480b-a35b-instruct"'
assert_contains "$direct_option_message" '"content": "write shell"'

direct_config_message="$("$AI_WRAPPER" --config "$config" --model code --dry-run "configured shell")"
assert_contains "$direct_config_message" '"model": "qwen/qwen3-coder-480b-a35b-instruct"'
assert_contains "$direct_config_message" '"content": "configured shell"'

chat_ui="$(printf '/status\n/exit\n' | OOONANA_AI_CONFIG="$config" "$AI_WRAPPER" chat --no-stream)"
assert_contains "$chat_ui" "Ooonana AI"
assert_contains "$chat_ui" "mode: chat"
assert_contains "$chat_ui" "ooonana ai>"

rewind_ui="$(printf 'first turn\nsecond turn\n/history\n/rewind\n/history\n/exit\n' | OOONANA_AI_CONFIG="$config" OOONANA_AI_MOCK=1 "$AI_WRAPPER" chat --session rewind-test --no-stream)"
assert_contains "$rewind_ui" "first turn"
assert_contains "$rewind_ui" "second turn"
assert_contains "$rewind_ui" "rewound 1 turn(s)"
session_json="$(cat "$state/sessions/rewind-test.jsonl")"
assert_contains "$session_json" "first turn"
assert_not_contains "$session_json" "second turn"

default_chat_ui="$(printf '/exit\n' | OOONANA_AI_CONFIG="$config" "$AI_WRAPPER")"
assert_contains "$default_chat_ui" "Ooonana AI"
assert_contains "$default_chat_ui" "mode: chat"

install_out="$(OOONANA_WSL_BIN_DIR="$tmp/bin" bash "$ROOT/scripts/install-ooonana-ai-wsl.sh")"
assert_contains "$install_out" "installed ooonana"
[[ -L "$tmp/bin/ooonana" ]] || fail "install script missing ooonana symlink"
[[ -L "$tmp/bin/ooonana-ai" ]] || fail "install script missing ooonana-ai symlink"
symlink_status="$(PATH="$tmp/bin:$PATH" OOONANA_AI_CONFIG="$config" ooonana-ai status --model code)"
assert_contains "$symlink_status" "Ooonana AI status"
assert_contains "$symlink_status" "qwen/qwen3-coder-480b-a35b-instruct"

printf 'ok ooonana-ai\n'
