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
[[ -x "$ROOT/packages/ooonana/usr/bin/ooonana-ai-launch" ]] || fail "missing ai launch wrapper"
[[ -x "$BUNANA" ]] || fail "missing bunana command"
[[ -x "$OONANA_GAME" ]] || fail "missing oonana game"
[[ -x "$ROOT/packages/ooonana/usr/bin/ooonana-game-launch" ]] || fail "missing game launcher"
[[ -f "$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py" ]] || fail "missing Python oonana game"
[[ -f "$ROOT/packages/ooonana/var/lib/ooonana/packages/installed/ooonana-core.pkg" ]] || fail "missing native core package state"
[[ -f "$ROOT/packages/ooonana/usr/share/applications/oonana.desktop" ]] || fail "missing oonana desktop launcher"
[[ -x "$NEOFETCH" ]] || fail "missing neofetch fallback"
[[ -f "$ROOT/packages/ooonana/etc/neofetch/config.conf" ]] || fail "missing neofetch config"

first_line="$(sed -n '1p' "$CLI")"
[[ "$first_line" == "#!/bin/sh" ]] || fail "CLI must use /bin/sh shebang: $first_line"

version="$("$CLI" version)"
[[ "$version" == "ooonana 0.8.18" ]] || fail "bad version: $version"

sh_version="$(sh "$CLI" version)"
[[ "$sh_version" == "ooonana 0.8.18" ]] || fail "bad sh version: $sh_version"

doctor="$("$CLI" doctor || true)"
[[ "$doctor" == *"kernel:"* ]] || fail "doctor missing kernel"
[[ "$doctor" == *"apt:"* ]] || fail "doctor missing apt"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/lib/ooonana"
cp "$OONANA_GAME" "$tmp/bin/oonana"
cp "$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py" "$tmp/lib/ooonana/oonana_game.py"
chmod 0755 "$tmp/bin/oonana"
chmod 0644 "$tmp/lib/ooonana/oonana_game.py"
readonly_game_help="$("$tmp/bin/oonana" --help)"
[[ "$readonly_game_help" == *"Ooonana brickout"* ]] || fail "readable Python game did not launch"

ai_doctor="$(OOONANA_AI_CONFIG="$tmp/missing-ai.env" "$CLI" ai doctor || true)"
[[ "$ai_doctor" == *"AI config missing"* ]] || fail "ai doctor missing config guard"

