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
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

write_start_script() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/start-ooonana-i3" <<'EOF'
#!/bin/sh
set -eu

case "${HOME:-}" in
  ""|/) export HOME="/root" ;;
  *) export HOME ;;
esac
mkdir -p "$HOME" /tmp
touch "$HOME/.Xauthority" 2>/dev/null || true
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

if grep -q 'ooonana.smoke=1' /proc/cmdline 2>/dev/null; then
  if grep -q 'ooonana.gui-smoke=1' /proc/cmdline 2>/dev/null &&
    command -v startx >/dev/null 2>&1 &&
    command -v i3 >/dev/null 2>&1; then
    exec startx /usr/bin/ooonana-i3-smoke-session
  fi
  echo "OOONANA_FULL_I3_OK"
  exit 0
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
  exec /usr/bin/ooonana-i3-session
fi

if command -v startx >/dev/null 2>&1 && command -v i3 >/dev/null 2>&1; then
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
      ;;
    *)
      OOONANA_THEME="dark"
      OOONANA_BG="#050505"
      OOONANA_FG="#ffb21a"
      ;;
  esac
  OOONANA_CURSOR="#ffb21a"
  export OOONANA_THEME OOONANA_BG OOONANA_FG OOONANA_CURSOR
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
    printf 'OOONANA_THEME="%s"\n' "$OOONANA_THEME"
    printf 'OOONANA_BG="%s"\n' "$OOONANA_BG"
    printf 'OOONANA_FG="%s"\n' "$OOONANA_FG"
    printf 'OOONANA_CURSOR="%s"\n' "$OOONANA_CURSOR"
    ;;
  apply)
    xsetroot -solid "$OOONANA_BG" 2>/dev/null || true
    wallpaper="/usr/share/ooonana/wallpapers/ooonana-wallpaper.png"
    if [ -n "${HOME:-}" ] && [ -f "$HOME/.config/ooonana/wallpaper" ]; then
      IFS= read -r saved_wallpaper <"$HOME/.config/ooonana/wallpaper" || saved_wallpaper=""
      [ -n "$saved_wallpaper" ] && wallpaper="$saved_wallpaper"
    fi
    if command -v hsetroot >/dev/null 2>&1 && [ -f "$wallpaper" ]; then
      hsetroot -cover "$wallpaper" && exit 0 || true
    fi
    if command -v feh >/dev/null 2>&1 && [ -f "$wallpaper" ]; then
      feh --bg-fill "$wallpaper" || true
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

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-browser" <<'EOF'
#!/bin/sh
set -eu
url="${1:-about:blank}"
if command -v chromium >/dev/null 2>&1; then
  exec chromium --no-first-run --disable-default-apps "$url"
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

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-wifi" <<'EOF'
#!/bin/sh
set -eu
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
if command -v blueman-manager >/dev/null 2>&1; then
  exec blueman-manager
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "blueman missing"; echo "run: ooonana get blueman"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/hsetroot" <<'EOF'
#!/bin/sh
set -eu
color=""
image=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -solid)
      color="${2:-}"
      shift 2
      ;;
    -cover|-fill|-full)
      image="${2:-}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
if [ -n "$image" ] && [ -f "$image" ] && command -v feh >/dev/null 2>&1; then
  exec feh --bg-fill "$image"
fi
if [ -n "$color" ] && command -v xsetroot >/dev/null 2>&1; then
  exec xsetroot -solid "$color"
fi
if command -v xsetroot >/dev/null 2>&1; then
  exec xsetroot -name "Ooonana OS"
fi
exit 0
EOF

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

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-music" <<'EOF'
#!/bin/sh
set -eu
if command -v ncmpcpp >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e ncmpcpp
fi
if command -v mpc >/dev/null 2>&1; then
  exec ooonana-theme-env xterm -e sh -lc 'mpc status; exec sh'
fi
exec ooonana-theme-env xterm -e sh -lc 'echo "music tools missing"; echo "run: ooonana get mpd mpc ncmpcpp"; exec sh'
EOF

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
  value="$(yad --center --title "Ooonana Brightness" --scale --min-value=1 --max-value=100 --value=75 --button=Apply:0 2>/dev/null || true)"
  [ -n "$value" ] && exec brightnessctl set "${value}%"
fi
exec ooonana-theme-env xterm -e sh -lc 'brightnessctl; echo; echo "Usage: ooonana-brightness 75%"; exec sh'
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-settings" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "yad settings menu"
  echo "actions: theme wallpaper display audio wifi bluetooth brightness screenshot editor music processes ranger repo about"
  echo "OOONANA_SETTINGS_GUI_OK"
  exit 0
