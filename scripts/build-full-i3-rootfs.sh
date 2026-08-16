#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
SCRATCH_ROOTFS="$WORK_DIR/scratch-rootfs"
ROOTFS="$WORK_DIR/full-i3-rootfs"
TARBALL="$WORK_DIR/ooonana-full-i3-rootfs.tar.gz"
REPO="$WORK_DIR/full-i3-repo"
STAGED_REPO=""
PACKAGE_PROFILE="$ROOT/configs/packages/full-i3.list"
OS_VERSION="${OOONANA_OS_VERSION:-0.1.8}"
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana full-i3 rootfs.

Usage:
  scripts/build-full-i3-rootfs.sh [options]

Options:
  --work-dir PATH       Build directory (default: /var/tmp/ooonana-os/build)
  --scratch-rootfs PATH Existing minimal scratch rootfs
  --rootfs PATH         Full i3 rootfs output path
  --tarball PATH        Full i3 rootfs tarball output path
  --repo PATH           Ooonana repo containing branding/i3/full-i3 package metadata
  --package-profile PATH
                        Required full-edition package list
  --force               Delete existing rootfs and tarball first
  -h, --help            Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; SCRATCH_ROOTFS="$2/scratch-rootfs"; ROOTFS="$2/full-i3-rootfs"; TARBALL="$2/ooonana-full-i3-rootfs.tar.gz"; REPO="$2/full-i3-repo"; shift 2 ;;
    --scratch-rootfs) SCRATCH_ROOTFS="$2"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --tarball) TARBALL="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --package-profile) PACKAGE_PROFILE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

write_start_script() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/start-ooonana-i3" <<'EOF'
#!/bin/sh
set -eu

SESSION_USER=""
if [ "${1:-}" = "--user" ]; then
  SESSION_USER="${2:-}"
  shift 2
fi

case "${HOME:-}" in
  ""|/) export HOME="/root" ;;
  *) export HOME ;;
esac
mkdir -p "$HOME" /tmp
touch "$HOME/.Xauthority" 2>/dev/null || true
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

prepare_xorg_video_config() {
  mkdir -p /etc/X11/xorg.conf.d
  if [ -d /sys/firmware/efi ] && [ -e /dev/fb0 ] && [ ! -e /dev/dri/card0 ] && [ -f /usr/share/ooonana/xorg-fbdev.conf ]; then
    cp /usr/share/ooonana/xorg-fbdev.conf /etc/X11/xorg.conf.d/20-ooonana-video.conf
  else
    rm -f /etc/X11/xorg.conf.d/20-ooonana-video.conf
  fi
}

if grep -q 'ooonana.smoke=1' /proc/cmdline 2>/dev/null; then
  if grep -q 'ooonana.gui-smoke=1' /proc/cmdline 2>/dev/null &&
    command -v startx >/dev/null 2>&1 &&
    command -v i3 >/dev/null 2>&1; then
    prepare_xorg_video_config
    exec startx /usr/bin/ooonana-i3-smoke-session
  fi
  echo "OOONANA_FULL_I3_OK"
  exit 0
fi

if grep -q 'ooonana.install=1' /proc/cmdline 2>/dev/null; then
  if command -v startx >/dev/null 2>&1 &&
    command -v i3 >/dev/null 2>&1 &&
    [ -x /usr/bin/ooonana-i3-installer-session ]; then
    prepare_xorg_video_config
    exec startx /usr/bin/ooonana-i3-installer-session
  fi
  if [ -x /usr/bin/ooonana-gui-installer ]; then
    exec /usr/bin/ooonana-gui-installer
  fi
  exec /usr/bin/ooonana-install-wizard
fi

if [ -z "$SESSION_USER" ] &&
  [ "$(id -u 2>/dev/null || echo 1)" = "0" ] &&
  grep -q '^ooonana:' /etc/passwd 2>/dev/null; then
  SESSION_USER="ooonana"
fi

is_wsl_session() {
  [ -n "${WSL_DISTRO_NAME:-}" ] && return 0
  [ -n "${WSL_INTEROP:-}" ] && return 0
  grep -qi microsoft /proc/version 2>/dev/null && return 0
  grep -qi wsl /proc/sys/kernel/osrelease 2>/dev/null && return 0
  return 1
}

if is_wsl_session &&
  [ -n "${DISPLAY:-}" ] &&
  command -v i3 >/dev/null 2>&1 &&
  [ -x /usr/bin/ooonana-i3-session ]; then
  if [ -n "$SESSION_USER" ]; then
    exec /usr/bin/ooonana-i3-session --user "$SESSION_USER"
  fi
  exec /usr/bin/ooonana-i3-session
fi

if command -v startx >/dev/null 2>&1 && command -v i3 >/dev/null 2>&1; then
  prepare_xorg_video_config
  if [ -n "$SESSION_USER" ]; then
    exec startx /usr/bin/ooonana-i3-session --user "$SESSION_USER"
  fi
  exec startx /usr/bin/ooonana-i3-session
fi

echo "Ooonana full-i3"
echo "Missing startx or i3. Build/publish the full-i3 package repo, then run: ooonana get full-i3"
exec /bin/sh -l
EOF
}

write_theme_helpers() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-theme-env" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
export LANG="${LANG:-C.UTF-8}"
export LC_CTYPE="${LC_CTYPE:-C.UTF-8}"
export PYTHONUTF8=1

load_theme() {
  theme="${OOONANA_THEME:-}"
  if [ -z "$theme" ] && [ -n "${HOME:-}" ] && [ -f "$HOME/.config/ooonana/theme" ]; then
    IFS= read -r theme <"$HOME/.config/ooonana/theme" || theme=""
  fi
  if [ -z "$theme" ] && [ -f /etc/ooonana/theme ]; then
    IFS= read -r theme </etc/ooonana/theme || theme=""
  fi

  case "$theme" in
    light)
      OOONANA_THEME="light"
      OOONANA_BG="#ffb21a"
      OOONANA_FG="#1b1202"
      OOONANA_GTK_THEME="Adwaita"
      OOONANA_GTK_DARK="false"
      ;;
    *)
      OOONANA_THEME="dark"
      OOONANA_BG="#050505"
      OOONANA_FG="#ffb21a"
      OOONANA_GTK_THEME="Adwaita:dark"
      OOONANA_GTK_DARK="true"
      ;;
  esac
  OOONANA_CURSOR="#ffb21a"
  GTK_THEME="$OOONANA_GTK_THEME"
  GDK_BACKEND="${GDK_BACKEND:-x11}"
  export OOONANA_THEME OOONANA_BG OOONANA_FG OOONANA_CURSOR OOONANA_GTK_THEME OOONANA_GTK_DARK GTK_THEME GDK_BACKEND
}

load_theme

write_theme() {
  new_theme="$1"
  if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
    mkdir -p /etc/ooonana
    printf '%s\n' "$new_theme" >/etc/ooonana/theme
  else
    mkdir -p "${HOME:-/tmp}/.config/ooonana"
    printf '%s\n' "$new_theme" >"${HOME:-/tmp}/.config/ooonana/theme"
  fi
}

case "${1:-env}" in
  env)
    printf 'PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'
    printf 'OOONANA_THEME="%s"\n' "$OOONANA_THEME"
    printf 'OOONANA_BG="%s"\n' "$OOONANA_BG"
    printf 'OOONANA_FG="%s"\n' "$OOONANA_FG"
    printf 'OOONANA_CURSOR="%s"\n' "$OOONANA_CURSOR"
    printf 'OOONANA_GTK_THEME="%s"\n' "$OOONANA_GTK_THEME"
    printf 'OOONANA_GTK_DARK="%s"\n' "$OOONANA_GTK_DARK"
    printf 'GTK_THEME="%s"\n' "$OOONANA_GTK_THEME"
    printf 'GDK_BACKEND="x11"\n'
    ;;
  apply)
    config_home="${XDG_CONFIG_HOME:-${HOME:-/root}/.config}"
    mkdir -p "$config_home/gtk-3.0"
    cat >"$config_home/gtk-3.0/settings.ini" <<SETTINGS
[Settings]
gtk-theme-name=Adwaita
gtk-application-prefer-dark-theme=$OOONANA_GTK_DARK
gtk-icon-theme-name=Adwaita
gtk-font-name=Sans 10
gtk-button-images=1
gtk-menu-images=1
gtk-decoration-layout=menu:minimize,maximize,close
SETTINGS
    cat >"$config_home/gtk-3.0/gtk.css" <<CSS
@define-color ooonana_bg $OOONANA_BG;
@define-color ooonana_fg $OOONANA_FG;
@define-color ooonana_accent #ffb21a;
@define-color ooonana_panel #11161d;
@define-color ooonana_panel_alt #171e27;
@define-color ooonana_border #364252;
@define-color ooonana_muted #9ba5b4;
window, dialog, .background { background-color: @ooonana_bg; color: @ooonana_fg; }
headerbar { background: @ooonana_panel; color: @ooonana_accent; border-bottom: 1px solid @ooonana_border; padding: 4px 8px; }
headerbar .title { font-weight: bold; }
headerbar .subtitle { color: @ooonana_muted; }
button { background: @ooonana_panel_alt; color: @ooonana_fg; border: 1px solid @ooonana_border; border-radius: 4px; padding: 7px 12px; }
button:hover { background: #222c38; border-color: @ooonana_accent; }
button:checked, button.suggested-action { background: @ooonana_accent; color: #080a0d; border-color: @ooonana_accent; }
entry, textview, treeview, list { background: #0d1117; color: @ooonana_fg; border-color: @ooonana_border; }
entry { padding: 8px; border-radius: 4px; }
treeview header button { background: @ooonana_panel_alt; color: @ooonana_accent; }
treeview:selected, row:selected { background: #283441; color: #ffffff; }
notebook header { background: #0d1117; }
notebook tab { padding: 8px 14px; }
notebook tab:checked { color: @ooonana_accent; border-bottom: 2px solid @ooonana_accent; }
scale highlight { background: @ooonana_accent; }
scale trough { background: #2a3442; min-height: 6px; border-radius: 3px; }
scrollbar slider { background: #4d5a69; border-radius: 4px; min-width: 7px; min-height: 7px; }
scrollbar slider:hover { background: @ooonana_accent; }
tooltip { background: @ooonana_panel; color: @ooonana_fg; border: 1px solid @ooonana_accent; }
CSS
    xsetroot -solid "$OOONANA_BG" 2>/dev/null || true
    wallpaper="/usr/share/ooonana/wallpapers/ooonana-notes.jpg"
    wallpaper_mode="fit"
    if [ -n "${HOME:-}" ] && [ -f "$HOME/.config/ooonana/wallpaper" ]; then
      IFS= read -r saved_wallpaper <"$HOME/.config/ooonana/wallpaper" || saved_wallpaper=""
      [ -n "$saved_wallpaper" ] && wallpaper="$saved_wallpaper"
    fi
    if [ -n "${HOME:-}" ] && [ -f "$HOME/.config/ooonana/wallpaper-mode" ]; then
      IFS= read -r wallpaper_mode <"$HOME/.config/ooonana/wallpaper-mode" || wallpaper_mode="fit"
    fi
    case "$wallpaper_mode" in
      fit|fill|center|stretch|tile) ;;
      *) wallpaper_mode="fit" ;;
    esac
    if command -v hsetroot >/dev/null 2>&1 && [ -f "$wallpaper" ]; then
      hsetroot "-$wallpaper_mode" "$wallpaper" && exit 0 || true
    fi
    if command -v feh >/dev/null 2>&1 && [ -f "$wallpaper" ]; then
      xsetroot -solid "$OOONANA_BG" 2>/dev/null || true
      case "$wallpaper_mode" in
        fit) feh --bg-max "$wallpaper" || true ;;
        fill) feh --bg-fill "$wallpaper" || true ;;
        center) feh --bg-center "$wallpaper" || true ;;
        stretch) feh --bg-scale "$wallpaper" || true ;;
        tile) feh --bg-tile "$wallpaper" || true ;;
      esac
    fi
    ;;
  toggle)
    case "$OOONANA_THEME" in
      dark) write_theme light ;;
      *) write_theme dark ;;
    esac
    exec "$0" apply
    ;;
  xterm)
    shift
    if [ "$#" -eq 0 ]; then
      exec xterm -bg "$OOONANA_BG" -fg "$OOONANA_FG" -cr "$OOONANA_CURSOR" -e /bin/sh -l
    fi
    exec xterm -bg "$OOONANA_BG" -fg "$OOONANA_FG" -cr "$OOONANA_CURSOR" "$@"
    ;;
  *)
    echo "usage: ooonana-theme-env [env|apply|toggle|xterm]" >&2
    exit 1
    ;;
esac
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/local/bin/yad" <<'EOF'
#!/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if command -v ooonana-theme-env >/dev/null 2>&1; then
  eval "$(ooonana-theme-env env)"
  ooonana-theme-env apply >/dev/null 2>&1 || true
fi
if [ -x /usr/bin/yad ]; then
  exec /usr/bin/yad --window-icon=/usr/share/ooonana/logo.png "$@"
fi
echo "yad missing" >&2
exit 127
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/gtk-3.0/settings.ini" <<'EOF'
[Settings]
gtk-theme-name=Adwaita
gtk-application-prefer-dark-theme=true
gtk-icon-theme-name=Adwaita
gtk-font-name=Sans 10
gtk-button-images=1
gtk-menu-images=1
gtk-decoration-layout=menu:minimize,maximize,close
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/root/.config/gtk-3.0/settings.ini" <<'EOF'
[Settings]
gtk-theme-name=Adwaita
gtk-application-prefer-dark-theme=true
gtk-icon-theme-name=Adwaita
gtk-font-name=Sans 10
gtk-button-images=1
gtk-menu-images=1
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/root/.config/gtk-3.0/gtk.css" <<'EOF'
@define-color ooonana_bg #050505;
@define-color ooonana_fg #f7ead0;
@define-color ooonana_accent #ffb21a;
@define-color ooonana_panel #11161d;
@define-color ooonana_border #364252;
window, dialog, .background { background-color: @ooonana_bg; color: @ooonana_fg; }
headerbar { background: @ooonana_panel; color: @ooonana_accent; border-bottom: 1px solid @ooonana_border; }
button { background: #171e27; color: @ooonana_fg; border: 1px solid @ooonana_border; border-radius: 4px; padding: 7px 12px; }
button:hover { background: #222c38; border-color: @ooonana_accent; }
button:checked, button.suggested-action { background: @ooonana_accent; color: #080a0d; }
entry, textview, treeview, list { background: #0d1117; color: @ooonana_fg; border-color: @ooonana_border; }
treeview:selected, row:selected { background: #283441; color: #ffffff; }
scale highlight { background: @ooonana_accent; }
EOF
}

write_desktop_helpers() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-open" <<'EOF'
#!/bin/sh
set -eu

for cmd in "$@"; do
  if command -v "$cmd" >/dev/null 2>&1; then
    exec "$cmd"
  fi
done
printf 'missing app: %s\n' "$*" >&2
exit 1
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-apps" <<'EOF'
#!/bin/sh
set -eu
NATIVE_APP="/usr/lib/ooonana/ui/launcher_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" "$@"
fi
exec rofi -show drun -theme /etc/ooonana/rofi.rasi
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-run-admin" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "root: direct"
  echo "user: passwordless sudo, doas fallback"
  echo "OOONANA_ADMIN_HELPER_OK"
  exit 0
fi

[ "$#" -gt 0 ] || {
  echo "usage: ooonana-run-admin COMMAND [ARGS...]" >&2
  exit 2
}

if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
  exec "$@"
fi
if command -v sudo >/dev/null 2>&1; then
  if sudo -n /bin/true >/dev/null 2>&1; then
    exec sudo -n "$@"
  fi
fi
if command -v doas >/dev/null 2>&1; then
  if doas -n /bin/true >/dev/null 2>&1; then
    exec doas -n "$@"
  fi
fi
echo "admin helper unavailable: install doas or sudo" >&2
exit 126
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-browser" <<'EOF'
#!/bin/sh
set -eu
url="${1:-about:blank}"
case "${DBUS_SESSION_BUS_ADDRESS:-}" in
  unix:*|tcp:*) ;;
  *) unset DBUS_SESSION_BUS_ADDRESS ;;
esac
if [ -z "${OOONANA_BROWSER_DBUS:-}" ] &&
  [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] &&
  command -v dbus-run-session >/dev/null 2>&1; then
  export OOONANA_BROWSER_DBUS=1
  exec dbus-run-session -- "$0" "$@"
fi
if command -v chromium >/dev/null 2>&1; then
  log="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/ooonana/chromium.log"
  mkdir -p "${log%/*}"
  chromium --no-first-run --disable-default-apps --disable-dev-shm-usage "$url" 2>"$log" && exit 0
  printf '\nNormal GPU launch failed; retrying software rendering.\n' >>"$log"
  chromium --no-first-run --disable-default-apps --disable-dev-shm-usage \
    --disable-gpu --disable-software-rasterizer --disable-features=Vulkan \
    "$url" 2>>"$log" && exit 0
  exec ooonana-theme-env xterm -e sh -lc 'echo "Chromium failed:"; tail -80 "${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/ooonana/chromium.log"; echo; echo "Log saved. Press Enter."; read _'
fi
if command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser "$url"
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "chromium missing"; echo "run: ooonana get chromium"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-files" <<'EOF'
#!/bin/sh
set -eu
path="${1:-${HOME:-/root}}"
if command -v nemo >/dev/null 2>&1; then
  exec nemo "$path"
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "nemo missing"; echo "run: ooonana get nemo"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-hardware-reprobe" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

LOG="${OOONANA_HARDWARE_LOG:-/var/log/ooonana-hardware.log}"
mkdir -p /run /var/log

if [ "$(id -u 2>/dev/null || echo 1)" != "0" ]; then
  exec ooonana-run-admin "$0" "$@"
fi

log() {
  printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true
}

unblock_rfkill() {
  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock all >>"$LOG" 2>&1 || true
  fi
  for state in /sys/class/rfkill/rfkill*/soft; do
    [ -e "$state" ] || continue
    [ -w "$state" ] || continue
    printf '0' >"$state" 2>/dev/null || true
  done
}

case "${1:-}" in
  --force|force) force=1; mode=all ;;
  --force-wifi|force-wifi) force=1; mode=wifi ;;
  --force-bluetooth|force-bluetooth) force=1; mode=bluetooth ;;
  *) force=0; mode=all ;;
esac

if [ "$force" -eq 0 ] && [ -f /run/ooonana-hardware-reprobe.done ]; then
  exit 0
fi

unblock_rfkill

if [ -w /sys/bus/pci/rescan ]; then
  printf '1' >/sys/bus/pci/rescan 2>>"$LOG" || true
fi

if command -v modprobe >/dev/null 2>&1; then
  if [ "$mode" != "bluetooth" ]; then
    for module in \
      iwlwifi rtw89_pci rtw88_pci mt7921e ath10k_pci ath11k_pci ath12k_pci \
      brcmfmac rtl8xxxu mt7921u; do
      modprobe "$module" >>"$LOG" 2>&1 || true
    done
  fi
  if [ "$mode" != "wifi" ]; then
    for module in bluetooth btusb btintel btrtl btqca uhid uinput; do
      modprobe "$module" >>"$LOG" 2>&1 || true
    done
  fi
fi