pkg_help="$("$CLI" help)"
pkg_help_lines="$(printf '%s\n' "$pkg_help" | wc -l | tr -d ' ')"
[[ "$pkg_help_lines" -le 55 ]] || fail "help too long: $pkg_help_lines lines"
[[ "$pkg_help" == *"ooonana 0.8.18"* ]] || fail "help missing version header"
[[ "$pkg_help" == *"Usage: ooonana [options] command"* ]] || fail "help missing apt-style usage"
[[ "$pkg_help" == *"Ooonana is a commandline package manager"* ]] || fail "help missing package manager summary"
[[ "$pkg_help" == *"Most used commands:"* ]] || fail "help missing most used section"
[[ "$pkg_help" == *"  install - install packages"* ]] || fail "help missing install command"
[[ "$pkg_help" == *"  search - search package names and descriptions"* ]] || fail "help missing search"
[[ "$pkg_help" == *"  upgrade - upgrade installed packages"* ]] || fail "help missing upgrade"
[[ "$pkg_help" == *"  verify - verify installed package files"* ]] || fail "help missing verify"
[[ "$pkg_help" == *"  repo - manage Ooonana package sources and indexes"* ]] || fail "help missing repo"
[[ "$pkg_help" == *"  me - show Ooonana logo"* ]] || fail "help missing me"
[[ "$pkg_help" == *"  wsl - check WSL helper distro"* ]] || fail "help missing wsl"
[[ "$pkg_help" == *"See 'ooonana help packages'"* ]] || fail "help missing topic hint"
[[ "$pkg_help" != *"ooonana ai provider [show|set nim|set gemini]"* ]] || fail "main help too detailed"
usage_alias="$("$CLI" usage)"
[[ "$usage_alias" == "$pkg_help" ]] || fail "usage alias differs from help"
reinstall_dry="$(OOONANA_ROOT="$tmp/root" "$CLI" reinstall nano --dry-run 2>&1 || true)"
[[ "$reinstall_dry" == *"would update repos"* ]] || fail "reinstall alias missing"

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
[[ "$game_help" == *"Installer game engine"* ]] || fail "oonana game help missing installer engine"
[[ "$game_help" == *"Bricks spell OOONANA OS"* ]] || fail "oonana game help missing word"
[[ "$game_help" == *"real-time Python terminal game"* ]] || fail "oonana game help missing real-time mode"
[[ "$game_help" == *"full Ooonana logo ball"* ]] || fail "oonana game help missing logo ball"
[[ "$game_help" == *"combo"* ]] || fail "oonana game help missing combo"
[[ "$game_help" == *"arrow keys"* ]] || fail "oonana game help missing arrow keys"
[[ "$game_help" == *"p      pause"* ]] || fail "oonana game help missing pause"
[[ "$game_help" == *"r      restart"* ]] || fail "oonana game help missing restart"
[[ "$game_help" == *"1/2/3  speed"* ]] || fail "oonana game help missing speed controls"
[[ "$game_help" == *"q      quit"* ]] || fail "oonana game help missing quit"
game_quit="$(printf 'q\n' | NO_COLOR=1 "$OONANA_GAME" --snapshot)"
[[ "$game_quit" == *"Ooonana OS Breakout"* ]] || fail "oonana game did not draw"
[[ "$game_quit" == *"OOONANA OS"* ]] || fail "oonana game did not show brick word"
[[ "$game_quit" == *"combo:"* ]] || fail "oonana game did not show combo"
[[ "$game_quit" == *" __________"* ]] || fail "oonana game did not draw logo ball"
[[ "$game_quit" == *"/|   \\__/   |\\"* ]] || fail "oonana game did not draw straight logo arms"
[[ "$game_quit" == *"    |    |"* ]] || fail "oonana game did not draw logo legs"
[[ "$game_quit" == *"Speed: 2"* ]] || fail "oonana game did not show speed"
[[ "$game_quit" == *"bye. score:"* ]] || fail "oonana game did not quit cleanly"
game_src="$(<"$OONANA_GAME")"
[[ "$game_src" == *"exec python3"* ]] || fail "oonana wrapper must use python game"
[[ "$game_src" == *'[ -r "$GAME" ]'* ]] || fail "oonana wrapper must accept readable Python game"
game_py="$(<"$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py")"
[[ "$game_py" == *"BRICKS_MAP"* ]] || fail "python game missing brick map"
[[ "$game_py" == *"LOGO_BALL"* ]] || fail "python game missing logo ball"
[[ "$game_py" == *"BALL_FACES"* ]] || fail "python game missing ball faces"
[[ "$game_py" == *"def render_diff("* ]] || fail "python game missing row-diff renderer"
[[ "$game_py" == *"def decode_key("* ]] || fail "python game missing escape decoder"
[[ "$game_py" == *"def game_dimensions("* ]] || fail "python game missing terminal sizing"
[[ "$game_py" == *"\\033[{row};1H"* ]] || fail "python game must repaint changed rows"
NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py" <<'PY' || fail "oonana game behavior failed"
import importlib.util
import os
import pty
import sys
import threading
import time
import tty

spec = importlib.util.spec_from_file_location("oonana_game", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.decode_key("\x1b", "[D") == "left"
assert module.decode_key("\x1b", "[C") == "right"
assert module.decode_key("\x1b", "OD") == "left"
assert module.decode_key("\x1b", "OC") == "right"
assert module.decode_key("\x1b", "[1;5D") == "left"
assert module.decode_key("\x1b", "[1;5C") == "right"
game = module.Game(width=112, height=38)
assert game.width == 112 and game.height == 38
assert all(len(line) == 112 for line in game.render_lines())
start = game.paddle_x
game.handle_key("left")
assert game.paddle_x < start
game.handle_key("right")
assert game.paddle_x == start

master, slave = pty.openpty()
old_stdin = module.sys.stdin

class PtyInput:
    def fileno(self):
        return slave

try:
    tty.setcbreak(slave)
    module.sys.stdin = PtyInput()

    def send_fragmented_arrow():
        os.write(master, b"\x1b")
        time.sleep(0.03)
        os.write(master, b"[")
        time.sleep(0.03)
        os.write(master, b"D")

    sender = threading.Thread(target=send_fragmented_arrow)
    sender.start()
    assert module.get_key(0.3) == "left"
    sender.join()
finally:
    module.sys.stdin = old_stdin
    os.close(master)
    os.close(slave)
PY
[[ "$(<"$ROOT/packages/ooonana/usr/share/applications/oonana.desktop")" == *"Exec=ooonana-game-launch"* ]] || fail "oonana desktop launcher wrong exec"
[[ "$(<"$ROOT/packages/ooonana/usr/share/applications/oonana.desktop")" == *"Terminal=false"* ]] || fail "oonana desktop launcher must use dedicated terminal"
neofetch_out="$("$NEOFETCH")"
[[ "$neofetch_out" == *"Ooonana OS"* ]] || fail "neofetch missing logo"
grep -q 'ascii_distro="Ooonana"' "$ROOT/packages/ooonana/etc/neofetch/config.conf" || fail "neofetch config missing Ooonana logo"

printf 'ok cli\n'