fi

open_term() {
  if command -v ooonana-theme-env >/dev/null 2>&1; then
    exec ooonana-theme-env xterm -e sh -lc 'ooonana help ui; exec sh'
  fi
  exec sh -lc 'ooonana help ui; exec sh'
}

if [ -z "${DISPLAY:-}" ] || ! command -v yad >/dev/null 2>&1; then
  open_term
fi

while :; do
  action="$(yad --center --title "Ooonana Settings" --width=520 --height=360 \
    --list --print-column=1 --column Action --column Description \
    theme "Dark/light theme" \
    wallpaper "Choose desktop wallpaper" \
    display "Open display layout" \
    audio "Open audio controls" \
    wifi "Open NetworkManager" \
    bluetooth "Open Bluetooth manager" \
    brightness "Set display brightness" \
    screenshot "Take screenshot" \
    editor "Open Geany/Vim" \
    music "Open MPD client" \
    processes "Open htop" \
    ranger "Open terminal file manager" \
    repo "Set cloud package repo" \
    about "Show Ooonana info" 2>/dev/null || true)"
  [ -n "$action" ] || exit 0
  case "$action" in
    theme)
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
          ;;
      esac
      ;;
    wallpaper)
      file="$(yad --center --title "Ooonana Wallpaper" --file --filename="/usr/share/ooonana/wallpapers/" 2>/dev/null || true)"
      [ -n "$file" ] && ooonana-wallpaper "$file" || true
      ;;
    display)
      command -v arandr >/dev/null 2>&1 && arandr || yad --center --title "Display" --text "arandr missing"
      ;;
    audio)
      command -v pavucontrol >/dev/null 2>&1 && pavucontrol || yad --center --title "Audio" --text "pavucontrol missing"
      ;;
    wifi)
      ooonana-wifi || true
      ;;
    bluetooth)
      ooonana-bluetooth || true
      ;;
    brightness)
      ooonana-brightness || true
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
      repo="$(yad --center --title "Ooonana Repo" --entry --text "Cloud package repo URL" --entry-text "https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz" 2>/dev/null || true)"
      if [ -n "$repo" ]; then
        mkdir -p /etc/ooonana/sources.d 2>/dev/null || true
        {
          printf 'OOONANA_REPO_NAME="cloud"\n'
          printf 'OOONANA_REPO_URI="%s"\n' "$repo"
        } >/etc/ooonana/sources.d/cloud.repo 2>/dev/null ||
          yad --center --title "Repo" --text "Need root to write /etc/ooonana/sources.d/cloud.repo"
      fi
      ;;
    about)
      if [ -f /usr/share/ooonana/logo.txt ]; then
        yad --center --title "Ooonana OS" --text-info --filename=/usr/share/ooonana/logo.txt --width=520 --height=260
      else
        yad --center --title "Ooonana OS" --text "Ooonana OS"
      fi
      ;;
  esac
done
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-wallpaper" <<'EOF'
#!/bin/sh
set -eu
wallpaper="${1:-/usr/share/ooonana/wallpapers/ooonana-wallpaper.png}"
if [ ! -f "$wallpaper" ]; then
  printf 'missing wallpaper: %s\n' "$wallpaper" >&2
  exit 1
fi
mkdir -p "${HOME:-/root}/.config/ooonana"
printf '%s\n' "$wallpaper" >"${HOME:-/root}/.config/ooonana/wallpaper"
if command -v hsetroot >/dev/null 2>&1; then
  exec hsetroot -cover "$wallpaper"
fi
if command -v feh >/dev/null 2>&1; then
  exec feh --bg-fill "$wallpaper"
fi
exec ooonana-theme-env apply
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
background = #050505
foreground = #ffb21a
accent = #ffd37a
urgent = #ff4d2e

[bar/ooonana]
width = 100%
height = 28
background = ${colors.background}
foreground = ${colors.foreground}
line-size = 2
line-color = ${colors.accent}
font-0 = monospace:size=10;2
modules-left = workspaces title
modules-center = logo
modules-right = wlan battery date

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
label-unfocused-padding = 2

[module/title]
type = internal/xwindow
label = %title:0:48:...%

[module/wlan]
type = internal/network
interface-type = wireless
label-connected = wifi %essid%
label-disconnected = wifi off

[module/battery]
type = internal/battery
battery = BAT0
adapter = AC

