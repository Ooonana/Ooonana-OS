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
trap 'rm -f -- "$work/launcher" "$work/picom" "$work/compositor.conf"; rmdir -- "$work"' EXIT
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
# Xephyr/WSLg can lose XDamage regions: Nemo's sidebar/menu remained black
# until full repaint. Keep this workaround outside packaged/physical defaults.
compositor="$prefix/usr/local/bin/picom"
wsl_config="$prefix/etc/ooonana/picom-wsl.conf"
if [ -L "$compositor" ] || { [ -e "$compositor" ] &&
   ! grep -qx '# Ooonana WSL compositor adapter.' "$compositor"; }; then
  echo 'WSL compositor: custom local wrapper retained; full-repaint adaptation skipped' >&2
elif [ -L "$wsl_config" ] || { [ -e "$wsl_config" ] &&
   ! grep -qx '# Ooonana WSL compositor adapter.' "$wsl_config"; }; then
  echo 'WSL compositor: custom local config retained; adaptation skipped' >&2
else
  # CLI-only no-use-damage did not reliably repaint the themed Nemo fixture.
  # Derive a WSL-only config; keep redirection as well as full redraw enabled.
  # Refuse unfamiliar layouts instead of changing a user's custom settings.
  if ! awk '
    BEGIN { print "# Ooonana WSL compositor adapter." }
    /^[[:space:]]*use-damage[[:space:]]*=[[:space:]]*(true|false);[[:space:]]*$/ {
      print "use-damage = false;"; damage++; next
    }
    /^[[:space:]]*unredir-if-possible[[:space:]]*=[[:space:]]*(true|false);[[:space:]]*$/ {
      print "unredir-if-possible = false;"; redirect++; next
    }
    { print }
    END { if (damage != 1 || redirect != 1) exit 1 }
  ' "$prefix/etc/ooonana/picom.conf" >"$work/compositor.conf"; then
    echo 'WSL compositor: unknown config layout; existing override retained' >&2
    exit 1
  fi
  cat >"$work/picom" <<'COMPOSITOR'
#!/bin/sh
# Ooonana WSL compositor adapter.
if [ "$#" -eq 4 ] && [ "$1" = --backend ] &&
   { [ "$2" = xrender ] || [ "$2" = glx ]; } &&
   [ "$3" = --config ] && [ "$4" = /etc/ooonana/picom.conf ]; then
  exec /usr/bin/picom --backend "$2" --config /etc/ooonana/picom-wsl.conf --no-use-damage
fi
# Preserve custom invocation/configuration rather than forcing desktop defaults.
exec /usr/bin/picom --no-use-damage "$@"
COMPOSITOR
  sh -n "$work/picom"
  install -m 0644 "$work/compositor.conf" "$wsl_config"
  install -m 0755 "$work/picom" "$compositor"
fi
echo 'WSL desktop adapter installed: /usr/local/bin/start-ooonana-i3'
