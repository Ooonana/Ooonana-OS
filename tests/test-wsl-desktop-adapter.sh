#!/bin/sh
set -eu
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
work="$(mktemp -d /var/tmp/ooonana-wsl-adapter-test.XXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/root/etc/ooonana" "$work/root/usr/bin"
printf 'use-damage = true;\nunredir-if-possible = true;\ncorner-radius = 14;\n' >"$work/root/etc/ooonana/picom.conf"
config_before="$(sha256sum "$work/root/etc/ooonana/picom.conf" | cut -d' ' -f1)"
printf 'ID=ubuntu\n' >"$work/root/etc/os-release"
if OOONANA_ROOT="$work/root" sh "$ROOT/scripts/install-wsl-desktop-adapter.sh" >/dev/null 2>&1; then
  echo 'FAIL: adapter accepted Ubuntu' >&2; exit 1
fi
printf 'ID=ooonana\n' >"$work/root/etc/os-release"
printf '[boot]\nsystemd=false\n' >"$work/root/etc/wsl.conf"
awk '
  /install .*start-ooonana-i3.*EOF/ { capture=1; next }
  capture && /^EOF$/ { exit }
  capture { print }
' "$ROOT/scripts/build-full-i3-rootfs.sh" >"$work/root/usr/bin/start-ooonana-i3"
chmod +x "$work/root/usr/bin/start-ooonana-i3"
before="$(sha256sum "$work/root/usr/bin/start-ooonana-i3" | cut -d' ' -f1)"
OOONANA_ROOT="$work/root" sh "$ROOT/scripts/install-wsl-desktop-adapter.sh"
target="$work/root/usr/local/bin/start-ooonana-i3"
# Match the generated shell expression, not this test's environment.
# shellcheck disable=SC2016
grep -Fq '"$tries" -le 600' "$target"
grep -Fq 'export GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb' "$target"
if grep -Fq /usr/bin/start-ooonana-i3 "$target"; then exit 1; fi
[ "$before" = "$(sha256sum "$work/root/usr/bin/start-ooonana-i3" | cut -d' ' -f1)" ]
compositor="$work/root/usr/local/bin/picom"
grep -Fq 'exec /usr/bin/picom --no-use-damage "$@"' "$compositor"
grep -Fq -- '--config /etc/ooonana/picom-wsl.conf --no-use-damage' "$compositor"
grep -qx 'use-damage = false;' "$work/root/etc/ooonana/picom-wsl.conf"
grep -qx 'unredir-if-possible = false;' "$work/root/etc/ooonana/picom-wsl.conf"
grep -qx 'corner-radius = 14;' "$work/root/etc/ooonana/picom-wsl.conf"
[ "$config_before" = "$(sha256sum "$work/root/etc/ooonana/picom.conf" | cut -d' ' -f1)" ]
[ -x "$compositor" ]
printf '#!/bin/sh\n# custom compositor\nexit 0\n' >"$compositor"
custom_before="$(sha256sum "$compositor" | cut -d' ' -f1)"
OOONANA_ROOT="$work/root" sh "$ROOT/scripts/install-wsl-desktop-adapter.sh" >/dev/null 2>&1
[ "$custom_before" = "$(sha256sum "$compositor" | cut -d' ' -f1)" ]
rm -- "$compositor"
ln -s "$target" "$compositor"
OOONANA_ROOT="$work/root" sh "$ROOT/scripts/install-wsl-desktop-adapter.sh" >/dev/null 2>&1
[ -L "$compositor" ]
rm -- "$compositor"
printf '# Custom compositor configuration\n' >"$work/root/etc/ooonana/picom-wsl.conf"
OOONANA_ROOT="$work/root" sh "$ROOT/scripts/install-wsl-desktop-adapter.sh" >/dev/null 2>&1
[ ! -e "$compositor" ]
grep -qx '# Custom compositor configuration' "$work/root/etc/ooonana/picom-wsl.conf"
local_before="$(sha256sum "$target" | cut -d' ' -f1)"
# An unfamiliar future launcher must not replace the existing working adapter.
printf '#!/bin/sh\nexit 0\n' >"$work/root/usr/bin/start-ooonana-i3"
if OOONANA_ROOT="$work/root" sh "$ROOT/scripts/install-wsl-desktop-adapter.sh" >/dev/null 2>&1; then exit 1; fi
[ "$local_before" = "$(sha256sum "$target" | cut -d' ' -f1)" ]
printf 'ok wsl-desktop-adapter: OS guard, bounded wait, X11, recursion, full repaint/redirection, packaged config unchanged, custom overrides retained\n'
