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
grep -Fq 'ooonana_wsl_prepare_runtime "$(id -u "$SESSION_USER")" "$(id -g "$SESSION_USER")" || return 1' "$target"
grep -Fq '! ooonana_wsl_runtime_ready "$(id -u)"; }; then' "$target"
grep -Fq 'XDG_RUNTIME_DIR="/run/user/$(id -u)"' "$target"
grep -Fq 'unset DBUS_SESSION_BUS_ADDRESS OOONANA_DBUS_SESSION' "$target"
if grep -Fq 'ooonana/wsl-runtime' "$target"; then exit 1; fi
if grep -Fq /usr/bin/start-ooonana-i3 "$target"; then exit 1; fi
[ "$before" = "$(sha256sum "$work/root/usr/bin/start-ooonana-i3" | cut -d' ' -f1)" ]
# Check the embedded guards without touching the host's real /run hierarchy.
awk '/^# Ooonana WSL runtime guards/ {capture=1} capture && /^set -eu$/ {exit} capture {print}' "$target" >"$work/runtime.sh"
. "$work/runtime.sh"
fixture_uid="$(id -u)"; fixture_gid="$(id -g)"
runtime_root="$work/runtime"
mkdir "$runtime_root"
if ooonana_wsl_runtime_ready "$fixture_uid" "$runtime_root"; then exit 1; fi
ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" "$runtime_root"
runtime_dir="$runtime_root/run/user/$fixture_uid"
[ "$(stat -c %a "$runtime_dir")" = 700 ]
[ "$(stat -c %u "$runtime_dir")" = "$fixture_uid" ]
printf 'keep runtime contents\n' >"$runtime_dir/sentinel"
chmod 0755 "$runtime_dir"
if ooonana_wsl_runtime_ready "$fixture_uid" "$runtime_root"; then exit 1; fi
ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" "$runtime_root"
grep -qx 'keep runtime contents' "$runtime_dir/sentinel"
ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" "$runtime_root"
for invalid_id in '' '1:2' 'abc' '../3'; do
  if ooonana_wsl_prepare_runtime "$invalid_id" "$fixture_gid" "$runtime_root" 2>/dev/null; then exit 1; fi
  if ooonana_wsl_prepare_runtime "$fixture_uid" "$invalid_id" "$runtime_root" 2>/dev/null; then exit 1; fi
done
if ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" relative 2>/dev/null; then exit 1; fi
other_uid="$((fixture_uid + 1))"
mkdir -m 0700 "$runtime_root/run/user/$other_uid"
if ooonana_wsl_prepare_runtime "$other_uid" "$fixture_gid" "$runtime_root" 2>/dev/null; then exit 1; fi
[ "$(stat -c %u "$runtime_root/run/user/$other_uid")" = "$fixture_uid" ]
mkdir "$work/linked-runtime"
ln -s "$runtime_dir" "$work/linked-runtime/run"
if ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" "$work/linked-runtime" 2>/dev/null; then exit 1; fi
mkdir -p "$work/linked-user/run/user"
ln -s "$runtime_dir" "$work/linked-user/run/user/$fixture_uid"
if ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" "$work/linked-user" 2>/dev/null; then exit 1; fi
[ -L "$work/linked-user/run/user/$fixture_uid" ]
chmod 0777 "$runtime_root/run/user"
if ooonana_wsl_prepare_runtime "$fixture_uid" "$fixture_gid" "$runtime_root" 2>/dev/null; then exit 1; fi
chmod 0755 "$runtime_root/run/user"
ooonana_wsl_runtime_ready "$fixture_uid" "$runtime_root"
grep -qx 'keep runtime contents' "$runtime_dir/sentinel"
# Execute the exact generated selection block, not a second implementation.
printf 'select_runtime() {\n' >"$work/select-runtime.sh"
awk '
  /^  if is_wsl_session; then$/ {capture=1}
  capture {print}
  capture && /^  fi$/ {exit}
' "$target" >>"$work/select-runtime.sh"
printf '}\n' >>"$work/select-runtime.sh"
is_wsl_session() { return 0; }
ooonana_wsl_runtime_ready() { [ "${fixture_ready:-1}" = 1 ]; }
. "$work/select-runtime.sh"
(
  XDG_RUNTIME_DIR=/home/qa/old-runtime
  DBUS_SESSION_BUS_ADDRESS=unix:path=/home/qa/old-runtime/bus
  OOONANA_DBUS_SESSION=1
  select_runtime
  [ "$XDG_RUNTIME_DIR" = "/run/user/$fixture_uid" ]
  [ "${DBUS_SESSION_BUS_ADDRESS+x}" != x ]
  [ "${OOONANA_DBUS_SESSION+x}" != x ]
)
(
  XDG_RUNTIME_DIR="/run/user/$fixture_uid"
  DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
  OOONANA_DBUS_SESSION=1
  select_runtime
  [ "$DBUS_SESSION_BUS_ADDRESS" = "unix:path=$XDG_RUNTIME_DIR/bus" ]
  [ "$OOONANA_DBUS_SESSION" = 1 ]
)
(
  fixture_ready=0
  XDG_RUNTIME_DIR=/home/qa/old-runtime
  if select_runtime 2>/dev/null; then exit 1; fi
  [ "$XDG_RUNTIME_DIR" = /home/qa/old-runtime ]
)
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
printf 'ok wsl-desktop-adapter: OS guard, canonical private runtime, unsafe paths refused, bus reset, bounded wait, X11, recursion, full repaint/redirection, packaged config unchanged, custom overrides retained\n'
