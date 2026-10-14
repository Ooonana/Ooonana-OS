#!/bin/sh
# WSL-local adaptation; never rewrites the packaged launcher or ISO payload.
set -eu
target_root="${OOONANA_ROOT:-/}"
target_root="$(readlink -f "$target_root")"
prefix="${target_root%/}"
[ "$(sed -n 's/^ID=//p' "$prefix/etc/os-release" | tr -d '\"')" = ooonana ] || {
  echo 'WSL adapter: refusing non-Ooonana root' >&2; exit 1;
}
[ -f "$prefix/etc/wsl.conf" ] || { echo 'WSL adapter: missing WSL configuration' >&2; exit 1; }
source_helper="$prefix/usr/bin/start-ooonana-i3"
[ -x "$source_helper" ] || { echo 'WSL adapter: missing packaged launcher' >&2; exit 1; }
mkdir -p "$prefix/usr/local/bin"
work="$(mktemp -d "$prefix/usr/local/bin/.ooonana-wsl-adapter.XXXXXX")"
trap 'rm -f -- "$work/launcher"; rmdir -- "$work"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Derive from installed version instead of maintaining a forked launcher.
awk '
  /\/usr\/bin\/start-ooonana-i3/ {
    calls += gsub(/\/usr\/bin\/start-ooonana-i3/, "/usr/local/bin/start-ooonana-i3")
  }
  /\[ "\$tries" -le 50 \]/ {
    waits += sub(/-le 50/, "-le 600")
  }
  { print }
  /^run_nested_i3\(\) \{$/ {
    print "  export GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb"
    backends++
  }
  END { if (calls != 3 || waits != 1 || backends != 1) exit 1 }
' "$source_helper" >"$work/launcher" || {
  echo 'WSL adapter: unknown launcher layout; existing override retained' >&2; exit 1;
}
sh -n "$work/launcher"
install -m 0755 "$work/launcher" "$prefix/usr/local/bin/start-ooonana-i3"
echo 'WSL desktop adapter installed: /usr/local/bin/start-ooonana-i3'