rebind_driver() {
  driver="$1"
  for dir in /sys/bus/*/drivers/"$driver"; do
    [ -d "$dir" ] || continue
    [ -w "$dir/unbind" ] || continue
    [ -w "$dir/bind" ] || continue
    for dev in "$dir"/*; do
      [ -L "$dev" ] || continue
      dev_id="${dev##*/}"
      case "$dev_id" in
        bind|unbind|uevent|module|new_id|remove_id) continue ;;
      esac
      printf '%s' "$dev_id" >"$dir/unbind" 2>/dev/null || continue
      printf '%s' "$dev_id" >"$dir/bind" 2>/dev/null || true
      log "rebound $driver $dev_id"
    done
  done
}

bind_unclaimed_intel_wifi() {
  bind=/sys/bus/pci/drivers/iwlwifi/bind
  [ -w "$bind" ] || return 0
  for dev in /sys/bus/pci/devices/*; do
    [ -d "$dev" ] || continue
    [ -L "$dev/driver" ] && continue
    [ "$(cat "$dev/vendor" 2>/dev/null || true)" = "0x8086" ] || continue
    case "$(cat "$dev/class" 2>/dev/null || true)" in
      0x0280*) ;;
      *) continue ;;
    esac
    [ -w "$dev/power/control" ] && printf 'on' >"$dev/power/control" 2>/dev/null || true
    dev_id="${dev##*/}"
    printf '%s' "$dev_id" >"$bind" 2>>"$LOG" || true
    log "requested iwlwifi bind $dev_id"
  done
}

bind_unclaimed_intel_bluetooth() {
  bind=/sys/bus/usb/drivers/btusb/bind
  [ -w "$bind" ] || return 0
  for interface in /sys/bus/usb/devices/*:*; do
    [ -d "$interface" ] || continue
    [ -L "$interface/driver" ] && continue
    parent="${interface%:*}"
    [ "$(cat "$parent/idVendor" 2>/dev/null || true)" = "8087" ] || continue
    [ -w "$parent/authorized" ] && printf '1' >"$parent/authorized" 2>/dev/null || true
    [ -w "$parent/power/control" ] && printf 'on' >"$parent/power/control" 2>/dev/null || true
    class="$(cat "$interface/bInterfaceClass" 2>/dev/null || true)"
    subclass="$(cat "$interface/bInterfaceSubClass" 2>/dev/null || true)"
    protocol="$(cat "$interface/bInterfaceProtocol" 2>/dev/null || true)"
    case "$class:$subclass:$protocol" in
      e0:01:01|ff:01:01) ;;
      *) continue ;;
    esac
    interface_id="${interface##*/}"
    printf '%s' "$interface_id" >"$bind" 2>>"$LOG" || true
    log "requested btusb bind $interface_id"
  done
}

if [ "$force" -eq 1 ]; then
  if [ "$mode" != "bluetooth" ]; then
    for driver in \
      iwlwifi rtw89_pci rtw88_pci mt7921e ath10k_pci ath11k_pci ath12k_pci \
      brcmfmac rtl8xxxu mt7921u; do
      rebind_driver "$driver"
    done
  fi
  if [ "$mode" != "wifi" ]; then
    rebind_driver btusb
  fi
fi

[ "$mode" = "bluetooth" ] || bind_unclaimed_intel_wifi
[ "$mode" = "wifi" ] || bind_unclaimed_intel_bluetooth

if command -v udevadm >/dev/null 2>&1; then
  udevadm trigger --action=add >/dev/null 2>&1 || true
  udevadm trigger --subsystem-match=pci --action=add >/dev/null 2>&1 || true
  udevadm trigger --subsystem-match=usb --action=add >/dev/null 2>&1 || true
  udevadm trigger --subsystem-match=rfkill --action=change >/dev/null 2>&1 || true
  udevadm trigger --subsystem-match=net --action=add >/dev/null 2>&1 || true
  udevadm trigger --subsystem-match=bluetooth --action=add >/dev/null 2>&1 || true
  udevadm settle --timeout=8 >/dev/null 2>&1 || true
fi

touch /run/ooonana-hardware-reprobe.done 2>/dev/null || true
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-wireless-diagnose" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

LOG="${OOONANA_WIRELESS_LOG:-/var/log/ooonana-wireless-diagnose.log}"
mkdir -p "${LOG%/*}"

if [ "$(id -u 2>/dev/null || echo 1)" != "0" ]; then
  exec ooonana-run-admin "$0" "$@"
fi

run_limited() {
  limit="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$limit" "$@"
  else
    "$@"
  fi
}

collect() {
  echo "Ooonana wireless diagnostic"
  date 2>/dev/null || true
  uname -a 2>/dev/null || true
  echo
  echo "== kernel command line =="
  cat /proc/cmdline 2>/dev/null || true
  echo
  echo "== firmware overlay =="
  cat /usr/share/ooonana/intel-wireless-firmware.version 2>/dev/null || echo "current Intel firmware overlay missing"
  echo
  echo "== rfkill =="
  rfkill list 2>/dev/null || echo "rfkill unavailable"
  echo
  echo "== network interfaces =="
  ip -brief link 2>/dev/null || ifconfig -a 2>/dev/null || true
  echo
  echo "== NetworkManager =="
  run_limited 6 nmcli general status 2>/dev/null || true
  run_limited 6 nmcli device status 2>/dev/null || true
  echo
  echo "== Bluetooth =="
  run_limited 6 bluetoothctl show 2>/dev/null || true
  run_limited 6 btmgmt info 2>/dev/null || true
  echo
  echo "== PCI network devices =="
  if command -v lspci >/dev/null 2>&1; then
    run_limited 6 lspci -nnk 2>/dev/null | sed -n '/Network controller/,+4p;/Wireless/,+4p'
  fi
  for dev in /sys/bus/pci/devices/*; do
    [ -d "$dev" ] || continue
    case "$(cat "$dev/class" 2>/dev/null || true)" in
      0x0280*) ;;
      *) continue ;;
    esac
    printf '%s vendor=%s device=%s driver=%s\n' "${dev##*/}" \
      "$(cat "$dev/vendor" 2>/dev/null || echo unknown)" \
      "$(cat "$dev/device" 2>/dev/null || echo unknown)" \
      "$(basename "$(readlink "$dev/driver" 2>/dev/null || echo unbound)")"
  done
  echo
  echo "== USB Bluetooth candidates =="
  if command -v lsusb >/dev/null 2>&1; then
    lsusb 2>/dev/null || true
  fi
  for dev in /sys/bus/usb/devices/*; do
    [ -f "$dev/idVendor" ] || continue
    printf '%s %s:%s product=%s\n' "${dev##*/}" \
      "$(cat "$dev/idVendor" 2>/dev/null || echo unknown)" \
      "$(cat "$dev/idProduct" 2>/dev/null || echo unknown)" \
      "$(cat "$dev/product" 2>/dev/null || echo unknown)"
  done
  echo
  echo "== relevant kernel messages =="
  dmesg 2>/dev/null | grep -Ei 'iwlwifi|firmware|bluetooth|btusb|btintel|rfkill|wlan|wifi|cnvi' | tail -160 || true
}

collect >"$LOG" 2>&1
cat "$LOG"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-service-repair" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if [ "$(id -u 2>/dev/null || echo 1)" != "0" ]; then
  exec ooonana-run-admin "$0" "$@"
fi

LOG="${OOONANA_SERVICE_LOG:-/var/log/ooonana-services.log}"
mkdir -p /run/dbus /var/lib/dbus /var/log /run/NetworkManager /run/wpa_supplicant /var/lib/NetworkManager /var/lib/bluetooth /etc /dev/shm
chmod 0755 /run/dbus 2>/dev/null || true
chmod 1777 /dev/shm 2>/dev/null || true
if [ ! -L /var/run ]; then
  rm -rf /var/run
  ln -s /run /var/run
fi
if ! grep -q '[[:space:]]/dev/shm[[:space:]]' /proc/mounts 2>/dev/null; then
  mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /dev/shm >>"$LOG" 2>&1 || true
fi

log() {
  printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true
}

unblock_rfkill() {
  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock all >>"$LOG" 2>&1 || true
  fi
  for state in /sys/class/rfkill/rfkill*/soft; do
    [ -e "$state" ] || continue
    [ -w "$state" ] || continue
    printf '0' >"$state" 2>/dev/null || true
  done
}

bluetooth_daemon() {
  for path in bluetoothd /usr/lib/bluetooth/bluetoothd /usr/libexec/bluetooth/bluetoothd /usr/sbin/bluetoothd; do
    if command -v "$path" >/dev/null 2>&1; then
      command -v "$path"
      return 0
    fi
    [ -x "$path" ] && { printf '%s\n' "$path"; return 0; }
  done
  return 1
}

network_manager_daemon() {
  for path in NetworkManager /usr/sbin/NetworkManager /sbin/NetworkManager /usr/bin/NetworkManager; do
    if command -v "$path" >/dev/null 2>&1; then
      command -v "$path"
      return 0
    fi
    [ -x "$path" ] && { printf '%s\n' "$path"; return 0; }
  done
  return 1
}

device_manager_running() {
  [ -S /run/udev/control ] ||
    process_running udevd ||
    process_running eudevd
}

process_running() {
  name="$1"
  if command -v pidof >/dev/null 2>&1; then
    pidof "$name" >/dev/null 2>&1
  else
    /bin/busybox pidof "$name" >/dev/null 2>&1
  fi
}

start_device_manager() {
  mkdir -p /run/udev
  device_manager_running && return 0
  if command -v udevd >/dev/null 2>&1; then
    udevd --daemon >>"$LOG" 2>&1 || true
  elif command -v eudevd >/dev/null 2>&1; then
    eudevd --daemon >>"$LOG" 2>&1 || true
  fi
  if command -v udevadm >/dev/null 2>&1; then
    run_limited 4 udevadm trigger --action=add >>"$LOG" 2>&1 || true
    run_limited 6 udevadm settle --timeout=5 >>"$LOG" 2>&1 || true
  fi
}

ensure_identity() {
  grep -q '^messagebus:' /etc/group 2>/dev/null || echo 'messagebus:x:81:' >>/etc/group
  grep -q '^messagebus:' /etc/passwd 2>/dev/null || echo 'messagebus:x:81:81:DBus Message Bus:/run/dbus:/bin/false' >>/etc/passwd
  grep -q '^pulse:' /etc/group 2>/dev/null || echo 'pulse:x:70:' >>/etc/group
  grep -q '^pulse-access:' /etc/group 2>/dev/null || echo 'pulse-access:x:71:' >>/etc/group
  grep -q '^pulse:' /etc/passwd 2>/dev/null || echo 'pulse:x:70:70:PulseAudio:/run/pulse:/bin/false' >>/etc/passwd
  mkdir -p /run/pulse
  chown 70:70 /run/pulse 2>/dev/null || true
  if grep -qx '11111111111111111111111111111111' /etc/machine-id 2>/dev/null; then
    : >/etc/machine-id
    : >/var/lib/dbus/machine-id
  fi
  if [ ! -s /etc/machine-id ]; then
    if command -v dbus-uuidgen >/dev/null 2>&1; then
      dbus-uuidgen >/etc/machine-id 2>/dev/null || true
    else
      cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-' >/etc/machine-id || true
    fi
  fi
  if [ -s /etc/machine-id ] &&
    { [ ! -s /var/lib/dbus/machine-id ] || ! /bin/busybox cmp -s /etc/machine-id /var/lib/dbus/machine-id; }; then
    cp /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || true
  fi
}

wait_for() {
  desc="$1"
  shift
  i=0
  while [ "$i" -lt 5 ]; do
    "$@" >/dev/null 2>&1 && return 0
    sleep 1
    i=$((i + 1))
  done
  log "wait timeout: $desc"
  return 1
}

run_limited() {
  limit="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$limit" "$@"
  else
    "$@"
  fi
}

dbus_ready() {
  [ -S /run/dbus/system_bus_socket ] || return 1
  if command -v dbus-send >/dev/null 2>&1; then
    run_limited 3 dbus-send --system --print-reply \
      --dest=org.freedesktop.DBus / org.freedesktop.DBus.ListNames >/dev/null 2>&1
    return $?
  fi
  process_running dbus-daemon
}

start_dbus() {
  dbus_ready && return 0
  rm -f /run/dbus/system_bus_socket /run/dbus/pid
  command -v dbus-daemon >/dev/null 2>&1 || {
    log "dbus-daemon missing"
    return 1
  }
  dbus-daemon --system --fork --nopidfile >>"$LOG" 2>&1 || true
  wait_for "system D-Bus" dbus_ready
}

stop_daemon() {
  name="$1"
  process_running "$name" || return 0
  /bin/busybox killall "$name" >>"$LOG" 2>&1 || true
  i=0
  while process_running "$name" && [ "$i" -lt 3 ]; do
    sleep 1
    i=$((i + 1))
  done
  if process_running "$name"; then
    /bin/busybox killall -9 "$name" >>"$LOG" 2>&1 || true
  fi
}

network_manager_ready() {
  process_running NetworkManager || return 1
  command -v nmcli >/dev/null 2>&1 || return 0
  run_limited 3 nmcli -t -f STATE general >/dev/null 2>&1
}

wpa_supplicant_ready() {
  process_running wpa_supplicant || return 1
  if command -v dbus-send >/dev/null 2>&1; then
    run_limited 3 dbus-send --system --print-reply \
      --dest=fi.w1.wpa_supplicant1 /fi/w1/wpa_supplicant1 \
      org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1
    return $?
  fi
  return 0
}

dbus_activation_helper_ready() {
  helper=/usr/libexec/dbus-daemon-launch-helper
  [ -x "$helper" ] || {
    log "D-Bus activation helper missing: $helper"
    return 1
  }
  metadata="$(/bin/busybox stat -c '%u:%g:%a' "$helper" 2>/dev/null || true)"
  [ "$metadata" = "0:81:4750" ] || {
    log "D-Bus activation helper permissions invalid: ${metadata:-unknown}; expected 0:81:4750"
    return 1
  }
}

start_wpa_supplicant() {
  wpa_supplicant_ready && return 0
  dbus_activation_helper_ready || return 1
  command -v dbus-send >/dev/null 2>&1 || {
    log "dbus-send missing; cannot activate wpa_supplicant"
    return 1
  }
  run_limited 8 dbus-send --system --print-reply \
    --dest=org.freedesktop.DBus / org.freedesktop.DBus.StartServiceByName \
    string:fi.w1.wpa_supplicant1 uint32:0 >>"$LOG" 2>&1 || return 1
  if ! wait_for wpa_supplicant wpa_supplicant_ready; then
    log "wpa_supplicant D-Bus activation failed"
    return 1
  fi
}

wifi_device_ready() {
  interface="$1"
  state="$(run_limited 4 nmcli -g GENERAL.STATE device show "$interface" 2>/dev/null || true)"
  state="${state%% *}"
  [ -n "$state" ] && [ "$state" -ge 30 ] 2>/dev/null
}

wait_for_wifi_device() {
  interface="$1"
  i=0
  while [ "$i" -lt 30 ]; do
    wifi_device_ready "$interface" && return 0
    sleep 1
    i=$((i + 1))
  done
  log "Wi-Fi device stayed unavailable: $interface"
  run_limited 5 nmcli -f GENERAL.TYPE,GENERAL.NM-MANAGED,GENERAL.STATE,GENERAL.REASON,GENERAL.DRIVER,GENERAL.FIRMWARE-VERSION,WIFI-PROPERTIES \
    device show "$interface" >>"$LOG" 2>&1 || true
  rfkill list >>"$LOG" 2>&1 || true
  iw dev "$interface" info >>"$LOG" 2>&1 || true
  tail -120 /var/log/NetworkManager.log >>"$LOG" 2>/dev/null || true
  return 1
}

start_network_manager() {
  nm_daemon="$(network_manager_daemon || true)"
  [ -n "$nm_daemon" ] || {
    log "NetworkManager missing from PATH and standard sbin paths"
    return 1
  }
  if [ "$FORCE_WIFI" -eq 1 ]; then
    stop_daemon NetworkManager
    stop_daemon wpa_supplicant
  fi
  if ! process_running NetworkManager; then
    mkdir -p /run/NetworkManager
    "$nm_daemon" --no-daemon --log-level=INFO \
      --log-domains=PLATFORM,RFKILL,WIFI,WIFI_SCAN,SUPPLICANT,DEVICE \
      >/var/log/NetworkManager.log 2>&1 &
    echo "$!" >/run/NetworkManager/ooonana.pid
  fi
  if ! wait_for NetworkManager network_manager_ready; then
    log "NetworkManager failed readiness check"
    tail -80 /var/log/NetworkManager.log >>"$LOG" 2>/dev/null || true
    return 1
  fi
  # NetworkManager owns supplicant. Trigger its packaged D-Bus service only
  # after NetworkManager is alive; never race it with a separately spawned daemon.
  start_wpa_supplicant || {
    tail -120 /var/log/NetworkManager.log >>"$LOG" 2>/dev/null || true
    return 1
  }
  run_limited 4 nmcli networking on >>"$LOG" 2>&1 || true
  run_limited 4 nmcli radio wifi on >>"$LOG" 2>&1 || true
  for interface in /sys/class/net/wl*; do
    [ -d "$interface" ] || continue
    interface="${interface##*/}"
    if ! wait_for_wifi_device "$interface"; then
      return 1
    fi
    if command -v iw >/dev/null 2>&1; then
      run_limited 4 iw dev "$interface" set power_save off >>"$LOG" 2>&1 || true
    fi
    run_limited 15 nmcli device wifi rescan ifname "$interface" >>"$LOG" 2>&1 || true
  done
  return 0
}

bluez_ready() {
  process_running bluetoothd || return 1
  if command -v dbus-send >/dev/null 2>&1; then
    run_limited 3 dbus-send --system --print-reply \
      --dest=org.freedesktop.DBus / org.freedesktop.DBus.GetNameOwner \
      string:org.bluez >/dev/null 2>&1
    return $?
  fi
  return 0
}

start_bluetooth() {
  bt_daemon="$(bluetooth_daemon || true)"
  [ -n "$bt_daemon" ] || {
    log "bluetoothd missing"
    return 1
  }
  if [ "$FORCE_BLUETOOTH" -eq 1 ]; then
    stop_daemon bluetoothd
  fi
  if ! process_running bluetoothd; then
    "$bt_daemon" -n >/var/log/bluetoothd.log 2>&1 &
    echo "$!" >/run/ooonana/bluetoothd.pid
  fi
  if ! wait_for bluetoothd bluez_ready; then
    log "bluetoothd failed readiness check"
    tail -80 /var/log/bluetoothd.log >>"$LOG" 2>/dev/null || true
    return 1
  fi
  if find /sys/class/bluetooth -maxdepth 1 -name 'hci*' 2>/dev/null | grep -q .; then
    run_limited 4 bluetoothctl power on >>"$LOG" 2>&1 || true
    if command -v btmgmt >/dev/null 2>&1; then
      run_limited 4 btmgmt power on >>"$LOG" 2>&1 || true
    fi
  else
    log "bluetoothd ready; no Bluetooth controller detected"
  fi
  return 0
}

