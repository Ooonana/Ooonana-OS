#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
BUNANA="$ROOT/packages/ooonana/usr/bin/bunana"
OONANA_GAME="$ROOT/packages/ooonana/usr/bin/oonana"
NEOFETCH="$ROOT/packages/ooonana/usr/bin/neofetch"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ -x "$CLI" ]] || fail "missing executable CLI"
[[ -x "$BUNANA" ]] || fail "missing bunana command"
[[ -x "$OONANA_GAME" ]] || fail "missing oonana game"
[[ -x "$NEOFETCH" ]] || fail "missing neofetch fallback"
[[ -f "$ROOT/packages/ooonana/etc/neofetch/config.conf" ]] || fail "missing neofetch config"

first_line="$(sed -n '1p' "$CLI")"
[[ "$first_line" == "#!/bin/sh" ]] || fail "CLI must use /bin/sh shebang: $first_line"

version="$("$CLI" version)"
[[ "$version" == "ooonana 0.8.0" ]] || fail "bad version: $version"

sh_version="$(sh "$CLI" version)"
[[ "$sh_version" == "ooonana 0.8.0" ]] || fail "bad sh version: $sh_version"

doctor="$("$CLI" doctor || true)"
[[ "$doctor" == *"kernel:"* ]] || fail "doctor missing kernel"
[[ "$doctor" == *"apt:"* ]] || fail "doctor missing apt"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ai_doctor="$(OOONANA_AI_CONFIG="$tmp/missing-ai.env" "$CLI" ai doctor || true)"
[[ "$ai_doctor" == *"AI config missing"* ]] || fail "ai doctor missing config guard"

pkg_help="$("$CLI" help)"
[[ "$pkg_help" == *"ooonana get PACKAGE"* ]] || fail "help missing package manager"
[[ "$pkg_help" == *"ooonana search QUERY"* ]] || fail "help missing search"
[[ "$pkg_help" == *"ooonana upgrade [PACKAGE...]"* ]] || fail "help missing upgrade"
[[ "$pkg_help" == *"ooonana verify PACKAGE"* ]] || fail "help missing verify"
[[ "$pkg_help" == *"ooonana repo index [PATH]"* ]] || fail "help missing repo index"
[[ "$pkg_help" == *"ooonana me"* ]] || fail "help missing me"
[[ "$pkg_help" == *"ooonana wsl [doctor|status]"* ]] || fail "help missing wsl"

me="$("$CLI" me)"
[[ "$me" == *"Ooonana OS"* ]] || fail "me missing label"
[[ "$me" == *"__________________"* ]] || fail "me missing logo"
[[ "$me" == *"\\______/"* ]] || fail "me missing face"

wsl="$("$CLI" wsl status)"
[[ "$wsl" == *"wsl:"* ]] || fail "wsl missing state"
[[ "$wsl" == *"qemu:"* ]] || fail "wsl missing qemu"

bunana_help="$("$BUNANA" --help)"
[[ "$bunana_help" == *"bunana --restart"* ]] || fail "bunana help missing restart"
game_help="$("$OONANA_GAME" --help)"
[[ "$game_help" == *"Ooonana brickout"* ]] || fail "oonana game help missing"
game_quit="$(printf 'q\n' | NO_COLOR=1 "$OONANA_GAME")"
[[ "$game_quit" == *"oonana brickout"* ]] || fail "oonana game did not draw"
[[ "$game_quit" == *"bye. score:"* ]] || fail "oonana game did not quit cleanly"
neofetch_out="$("$NEOFETCH")"
[[ "$neofetch_out" == *"Ooonana OS"* ]] || fail "neofetch missing logo"
grep -q 'ascii_distro="Ooonana"' "$ROOT/packages/ooonana/etc/neofetch/config.conf" || fail "neofetch config missing Ooonana logo"

printf 'ok cli\n'