[module/date]
type = internal/date
date = %Y-%m-%d %H:%M
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/rofi.rasi" <<'EOF'
* {
  background: #050505;
  foreground: #ffb21a;
  selected: #281604;
  urgent: #ff4d2e;
  font: "monospace 11";
}
window {
  width: 42%;
  border: 2px;
  border-color: @foreground;
  background-color: @background;
}
inputbar, listview {
  background-color: @background;
  text-color: @foreground;
}
element selected {
  background-color: @selected;
  text-color: #fff0c7;
}
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/picom.conf" <<'EOF'
backend = "xrender";
vsync = true;
shadow = true;
shadow-radius = 7;
shadow-opacity = 0.25;
fading = true;
fade-delta = 4;
corner-radius = 0;
EOF

  install -D -m 0644 /dev/stdin "$ROOTFS/etc/ooonana/dunstrc" <<'EOF'
[global]
font = monospace 10
frame_color = "#ffb21a"
separator_color = "#ffb21a"
background = "#050505"
foreground = "#ffb21a"
geometry = "340x5-20+40"
corner_radius = 0
[urgency_critical]
background = "#281604"
foreground = "#fff0c7"
frame_color = "#ff4d2e"
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
  case "$1" in
    /dev/nvme*n*p[0-9]*) printf '%s\n' "${1%p[0-9]*}" ;;
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
  --field "Cloud repo" "https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz" \
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
    set -- "$@" --bootloader none
    [ -n "$home_part" ] && set -- "$@" --home-part "$home_part"
    [ -n "$swap_part" ] && set -- "$@" --swap-part "$swap_part"
    [ -n "$efi_part" ] && set -- "$@" --efi-part "$efi_part"
    [ "$format_root" = "TRUE" ] || set -- "$@" --keep-root
    [ "$format_home" = "TRUE" ] || set -- "$@" --keep-home
    [ "$format_swap" = "TRUE" ] || set -- "$@" --keep-swap
    [ "$format_efi" = "TRUE" ] && set -- "$@" --format-efi || set -- "$@" --keep-efi
    ;;
  *)
    :
    ;;
esac

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
DEFAULT_CLOUD_REPO="${OOONANA_DEFAULT_CLOUD_REPO:-https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz}"
PASSWORD_VALUE=""
YES=0
DRY_RUN=0
LOG_FILE="/var/log/ooonana-install-wizard.log"

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
  case "$1" in
    /dev/nvme*n*p[0-9]*) printf '%s\n' "${1%p[0-9]*}" ;;
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

if [ -x /usr/bin/ooonana-theme-env ]; then
  eval "$(/usr/bin/ooonana-theme-env env)"
  ooonana-theme-env apply
fi

if command -v ooonana-setup >/dev/null 2>&1; then
  ooonana-setup --first-boot --gui >/var/log/ooonana-setup.log 2>&1 &
fi

exec i3
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
Exec=ooonana-settings
Terminal=false
Categories=Settings;System;
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
mount -t tmpfs tmpfs /run 2>/dev/null || true

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

start_persistence() {
  grep -q 'ooonana.persistence=1' /proc/cmdline 2>/dev/null || return 0
  mkdir -p /mnt/persist
  persist_dev=""
  for candidate in \
    /dev/disk/by-label/OOONANA_PERSIST \
    /dev/disk/by-label/ooonana-persist \
    /dev/disk/by-label/OOONANA-PERSIST; do
    if [ -e "$candidate" ]; then
      persist_dev="$candidate"
      break
    fi
  done
  if [ -z "$persist_dev" ]; then
    echo "OOONANA_PERSISTENCE_WAIT"
    return 0
  fi
  if mount "$persist_dev" /mnt/persist 2>/dev/null; then
    mkdir -p /mnt/persist/home /mnt/persist/etc-ooonana /mnt/persist/var-lib-ooonana /mnt/persist/var-cache-ooonana
    mkdir -p /home /etc/ooonana /var/lib/ooonana /var/cache/ooonana
    mount --bind /mnt/persist/home /home 2>/dev/null || true
    mount --bind /mnt/persist/etc-ooonana /etc/ooonana 2>/dev/null || true
    mount --bind /mnt/persist/var-lib-ooonana /var/lib/ooonana 2>/dev/null || true
    mount --bind /mnt/persist/var-cache-ooonana /var/cache/ooonana 2>/dev/null || true
    echo "OOONANA_PERSISTENCE_OK"
  else
    echo "OOONANA_PERSISTENCE_FAIL"
  fi
}

start_persistence

host="ooonana"
if [ -f /etc/hostname ]; then
  read -r host </etc/hostname || host="ooonana"
fi
[ -n "$host" ] || host="ooonana"
hostname "$host" 2>/dev/null || true

if [ -f /usr/share/ooonana/logo.txt ]; then
  cat /usr/share/ooonana/logo.txt
