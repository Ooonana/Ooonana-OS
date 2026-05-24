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
[[ "$version" == "ooonana 0.2.0" ]] || fail "bad version: $version"

doctor="$("$CLI" doctor || true)"
[[ "$doctor" == *"kernel:"* ]] || fail "doctor missing kernel"
[[ "$doctor" == *"apt:"* ]] || fail "doctor missing apt"

ai_doctor="$("$CLI" ai doctor || true)"
[[ "$ai_doctor" == *"AI config missing"* ]] || fail "ai doctor missing config guard"

pkg_help="$("$CLI" help)"
[[ "$pkg_help" == *"ooonana get PACKAGE"* ]] || fail "help missing package manager"

printf 'ok cli\n'