MODE="${1:-all}"
FORCE_WIFI=0
FORCE_BLUETOOTH=0
REPROBE_WIFI=0
REPROBE_BLUETOOTH=0
case "$MODE" in
  boot|all) MODE=all ;;
  wifi) MODE=wifi ;;
  bluetooth) MODE=bluetooth ;;
  force|--force) MODE=all; FORCE_WIFI=1; FORCE_BLUETOOTH=1 ;;
  force-wifi) MODE=wifi; FORCE_WIFI=1 ;;
  force-bluetooth) MODE=bluetooth; FORCE_BLUETOOTH=1 ;;
  deep|--deep) MODE=all; FORCE_WIFI=1; FORCE_BLUETOOTH=1; REPROBE_WIFI=1; REPROBE_BLUETOOTH=1 ;;
  deep-wifi) MODE=wifi; FORCE_WIFI=1; REPROBE_WIFI=1 ;;
  deep-bluetooth) MODE=bluetooth; FORCE_BLUETOOTH=1; REPROBE_BLUETOOTH=1 ;;
  status)
    printf 'dbus=%s\n' "$(dbus_ready && echo running || echo stopped)"
    printf 'networkmanager=%s\n' "$(network_manager_ready && echo running || echo stopped)"
    printf 'wpa_supplicant=%s\n' "$(wpa_supplicant_ready && echo running || echo stopped)"
    printf 'bluetoothd=%s\n' "$(bluez_ready && echo running || echo stopped)"
    exit 0
    ;;
  *) echo "usage: ooonana-service-repair [all|wifi|bluetooth|force|force-wifi|force-bluetooth|deep|deep-wifi|deep-bluetooth|status]" >&2; exit 2 ;;
esac

mkdir -p /run/ooonana /run/lock /etc/NetworkManager/conf.d /etc/wpa_supplicant
log "service repair mode=$MODE force_wifi=$FORCE_WIFI force_bluetooth=$FORCE_BLUETOOTH reprobe_wifi=$REPROBE_WIFI reprobe_bluetooth=$REPROBE_BLUETOOTH"
ensure_identity
start_device_manager
if ! start_dbus; then
  echo "ooonana: system D-Bus failed; see $LOG" >&2
  exit 1
fi

reprobe_mode=""
if [ "$REPROBE_WIFI" -eq 1 ] && [ "$REPROBE_BLUETOOTH" -eq 1 ]; then
  reprobe_mode="--force"
elif [ "$REPROBE_WIFI" -eq 1 ]; then
  reprobe_mode="--force-wifi"
elif [ "$REPROBE_BLUETOOTH" -eq 1 ]; then
  reprobe_mode="--force-bluetooth"
fi
if [ -n "$reprobe_mode" ]; then
  command -v ooonana-hardware-reprobe >/dev/null 2>&1 &&
    run_limited 20 ooonana-hardware-reprobe "$reprobe_mode" >>"$LOG" 2>&1 || true
fi
unblock_rfkill

result=0
case "$MODE" in
  wifi)
    start_network_manager || result=1
    ;;
  bluetooth)
    start_bluetooth || result=1
    ;;
  all)
    start_network_manager || result=1
    start_bluetooth || result=1
    ;;
esac

if ! find /sys/class/net -maxdepth 1 -name 'wl*' 2>/dev/null | grep -q . ||
  ! find /sys/class/bluetooth -maxdepth 1 -name 'hci*' 2>/dev/null | grep -q .; then
  command -v ooonana-wireless-diagnose >/dev/null 2>&1 &&
    run_limited 20 ooonana-wireless-diagnose >>"$LOG" 2>&1 || true
fi

if [ "$result" -ne 0 ]; then
  echo "ooonana: service start failed; see $LOG" >&2
  exit "$result"
fi
exit 0
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-service-watchdog" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

interval="${OOONANA_SERVICE_WATCHDOG_INTERVAL:-30}"
case "$interval" in
  ''|*[!0-9]*) interval=30 ;;
esac
[ "$interval" -ge 10 ] 2>/dev/null || interval=10
mkdir -p /run/ooonana /var/log
pidfile=/run/ooonana/service-watchdog.pid
if [ -s "$pidfile" ]; then
  old_pid="$(cat "$pidfile" 2>/dev/null || true)"
  [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null && exit 0
fi
echo "$$" >"$pidfile"
trap 'rm -f "$pidfile"' EXIT INT TERM

running() {
  /bin/busybox pidof "$1" >/dev/null 2>&1
}

run_limited() {
  seconds="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@"
  elif [ -x /bin/busybox ]; then
    /bin/busybox timeout "$seconds" "$@"
  else
    "$@"
  fi
}

dbus_ready() {
  [ -S /run/dbus/system_bus_socket ] || return 1
  command -v dbus-send >/dev/null 2>&1 || return 0
  run_limited 3 dbus-send --system --print-reply \
    --dest=org.freedesktop.DBus / org.freedesktop.DBus.ListNames >/dev/null 2>&1
}

network_manager_ready() {
  running NetworkManager || return 1
  command -v nmcli >/dev/null 2>&1 || return 1
  run_limited 5 nmcli -t -f STATE general >/dev/null 2>&1
}

bluez_ready() {
  running bluetoothd || return 1
  dbus_ready || return 1
  run_limited 5 dbus-send --system --print-reply \
    --dest=org.freedesktop.DBus / org.freedesktop.DBus.GetNameOwner \
    string:org.bluez >/dev/null 2>&1
}

while sleep "$interval"; do
  if ! dbus_ready || ! network_manager_ready; then
    ooonana-service-repair force-wifi >>/var/log/ooonana-service-watchdog.log 2>&1 || true
  fi
  if ! bluez_ready; then
    ooonana-service-repair force-bluetooth >>/var/log/ooonana-service-watchdog.log 2>&1 || true
  fi
done
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-wifi" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if command -v ooonana-wifi-panel >/dev/null 2>&1; then
  exec ooonana-wifi-panel "$@"
fi
command -v ooonana-service-repair >/dev/null 2>&1 && ooonana-service-repair wifi >/dev/null 2>&1 || true
if command -v nm-connection-editor >/dev/null 2>&1; then
  exec nm-connection-editor
fi
if command -v nmtui >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e nmtui
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "NetworkManager UI missing"; echo "run: ooonana get network-manager-applet"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-bluetooth" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if command -v ooonana-bluetooth-panel >/dev/null 2>&1; then
  exec ooonana-bluetooth-panel "$@"
fi
command -v ooonana-service-repair >/dev/null 2>&1 && ooonana-service-repair bluetooth >/dev/null 2>&1 || true
if command -v blueman-manager >/dev/null 2>&1; then
  exec blueman-manager
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "blueman missing"; echo "run: ooonana get blueman"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-touchpad" <<'EOF'
#!/bin/sh
set -eu

action="${1:-status}"

touchpad_ids() {
  command -v xinput >/dev/null 2>&1 || return 0
  xinput list 2>/dev/null | awk '
    BEGIN { IGNORECASE=1 }
    /touchpad|trackpad|elan|syna/ && /id=/ {
      line=$0
      sub(/^.*id=/, "", line)
      sub(/[[:space:]].*$/, "", line)
      if (line ~ /^[0-9]+$/) print line
    }
  '
}

set_enabled() {
  state="$1"
  changed=0
  for id in $(touchpad_ids | sort -u); do
    [ -n "$id" ] || continue
    xinput set-prop "$id" "Device Enabled" "$state" >/dev/null 2>&1 || true
    changed=1
  done
  return "$changed"
}

status() {
  printf 'Ooonana touchpad status\n'
  printf '======================\n'
  if command -v xinput >/dev/null 2>&1; then
    xinput list || true
    printf '\nTouchpad properties\n'
    printf '===================\n'
    for id in $(touchpad_ids | sort -u); do
      printf '\n[id %s]\n' "$id"
      xinput list-props "$id" 2>/dev/null || true
    done
  else
    printf 'xinput missing\n'
  fi
  printf '\nKernel hints\n'
  printf '============\n'
  dmesg 2>/dev/null | grep -Ei 'i2c|hid|elan|synaptics|touch|lpss|gpio|pinctrl|samsung' | tail -80 || true
  printf '\nInput devices\n'
  printf '=============\n'
  cat /proc/bus/input/devices 2>/dev/null || true
}

case "$action" in
  on|enable)
    set_enabled 1 || true
    command -v notify-send >/dev/null 2>&1 && notify-send 'Ooonana touchpad' 'enabled' || true
    ;;
  off|disable)
    set_enabled 0 || true
    command -v notify-send >/dev/null 2>&1 && notify-send 'Ooonana touchpad' 'disabled' || true
    ;;
  toggle)
    first="$(touchpad_ids | sort -u | head -n 1 || true)"
    if [ -n "$first" ] && xinput list-props "$first" 2>/dev/null | grep -q 'Device Enabled.*:[[:space:]]*1'; then
      set_enabled 0 || true
      command -v notify-send >/dev/null 2>&1 && notify-send 'Ooonana touchpad' 'disabled' || true
    else
      set_enabled 1 || true
      command -v notify-send >/dev/null 2>&1 && notify-send 'Ooonana touchpad' 'enabled' || true
    fi
    ;;
  status|doctor|diag)
    status
    ;;
  *)
    printf 'Usage: ooonana-touchpad [status|diag|on|off|toggle]\n' >&2
    exit 2
    ;;
esac
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-rofi-wifi" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
command -v ooonana-service-repair >/dev/null 2>&1 && ooonana-service-repair wifi >/dev/null 2>&1 || true
choose() {
  if [ -n "${DISPLAY:-}" ] && command -v rofi >/dev/null 2>&1; then
    printf ' Connections\n Editor\n TUI\n Status\n' | rofi -dmenu -i -p "Wi-Fi" -theme /etc/ooonana/rofi.rasi 2>/dev/null || true
  else
    printf 'Editor\n'
  fi
}
action="$(choose)"
case "$action" in
  *Connections*|*Editor*) exec ooonana-wifi ;;
  *TUI*) command -v nmtui >/dev/null 2>&1 && exec ooonana-theme-env xterm -e nmtui ;;
  *Status*) exec ooonana-theme-env xterm -e sh -lc 'nmcli dev status 2>/dev/null || ip addr; exec sh' ;;
esac
exit 0
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-rofi-bluetooth" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
command -v ooonana-service-repair >/dev/null 2>&1 && ooonana-service-repair bluetooth >/dev/null 2>&1 || true
choose() {
  if [ -n "${DISPLAY:-}" ] && command -v rofi >/dev/null 2>&1; then
    printf ' Manager\n Devices\n Power On\n Power Off\n' | rofi -dmenu -i -p "Bluetooth" -theme /etc/ooonana/rofi.rasi 2>/dev/null || true
  else
    printf 'Manager\n'
  fi
}
action="$(choose)"
case "$action" in
  *Manager*) exec ooonana-bluetooth ;;
  *Devices*) exec ooonana-theme-env xterm -e sh -lc 'bluetoothctl devices 2>/dev/null || echo "bluetoothctl missing"; exec sh' ;;
  *"Power On"*) bluetoothctl power on >/dev/null 2>&1 || true ;;
  *"Power Off"*) bluetoothctl power off >/dev/null 2>&1 || true ;;
esac
exit 0
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-wifi-panel" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
NATIVE_APP="/usr/lib/ooonana/ui/wifi_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" "$@"
fi
command -v ooonana-service-repair >/dev/null 2>&1 && ooonana-service-repair wifi >/dev/null 2>&1 || true
if [ -n "${DISPLAY:-}" ] && command -v yad >/dev/null 2>&1; then
  nm_state="$(nmcli -t -f STATE general 2>/dev/null | head -n 1 || true)"
  wifi_radio="$(nmcli -t -f WIFI radio 2>/dev/null | head -n 1 || true)"
  [ -n "$nm_state" ] || nm_state="service not ready"
  [ -n "$wifi_radio" ] || wifi_radio="unknown"
  needs_repair=0
  nmcli general status >/dev/null 2>&1 || needs_repair=1
  device_summary="$(nmcli -t -f DEVICE,TYPE,STATE dev status 2>/dev/null | sed 's/:/ /g' | head -n 3 | tr '\n' '; ' || true)"
  network_summary="$(nmcli dev wifi list 2>/dev/null | head -n 5 | tr '\n' '; ' || true)"
  rfkill_summary="$(rfkill list 2>/dev/null | awk 'NR <= 8 { gsub(/^[[:space:]]+/, ""); printf "%s; ", $0 }' || true)"
  [ -n "$device_summary" ] || device_summary="$(ip -brief addr 2>/dev/null | head -n 3 | tr '\n' '; ' || true)"
  [ -n "$device_summary" ] || device_summary="no network device data"
  [ -n "$network_summary" ] || network_summary="no scan data yet"
  [ -n "$rfkill_summary" ] || rfkill_summary="rfkill unavailable or no block data"
  if [ "$needs_repair" = "1" ]; then
    if yad --center --title "Ooonana Wi-Fi" --width=760 --height=500 \
      --text "Wi-Fi control\nService: $nm_state    Radio: $wifi_radio\nRepair Service means NetworkManager did not answer yet." \
      --list --print-column=1 --column Action --column Status --column Detail \
      "Open Editor" "$nm_state" "Open NetworkManager connection editor" \
      "Scan Networks" "$wifi_radio" "$network_summary" \
      "Turn Wi-Fi On" "$wifi_radio" "Enable radio and networking" \
      "Devices" "$nm_state" "$device_summary" \
      "Radio/RFKill" "$wifi_radio" "$rfkill_summary" \
      --button="Open Editor":0 --button="Scan Networks":2 --button="Turn Wi-Fi On":5 --button="Repair Service":3 --button=Refresh:4 --button=Close:1 2>/dev/null; then
      rc=0
    else
      rc="$?"
    fi
  else
    if yad --center --title "Ooonana Wi-Fi" --width=760 --height=500 \
      --text "Wi-Fi control\nService: $nm_state    Radio: $wifi_radio" \
      --list --print-column=1 --column Action --column Status --column Detail \
      "Open Editor" "$nm_state" "Open NetworkManager connection editor" \
      "Scan Networks" "$wifi_radio" "$network_summary" \
      "Turn Wi-Fi On" "$wifi_radio" "Enable radio and networking" \
      "Devices" "$nm_state" "$device_summary" \
      "Radio/RFKill" "$wifi_radio" "$rfkill_summary" \
      --button="Open Editor":0 --button="Scan Networks":2 --button="Turn Wi-Fi On":5 --button=Refresh:4 --button=Close:1 2>/dev/null; then
      rc=0
    else
      rc="$?"
    fi
  fi
  case "$rc" in
    0) exec ooonana-wifi ;;
    2) nmcli dev wifi rescan >/dev/null 2>&1 || true; exec ooonana-wifi-panel ;;
    3) ooonana-service-repair force-wifi >/dev/null 2>&1 || true; exec ooonana-wifi-panel ;;
    4) exec ooonana-wifi-panel ;;
    5) nmcli networking on >/dev/null 2>&1 || true; nmcli radio wifi on >/dev/null 2>&1 || true; exec ooonana-wifi-panel ;;
  esac
  exit 0
fi
exec ooonana-rofi-wifi
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-wifi-status" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if ! command -v nmcli >/dev/null 2>&1; then
  printf '\357\207\253 --\n'
  exit 0
fi
radio="$(nmcli -t -f WIFI radio 2>/dev/null | head -n 1 || true)"
case "$radio" in
  enabled)
    name="$(nmcli -t -f TYPE,NAME connection show --active 2>/dev/null | awk -F: '$1 == "802-11-wireless" { print $2; exit }')"
    if [ -n "$name" ]; then
      printf '\357\207\253 %s\n' "$name"
    else
      printf '\357\207\253\n'
    fi
    ;;
  *) printf '\357\207\253 off\n' ;;
esac
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-bluetooth-panel" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
NATIVE_APP="/usr/lib/ooonana/ui/bluetooth_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" "$@"
fi
command -v ooonana-service-repair >/dev/null 2>&1 && ooonana-service-repair bluetooth >/dev/null 2>&1 || true
if [ -n "${DISPLAY:-}" ] && command -v yad >/dev/null 2>&1; then
  bt_state="$(bluetoothctl show 2>/dev/null | awk -F': ' '/Powered/ {print $2; exit}' || true)"
  [ -n "$bt_state" ] || bt_state="service not ready"
  needs_repair=0
  bluetoothctl show >/dev/null 2>&1 || needs_repair=1
  controller_summary="$(bluetoothctl show 2>/dev/null | awk -F': ' 'NR <= 12 { gsub(/^[[:space:]]+/, ""); printf "%s; ", $0 }' || true)"
  device_summary="$(bluetoothctl devices 2>/dev/null | head -n 8 | tr '\n' '; ' || true)"
  rfkill_summary="$(rfkill list bluetooth 2>/dev/null | awk 'NR <= 8 { gsub(/^[[:space:]]+/, ""); printf "%s; ", $0 }' || true)"
  [ -n "$controller_summary" ] || controller_summary="controller not ready"
  [ -n "$device_summary" ] || device_summary="no paired devices listed"
  [ -n "$rfkill_summary" ] || rfkill_summary="rfkill unavailable or no bluetooth block data"
  if [ "$needs_repair" = "1" ]; then
    if yad --center --title "Ooonana Bluetooth" --width=760 --height=500 \
      --text "Bluetooth control\nPower: $bt_state\nRepair Service means bluetoothd did not answer yet." \
      --list --print-column=1 --column Action --column Status --column Detail \
      "Open Manager" "$bt_state" "Open Blueman device manager" \
      "Power On" "$bt_state" "Enable Bluetooth controller" \
      "Power Off" "$bt_state" "Disable Bluetooth controller" \
      "Devices" "$bt_state" "$device_summary" \
      "Radio/RFKill" "$bt_state" "$rfkill_summary" \
      "Controller" "$bt_state" "$controller_summary" \
      --button="Open Manager":0 --button="Power On":2 --button="Power Off":3 --button="Repair Service":4 --button=Refresh:5 --button=Close:1 2>/dev/null; then
      rc=0
    else
      rc="$?"
    fi
  else
    if yad --center --title "Ooonana Bluetooth" --width=760 --height=500 \
      --text "Bluetooth control\nPower: $bt_state" \
      --list --print-column=1 --column Action --column Status --column Detail \
      "Open Manager" "$bt_state" "Open Blueman device manager" \
      "Power On" "$bt_state" "Enable Bluetooth controller" \
      "Power Off" "$bt_state" "Disable Bluetooth controller" \
      "Devices" "$bt_state" "$device_summary" \
      "Radio/RFKill" "$bt_state" "$rfkill_summary" \
      "Controller" "$bt_state" "$controller_summary" \
      --button="Open Manager":0 --button="Power On":2 --button="Power Off":3 --button=Refresh:5 --button=Close:1 2>/dev/null; then
      rc=0
    else
      rc="$?"
    fi
  fi
  case "$rc" in
    0) exec ooonana-bluetooth ;;
    2) bluetoothctl power on >/dev/null 2>&1 || true ;;
    3) bluetoothctl power off >/dev/null 2>&1 || true ;;
    4) ooonana-service-repair force-bluetooth >/dev/null 2>&1 || true; exec ooonana-bluetooth-panel ;;
    5) exec ooonana-bluetooth-panel ;;
  esac
  exit 0
fi
exec ooonana-rofi-bluetooth
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-bluetooth-status" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if ! command -v bluetoothctl >/dev/null 2>&1; then
  printf '\357\212\223 --\n'
  exit 0
fi
powered="$({ bluetoothctl show || true; } 2>/dev/null | awk -F': ' '/Powered:/ { print $2; exit }')"
case "$powered" in
  yes) printf '\357\212\223\n' ;;
  *) printf '\357\212\223 off\n' ;;
esac
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-rofi-brightness" <<'EOF'
#!/bin/sh
set -eu
choose() {
  if [ -n "${DISPLAY:-}" ] && command -v rofi >/dev/null 2>&1; then
    printf ' 25%%\n 50%%\n 75%%\n 100%%\n Up 5%%\n Down 5%%\n▰ Slider\n' | rofi -dmenu -i -p "Brightness" -theme /etc/ooonana/rofi.rasi 2>/dev/null || true
  else
    printf 'Slider\n'
  fi
}
action="$(choose)"
case "$action" in
  *25%*) exec ooonana-brightness 25% ;;
  *50%*) exec ooonana-brightness 50% ;;
  *75%*) exec ooonana-brightness 75% ;;
  *100%*) exec ooonana-brightness 100% ;;
  *"Up 5%"*) exec ooonana-brightness +5% ;;
  *"Down 5%"*) exec ooonana-brightness 5%- ;;
  *Slider*) exec ooonana-brightness ;;
