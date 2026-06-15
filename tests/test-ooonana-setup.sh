#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
SETUP="$ROOT/packages/ooonana/usr/bin/ooonana-setup"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

[[ -x "$SETUP" ]] || fail "missing executable setup command"
setup_src="$(<"$SETUP")"
assert_contains "$setup_src" 'yad --center --title "Ooonana Setup"'
assert_contains "$setup_src" "OOONANA_SETUP_GUI_OK"
assert_contains "$setup_src" "fields: user password network address gateway dns theme cloud-repo done"
assert_contains "$setup_src" 'xterm -title "Ooonana Setup"'
assert_contains "$setup_src" 'OOONANA_THEME:-dark'
assert_contains "$setup_src" 'XTERM_BG="#050505"'
assert_contains "$setup_src" 'XTERM_BG="#ffb21a"'
assert_contains "$setup_src" '-cr "$XTERM_CURSOR"'

help="$("$SETUP" --help)"
assert_contains "$help" "Ooonana first-boot setup"
assert_contains "$help" "--first-boot"
assert_contains "$help" "--cloud-repo URI"
assert_contains "$help" "--network dhcp|static"
assert_contains "$help" "--user NAME"
assert_contains "$help" "--password"
assert_contains "$help" "--theme dark|light"

cli_help="$("$CLI" help)"
assert_contains "$cli_help" "ooonana setup"

dry="$("$CLI" setup --dry-run --user ryan --password --network dhcp --theme dark --cloud-repo https://example.test/repo --done)"
assert_contains "$dry" "would create user ryan"
assert_contains "$dry" "would set password for ryan"
assert_contains "$dry" "would configure dhcp network"
assert_contains "$dry" "would write theme dark"
assert_contains "$dry" "would add cloud repo https://example.test/repo"
assert_contains "$dry" "would mark setup done"
assert_contains "$dry" "OOONANA_SETUP_OK"

gui_dry="$("$SETUP" --gui --dry-run)"
assert_contains "$gui_dry" "yad setup gui"
assert_contains "$gui_dry" "fields: user password network address gateway dns theme cloud-repo done"
assert_contains "$gui_dry" "OOONANA_SETUP_GUI_OK"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
rootfs="$tmp/root"
mkdir -p "$rootfs/etc/ooonana/sources.d" "$rootfs/etc/network" "$rootfs/etc" "$rootfs/var/lib/ooonana"
cat > "$rootfs/etc/passwd" <<'EOF'
root:x:0:0:root:/root:/bin/sh
EOF
cat > "$rootfs/etc/group" <<'EOF'
root:x:0:
EOF

real_run="$(OOONANA_ROOT="$rootfs" "$SETUP" \
  --user ryan \
  --network static \
  --address 10.0.2.15/24 \
  --gateway 10.0.2.2 \
  --dns 1.1.1.1,8.8.8.8 \
  --theme light \
  --cloud-repo http://127.0.0.1/repo \
  --done)"
assert_contains "$real_run" "user: ryan"
assert_contains "$real_run" "network: static"
assert_contains "$real_run" "theme: light"
assert_contains "$real_run" "cloud repo: http://127.0.0.1/repo"
assert_contains "$real_run" "OOONANA_SETUP_OK"

assert_contains "$(<"$rootfs/etc/passwd")" "ryan:x:1000:1000:Ooonana User:/home/ryan:/bin/sh"
assert_contains "$(<"$rootfs/etc/group")" "ryan:x:1000:"
[[ -d "$rootfs/home/ryan" ]] || fail "missing user home"
assert_contains "$(<"$rootfs/etc/network/interfaces")" "iface eth0 inet static"
assert_contains "$(<"$rootfs/etc/network/interfaces")" "address 10.0.2.15/24"
assert_contains "$(<"$rootfs/etc/network/interfaces")" "gateway 10.0.2.2"
assert_contains "$(<"$rootfs/etc/network/interfaces")" "dns-nameservers 1.1.1.1 8.8.8.8"
[[ "$(<"$rootfs/etc/ooonana/theme")" == "light" ]] || fail "wrong setup theme"
assert_contains "$(<"$rootfs/etc/ooonana/theme.conf")" 'OOONANA_THEME="light"'
assert_contains "$(<"$rootfs/etc/ooonana/sources.d/cloud.repo")" 'OOONANA_REPO_NAME="cloud"'
assert_contains "$(<"$rootfs/etc/ooonana/sources.d/cloud.repo")" 'OOONANA_REPO_URI="http://127.0.0.1/repo"'
[[ -f "$rootfs/var/lib/ooonana/setup.done" ]] || fail "missing setup marker"

skip="$(OOONANA_ROOT="$rootfs" "$SETUP" --first-boot)"
assert_contains "$skip" "setup: already complete"

printf 'ok ooonana-setup\n'
