#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ -x "$CLI" ]] || fail "missing executable CLI"

version="$("$CLI" version)"
[[ "$version" == "ooonana 0.3.0" ]] || fail "bad version: $version"

doctor="$("$CLI" doctor || true)"
[[ "$doctor" == *"kernel:"* ]] || fail "doctor missing kernel"
[[ "$doctor" == *"apt:"* ]] || fail "doctor missing apt"

ai_doctor="$("$CLI" ai doctor || true)"
[[ "$ai_doctor" == *"AI config missing"* ]] || fail "ai doctor missing config guard"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
config="$tmp/ai.env"
setup="$(OOONANA_AI_CONFIG="$config" "$CLI" ai setup)"
[[ "$setup" == *"AI config:"* ]] || fail "ai setup did not print config path"
[[ -f "$config" ]] || fail "ai setup did not create config"

ai_missing_key="$(OOONANA_AI_CONFIG="$config" "$CLI" ai doctor || true)"
[[ "$ai_missing_key" == *"AI config missing NVIDIA_API_KEY"* ]] || fail "ai doctor missing NVIDIA key guard"

env_context="$("$CLI" ai env)"
[[ "$env_context" == *"assistant_name: Ooonana"* ]] || fail "ai env missing identity"
[[ "$env_context" == *"uname:"* ]] || fail "ai env missing uname"
[[ "$env_context" == *"[workspace]"* ]] || fail "ai env missing workspace"

models="$("$CLI" ai models)"
[[ "$models" == *"nvidia/nemotron-3-super-120b-a12b"* ]] || fail "ai models missing default NIM model"

status="$("$CLI" ai status)"
[[ "$status" == *"Ooonana AI status"* ]] || fail "ai status missing title"
[[ "$status" == *"provider: NVIDIA NIM"* ]] || fail "ai status missing provider"

ping="$(OOONANA_AI_MOCK=1 "$CLI" ai ping)"
[[ "$ping" == *"Ooonana mock response"* ]] || fail "ai ping mock did not run"

mock="$(OOONANA_AI_MOCK=1 "$CLI" ai ask --no-stream "who are you?")"
[[ "$mock" == *"Ooonana mock response"* ]] || fail "ai ask mock did not run"

pkg_help="$("$CLI" help)"
[[ "$pkg_help" == *"ooonana get PACKAGE"* ]] || fail "help missing package manager"
[[ "$pkg_help" == *"ooonana ai chat"* ]] || fail "help missing ai chat"

printf 'ok cli\n'