esac
exit 0
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-brightness-panel" <<'EOF'
#!/bin/sh
set -eu
NATIVE_APP="/usr/lib/ooonana/ui/controls_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" brightness "$@"
fi
if ! command -v brightnessctl >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e sh -lc 'echo "brightnessctl missing"; echo "run: ooonana get brightnessctl"; exec sh'
fi
current="$(brightnessctl -m 2>/dev/null | awk -F, '{gsub(/%/,"",$4); print $4; exit}')"
[ -n "$current" ] || current=75
if [ -n "${DISPLAY:-}" ] && command -v yad >/dev/null 2>&1; then
  set +e
  value="$(yad --scale --title "Brightness" --center --width=420 --height=120 \
    --min-value=0 --max-value=100 --value="$current" \
    --button=Cancel:1 --button=Apply:0 2>/dev/null)"
  rc="$?"
  set -e
  [ "$rc" -eq 0 ] && [ -n "$value" ] && exec brightnessctl set "${value}%"
  exit 0
fi
exec ooonana-brightness
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-audio-panel" <<'EOF'
#!/bin/sh
set -eu
NATIVE_APP="/usr/lib/ooonana/ui/controls_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" audio "$@"
fi
current="50"
if command -v pactl >/dev/null 2>&1; then
  current="$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | awk -F/ 'NR==1 {gsub(/[% ]/,"",$2); print $2; exit}')"
fi
case "$current" in ""|*[!0-9]*) current=50 ;; esac
if [ -n "${DISPLAY:-}" ] && command -v yad >/dev/null 2>&1; then
  set +e
  value="$(yad --scale --title "Sound" --center --width=420 --height=120 \
    --min-value=0 --max-value=150 --value="$current" \
    --button=Mixer:2 --button=Cancel:1 --button=Apply:0 2>/dev/null)"
  rc="$?"
  set -e
  case "$rc" in
    0) [ -n "$value" ] && exec pactl set-sink-volume @DEFAULT_SINK@ "${value}%" ;;
    2) command -v pavucontrol >/dev/null 2>&1 && exec pavucontrol ;;
  esac
  exit 0
fi
if command -v pavucontrol >/dev/null 2>&1; then
  exec pavucontrol
fi
exec ooonana-theme-env xterm -e sh -lc 'pactl info 2>/dev/null || echo "pactl missing"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-audio-status" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
if command -v pactl >/dev/null 2>&1 && pactl info >/dev/null 2>&1; then
  muted="$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | awk '{ print $2 }')"
  volume="$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | awk -F/ 'NR == 1 { gsub(/[ %]/, "", $2); print $2; exit }')"
  case "$volume" in ''|*[!0-9]*) volume=0 ;; esac
  if [ "$muted" = "yes" ]; then
    printf '\357\200\246 muted\n'
  elif [ "$volume" -ge 60 ]; then
    printf '\357\200\250 %s%%\n' "$volume"
  elif [ "$volume" -gt 0 ]; then
    printf '\357\200\247 %s%%\n' "$volume"
  else
    printf '\357\200\246 0%%\n'
  fi
  exit 0
fi
if command -v amixer >/dev/null 2>&1; then
  volume="$(amixer get Master 2>/dev/null | awk -F'[][]' '/%/ { print $2; exit }')"
  [ -n "$volume" ] && { printf '\357\200\247 %s\n' "$volume"; exit 0; }
fi
printf '\357\200\246 --\n'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-battery-status" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
bat=""
for path in /sys/class/power_supply/BAT*; do
  [ -d "$path" ] || continue
  bat="$path"
  break
done
[ -n "$bat" ] || { printf '\357\211\204 --\n'; exit 0; }
capacity="$(cat "$bat/capacity" 2>/dev/null || printf '')"
status="$(cat "$bat/status" 2>/dev/null || printf '')"
case "$capacity" in ''|*[!0-9]*) capacity=0 ;; esac
case "$status" in
  Charging) icon='\357\207\246' ;;
  Full) icon='\357\211\200' ;;
  *) icon='\357\211\204' ;;
esac
printf '%b %s%%\n' "$icon" "$capacity"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-volume" <<'EOF'
#!/bin/sh
set -eu
exec ooonana-audio-panel "$@"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-rofi-power" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
choose() {
  if [ -n "${OOONANA_POWER_ACTION:-}" ]; then
    printf '%s\n' "$OOONANA_POWER_ACTION"
    return 0
  fi
  if [ -n "${DISPLAY:-}" ] && command -v rofi >/dev/null 2>&1; then
    printf 'Lock\nLog out\nRestart i3\nReboot\nShut down\nCancel\n' |
      rofi -dmenu -i -p "Power" -theme /etc/ooonana/rofi.rasi 2>/dev/null || true
    return 0
  fi
  if [ -t 0 ]; then
    printf '1) Lock\n2) Log out\n3) Restart i3\n4) Reboot\n5) Shut down\n6) Cancel\n> ' >&2
    read -r answer || answer=6
    case "$answer" in
      1) echo Lock ;;
      2) echo 'Log out' ;;
      3) echo 'Restart i3' ;;
      4) echo Reboot ;;
      5) echo 'Shut down' ;;
      *) echo Cancel ;;
    esac
  fi
}
if [ "${1:-}" = "--dry-run" ]; then
  echo "OOONANA_POWER_MENU_OK"
  exit 0
fi
action="$(choose)"
case "$action" in
  Lock) command -v i3lock >/dev/null 2>&1 && exec i3lock ;;
  "Log out") command -v i3-msg >/dev/null 2>&1 && i3-msg exit >/dev/null 2>&1 || true ;;
  "Restart i3") command -v i3-msg >/dev/null 2>&1 && i3-msg restart >/dev/null 2>&1 || true ;;
  Reboot) exec bunana --restart ;;
  "Shut down") exec bunana --shutdown ;;
esac
exit 0
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-power-menu" <<'EOF'
#!/bin/sh
set -eu
NATIVE_APP="/usr/lib/ooonana/ui/controls_app.py"
if [ "${1:-}" = "--dry-run" ] || [ -n "${OOONANA_POWER_ACTION:-}" ]; then
  exec ooonana-rofi-power "$@"
fi
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" power "$@"
fi
exec ooonana-rofi-power "$@"
EOF

  install -D -m 0755 "$ROOT/packages/ooonana/usr/bin/hsetroot" "$ROOTFS/usr/bin/hsetroot"

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/xsettingsd" <<'EOF'
#!/bin/sh
set -eu
case "${1:-}" in
  --help|-h)
    echo "Ooonana xsettingsd compatibility daemon"
    exit 0
    ;;
esac
while :; do
  sleep 3600
done
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-screenshot" <<'EOF'
#!/bin/sh
set -eu
dir="${HOME:-/root}/Pictures/Ooonana"
mkdir -p "$dir"
file="$dir/screenshot-$(date +%Y%m%d-%H%M%S).png"
if command -v maim >/dev/null 2>&1; then
  if [ "${1:-}" = "--select" ]; then
    maim -s "$file"
  else
    maim "$file"
  fi
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Ooonana Screenshot" "$file" || true
  fi
  printf '%s\n' "$file"
  exit 0
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "maim missing"; echo "run: ooonana get maim"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-editor" <<'EOF'
#!/bin/sh
set -eu
target="${1:-}"
if command -v geany >/dev/null 2>&1; then
  if [ -n "$target" ]; then
    exec geany "$target"
  fi
  exec geany
fi
if command -v vim >/dev/null 2>&1; then
  if [ -n "$target" ]; then
    exec ooonana-theme-env xterm -e vim "$target"
  fi
  exec ooonana-theme-env xterm -e vim
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "editor missing"; echo "run: ooonana get geany vim"; exec sh'
EOF

  install -D -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-music" "$ROOTFS/usr/bin/ooonana-music"
  install -D -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-media-control" "$ROOTFS/usr/bin/ooonana-media-control"
  install -D -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-media-status" "$ROOTFS/usr/bin/ooonana-media-status"

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-processes" <<'EOF'
#!/bin/sh
set -eu
if command -v htop >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e htop
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "htop missing"; echo "run: ooonana get htop"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-ranger" <<'EOF'
#!/bin/sh
set -eu
path="${1:-${HOME:-/root}}"
if command -v ranger >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e ranger "$path"
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "ranger missing"; echo "run: ooonana get ranger"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-brightness" <<'EOF'
#!/bin/sh
set -eu
if ! command -v brightnessctl >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e sh -lc 'echo "brightnessctl missing"; echo "run: ooonana get brightnessctl"; exec sh'
fi
if [ "$#" -gt 0 ]; then
  exec brightnessctl set "$1"
fi
if [ -n "${DISPLAY:-}" ] && command -v yad >/dev/null 2>&1; then
  current="$(brightnessctl -m 2>/dev/null | awk -F, '{gsub(/%/,"",$4); print $4; exit}')"
  [ -n "$current" ] || current=75
  value="$(yad --center --title "Ooonana Brightness" --scale --min-value=1 --max-value=100 --value="$current" --button=Apply:0 2>/dev/null || true)"
  [ -n "$value" ] && exec brightnessctl set "${value}%"
fi
exec ooonana-theme-env xterm -e sh -lc 'brightnessctl; echo; echo "Usage: ooonana-brightness 75%"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-brightness-status" <<'EOF'
#!/bin/sh
set -eu
value="0"
if command -v brightnessctl >/dev/null 2>&1; then
  value="$(brightnessctl -m 2>/dev/null | awk -F, '{gsub(/%/,"",$4); print $4; exit}')"
fi
case "$value" in
  ''|*[!0-9]*) value=0 ;;
esac
filled=$(( (value + 9) / 10 ))
bar=""
i=1
while [ "$i" -le 10 ]; do
  if [ "$i" -le "$filled" ]; then
    bar="${bar}#"
  else
    bar="${bar}-"
  fi
  i=$((i + 1))
done
printf ' %s %s%%\n' "$bar" "$value"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-packages-app" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "yad packages app"
  echo "actions: update search install remove upgrade sources doctor"
  echo "native GTK app: /usr/lib/ooonana/ui/packages_app.py"
  echo "OOONANA_PACKAGES_NATIVE_OK"
  echo "OOONANA_PACKAGES_APP_OK"
  exit 0
fi

NATIVE_APP="/usr/lib/ooonana/ui/packages_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" "$@"
fi

open_term() {
  if command -v ooonana-theme-env >/dev/null 2>&1; then
    exec ooonana-theme-env xterm -e sh -lc 'ooonana help packages; exec sh'
  fi
  exec sh -lc 'ooonana help packages; exec sh'
}

run_log() {
  title="$1"
  shift
  tmp="${TMPDIR:-/tmp}/ooonana-packages.$$"
  mkdir -p "$tmp"
  log="$tmp/log.txt"
  {
    printf '$'
    printf ' %s' "$@"
    printf '\n\n'
    "$@"
  } >"$log" 2>&1 || true
  yad --center --title "$title" --width=780 --height=520 --text-info --filename="$log" 2>/dev/null || true
  rm -rf "$tmp"
}

if [ -z "${DISPLAY:-}" ] || ! command -v yad >/dev/null 2>&1; then
  open_term
fi

while :; do
  action="$(yad --center --title "Ooonana Packages" --width=560 --height=360 \
    --list --print-column=1 --column Action --column Description \
    update "Sync package repos" \
    search "Search packages" \
    install "Install package" \
    remove "Remove package" \
    upgrade "Upgrade installed packages" \
    sources "Show configured repos" \
    doctor "Check package repos" 2>/dev/null || true)"
  [ -n "$action" ] || exit 0
  case "$action" in
    update)
      run_log "Ooonana Packages Update" ooonana update
      ;;
    search)
      query="$(yad --center --title "Ooonana Package Search" --entry --text "Search query" 2>/dev/null || true)"
      [ -n "$query" ] && run_log "Ooonana Package Search" ooonana search "$query"
      ;;
    install)
      pkg="$(yad --center --title "Ooonana Install Package" --entry --text "Package name" 2>/dev/null || true)"
      [ -n "$pkg" ] && run_log "Ooonana Install Package" ooonana get "$pkg"
      ;;
    remove)
      pkg="$(yad --center --title "Ooonana Remove Package" --entry --text "Package name" 2>/dev/null || true)"
      [ -n "$pkg" ] && run_log "Ooonana Remove Package" ooonana remove "$pkg"
      ;;
    upgrade)
      run_log "Ooonana Packages Upgrade" ooonana upgrade
      ;;
    sources)
      run_log "Ooonana Package Sources" ooonana sources
      ;;
    doctor)
      run_log "Ooonana Repo Doctor" ooonana repo doctor
      ;;
  esac
done
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-packages" <<'EOF'
#!/bin/sh
set -eu
app="$(dirname "$0")/ooonana-packages-app"
[ -x "$app" ] && exec "$app" "$@"
exec ooonana-packages-app "$@"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-settings" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "yad settings menu"
  echo "actions: theme wallpaper display audio wifi bluetooth packages brightness screenshot editor music processes ranger ai terminal browser files repo about"
  echo "sections: System Hardware Applications Ooonana"
  echo "XFCE-style control center"
  echo "settings sidebar: System Hardware Network Appearance Apps Ooonana Logs"
  echo "category screens: status cards actions details"
  echo "status cards: theme wallpaper network bluetooth audio display repo"
  echo "control center layout"
  echo "settings tabs: Overview System Hardware Apps Ooonana Logs"
  echo "quick controls: theme wallpaper brightness volume wifi bluetooth display repo"
  echo "icon grid: theme wallpaper display audio wifi bluetooth brightness terminal browser files packages ai"
  echo "brightness scale: current brightnessctl value"
  echo "safe launchers: terminal browser files ai packages"
  echo "GitLab Pages repo: https://ooonana.gitlab.io/ooonana-repo"
  echo "OOONANA_SETTINGS_THEME_OK"
  echo "native GTK app: /usr/lib/ooonana/ui/settings_app.py"
  echo "OOONANA_SETTINGS_NATIVE_OK"
  echo "OOONANA_SETTINGS_GUI_OK"
  exit 0
fi

NATIVE_APP="/usr/lib/ooonana/ui/settings_app.py"
if [ -x /usr/bin/python3 ] && [ -f "$NATIVE_APP" ] &&
  /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
  exec /usr/bin/python3 "$NATIVE_APP" "$@"
fi

open_term() {
  if command -v ooonana-theme-env >/dev/null 2>&1; then
    exec ooonana-theme-env xterm -e sh -lc 'ooonana help ui; exec sh'
  fi
  exec sh -lc 'ooonana help ui; exec sh'
}

theme_status() {
  if [ -f "${HOME:-/root}/.config/ooonana/theme" ]; then
    read -r theme <"${HOME:-/root}/.config/ooonana/theme" || theme=""
  elif [ -f /etc/ooonana/theme ]; then
    read -r theme </etc/ooonana/theme || theme=""
  else
    theme="${OOONANA_THEME:-dark}"
  fi
  [ -n "$theme" ] || theme="dark"
  printf '%s\n' "$theme"
}

wallpaper_status() {
  if [ -f "${HOME:-/root}/.config/ooonana/wallpaper" ]; then
    read -r wallpaper <"${HOME:-/root}/.config/ooonana/wallpaper" || wallpaper=""
  else
    wallpaper="/usr/share/ooonana/wallpapers/ooonana-notes.jpg"
  fi
  printf '%s\n' "$wallpaper"
}

launch_terminal() {
  if command -v ooonana-theme-env >/dev/null 2>&1 && command -v xterm >/dev/null 2>&1; then
    ooonana-theme-env xterm -e sh -lc "${1:-exec sh}" &
    return 0
  fi
  sh -lc "${1:-exec sh}"
}

settings_status_text() {
  wifi_status="service not ready"
  if command -v nmcli >/dev/null 2>&1; then
    wifi_status="$(nmcli -t -f STATE general 2>/dev/null | head -n 1 || true)"
    [ -n "$wifi_status" ] || wifi_status="service not ready"
  fi
  bluetooth_status="service not ready"
  if command -v bluetoothctl >/dev/null 2>&1; then
    bluetooth_status="$(bluetoothctl show 2>/dev/null | awk -F': ' '/Powered/ {print $2; exit}' || true)"
    [ -n "$bluetooth_status" ] || bluetooth_status="service not ready"
  fi
  printf 'one-window settings hub\n'
  printf 'Theme: %s\n' "$(theme_status)"
  printf 'Wallpaper: %s\n' "$(basename "$(wallpaper_status)" 2>/dev/null || echo wallpaper)"
  printf 'Wi-Fi: %s\n' "$wifi_status"
  printf 'Bluetooth: %s\n' "$bluetooth_status"
  printf 'Audio: %s\n' "$(command -v pavucontrol >/dev/null 2>&1 && echo pavucontrol || echo basic)"
}

show_status_cards() {
  overview="${TMPDIR:-/tmp}/ooonana-settings-overview.$$"
  {
    printf 'XFCE-style control center\n'
    printf 'Ooonana Control Center\n'
    printf '======================\n\n'
    printf 'Theme      %s\n' "$(theme_status)"
    printf 'Wallpaper  %s\n' "$(wallpaper_status)"
    printf 'Display    %s\n' "$(command -v arandr >/dev/null 2>&1 && echo arandr || echo xrandr)"
    printf 'Audio      %s\n' "$(command -v pavucontrol >/dev/null 2>&1 && echo pavucontrol || echo basic)"
    printf 'Wi-Fi      %s\n' "$(command -v nm-connection-editor >/dev/null 2>&1 && echo NetworkManager || echo basic)"
    printf 'Bluetooth  %s\n' "$(command -v blueman-manager >/dev/null 2>&1 && echo blueman || echo missing)"
    printf 'Repo       %s\n' "https://ooonana.gitlab.io/ooonana-repo"
    printf '\nQuick controls: theme wallpaper brightness volume wifi bluetooth display repo\n'
    printf 'Settings tabs: Overview System Hardware Network Appearance Apps Ooonana Logs\n'
    printf 'Network/Bluetooth/Audio ready when services are running\n'
  } >"$overview"
  yad --center --title "Ooonana Control Center" --width=760 --height=500 \
    --text-info --filename="$overview" \
    --button=Settings:0 --button=Close:1 2>/dev/null
  rc="$?"
  rm -f "$overview"
  return "$rc"
}

show_overview() {
  show_status_cards
}