fi
echo "Ooonana full i3 rootfs"

if grep -q 'ooonana.smoke=1' /proc/cmdline 2>/dev/null; then
  if /usr/bin/ooonana version | grep -q 'ooonana 0.8.0' &&
    /usr/bin/ooonana list --installed | grep -q 'full-i3'; then
    echo "OOONANA_CLI_OK"
  else
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
  /usr/bin/start-ooonana-i3 || true
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
  install -D -m 0644 "$ROOT/branding/i3/config" "$ROOTFS/etc/i3/config"
}

shell_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

install_full_i3_packages() {
  local sources_dir
  sources_dir="$(dirname "$ROOTFS")/full-i3-build-sources"
  [[ -d "$REPO" ]] || ooonana_die "missing full-i3 repo: $REPO"
  [[ -f "$REPO/full-i3.pkg" ]] || ooonana_die "missing full-i3 package metadata: $REPO/full-i3.pkg"
  [[ -d "$ROOTFS/usr/lib/ooonana/repo" ]] || ooonana_die "missing rootfs builtin repo: $ROOTFS/usr/lib/ooonana/repo"

  rm -rf "$sources_dir"
  mkdir -p "$sources_dir" "$ROOTFS/var/cache/ooonana" "$ROOTFS/var/lib/ooonana/packages/installed"
  {
    printf 'OOONANA_REPO_NAME="full-i3-build"\n'
    printf 'OOONANA_REPO_URI="%s"\n' "$(shell_escape "$REPO")"
  } > "$sources_dir/full-i3.repo"

  OOONANA_ROOT="$ROOTFS" \
    OOONANA_REPO_DIR="$ROOTFS/usr/lib/ooonana/repo" \
    OOONANA_SOURCES_DIR="$sources_dir" \
    OOONANA_STATE_DIR="$ROOTFS/var/lib/ooonana/packages" \
    OOONANA_CACHE_DIR="$ROOTFS/var/cache/ooonana" \
    "$ROOT/packages/ooonana/usr/bin/ooonana" get full-i3 >/dev/null
}

write_tarball() {
  mkdir -p "$(dirname "$TARBALL")"
  rm -f "$TARBALL"
  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --numeric-owner \
    --owner=0 \
    --group=0 \
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

main() {
  ooonana_require_linux
  ooonana_require_commands awk chmod cp gzip install mkdir rm sed sha256sum tar
  [[ -d "$SCRATCH_ROOTFS" ]] || ooonana_die "missing scratch rootfs: $SCRATCH_ROOTFS"
  [[ -x "$SCRATCH_ROOTFS/bin/sh" ]] || ooonana_die "invalid scratch rootfs: missing /bin/sh"
  [[ -f "$ROOT/branding/logo.svg" ]] || ooonana_die "missing branding/logo.svg"
  [[ -f "$ROOT/branding/logo.png" ]] || ooonana_die "missing branding/logo.png"
  [[ -f "$ROOT/branding/wallpaper.svg" ]] || ooonana_die "missing branding/wallpaper.svg"
  [[ -f "$ROOT/branding/wallpaper.png" ]] || ooonana_die "missing branding/wallpaper.png"
  [[ -f "$ROOT/branding/i3/config" ]] || ooonana_die "missing branding/i3/config"

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
    "$ROOTFS/usr/bin/ooonana-setup" \
    "$ROOTFS/usr/bin/bunana" \
    "$ROOTFS/usr/bin/oonana" \
    "$ROOTFS/usr/bin/clear" \
    "$ROOTFS/usr/bin/neofetch" \
    "$ROOTFS/usr/bin/ooonana-neofetch" \
    "$ROOTFS/usr/sbin/ooonana-install"
  mkdir -p "$ROOTFS/etc/ooonana" "$ROOTFS/var/lib/ooonana/packages/installed" "$ROOTFS/var/log"
  printf '127.0.0.1 localhost ooonana\n' > "$ROOTFS/etc/hosts"
  printf 'full-i3\n' > "$ROOTFS/etc/ooonana/edition"
  install_full_i3_packages
  install_branding
  write_start_script
  write_theme_helpers
  write_desktop_helpers
  write_gui_installer
  write_xorg_input_config
  write_full_init_script
  printf 'packages-installed\n' > "$ROOTFS/etc/ooonana/edition-state"
  write_tarball
  chmod -R a+rwX "$ROOTFS" 2>/dev/null || true

  ooonana_log "full-i3 rootfs ready: $ROOTFS"
  ooonana_log "full-i3 rootfs tarball ready: $TARBALL"
}

main "$@"
