#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ -x "$CLI" ]] || fail "missing executable CLI"

first_line="$(sed -n '1p' "$CLI")"
[[ "$first_line" == "#!/bin/sh" ]] || fail "CLI must use /bin/sh shebang: $first_line"

version="$("$CLI" version)"
[[ "$version" == "ooonana 0.3.0" ]] || fail "bad version: $version"

sh_version="$(sh "$CLI" version)"
[[ "$sh_version" == "ooonana 0.3.0" ]] || fail "bad sh version: $sh_version"

doctor="$("$CLI" doctor || true)"
[[ "$doctor" == *"kernel:"* ]] || fail "doctor missing kernel"
[[ "$doctor" == *"apt:"* ]] || fail "doctor missing apt"

ai_doctor="$("$CLI" ai doctor || true)"
[[ "$ai_doctor" == *"AI config missing"* ]] || fail "ai doctor missing config guard"

pkg_help="$("$CLI" help)"
[[ "$pkg_help" == *"ooonana get PACKAGE"* ]] || fail "help missing package manager"

printf 'ok cli\n'