show_category() {
  section="$1"
  case "$section" in
    System)
      yad --center --title "Ooonana Settings - System" --width=820 --height=560 \
        --text "category screen: System" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" overview "Overview" "Status cards and system summary" \
        "" theme "Theme" "Dark/light theme and apply now" \
        "" power "Power" "Shutdown, restart, logout" 2>/dev/null || true
      ;;
    Hardware)
      yad --center --title "Ooonana Settings - Hardware" --width=820 --height=560 \
        --text "category screen: Hardware" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" display "Display" "Monitor layout with arandr" \
        "" audio "Audio" "Volume slider and pavucontrol" \
        "" brightness "Brightness" "Backlight slider" 2>/dev/null || true
      ;;
    Network)
      yad --center --title "Ooonana Settings - Network" --width=820 --height=560 \
        --text "category screen: Network" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" wifi "Wi-Fi" "NetworkManager status and scan panel" \
        "" bluetooth "Bluetooth" "Bluetooth status and device panel" \
        "" repo "Repo" "Set GitLab Pages or backup repo" 2>/dev/null || true
      ;;
    Appearance)
      yad --center --title "Ooonana Settings - Appearance" --width=820 --height=560 \
        --text "category screen: Appearance" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" theme "Theme" "Dark/light theme" \
        "" wallpaper "Wallpaper" "Choose desktop wallpaper" 2>/dev/null || true
      ;;
    Apps|Applications)
      yad --center --title "Ooonana Settings - Apps" --width=820 --height=560 \
        --text "category screen: Applications" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" browser "Browser" "Open Chromium" \
        "" files "Files" "Open Nemo file manager" \
        "" terminal "Terminal" "Open themed terminal" \
        "" screenshot "Screenshot" "Take screenshot" \
        "" editor "Editor" "Open Geany or Vim" \
        "" music "Music" "Open MPD client" \
        "" processes "Processes" "Open htop" \
        "" ranger "Ranger" "Open terminal file manager" 2>/dev/null || true
      ;;
    Ooonana)
      yad --center --title "Ooonana Settings - Ooonana" --width=820 --height=560 \
        --text "category screen: Ooonana" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" packages "Packages" "Open package manager" \
        "" ai "AI" "Open Ooonana AI workbench" \
        "" installer "Installer" "Install Ooonana OS" \
        "" overview "Overview" "Show system status inside Settings" 2>/dev/null || true
      ;;
    Logs)
      yad --center --title "Ooonana Settings - Logs" --width=820 --height=560 \
        --text "category screen: Logs" \
        --list --print-column=2 --column Icon --column Action --column Name --column Description \
        "" logs "Logs" "Open settings log" \
        "" overview "Overview" "Show system status inside Settings" 2>/dev/null || true
      ;;
    *)
      show_status_cards || true
      ;;
  esac
}

choose_settings_action() {
  section="$(yad --center --title "Ooonana Settings" --width=420 --height=500 \
    --text "settings sidebar
$(settings_status_text)" \
    --list --print-column=1 --column "System Hardware Network Appearance Apps Ooonana Logs" \
    System Hardware Network Appearance Apps Ooonana Logs 2>/dev/null || true)"
  [ -n "$section" ] || return 0
  show_category "$section"
}

set_theme_action() {
  theme="$(yad --center --title "Ooonana Theme" --form --field "Theme:CB" "dark!light" 2>/dev/null | cut -d'|' -f1 || true)"
  case "$theme" in
    dark|light)
      if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
        mkdir -p /etc/ooonana
        printf '%s\n' "$theme" >/etc/ooonana/theme
      else
        mkdir -p "${HOME:-/tmp}/.config/ooonana"
        printf '%s\n' "$theme" >"${HOME:-/tmp}/.config/ooonana/theme"
      fi
      ooonana-theme-env apply 2>/dev/null || true
      yad --center --title "Ooonana Theme" --text "Theme changed to $theme" --timeout=2 2>/dev/null || true
      echo "OOONANA_SETTINGS_THEME_OK" >/dev/null
      ;;
  esac
}

show_settings_logs() {
  log="${XDG_RUNTIME_DIR:-/tmp}/ooonana-settings.log"
  [ -f "$log" ] || printf 'settings log ready\n' >"$log" 2>/dev/null || true
  yad --center --title "Ooonana Settings Logs" --width=760 --height=520 \
    --text-info --filename="$log" 2>/dev/null || true
}

if [ -z "${DISPLAY:-}" ] || ! command -v yad >/dev/null 2>&1; then
  open_term
fi

while :; do
  action="$(choose_settings_action)"
  [ -n "$action" ] || exit 0
  case "$action" in
    overview)
      show_status_cards || true
      ;;
    theme)
      set_theme_action
      ;;
    wallpaper)
      file="$(yad --center --title "Ooonana Wallpaper" --file --filename="/usr/share/ooonana/wallpapers/" 2>/dev/null || true)"
      [ -n "$file" ] && ooonana-wallpaper "$file" || true
      ;;
    display)
      command -v arandr >/dev/null 2>&1 && arandr || yad --center --title "Display" --text "arandr missing"
      ;;
    audio)
      if command -v ooonana-audio-panel >/dev/null 2>&1; then
        ooonana-audio-panel || true
      elif command -v pavucontrol >/dev/null 2>&1; then
        pavucontrol
      else
        yad --center --title "Audio" --text "pavucontrol missing"
      fi
      ;;
    wifi)
      ooonana-wifi-panel || true
      ;;
    bluetooth)
      ooonana-bluetooth-panel || true
      ;;
    packages)
      ooonana-packages-app || true
      ;;
    ai)
      ooonana-ai-app || true
      ;;
    browser)
      ooonana-browser || true
      ;;
    files)
      ooonana-files || true
      ;;
    terminal)
      launch_terminal 'exec sh -l'
      ;;
    brightness)
      ooonana-brightness-panel || true
      ;;
    screenshot)
      ooonana-screenshot || true
      ;;
    editor)
      ooonana-editor || true
      ;;
    music)
      ooonana-music || true
      ;;
    processes)
      ooonana-processes || true
      ;;
    ranger)
      ooonana-ranger || true
      ;;
    repo)
      repo="$(yad --center --title "Ooonana Repo" --form \
        --text "GitLab Pages repo is default. GitHub release tarball is backup." \
        --field "Repo:CB" "https://ooonana.gitlab.io/ooonana-repo!https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz" \
        --field "Custom" "" 2>/dev/null || true)"
      if [ -n "$repo" ]; then
        chosen="$(printf '%s' "$repo" | cut -d'|' -f2)"
        [ -n "$chosen" ] || chosen="$(printf '%s' "$repo" | cut -d'|' -f1)"
        mkdir -p /etc/ooonana/sources.d 2>/dev/null || true
        {
          printf 'OOONANA_REPO_NAME="gitlab"\n'
          printf 'OOONANA_REPO_URI="%s"\n' "$chosen"
        } >/etc/ooonana/sources.d/cloud.repo 2>/dev/null ||
          yad --center --title "Repo" --text "Need root to write /etc/ooonana/sources.d/cloud.repo"
      fi
      ;;
    installer)
      ooonana-gui-installer || true
      ;;
    power)
      ooonana-power-menu || true
      ;;
    logs)
      show_settings_logs
      ;;
    about)
      show_info
      ;;
  esac
done
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-settings-launch" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "launches ooonana-settings with GUI/terminal fallback"
  echo "OOONANA_SETTINGS_LAUNCH_OK"
  exit 0
fi

log="${XDG_RUNTIME_DIR:-/tmp}/ooonana-settings.log"
rm -f "$log" 2>/dev/null || true

if ooonana-settings "$@" >"$log" 2>&1; then
  exit 0
fi

status="$?"
if [ -n "${DISPLAY:-}" ] && command -v yad >/dev/null 2>&1; then
  yad --center --title "Ooonana Settings" \
    --text "Ooonana Settings failed to launch. Log: $log" \
    --button=Close:1 --button=Log:0 2>/dev/null &&
    yad --center --title "Ooonana Settings Log" --width=760 --height=520 \
      --text-info --filename="$log" 2>/dev/null || true
fi

if command -v ooonana-theme-env >/dev/null 2>&1 && command -v xterm >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -title "Ooonana Settings Log" -e sh -lc "cat '$log' 2>/dev/null; printf '\nexit: $status\n'; exec sh"
fi

cat "$log" 2>/dev/null || true
exit "$status"
EOF

  install -D -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-wallpaper" "$ROOTFS/usr/bin/ooonana-wallpaper"

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/NetworkManager/NetworkManager.conf" <<'EOF'
[main]
plugins=keyfile
dhcp=internal
auth-polkit=false

[device-ooonana-wifi]
match-device=type:wifi
managed=1
wifi.backend=wpa_supplicant
wifi.scan-rand-mac-address=no

[ifupdown]
managed=true
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/bluetooth/main.conf" <<'EOF'
[General]
Name = Ooonana
ControllerMode = dual
FastConnectable = true
DiscoverableTimeout = 180
PairableTimeout = 0
JustWorksRepairing = always

[Policy]
AutoEnable = true
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/xsettingsd.conf" <<'EOF'
Net/ThemeName "Adwaita-dark"
Net/IconThemeName "Adwaita"
Gtk/FontName "Sans 10"
Gtk/CursorThemeName "Adwaita"
Gtk/ButtonImages 1
Gtk/MenuImages 1
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/polybar.ini" <<'EOF'
[colors]
background = #080a0d
background-alt = #151a21
foreground = #ffb21a
accent = #ffd37a
muted = #7a5014
urgent = #050505
cool = #5eb6ff

[bar/ooonana]
width = 100%
height = 34
offset-x = 0
offset-y = 0
radius = 0
fixed-center = true
background = ${colors.background}
foreground = ${colors.foreground}
border-size = 0
padding-left = 1
padding-right = 1
module-margin = 0
separator = "  "
separator-foreground = ${colors.muted}
line-size = 2
line-color = ${colors.accent}
font-0 = monospace:size=10;2
font-1 = "Font Awesome 7 Free Solid:size=10;2"
font-2 = "Font Awesome 6 Free Solid:size=10;2"
font-3 = "Font Awesome 5 Free Solid:size=10;2"
font-4 = "Font Awesome 6 Brands:size=10;2"
font-5 = "Font Awesome 5 Brands:size=10;2"
modules-left = brand workspaces terminal browser files editor media title win-min win-full win-close
modules-center =
modules-right = audio brightness battery bluetooth wifi date power
tray-position = right
tray-padding = 2
wm-restack = i3
override-redirect = false
enable-ipc = true

[module/brand]
type = custom/text
content = Ooonana
content-foreground = ${colors.foreground}
content-background = ${colors.background}
content-padding = 2
click-left = ooonana-apps
click-right = ooonana-settings-launch

[module/launcher]
type = custom/text
content = Ooonana
content-foreground = ${colors.cool}
content-background = ${colors.background-alt}
content-padding = 2
click-left = ooonana-apps

[module/terminal]
type = custom/text
content = 
content-foreground = ${colors.accent}
content-background = ${colors.background-alt}
content-padding = 2
click-left = ooonana-theme-env xterm

[module/browser]
type = custom/text
content = 
content-foreground = ${colors.accent}
content-background = ${colors.background-alt}
content-padding = 2
click-left = ooonana-browser

[module/files]
type = custom/text
content = 
content-foreground = ${colors.accent}
content-background = ${colors.background-alt}
content-padding = 2
click-left = ooonana-files

[module/editor]
type = custom/text
content = 
content-foreground = ${colors.accent}
content-background = ${colors.background-alt}
content-padding = 2
click-left = ooonana-editor

[module/media]
type = custom/script
exec = ooonana-media-status
interval = 2
label = %output%
label-foreground = ${colors.accent}
label-background = ${colors.background-alt}
label-padding = 2
click-left = ooonana-music
click-middle = ooonana-media-control play-pause
click-right = ooonana-media-control next
scroll-up = ooonana-media-control volume +5
scroll-down = ooonana-media-control volume -5

[module/win-close]
type = custom/text
content = 
content-foreground = ${colors.background}
content-background = ${colors.foreground}
content-padding = 2
click-left = i3-msg kill

[module/win-min]
type = custom/text
content = 
content-foreground = ${colors.accent}
content-background = ${colors.background-alt}
content-padding = 2
click-left = i3-msg move scratchpad
click-right = i3-msg scratchpad show

[module/win-full]
type = custom/text
content = 
content-foreground = ${colors.accent}
content-background = ${colors.background-alt}
content-padding = 2
click-left = i3-msg fullscreen toggle

[module/logo]
type = custom/text
content = Ooonana OS
content-foreground = ${colors.accent}

[module/workspaces]
type = internal/i3
format = <label-state>
label-focused = %name%
label-focused-foreground = ${colors.background}
label-focused-background = ${colors.foreground}
label-focused-padding = 2
label-unfocused = %name%
label-unfocused-foreground = ${colors.accent}
label-unfocused-background = ${colors.background-alt}
label-unfocused-padding = 2
label-visible = %name%
label-visible-foreground = ${colors.foreground}
label-visible-padding = 2
label-urgent = %name%
label-urgent-foreground = ${colors.background}
label-urgent-background = ${colors.urgent}
label-urgent-padding = 2

[module/title]
type = internal/xwindow
label = %title:0:42:...%
label-empty = desktop
label-foreground = ${colors.accent}
label-background = ${colors.background}
label-padding = 2

[module/wifi]
type = custom/script
exec = ooonana-wifi-status
interval = 5
label = %output%
label-foreground = ${colors.accent}
label-background = ${colors.background-alt}
label-padding = 2
click-left = ooonana-wifi-panel

[module/bluetooth]
type = custom/script
exec = ooonana-bluetooth-status
interval = 5
label = %output%
label-foreground = ${colors.accent}
label-background = ${colors.background-alt}
label-padding = 2
click-left = ooonana-bluetooth-panel
click-right = blueman-manager

[module/network]
type = internal/network
interface-type = wireless
label-connected =  %essid%
label-connected-foreground = ${colors.accent}
label-connected-background = ${colors.background-alt}
label-connected-padding = 2
label-disconnected =  off
label-disconnected-foreground = ${colors.muted}
label-disconnected-background = ${colors.background-alt}
label-disconnected-padding = 2

[module/audio]
type = custom/script
exec = ooonana-audio-status
interval = 5
label = %output%
label-foreground = ${colors.accent}
label-background = ${colors.background-alt}
label-padding = 2
click-left = ooonana-audio-panel
click-middle = pactl set-sink-mute @DEFAULT_SINK@ toggle
click-right = pavucontrol
scroll-up = pactl set-sink-volume @DEFAULT_SINK@ +5%
scroll-down = pactl set-sink-volume @DEFAULT_SINK@ -5%

[module/brightness]
type = custom/script
exec = ooonana-brightness-status
interval = 5
label = %output%
label-foreground = ${colors.accent}
label-background = ${colors.background-alt}
label-padding = 2
click-left = ooonana-brightness-panel
click-middle = brightnessctl set 50%
click-right = arandr
scroll-up = brightnessctl set +5%
scroll-down = brightnessctl set 5%-

[module/power]
type = custom/text
content = 
content-foreground = ${colors.foreground}
content-background = ${colors.background-alt}
content-padding = 2
click-left = ooonana-power-menu
click-right = i3lock

[module/battery]
type = custom/script
exec = ooonana-battery-status
interval = 30
label = %output%
label-foreground = ${colors.accent}
label-background = ${colors.background-alt}
label-padding = 2
click-left = ooonana-settings-launch

[module/date]
type = internal/date
interval = 5
date = %Y-%m-%d
time = %H:%M
label = %time%
label-foreground = ${colors.cool}
label-background = ${colors.background-alt}
label-padding = 2
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/rofi.rasi" <<'EOF'
configuration {
  modi: "drun,run,window";
  show-icons: true;
  sidebar-mode: true;
  drun-display-format: "{icon} {name}";
  display-drun: "Ooonana";
  display-run: "Ooonana";
  display-window: "Windows";
}
* {
  background: #050505;
  background-alt: #0f0c08;
  foreground: #ffb21a;
  accent: #ffd37a;
  muted: #7a5014;
  selected-normal-background: #ffb21a;
  selected-normal-foreground: #050505;
  selected-active-background: #ffd37a;
  selected-active-foreground: #050505;
  alternate-normal-background: #111111;
  urgent: #050505;
  font: "monospace 11";
}
window {
  width: 48%;
  location: center;
  anchor: center;
  border: 2px;
  border-color: #ffb21a;
  background-color: @background;
  padding: 0;
}
mainbox {
  background-color: @background;
  children: [ inputbar, mode-switcher, listview ];
  spacing: 10px;
  padding: 18px;
}
inputbar {
  background-color: @background;
  text-color: @foreground;
  border: 0 0 2px 0;
  border-color: @foreground;
  padding: 8px;
  children: [ prompt, textbox-prompt-colon, entry ];
}
prompt {
  text-color: @foreground;
  font: "monospace bold 11";
}
textbox-prompt-colon {
  expand: false;
  str: ":";
  text-color: @accent;
  margin: 0 6px 0 4px;
}
entry {
  text-color: @foreground;
  placeholder: "type app, command, or window";
  placeholder-color: @muted;
}
mode-switcher {
  background-color: @background;
  text-color: @foreground;
  spacing: 6px;
}
button {
  background-color: @background-alt;
  text-color: @foreground;
  padding: 6px 10px;
  border: 1px;
  border-color: @muted;
}
button selected {
  background-color: @selected-normal-background;
  text-color: @selected-normal-foreground;
  border-color: @selected-normal-background;
}
listview {
  background-color: @background;
  text-color: @foreground;
  lines: 12;
  columns: 1;
  fixed-height: true;
  dynamic: true;
  scrollbar: true;
}
element {
  background-color: @background-alt;
  text-color: @foreground;
  padding: 8px;
  margin: 2px 0;
}
element normal.normal {
  background-color: @background-alt;
  text-color: @foreground;
}
element alternate.normal {
  background-color: @alternate-normal-background;
  text-color: @foreground;
}
element selected.normal {
  background-color: @selected-normal-background;
  text-color: @selected-normal-foreground;
}
element selected.active {
  background-color: @selected-active-background;
  text-color: @selected-active-foreground;
}
element selected.urgent {
  background-color: @urgent;
  text-color: @selected-normal-foreground;
}
element-icon {
  size: 20px;
}
element-text {
  text-color: inherit;
}
scrollbar {
  width: 4px;
  handle-color: @foreground;
  background-color: @background-alt;
}
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/picom.conf" <<'EOF'
backend = "xrender";
vsync = true;
use-damage = true;
unredir-if-possible = true;
shadow = false;
shadow-radius = 16;
shadow-offset-x = -8;
shadow-offset-y = -8;
shadow-opacity = 0.36;
fading = false;
fade-delta = 6;
fade-in-step = 0.045;
fade-out-step = 0.045;
inactive-opacity = 1.0;
active-opacity = 1.0;
corner-radius = 0;
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/dunstrc" <<'EOF'
[global]
font = monospace 10
frame_color = "#ffb21a"
separator_color = "#ffb21a"
background = "#050505"
foreground = "#ffb21a"
origin = top-right
offset = 20x42
width = 340
height = 160
frame_width = 2
corner_radius = 0
highlight = "#ffb21a"
[urgency_critical]
background = "#050505"
foreground = "#ffb21a"
frame_color = "#ffb21a"
EOF
}

write_gui_installer() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-installer-gui" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "yad installer gui"
  echo "modes: erase-disk custom-existing-partitions"
  echo "fields: target home swap efi format-root format-home format-swap format-efi user password hostname theme repo source"
  echo "custom bootloader: UEFI GRUB requires an EFI partition"
  echo "OOONANA_INSTALLER_GUI_OK"
  exit 0
fi

fallback() {
  exec /usr/bin/ooonana-install-wizard "$@"
}

if [ -z "${DISPLAY:-}" ] || ! command -v yad >/dev/null 2>&1; then
  fallback "$@"
fi

default_target="/dev/vdb"
for dev in /dev/vdb /dev/sdb /dev/xvdb /dev/nvme0n2; do
  [ -b "$dev" ] && { default_target="$dev"; break; }
done

parent_disk() {
  if command -v lsblk >/dev/null 2>&1 && [ -b "$1" ]; then
    parent="$(lsblk -no PKNAME "$1" 2>/dev/null | sed -n '1p' || true)"
    if [ -n "$parent" ]; then
      printf '/dev/%s\n' "$parent"
      return 0
    fi
  fi
  case "$1" in
    /dev/nvme*n*p[0-9]*) printf '%s\n' "${1%p[0-9]*}" ;;
    /dev/mmcblk*p[0-9]*|/dev/loop*p[0-9]*) printf '%s\n' "${1%p[0-9]*}" ;;
    /dev/disk/by-id/*-part[0-9]*|/dev/disk/by-path/*-part[0-9]*) printf '%s\n' "${1%-part[0-9]*}" ;;
    /dev/*[0-9]) printf '%s\n' "${1%[0-9]*}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

root_disk() {
  root_dev="$(awk '$2 == "/" { print $1; exit }' /proc/mounts 2>/dev/null || true)"
  case "$root_dev" in
    /dev/*) parent_disk "$root_dev" ;;
    *) return 0 ;;
  esac
}

form="$(yad --center --title "Install Ooonana OS" --width=720 \
  --form --separator='|' \
  --field "Mode:CB" "erase-disk!custom-existing-partitions" \
  --field "Target disk or root partition" "$default_target" \
  --field "Home partition" "" \
  --field "Swap partition" "" \
  --field "EFI partition" "" \
  --field "Format root:CHK" TRUE \
  --field "Format home:CHK" TRUE \
  --field "Format swap:CHK" TRUE \
  --field "Format EFI:CHK" FALSE \
  --field "User" "ooonana" \
  --field "Password:H" "" \
  --field "Hostname" "ooonana" \
  --field "Theme:CB" "dark!light" \
  --field "Cloud repo" "https://ooonana.gitlab.io/ooonana-repo" \
  --field "Source root" "/" 2>/dev/null || true)"
[ -n "$form" ] || exit 0

field() {
  printf '%s' "$form" | cut -d'|' -f"$1"
}

mode="$(field 1)"
target="$(field 2)"
home_part="$(field 3)"
swap_part="$(field 4)"
efi_part="$(field 5)"
format_root="$(field 6)"
format_home="$(field 7)"
format_swap="$(field 8)"
format_efi="$(field 9)"
user_name="$(field 10)"
password="$(field 11)"
host_name="$(field 12)"
theme="$(field 13)"
cloud_repo="$(field 14)"
source_root="$(field 15)"

[ -n "$target" ] || { yad --center --title "Install Ooonana OS" --text "Target required"; exit 1; }
[ -n "$source_root" ] || source_root="/"
root="$(root_disk)"
if [ -n "$root" ] && { [ "$target" = "$root" ] || [ "$(parent_disk "$target")" = "$root" ]; } &&
  [ "${OOONANA_INSTALL_ALLOW_ROOT_TARGET:-0}" != "1" ]; then
  yad --center --title "Install Ooonana OS" --text "Target looks like the current root disk: $target"
  exit 1
fi

set -- /usr/sbin/ooonana-install --target "$target" --source "$source_root" --hostname "$host_name" --user "$user_name" --theme "$theme"
[ -n "$cloud_repo" ] && set -- "$@" --cloud-repo "$cloud_repo"
[ -n "$password" ] && set -- "$@" --password-stdin

case "$mode" in
  custom-existing-partitions)
    if [ -z "$efi_part" ]; then
      yad --center --title "Install Ooonana OS" \
        --text "Custom partition mode needs an EFI partition for a bootable install. Use erase-disk mode for automatic BIOS and UEFI setup."
      exit 1
    fi
    set -- "$@" --bootloader grub
    [ -n "$home_part" ] && set -- "$@" --home-part "$home_part"
    [ -n "$swap_part" ] && set -- "$@" --swap-part "$swap_part"
    set -- "$@" --efi-part "$efi_part"
    [ "$format_root" = "TRUE" ] || set -- "$@" --keep-root
    [ "$format_home" = "TRUE" ] || set -- "$@" --keep-home
    [ "$format_swap" = "TRUE" ] || set -- "$@" --keep-swap
    [ "$format_efi" = "TRUE" ] && set -- "$@" --format-efi || set -- "$@" --keep-efi
    ;;
  *)
    :
    ;;
esac

if [ "$(id -u 2>/dev/null || echo 1)" != "0" ]; then
  set -- ooonana-run-admin "$@"
fi

tmp_dir="${TMPDIR:-/tmp}/ooonana-installer-gui.$$"
mkdir -p "$tmp_dir"
preview="$tmp_dir/preview.txt"
log="$tmp_dir/install.log"
status_file="$tmp_dir/status"

if [ -n "$password" ]; then
  printf '%s\n' "$password" | "$@" --dry-run --yes >"$preview" 2>&1 || true
else
  "$@" --dry-run --yes >"$preview" 2>&1 || true
fi

yad --center --title "Ooonana Install Preview" --width=860 --height=560 \
  --text-info --filename="$preview" \
  --button=Cancel:1 --button=Install:0 2>/dev/null || exit 0

: >"$log"
(
  set +e
  if [ -n "$password" ]; then
    printf '%s\n' "$password" | "$@" --yes >"$log" 2>&1
  else
    "$@" --yes >"$log" 2>&1
  fi
  rc="$?"
  printf '%s\n' "$rc" >"$status_file"
) &
pid="$!"

yad --center --title "Ooonana Install Log" --width=860 --height=560 \
  --text-info --tail --filename="$log" --button=Close:0 2>/dev/null || true
wait "$pid" 2>/dev/null || true
status="$(cat "$status_file" 2>/dev/null || echo 1)"
if [ "$status" = "0" ]; then
  yad --center --title "Ooonana OS" --text "Install complete. Reboot when ready." 2>/dev/null || true
else
  if yad --center --title "Ooonana Install Failed" --text "Install failed. Open fallback shell?" --button=No:1 --button=Shell:0 2>/dev/null; then
    exec ooonana-theme-env xterm -e /bin/sh -l
  fi
fi
exit "$status"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-gui-installer" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "ooonana-installer-gui --dry-run"
  echo "xterm -title Ooonana Installer"
  echo "default theme: dark background, orange cursor"
  echo "ooonana-install-wizard --dry-run"
  echo "OOONANA_GUI_INSTALLER_OK"
  exit 0
fi

if [ "${OOONANA_INSTALL_FORCE_WIZARD:-0}" != "1" ] &&
  [ -n "${DISPLAY:-}" ] &&
  command -v yad >/dev/null 2>&1 &&
  [ -x /usr/bin/ooonana-installer-gui ]; then
  exec /usr/bin/ooonana-installer-gui "$@"
fi

xterm_theme() {
  case "${OOONANA_THEME:-dark}" in
    light)
      XTERM_BG="#ffb21a"
      XTERM_FG="#1b1202"
      ;;
    *)
      XTERM_BG="#050505"
      XTERM_FG="#ffb21a"
      ;;
  esac
  XTERM_CURSOR="#ffb21a"
}

wizard="/usr/bin/ooonana-install-wizard"
if [ ! -x "$wizard" ]; then
  echo "missing installer wizard: $wizard" >&2
  exit 1
fi

if [ -n "${DISPLAY:-}" ] && [ -z "${OOONANA_INSTALL_WIZARD_IN_TERMINAL:-}" ] && command -v xterm >/dev/null 2>&1; then
  xterm_theme
  exec env OOONANA_INSTALL_WIZARD_IN_TERMINAL=1 \
    xterm -title "Ooonana Installer" -bg "$XTERM_BG" -fg "$XTERM_FG" -cr "$XTERM_CURSOR" -e "$wizard" "$@"
else
  exec "$wizard" "$@"
fi
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-install-wizard" <<'EOF'
#!/bin/sh
set -eu

TARGET=""
SOURCE="/"
USER_NAME="ooonana"
HOSTNAME_VALUE="ooonana"
THEME="${OOONANA_THEME:-dark}"
CLOUD_REPO="${OOONANA_CLOUD_REPO:-}"
DEFAULT_CLOUD_REPO="${OOONANA_DEFAULT_CLOUD_REPO:-https://ooonana.gitlab.io/ooonana-repo}"
PASSWORD_VALUE=""
YES=0
DRY_RUN=0
if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
  LOG_FILE="/var/log/ooonana-install-wizard.log"
else
  LOG_FILE="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/ooonana/ooonana-install-wizard.log"
fi

usage() {
  cat <<'USAGE'
Ooonana graphical installer wizard.

Usage:
  ooonana-install-wizard [TARGET] [options]

Options:
  --target PATH   Target disk or ext4 image
  --source PATH   Source root (default: /)
  --user NAME     Installed user (default: ooonana)
  --hostname NAME Installed hostname (default: ooonana)
  --theme dark|light
  --cloud-repo URI
  --yes           Skip wizard prompts
  --dry-run       Print installer command only
  -h, --help      Show help
USAGE
}

die() {
  printf 'ooonana-install-wizard: %s\n' "$*" >&2
  exit 1
}

logo() {
  if [ -f /usr/share/ooonana/logo.txt ]; then
    cat /usr/share/ooonana/logo.txt
  else
    printf 'Ooonana OS\n'
  fi
}

screen() {
  clear 2>/dev/null || true
  logo
  printf '\n%s\n\n' "$1"
}

read_hidden() {
  prompt="$1"
  printf '%s' "$prompt" >&2
  if command -v stty >/dev/null 2>&1; then
    stty -echo 2>/dev/null || true
    read -r answer || answer=""
    stty echo 2>/dev/null || true
    printf '\n'
  else
    read -r answer || answer=""
  fi
  printf '%s\n' "$answer"
}

valid_theme() {
  case "$1" in
    dark|light) return 0 ;;
    *) return 1 ;;
  esac
}

valid_repo_uri() {
  case "$1" in
    ""|http://*|https://*|file://*|/*) return 0 ;;
    *) return 1 ;;
  esac
}

list_targets() {
  for dev in /dev/vd[a-z] /dev/sd[a-z] /dev/xvd[a-z] /dev/nvme[0-9]n[0-9]; do
    [ -b "$dev" ] && printf '%s\n' "$dev"
  done
}

parent_disk() {
  if command -v lsblk >/dev/null 2>&1 && [ -b "$1" ]; then
    parent="$(lsblk -no PKNAME "$1" 2>/dev/null | sed -n '1p' || true)"
    if [ -n "$parent" ]; then
      printf '/dev/%s\n' "$parent"
      return 0
    fi
  fi
  case "$1" in
    /dev/nvme*n*p[0-9]*) printf '%s\n' "${1%p[0-9]*}" ;;
    /dev/mmcblk*p[0-9]*|/dev/loop*p[0-9]*) printf '%s\n' "${1%p[0-9]*}" ;;
    /dev/disk/by-id/*-part[0-9]*|/dev/disk/by-path/*-part[0-9]*) printf '%s\n' "${1%-part[0-9]*}" ;;
    /dev/*[0-9]) printf '%s\n' "${1%[0-9]*}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

root_disk() {
  root_dev="$(awk '$2 == "/" { print $1; exit }' /proc/mounts 2>/dev/null || true)"
  case "$root_dev" in
    /dev/*) parent_disk "$root_dev" ;;
    *) return 0 ;;
  esac
}

is_root_target() {
  root="$(root_disk)"
  [ -n "$root" ] || return 1
  [ "$1" = "$root" ] || [ "$(parent_disk "$1")" = "$root" ]
}

suggest_target() {
  for dev in /dev/vdb /dev/sdb /dev/xvdb /dev/nvme0n2; do
    if [ -b "$dev" ] && ! is_root_target "$dev"; then
      printf '%s\n' "$dev"
      return 0
    fi
  done
  for dev in /dev/vd[a-z] /dev/sd[a-z] /dev/xvd[a-z] /dev/nvme[0-9]n[0-9]; do
    if [ -b "$dev" ] && ! is_root_target "$dev"; then
      printf '%s\n' "$dev"
      return 0
    fi
  done
  printf '/dev/vdb\n'
}

confirm_root_target() {
  if is_root_target "$TARGET" && [ "${OOONANA_INSTALL_ALLOW_ROOT_TARGET:-0}" != "1" ]; then
    die "target looks like current root disk: $TARGET"
  fi
}

run_installer() {
  mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
  set -- /usr/sbin/ooonana-install --target "$TARGET" --source "$SOURCE" --hostname "$HOSTNAME_VALUE" --user "$USER_NAME" --theme "$THEME" --yes
  if [ -n "$CLOUD_REPO" ]; then
    set -- "$@" --cloud-repo "$CLOUD_REPO"
  fi
  if [ -n "$PASSWORD_VALUE" ]; then
    set -- "$@" --password-stdin
  fi
  if [ "$(id -u 2>/dev/null || echo 1)" != "0" ]; then
    set -- ooonana-run-admin "$@"
  fi

  printf 'Target disk: %s\n' "$TARGET"
  printf 'Source root: %s\n' "$SOURCE"
  printf 'User: %s\n' "$USER_NAME"
  printf 'Hostname: %s\n' "$HOSTNAME_VALUE"
  printf 'Theme: %s\n' "$THEME"
  printf 'Package repo: %s\n' "${CLOUD_REPO:-none}"
  printf 'Progress log: %s\n\n' "$LOG_FILE"
  printf '[1/6] format target\n'
  printf '[2/6] copy Ooonana files\n'
  printf '[3/6] write user, hostname, theme\n'
  printf '[4/6] write package repo source\n'
  printf '[5/6] write fstab/install marker\n'
  printf '[6/6] finish\n\n'
  if [ -n "$PASSWORD_VALUE" ]; then
    if printf '%s\n' "$PASSWORD_VALUE" | "$@" >"$LOG_FILE" 2>&1; then
      cat "$LOG_FILE"
    else
      status="$?"
      cat "$LOG_FILE" 2>/dev/null || true
      return "$status"
    fi
  elif "$@" >"$LOG_FILE" 2>&1; then
    cat "$LOG_FILE"
  else
    status="$?"
    cat "$LOG_FILE" 2>/dev/null || true
    return "$status"
  fi
}

finish_prompt() {
  [ "$YES" -eq 0 ] || return 0
  printf '\nInstall complete. Press Enter to reboot, type shell to close: '
  read -r answer || answer=""
  case "$answer" in
    shell|SHELL|no|NO|n|N) return 0 ;;
    *)
      reboot -f 2>/dev/null || poweroff -f 2>/dev/null || true
      ;;
  esac
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --hostname) HOSTNAME_VALUE="$2"; shift 2 ;;
    --theme) THEME="$2"; shift 2 ;;
    --cloud-repo) CLOUD_REPO="$2"; shift 2 ;;
    --yes) YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -* ) die "unknown option: $1" ;;
    *)
      [ -z "$TARGET" ] || die "target already set: $TARGET"
      TARGET="$1"
      shift
      ;;
  esac
done

if [ "$DRY_RUN" -eq 1 ]; then
  target="${TARGET:-/dev/vdb}"
  printf 'Ooonana installer wizard\n'
  printf 'Step 1/8 choose target disk: %s\n' "$target"
  printf 'Step 2/8 create user: %s\n' "$USER_NAME"
  printf 'Step 3/8 set hostname: %s\n' "$HOSTNAME_VALUE"
  printf 'Step 4/8 choose theme: %s\n' "$THEME"
  printf 'Step 5/8 choose package repo: %s\n' "${CLOUD_REPO:-none}"
  printf 'Step 6/8 choose source root: %s\n' "$SOURCE"
  printf 'Step 7/8 confirm erase: INSTALL\n'
  printf 'Step 8/8 install, log, reboot\n'
  printf 'Progress log: %s\n' "$LOG_FILE"
  printf '/usr/sbin/ooonana-install --target %s --source %s --hostname %s --user %s --theme %s' "$target" "$SOURCE" "$HOSTNAME_VALUE" "$USER_NAME" "$THEME"
  [ -z "$CLOUD_REPO" ] || printf ' --cloud-repo %s' "$CLOUD_REPO"
  printf ' --yes\n'
  printf 'OOONANA_INSTALL_WIZARD_OK\n'
  exit 0
fi

if [ "$YES" -eq 0 ]; then
  screen "Step 1/8: Target disk"
  printf 'Known target disks:\n'
  list_targets || true
  default_target="$(suggest_target)"
  printf '\nTarget disk [%s]: ' "$default_target"
  read -r answer
  TARGET="${answer:-$default_target}"

  screen "Step 2/8: User account"
  printf 'User name [%s]: ' "$USER_NAME"
  read -r answer
  USER_NAME="${answer:-$USER_NAME}"
  password_one="$(read_hidden 'Password blank to set later: ')"
  if [ -n "$password_one" ]; then
    password_two="$(read_hidden 'Password again: ')"
    [ "$password_one" = "$password_two" ] || die "password mismatch"
    PASSWORD_VALUE="$password_one"
  fi

  screen "Step 3/8: Hostname"
  printf 'Hostname [%s]: ' "$HOSTNAME_VALUE"
  read -r answer
  HOSTNAME_VALUE="${answer:-$HOSTNAME_VALUE}"

  screen "Step 4/8: Theme"
  printf 'Theme dark/light [%s]: ' "$THEME"
  read -r answer
  THEME="${answer:-$THEME}"
  valid_theme "$THEME" || die "theme must be dark or light"

  screen "Step 5/8: Package repo"
  printf 'Repo picker:\n'
  printf '  blank: skip cloud repo\n'
  printf '  cloud: %s\n' "$DEFAULT_CLOUD_REPO"
  printf '  file:///path: local repo\n\n'
  printf 'Cloud repo URI [%s]: ' "${CLOUD_REPO:-skip}"
  read -r answer
  case "$answer" in
    "") ;;
    skip|none|NONE|no|NO) CLOUD_REPO="" ;;
    cloud) CLOUD_REPO="$DEFAULT_CLOUD_REPO" ;;
    *) CLOUD_REPO="$answer" ;;
  esac
  valid_repo_uri "$CLOUD_REPO" || die "bad cloud repo URI: $CLOUD_REPO"

  screen "Step 6/8: Source root"
  printf 'Source root [%s]: ' "$SOURCE"
  read -r answer
  SOURCE="${answer:-$SOURCE}"
fi

[ -n "$TARGET" ] || die "target required"
[ -n "$SOURCE" ] || die "source required"
[ -n "$USER_NAME" ] || die "user required"
[ -n "$HOSTNAME_VALUE" ] || die "hostname required"
valid_theme "$THEME" || die "theme must be dark or light"
valid_repo_uri "$CLOUD_REPO" || die "bad cloud repo URI: $CLOUD_REPO"
confirm_root_target

if [ "$YES" -eq 0 ]; then
  screen "Step 7/8: Confirm install"
  printf 'Target disk: %s\n' "$TARGET"
  printf 'Source root: %s\n' "$SOURCE"
  printf 'User: %s\n' "$USER_NAME"
  printf 'Hostname: %s\n' "$HOSTNAME_VALUE"
  printf 'Theme: %s\n' "$THEME"
  printf 'Package repo: %s\n' "${CLOUD_REPO:-none}"
  printf '\nThis erases target. Type INSTALL to continue: '
  read -r answer
  [ "$answer" = "INSTALL" ] || die "install cancelled"
fi

screen "Step 8/8: Installing"
if ! run_installer; then
  printf '\nOOONANA_INSTALL_WIZARD_FAIL\n'
  printf 'Install failed. Log: %s\n' "$LOG_FILE"
  if [ "$YES" -eq 0 ]; then
    printf 'Fallback shell. Type exit to close.\n'
    exec /bin/sh
  fi
  exit 1
fi
printf '\nOOONANA_INSTALL_WIZARD_OK\n'
finish_prompt
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-i3-smoke-session" <<'EOF'
#!/bin/sh
set -eu

if [ -z "${OOONANA_DBUS_SESSION:-}" ] &&
  [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] &&
  command -v dbus-run-session >/dev/null 2>&1; then
  export OOONANA_DBUS_SESSION=1
  exec dbus-run-session -- "$0" "$@"
fi

if [ -x /usr/bin/ooonana-theme-env ]; then
  eval "$(/usr/bin/ooonana-theme-env env)"
  ooonana-theme-env apply
fi

smoke_config="${TMPDIR:-/tmp}/ooonana-i3-smoke.config"
cat > "$smoke_config" <<'I3CONFIG'
# i3 config file (v4)
font pango:monospace 10
exec --no-startup-id sh -c 'sleep 2; for dev in /dev/ttyS0 /dev/console; do [ -e "$dev" ] && echo "OOONANA_FULL_I3_OK" >"$dev"; done; i3-msg exit >/dev/null 2>&1 || true'
I3CONFIG
exec i3 -c "$smoke_config"
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-i3-session" <<'EOF'
#!/bin/sh
set -eu

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
export LANG="${LANG:-C.UTF-8}"
export LC_CTYPE="${LC_CTYPE:-C.UTF-8}"
export PYTHONUTF8=1

if [ "${1:-}" = "--user" ]; then
  desktop_user="${2:-}"
  [ -n "$desktop_user" ] || {
    echo "missing desktop user" >&2
    exit 2
  }
  case "$desktop_user" in
    *[!a-zA-Z0-9_-]*)
      echo "invalid desktop user: $desktop_user" >&2
      exit 2
      ;;
  esac
  if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
    desktop_line="$(grep "^$desktop_user:" /etc/passwd 2>/dev/null | head -n 1 || true)"
    [ -n "$desktop_line" ] || {
      echo "desktop user missing: $desktop_user" >&2
      exit 1
    }
    desktop_uid="$(printf '%s\n' "$desktop_line" | cut -d: -f3)"
    desktop_gid="$(printf '%s\n' "$desktop_line" | cut -d: -f4)"
    desktop_home="$(printf '%s\n' "$desktop_line" | cut -d: -f6)"
    [ -n "$desktop_home" ] || desktop_home="/home/$desktop_user"
    mkdir -p "$desktop_home" "/run/user/$desktop_uid"
    chown "$desktop_uid:$desktop_gid" "$desktop_home" "/run/user/$desktop_uid"
    chmod 0700 "/run/user/$desktop_uid"
    source_authority="${XAUTHORITY:-${HOME:-/root}/.Xauthority}"
    target_authority="$desktop_home/.Xauthority"
    if [ -f "$source_authority" ]; then
      if [ "$source_authority" != "$target_authority" ]; then
        cp "$source_authority" "$target_authority" 2>/dev/null || true
      fi
      chown "$desktop_uid:$desktop_gid" "$target_authority" 2>/dev/null || true
      chmod 0600 "$target_authority" 2>/dev/null || true
      export XAUTHORITY="$target_authority"
    fi
    export HOME="$desktop_home"
    export USER="$desktop_user"
    export LOGNAME="$desktop_user"
    export SHELL=/bin/sh
    export XDG_CONFIG_HOME="$desktop_home/.config"
    export XDG_CACHE_HOME="$desktop_home/.cache"
    export XDG_STATE_HOME="$desktop_home/.local/state"
    export XDG_RUNTIME_DIR="/run/user/$desktop_uid"
    exec /bin/busybox su -m -s /bin/sh "$desktop_user" -c 'exec /usr/bin/ooonana-i3-session --user-session'
  fi
  shift 2
fi

if [ "${1:-}" = "--user-session" ]; then
  shift
fi

if [ -z "${OOONANA_DBUS_SESSION:-}" ] &&
  [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] &&
  command -v dbus-run-session >/dev/null 2>&1; then
  export OOONANA_DBUS_SESSION=1
  exec dbus-run-session -- "$0" "$@"
fi

if [ -x /usr/bin/ooonana-theme-env ]; then
  eval "$(/usr/bin/ooonana-theme-env env)"
  ooonana-theme-env apply
fi

mkdir -p "${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/ooonana"
command -v ooonana-audio-start >/dev/null 2>&1 && ooonana-audio-start >/dev/null 2>&1 || true

if command -v ooonana-setup >/dev/null 2>&1; then
  ooonana-setup --first-boot --gui >"${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/ooonana/setup.log" 2>&1 &
fi

exec i3
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-i3-installer-session" <<'EOF'
#!/bin/sh
set -eu

if [ -z "${OOONANA_DBUS_SESSION:-}" ] &&
  [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] &&
  command -v dbus-run-session >/dev/null 2>&1; then
  export OOONANA_DBUS_SESSION=1
  exec dbus-run-session -- "$0" "$@"
fi

if [ -x /usr/bin/ooonana-theme-env ]; then
  eval "$(/usr/bin/ooonana-theme-env env)"
  ooonana-theme-env apply
fi

installer_config="${TMPDIR:-/tmp}/ooonana-i3-installer.config"
cat > "$installer_config" <<'I3CONFIG'
# i3 config file (v4)
font pango:monospace 10
set $mod Mod4
bindsym $mod+Return exec ooonana-theme-env xterm -e /bin/sh -l
bindsym $mod+Shift+i exec ooonana-gui-installer
bindsym $mod+Shift+r restart
bindsym $mod+Shift+e exit
exec --no-startup-id sh -c 'sleep 1; ooonana-gui-installer || ooonana-install-wizard'
I3CONFIG

exec i3 -c "$installer_config"
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/usr/share/applications/ooonana-installer.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Install Ooonana OS
Exec=ooonana-installer-gui
Terminal=false
Categories=System;
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/usr/share/applications/ooonana-setup.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Ooonana Setup
Exec=ooonana-setup --gui
Terminal=false
Categories=System;
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/usr/share/applications/ooonana-settings.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Ooonana Settings
Exec=ooonana-settings-launch
Terminal=false
Categories=Settings;System;
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/usr/share/applications/ooonana-apps.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Ooonana Applications
Comment=Search and launch installed applications
Exec=ooonana-apps
Icon=/usr/share/ooonana/logo.png
Terminal=false
Categories=System;Utility;
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/usr/share/applications/ooonana-packages.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Ooonana Packages
Exec=ooonana-packages-app
Terminal=false
Categories=System;PackageManager;
EOF
}

write_xorg_input_config() {
  install -D -m 0644 /dev/stdin "$ROOTFS/etc/X11/xorg.conf.d/10-ooonana-input.conf" <<'EOF'
Section "ServerFlags"
    Option "AutoAddDevices" "true"
    Option "AutoEnableDevices" "true"
EndSection

Section "InputClass"
    Identifier "Ooonana keyboard"
    MatchIsKeyboard "on"
    Driver "libinput"
EndSection

Section "InputClass"
    Identifier "Ooonana pointer"
    MatchIsPointer "on"
    Driver "libinput"
EndSection

Section "InputClass"
    Identifier "Ooonana touchpad"
    MatchIsTouchpad "on"
    Driver "libinput"
    Option "Tapping" "on"
    Option "ClickMethod" "clickfinger"
    Option "NaturalScrolling" "true"
    Option "DisableWhileTyping" "true"
EndSection
EOF
}

write_xorg_video_config() {
  install -D -m 0644 /dev/stdin "$ROOTFS/usr/share/ooonana/xorg-fbdev.conf" <<'EOF'
Section "Device"
    Identifier "Ooonana framebuffer"
    Driver "fbdev"
EndSection

Section "Screen"
    Identifier "Ooonana screen"
    Device "Ooonana framebuffer"
EndSection
EOF
}

write_full_init_script() {
  install -D -m 0755 /dev/stdin "$ROOTFS/etc/init.d/rcS" <<'EOF'
#!/bin/sh
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mkdir -p /dev/pts
mount -t devpts devpts /dev/pts 2>/dev/null || true
mkdir -p /dev/shm
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /dev/shm 2>/dev/null || true
mount -t tmpfs tmpfs /run 2>/dev/null || true
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp 2>/dev/null || true
mkdir -p /run/dbus /var
if [ ! -L /var/run ]; then
  rm -rf /var/run
  ln -s /run /var/run
fi

start_persistence() {
  grep -q 'ooonana.persistence=1' /proc/cmdline 2>/dev/null || return 0
  persistence_mode="$(cat /mnt/ooonana-live/persistence-mode 2>/dev/null || true)"
  persistence_device="$(cat /mnt/ooonana-live/persistence-device 2>/dev/null || true)"
  if [ "$persistence_mode" != "usb" ] || [ -z "$persistence_device" ]; then
    echo "OOONANA_PERSISTENCE_SAFE_SKIP"
    return 0
  fi
  mkdir -p /mnt/persist
  mount --bind /mnt/ooonana-live/persist /mnt/persist 2>/dev/null || true
  echo "OOONANA_PERSISTENCE_OK:$persistence_device"
}

start_device_manager() {
  mkdir -p /run/udev
  if command -v udevd >/dev/null 2>&1 && command -v udevadm >/dev/null 2>&1; then
    udevd --daemon 2>/dev/null || true
    udevadm trigger --action=add 2>/dev/null || true
    udevadm settle --timeout=5 2>/dev/null || true
    return 0
  fi
  if command -v mdev >/dev/null 2>&1; then
    printf '%s\n' /sbin/mdev >/proc/sys/kernel/hotplug 2>/dev/null || true
    mdev -s 2>/dev/null || true
  fi
}

start_device_manager
start_persistence

configure_cpu_scaling() {
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    [ -w "$policy/scaling_governor" ] || continue
    governors="$(cat "$policy/scaling_available_governors" 2>/dev/null || true)"
    case " $governors " in
      *" schedutil "*) governor="schedutil" ;;
      *" ondemand "*) governor="ondemand" ;;
      *) continue ;;
    esac
    printf '%s\n' "$governor" >"$policy/scaling_governor" 2>/dev/null || true
  done
  if [ -w /proc/sys/kernel/sched_autogroup_enabled ]; then
    printf '1\n' >/proc/sys/kernel/sched_autogroup_enabled 2>/dev/null || true
  fi
}

configure_cpu_scaling

start_system_services() {
  command -v ooonana-service-repair >/dev/null 2>&1 || {
    printf '%s\n' 'ooonana-service-repair missing' >/var/log/ooonana-service-repair.log
    return 1
  }
  ooonana-service-repair boot >/var/log/ooonana-service-repair.log 2>&1 && return 0
  printf '%s\n' 'automatic service start failed; preserving hardware state for diagnostics' \
    >>/var/log/ooonana-service-repair.log
  return 1
}

start_system_services || true

start_service_watchdog() {
  command -v ooonana-service-watchdog >/dev/null 2>&1 || return 0
  ooonana-service-watchdog >/var/log/ooonana-service-watchdog.log 2>&1 &
}

start_service_watchdog

start_network_fallback() {
  mkdir -p /etc /var/log
  if [ ! -s /etc/resolv.conf ]; then
    {
      echo 'nameserver 1.1.1.1'
      echo 'nameserver 8.8.8.8'
    } >/etc/resolv.conf 2>/dev/null || true
  fi

  if command -v ip >/dev/null 2>&1; then
    ip link set lo up >/dev/null 2>&1 || true
  elif command -v ifconfig >/dev/null 2>&1; then
    ifconfig lo up >/dev/null 2>&1 || true
  fi

  if /bin/busybox pidof NetworkManager >/dev/null 2>&1; then
    return 0
  fi

  for devpath in /sys/class/net/*; do
    [ -e "$devpath" ] || continue
    iface="${devpath##*/}"
    [ "$iface" = "lo" ] && continue
    case "$iface" in
      wlan*|wl*) continue ;;
    esac
    if command -v ip >/dev/null 2>&1; then
      ip link set "$iface" up >/dev/null 2>&1 || true
    elif command -v ifconfig >/dev/null 2>&1; then
      ifconfig "$iface" up >/dev/null 2>&1 || true
    fi
  done

  if command -v udhcpc >/dev/null 2>&1 &&
    ! route -n 2>/dev/null | awk '$1 == "0.0.0.0" { found = 1 } END { exit found ? 0 : 1 }'; then
    for devpath in /sys/class/net/*; do
      [ -e "$devpath" ] || continue
      iface="${devpath##*/}"
      [ "$iface" = "lo" ] && continue
      case "$iface" in
        wlan*|wl*) continue ;;
      esac
      udhcpc -q -n -i "$iface" -t 3 -T 3 >/var/log/udhcpc-"$iface".log 2>&1 && break
    done
  fi
}

start_network_fallback

ensure_glib_schemas() {
  if command -v glib-compile-schemas >/dev/null 2>&1 &&
    [ -d /usr/share/glib-2.0/schemas ] &&
    [ ! -f /usr/share/glib-2.0/schemas/gschemas.compiled ]; then
    glib-compile-schemas /usr/share/glib-2.0/schemas 2>/dev/null || true
  fi
}

refresh_gtk_caches() {
  if command -v update-mime-database >/dev/null 2>&1 &&
    [ -d /usr/share/mime ] &&
    [ ! -s /usr/share/mime/mime.cache ]; then
    update-mime-database /usr/share/mime >/dev/null 2>&1 || true
  fi
  if command -v gdk-pixbuf-query-loaders >/dev/null 2>&1 &&
    [ -d /usr/lib/gdk-pixbuf-2.0/2.10.0/loaders ] &&
    [ ! -s /usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache ]; then
    mkdir -p /usr/lib/gdk-pixbuf-2.0/2.10.0
    gdk-pixbuf-query-loaders >/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache 2>/dev/null || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1 &&
    [ -d /usr/share/icons ]; then
    for theme in /usr/share/icons/*; do
      [ -d "$theme" ] || continue
      [ -s "$theme/icon-theme.cache" ] && continue
      gtk-update-icon-cache -q -t "$theme" >/dev/null 2>&1 || true
    done
  fi
}

refresh_font_caches() {
  font_cache=""
  [ -d /usr/share/fonts ] || return 0
  for cache in /var/cache/fontconfig/*.cache-*; do
    if [ -s "$cache" ]; then
      font_cache="$cache"
      break
    fi
  done
  [ -n "$font_cache" ] && return 0
  if command -v mkfontscale >/dev/null 2>&1; then
    for font_dir in /usr/share/fonts/*; do
      [ -d "$font_dir" ] || continue
      [ -s "$font_dir/fonts.scale" ] || mkfontscale "$font_dir" >/dev/null 2>&1 || true
      if command -v mkfontdir >/dev/null 2>&1 && [ ! -s "$font_dir/fonts.dir" ]; then
        mkfontdir "$font_dir" >/dev/null 2>&1 || true
      fi
    done
  fi
  if command -v fc-cache >/dev/null 2>&1; then
    fc-cache /usr/share/fonts >/dev/null 2>&1 || true
  fi
}

ensure_glib_schemas
refresh_font_caches
refresh_gtk_caches

host="ooonana"
if [ -f /etc/hostname ]; then
  read -r host </etc/hostname || host="ooonana"
fi
[ -n "$host" ] || host="ooonana"
hostname "$host" 2>/dev/null || true

if [ -f /usr/share/ooonana/boot-logo.txt ]; then
  printf '\033]P3ffb21a\033[1;33m'
  cat /usr/share/ooonana/boot-logo.txt
  printf '\033[0m'
elif [ -f /usr/share/ooonana/logo.txt ]; then
  printf '\033]P3ffb21a\033[1;33m'
  cat /usr/share/ooonana/logo.txt
  printf '\033[0m'
fi
echo "Ooonana full i3 rootfs"

if grep -q 'ooonana.smoke=1' /proc/cmdline 2>/dev/null; then
  missing_downloaders=""
  for cmd in python3 curl wget; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing_downloaders="$missing_downloaders $cmd"
    fi
  done
  if [ -n "$missing_downloaders" ]; then
    echo "OOONANA_DOWNLOADERS_FAIL$missing_downloaders"
    sync
    sleep 1
    reboot -f
  fi
  echo "OOONANA_DOWNLOADERS_OK python3 curl wget"
  cli_ok=1
  version_output="$(/usr/bin/ooonana version 2>&1)" || cli_ok=0
  installed_output="$(/usr/bin/ooonana list --installed 2>&1)" || cli_ok=0
  if [ "$cli_ok" -eq 1 ] &&
    printf '%s\n' "$version_output" | grep -q 'ooonana 0.8.19' &&
    printf '%s\n' "$installed_output" | grep -q 'full-i3'; then
    echo "OOONANA_CLI_OK"
  else
    printf '%s\n' "$version_output" "$installed_output"
    echo "OOONANA_CLI_FAIL"
    sync
    sleep 1
    reboot -f
  fi
  if ! /usr/bin/start-ooonana-i3; then
    echo "OOONANA_FULL_I3_FAIL"
    sync
    sleep 1
    reboot -f
  fi
  echo "OOONANA_BOOT_OK"
  sync
  sleep 1
  reboot -f
fi

if [ -x /usr/bin/start-ooonana-i3 ]; then
  desktop_user="ooonana"
  if ! grep -q 'ooonana.live=1' /proc/cmdline 2>/dev/null &&
    [ -s /etc/ooonana/default-user ]; then
    read -r desktop_user </etc/ooonana/default-user || desktop_user="ooonana"
  fi
  if grep -q "^$desktop_user:" /etc/passwd 2>/dev/null; then
    /usr/bin/start-ooonana-i3 --user "$desktop_user" || true
  else
    /usr/bin/start-ooonana-i3 || true
  fi
fi

echo "Ooonana full i3 fallback shell"
exec /bin/sh -l
EOF
}

install_branding() {
  install -D -m 0644 "$ROOT/branding/logo.svg" "$ROOTFS/usr/share/ooonana/logo.svg"
  install -D -m 0644 "$ROOT/branding/logo.png" "$ROOTFS/usr/share/ooonana/logo.png"
  install -D -m 0644 "$ROOT/branding/wallpaper.svg" "$ROOTFS/usr/share/ooonana/wallpapers/ooonana-wallpaper.svg"
  install -D -m 0644 "$ROOT/branding/wallpaper.png" "$ROOTFS/usr/share/ooonana/wallpapers/ooonana-wallpaper.png"
  install -D -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/wallpapers/ooonana-notes.jpg" "$ROOTFS/usr/share/ooonana/wallpapers/ooonana-notes.jpg"
  install -D -m 0644 "$ROOT/branding/i3/config" "$ROOTFS/etc/i3/config"
  install -D -m 0644 "$ROOT/branding/i3/config" "$ROOTFS/etc/i3/config.keycodes"
  install -D -m 0644 /dev/stdin "$ROOTFS/etc/xdg/autostart/nm-applet.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=NetworkManager Applet
Hidden=true
EOF
  install -D -m 0644 /dev/stdin "$ROOTFS/etc/xdg/autostart/blueman.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Blueman Applet
Hidden=true
EOF
}

install_downloader_fallbacks() {
  if [[ ! -e "$ROOTFS/usr/bin/wget" ]]; then
    install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/wget" <<'EOF'
#!/bin/sh
exec /bin/busybox wget "$@"
EOF
  fi
}

fix_blueman_activation() {
  local service="$ROOTFS/usr/share/dbus-1/system-services/org.blueman.Mechanism.service"
  [[ -f "$service" ]] || return 0
  sed -i '/^SystemdService=/d' "$service"
}

install_full_i3_packages() {
  local sources_dir
  sources_dir="$(dirname "$ROOTFS")/full-i3-build-sources"
  [[ -d "$STAGED_REPO" ]] || ooonana_die "missing staged full-i3 repo: $STAGED_REPO"
  [[ -f "$STAGED_REPO/full-i3.pkg" ]] || ooonana_die "missing full-i3 package metadata: $STAGED_REPO/full-i3.pkg"

  rm -rf "$sources_dir"
  mkdir -p "$sources_dir" "$ROOTFS/var/cache/ooonana" "$ROOTFS/var/lib/ooonana/packages/installed"

  OOONANA_ROOT="$ROOTFS" \
    OOONANA_REPO_DIR="$STAGED_REPO" \
    OOONANA_SOURCES_DIR="$sources_dir" \
    OOONANA_STATE_DIR="$ROOTFS/var/lib/ooonana/packages" \
    OOONANA_CACHE_DIR="$ROOTFS/var/cache/ooonana" \
    "$ROOT/packages/ooonana/usr/bin/ooonana" get full-i3 >/dev/null
}

verify_full_i3_repo() {
  local package work i3_deps
  [[ -f "$REPO/base.pkg" ]] || ooonana_die "full-i3 repo missing base.pkg"
  [[ -f "$REPO/full-i3.pkg" ]] || ooonana_die "full-i3 repo missing full-i3.pkg"
  [[ -f "$REPO/i3.pkg" ]] || ooonana_die "full-i3 repo missing i3.pkg"
  i3_deps="$(awk -F'"' '$1 == "OOONANA_PKG_DEPS=" { print $2; exit }' "$REPO/i3.pkg")"
  while IFS= read -r package; do
    [[ -f "$REPO/$package.pkg" ]] ||
      ooonana_die "full-i3 repo missing profile package: $package"
    case "$package" in
      base|branding|i3|full-i3) continue ;;
    esac
    case " $i3_deps " in
      *" $package "*) ;;
      *) ooonana_die "stale i3.pkg: dependency missing from bundle: $package" ;;
    esac
  done < <(ooonana_read_package_profile "$PACKAGE_PROFILE")
  work="$(mktemp -d)"
  mkdir -p "$work/sources" "$work/state" "$work/cache"
  if ! OOONANA_ROOT="$work/root" \
    OOONANA_REPO_DIR="$STAGED_REPO" \
    OOONANA_SOURCES_DIR="$work/sources" \
    OOONANA_STATE_DIR="$work/state" \
    OOONANA_CACHE_DIR="$work/cache" \
    "$ROOT/packages/ooonana/usr/bin/ooonana" get full-i3 --dry-run >/dev/null; then
    rm -rf "$work"
    ooonana_die "full-i3 repo dependency closure is incomplete"
  fi
  rm -rf "$work"
}

stage_full_i3_repo_metadata() {
  local archive file repo_abs target
  STAGED_REPO="$(dirname "$ROOTFS")/full-i3-repo-metadata"
  repo_abs="$(CDPATH='' cd -- "$REPO" && pwd)"
  rm -rf "$STAGED_REPO"
  mkdir -p "$STAGED_REPO"
  for file in "$REPO"/*.pkg "$REPO/index.tsv" "$REPO/SHA256SUMS" \
    "$REPO/SHA256SUMS.sig" "$REPO/repo.pub"; do
    [[ -f "$file" ]] || continue
    cp -a "$file" "$STAGED_REPO/"
  done
  if [[ -d "$REPO/hooks" ]]; then
    cp -a "$REPO/hooks" "$STAGED_REPO/hooks"
  fi
  if [[ -d "$REPO/archives" ]]; then
    ln -s "$repo_abs/archives" "$STAGED_REPO/archives"
  fi
  for file in "$REPO"/*.pkg; do
    [[ -f "$file" ]] || continue
    archive="$(awk -F'"' '$1 == "OOONANA_PKG_ARCHIVE=" { print $2; exit }' "$file")"
    [[ -n "$archive" ]] || continue
    case "$archive" in
      archives/*) continue ;;
      /*|../*|*/../*|..) ooonana_die "unsafe staged archive path: $archive" ;;
    esac
    target="$STAGED_REPO/$archive"
    mkdir -p "$(dirname "$target")"
    ln -s "$repo_abs/$archive" "$target"
  done
}

write_default_cloud_source() {
  mkdir -p "$ROOTFS/etc/ooonana/sources.d" "$ROOTFS/usr/lib/ooonana/repo"
  rm -rf "$ROOTFS/usr/lib/ooonana/repo"
  mkdir -p "$ROOTFS/usr/lib/ooonana/repo"
  cat > "$ROOTFS/etc/ooonana/sources.d/cloud.repo" <<'EOF'
OOONANA_REPO_NAME="gitlab"
OOONANA_REPO_URI="https://ooonana.gitlab.io/ooonana-repo"
EOF
  cat > "$ROOTFS/usr/lib/ooonana/repo/README.txt" <<'EOF'
Ooonana full-i3 uses cloud packages by default.
Run:
  ooonana update
  ooonana upgrade
EOF
}

compile_glib_schemas() {
  local schema_dir="$ROOTFS/usr/share/glib-2.0/schemas"
  [[ -d "$schema_dir" ]] || return 0
  if command -v glib-compile-schemas >/dev/null 2>&1; then
    glib-compile-schemas "$ROOTFS/usr/share/glib-2.0/schemas" >/dev/null 2>&1 ||
      ooonana_log "warning: could not compile GSettings schemas in full-i3 rootfs"
  fi
}

refresh_gtk_caches() {
  if [[ -d "$ROOTFS/usr/share/mime" ]] && command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "$ROOTFS/usr/share/mime" >/dev/null 2>&1 ||
      ooonana_log "warning: could not update MIME database in full-i3 rootfs"
  fi
  if [[ -d "$ROOTFS/usr/share/icons" ]] && command -v gtk-update-icon-cache >/dev/null 2>&1; then
    local theme
    for theme in "$ROOTFS"/usr/share/icons/*; do
      [[ -d "$theme" ]] || continue
      gtk-update-icon-cache -q -t -f "$theme" >/dev/null 2>&1 || true
    done
  fi
  if [[ "$(id -u)" -eq 0 ]] &&
    [[ -x "$ROOTFS/usr/bin/gdk-pixbuf-query-loaders" ]] &&
    [[ -d "$ROOTFS/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders" ]]; then
    chroot "$ROOTFS" /usr/bin/gdk-pixbuf-query-loaders \
      >"$ROOTFS/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache" 2>/dev/null || true
  fi
}

refresh_font_caches() {
  [[ -d "$ROOTFS/usr/share/fonts" ]] || return 0
  if [[ "$(id -u)" -eq 0 ]] && [[ -x "$ROOTFS/bin/sh" ]]; then
    chroot "$ROOTFS" /bin/sh -lc '
      if command -v mkfontscale >/dev/null 2>&1; then
        for font_dir in /usr/share/fonts/*; do
          [ -d "$font_dir" ] || continue
          mkfontscale "$font_dir" >/dev/null 2>&1 || true
          if command -v mkfontdir >/dev/null 2>&1; then
            mkfontdir "$font_dir" >/dev/null 2>&1 || true
          fi
        done
      fi
      if command -v fc-cache >/dev/null 2>&1; then
        fc-cache -r /usr/share/fonts >/dev/null 2>&1 || true
      fi
    ' >/dev/null 2>&1 || ooonana_log "warning: could not refresh font caches in full-i3 rootfs"
  fi
}

restore_busybox_init_links() {
  [[ -x "$ROOTFS/bin/busybox" ]] || return 0
  mkdir -p "$ROOTFS/bin" "$ROOTFS/sbin" "$ROOTFS/usr/bin"
  for applet in adduser awk basename cat chmod clear cp cut date dd df dirname dmesg echo env free grep hostname ifconfig ip ls mkdir mount mv passwd ps pwd readlink rm rmdir route sed sh sha256sum sleep sort sync tar touch tr udhcpc umount uname wc wget; do
    ln -sf busybox "$ROOTFS/bin/$applet"
  done
  for applet in init reboot poweroff halt mdev switch_root; do
    ln -sf ../bin/busybox "$ROOTFS/sbin/$applet"
  done
  ln -sf ../../bin/busybox "$ROOTFS/usr/bin/env"
}

write_full_groups() {
  local group_file="$ROOTFS/etc/group"
  touch "$group_file"
  for entry in \
    'root:x:0:' \
    'wheel:x:10:' \
    'tty:x:5:' \
    'disk:x:6:' \
    'lp:x:7:' \
    'dialout:x:20:' \
    'audio:x:29:' \
    'video:x:44:' \
    'input:x:97:' \
    'users:x:100:' \
    'netdev:x:101:' \
    'plugdev:x:102:' \
    'kmem:x:9:' \
    'cdrom:x:11:' \
    'tape:x:26:' \
    'kvm:x:34:' \
    'messagebus:x:81:' \
    'pulse:x:70:' \
    'pulse-access:x:71:'; do
    name="${entry%%:*}"
    grep -q "^$name:" "$group_file" 2>/dev/null || printf '%s\n' "$entry" >> "$group_file"
  done

  local passwd_file="$ROOTFS/etc/passwd"
  touch "$passwd_file"
  grep -q '^messagebus:' "$passwd_file" 2>/dev/null ||
    printf '%s\n' 'messagebus:x:81:81:DBus Message Bus:/run/dbus:/bin/false' >> "$passwd_file"
  grep -q '^pulse:' "$passwd_file" 2>/dev/null ||
    printf '%s\n' 'pulse:x:70:70:PulseAudio:/run/pulse:/bin/false' >> "$passwd_file"

  mkdir -p "$ROOTFS/var" "$ROOTFS/run"
  rm -rf "$ROOTFS/var/run"
  ln -s ../run "$ROOTFS/var/run"

  local live_user="ooonana"
  local live_uid="1000"
  local live_gid="1000"
  local home_dir="$ROOTFS/home/$live_user"
  if ! grep -q "^$live_user:" "$group_file" 2>/dev/null; then
    printf '%s:x:%s:\n' "$live_user" "$live_gid" >> "$group_file"
  fi
  if ! grep -q "^$live_user:" "$passwd_file" 2>/dev/null; then
    printf '%s:x:%s:%s:Ooonana Live User:/home/%s:/bin/sh\n' "$live_user" "$live_uid" "$live_gid" "$live_user" >> "$passwd_file"
  fi

  add_group_member() {
    local group_name="$1"
    local member="$2"
    local tmp_file="$group_file.tmp.$$"
    awk -F: -v OFS=: -v group_name="$group_name" -v member="$member" '
      $1 == group_name {
        n = split($4, members, ",")
        found = 0
        for (i = 1; i <= n; i++) if (members[i] == member) found = 1
        if (!found) $4 = ($4 == "" ? member : $4 "," member)
      }
      { print }
    ' "$group_file" > "$tmp_file"
    mv "$tmp_file" "$group_file"
  }
  for group_name in wheel audio video input lp netdev plugdev users; do
    add_group_member "$group_name" "$live_user"
  done

  local shadow_file="$ROOTFS/etc/shadow"
  touch "$shadow_file"
  grep -q "^$live_user:" "$shadow_file" 2>/dev/null ||
    printf '%s:!:20000:0:99999:7:::\n' "$live_user" >> "$shadow_file"
  chmod 0600 "$shadow_file"

  mkdir -p "$home_dir/.config/ooonana" "$home_dir/.cache" "$home_dir/.local/state/ooonana" "$home_dir/Desktop" "$home_dir/Downloads" "$home_dir/Pictures/Ooonana"
  if [[ "$(id -u)" -eq 0 ]]; then
    chown -R "$live_uid:$live_gid" "$home_dir"
  else
    chmod -R u+rwX "$home_dir"
  fi

  install -D -m 0400 /dev/stdin "$ROOTFS/etc/doas.d/ooonana.conf" <<'DOAS'
permit nopass keepenv :wheel
DOAS
  install -D -m 0400 /dev/stdin "$ROOTFS/etc/doas.conf" <<'DOAS'
permit nopass keepenv :wheel
DOAS
  install -D -m 0440 /dev/stdin "$ROOTFS/etc/sudoers.d/ooonana" <<'SUDOERS'
%wheel ALL=(ALL:ALL) NOPASSWD: ALL
SUDOERS
  cat > "$ROOTFS/etc/os-release" <<EOF
NAME="Ooonana OS"
ID=ooonana
PRETTY_NAME="Ooonana OS $OS_VERSION"
VERSION="$OS_VERSION"
VERSION_ID="$OS_VERSION"
HOME_URL="https://github.com/Ooonana/Ooonana-OS"
SUPPORT_URL="https://github.com/Ooonana/Ooonana-OS/issues"
EOF
  printf '%s\n' "$live_user" > "$ROOTFS/etc/ooonana/default-user"
  cat > "$ROOTFS/etc/wsl.conf" <<'WSL'
[boot]
systemd=false

[automount]
mountFsTab=false

[user]
default=ooonana
WSL

  mkdir -p "$ROOTFS/var/lib/dbus"
  printf '%s\n' '11111111111111111111111111111111' > "$ROOTFS/etc/machine-id"
  cp "$ROOTFS/etc/machine-id" "$ROOTFS/var/lib/dbus/machine-id"
}

write_tarball() {
  mkdir -p "$(dirname "$TARBALL")"
  rm -f "$TARBALL"
  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --numeric-owner \
    --pax-option=delete=atime,delete=ctime \
    --exclude='./dev/*' \
    --exclude='./proc/*' \
    --exclude='./sys/*' \
    --exclude='./run/*' \
    --exclude='./tmp/*' \
    -C "$ROOTFS" \
    -cf - \
    . | gzip -n > "$TARBALL"
  chmod a+rw "$TARBALL"
}

normalize_rootfs_permissions() {
  mkdir -p "$ROOTFS/tmp"
  chmod -R go-w "$ROOTFS" 2>/dev/null || true
  chmod 1777 "$ROOTFS/tmp"

  local setuid_path
  for setuid_path in \
    "$ROOTFS/usr/bin/doas" \
    "$ROOTFS/usr/bin/sudo" \
    "$ROOTFS/usr/bin/su" \
    "$ROOTFS/bin/su"; do
    [[ -f "$setuid_path" ]] && chmod 4755 "$setuid_path"
  done

  if [[ -f "$ROOTFS/usr/lib/chromium/chrome-sandbox" ]]; then
    chmod 4755 "$ROOTFS/usr/lib/chromium/chrome-sandbox"
  fi

  if [[ -f "$ROOTFS/usr/libexec/dbus-daemon-launch-helper" ]]; then
    if chown 0:81 "$ROOTFS/usr/libexec/dbus-daemon-launch-helper" 2>/dev/null; then
      chmod 4750 "$ROOTFS/usr/libexec/dbus-daemon-launch-helper"
    else
      # Unprivileged fixture builds cannot assign messagebus group 81.
      chmod 4755 "$ROOTFS/usr/libexec/dbus-daemon-launch-helper"
    fi
  fi
}

main() {
  ooonana_require_linux
  ooonana_require_commands awk chmod cp gzip install ln mkdir mktemp rm sed sha256sum stat tar
  [[ -d "$SCRATCH_ROOTFS" ]] || ooonana_die "missing scratch rootfs: $SCRATCH_ROOTFS"
  [[ -x "$SCRATCH_ROOTFS/bin/sh" ]] || ooonana_die "invalid scratch rootfs: missing /bin/sh"
  [[ -f "$ROOT/branding/logo.svg" ]] || ooonana_die "missing branding/logo.svg"
  [[ -f "$ROOT/branding/logo.png" ]] || ooonana_die "missing branding/logo.png"
  [[ -f "$ROOT/branding/wallpaper.svg" ]] || ooonana_die "missing branding/wallpaper.svg"
  [[ -f "$ROOT/branding/wallpaper.png" ]] || ooonana_die "missing branding/wallpaper.png"
  [[ -f "$ROOT/branding/i3/config" ]] || ooonana_die "missing branding/i3/config"
  if [[ ! -s "$REPO/index.tsv" || ! -s "$REPO/SHA256SUMS" ]]; then
    ooonana_log "package repository metadata missing; indexing $REPO"
    "$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$REPO" >/dev/null
  fi
  stage_full_i3_repo_metadata
  verify_full_i3_repo

  mkdir -p "$(dirname "$ROOTFS")"
  ooonana_require_unix_permissions "$(dirname "$ROOTFS")"

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ROOTFS"
    rm -f "$TARBALL"
  elif [[ -e "$ROOTFS" || -e "$TARBALL" ]]; then
    ooonana_die "full-i3 rootfs or tarball exists (use --force)"
  fi

  mkdir -p "$(dirname "$ROOTFS")"
  cp -a "$SCRATCH_ROOTFS" "$ROOTFS"
  cp -a "$ROOT/packages/ooonana/." "$ROOTFS/"
  chmod 0755 \
    "$ROOTFS/usr/bin/ooonana" \
    "$ROOTFS/usr/bin/ooonana-ai" \
    "$ROOTFS/usr/bin/ooonana-ai-app" \
    "$ROOTFS/usr/bin/ooonana-ai-launch" \
    "$ROOTFS/usr/bin/ooonana-setup" \
    "$ROOTFS/usr/bin/bunana" \
    "$ROOTFS/usr/bin/oonana" \
    "$ROOTFS/usr/bin/ooonana-game-launch" \
    "$ROOTFS/usr/lib/ooonana/oonana_game.py" \
    "$ROOTFS/usr/bin/clear" \
    "$ROOTFS/usr/bin/neofetch" \
    "$ROOTFS/usr/bin/ooonana-neofetch" \
    "$ROOTFS/usr/bin/ooonana-audio-start" \
    "$ROOTFS/usr/bin/which" \
    "$ROOTFS/usr/bin/strings" \
    "$ROOTFS/usr/bin/ooonana-settings-launch" \
    "$ROOTFS/usr/sbin/ooonana-install"
  mkdir -p "$ROOTFS/etc/ooonana" "$ROOTFS/var/lib/ooonana/packages/installed" "$ROOTFS/var/log"
  printf '127.0.0.1 localhost ooonana\n' > "$ROOTFS/etc/hosts"
  printf 'full-i3\n' > "$ROOTFS/etc/ooonana/edition"
  install_full_i3_packages
  case "${OOONANA_SKIP_INTEL_FIRMWARE:-0}" in
    0)
      bash "$ROOT/scripts/install-intel-wireless-firmware.sh" \
        "$ROOTFS" "${OOONANA_FIRMWARE_CACHE_DIR:-$(dirname "$ROOTFS")/firmware-cache}"
      ;;
    1) printf '[ooonana] Intel wireless firmware supplement skipped\n' ;;
    *) ooonana_die "OOONANA_SKIP_INTEL_FIRMWARE must be 0 or 1" ;;
  esac
  if [[ -x "$ROOTFS/usr/bin/python3" ]]; then
    rm -f "$ROOTFS/usr/bin/python"
    ln -s python3 "$ROOTFS/usr/bin/python"
  fi
  fix_blueman_activation
  install_downloader_fallbacks
  write_default_cloud_source
  compile_glib_schemas
  refresh_font_caches
  refresh_gtk_caches
  restore_busybox_init_links
  write_full_groups
  install_branding
  write_start_script
  write_theme_helpers
  write_desktop_helpers
  write_gui_installer
  write_xorg_input_config
  write_xorg_video_config
  write_full_init_script
  printf 'packages-installed\n' > "$ROOTFS/etc/ooonana/edition-state"
  normalize_rootfs_permissions
  write_tarball
  rm -rf "$STAGED_REPO"

  ooonana_log "full-i3 rootfs ready: $ROOTFS"
  ooonana_log "full-i3 rootfs tarball ready: $TARBALL"
}

main "$@"
