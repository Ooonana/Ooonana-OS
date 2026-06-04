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
exec /bin/sh
EOF
}

write_theme_helpers() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-theme-env" <<'EOF'
#!/bin/sh
set -eu

load_theme() {
  theme="${OOONANA_THEME:-}"
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

case "${1:-env}" in
  env)
    printf 'OOONANA_THEME="%s"\n' "$OOONANA_THEME"
    printf 'OOONANA_BG="%s"\n' "$OOONANA_BG"
    printf 'OOONANA_FG="%s"\n' "$OOONANA_FG"
    printf 'OOONANA_CURSOR="%s"\n' "$OOONANA_CURSOR"
    ;;
  apply)
    xsetroot -solid "$OOONANA_BG" 2>/dev/null || true
    if command -v feh >/dev/null 2>&1 && [ -f /usr/share/ooonana/wallpapers/ooonana-wallpaper.png ]; then
      feh --bg-fill /usr/share/ooonana/wallpapers/ooonana-wallpaper.png || true
    fi
    ;;
  xterm)
    shift
    exec xterm -bg "$OOONANA_BG" -fg "$OOONANA_FG" -cr "$OOONANA_CURSOR" "$@"
    ;;
  *)
    echo "usage: ooonana-theme-env [env|apply|xterm]" >&2
    exit 1
    ;;
esac
EOF
}

write_gui_installer() {
  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-gui-installer" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "--dry-run" ]; then
  echo "xterm -title Ooonana Installer"
  echo "default theme: dark background, orange cursor"
  echo "ooonana-install-wizard --dry-run"
  echo "OOONANA_GUI_INSTALLER_OK"
  exit 0
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
  printf 'Installing to %s from %s\n' "$TARGET" "$SOURCE"
  printf 'User: %s\n' "$USER_NAME"
  printf 'Hostname: %s\n' "$HOSTNAME_VALUE"
  printf 'Theme: %s\n' "$THEME"
  printf 'Log: %s\n\n' "$LOG_FILE"
  printf '[1/5] format target\n'
  printf '[2/5] copy Ooonana files\n'
  printf '[3/5] write user, hostname, theme\n'
  printf '[4/5] write fstab/install marker\n'
  printf '[5/5] finish\n\n'
  if [ -n "$PASSWORD_VALUE" ]; then
    if printf '%s\n' "$PASSWORD_VALUE" | /usr/sbin/ooonana-install --target "$TARGET" --source "$SOURCE" --hostname "$HOSTNAME_VALUE" --user "$USER_NAME" --theme "$THEME" --password-stdin --yes >"$LOG_FILE" 2>&1; then
      cat "$LOG_FILE"
    else
      status="$?"
      cat "$LOG_FILE" 2>/dev/null || true
      return "$status"
    fi
  elif /usr/sbin/ooonana-install --target "$TARGET" --source "$SOURCE" --hostname "$HOSTNAME_VALUE" --user "$USER_NAME" --theme "$THEME" --yes >"$LOG_FILE" 2>&1; then
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
  printf 'Step 1/6 target: %s\n' "$target"
  printf 'Step 2/6 user: %s\n' "$USER_NAME"
  printf 'Step 3/6 hostname: %s\n' "$HOSTNAME_VALUE"
  printf 'Step 4/6 theme: %s\n' "$THEME"
  printf 'Step 5/6 confirm: INSTALL\n'
  printf 'Step 6/6 reboot: optional\n'
  printf '/usr/sbin/ooonana-install --target %s --source %s --hostname %s --user %s --theme %s --yes\n' "$target" "$SOURCE" "$HOSTNAME_VALUE" "$USER_NAME" "$THEME"
  printf 'OOONANA_INSTALL_WIZARD_OK\n'
  exit 0
fi

if [ "$YES" -eq 0 ]; then
  screen "Step 1/6: Target disk"
  printf 'Known target disks:\n'
  list_targets || true
  default_target="$(suggest_target)"
  printf '\nTarget disk [%s]: ' "$default_target"
  read -r answer
  TARGET="${answer:-$default_target}"

  screen "Step 2/6: User account"
  printf 'User name [%s]: ' "$USER_NAME"
  read -r answer
  USER_NAME="${answer:-$USER_NAME}"
  password_one="$(read_hidden 'Password blank to set later: ')"
  if [ -n "$password_one" ]; then
    password_two="$(read_hidden 'Password again: ')"
    [ "$password_one" = "$password_two" ] || die "password mismatch"
    PASSWORD_VALUE="$password_one"
  fi

  screen "Step 3/6: Hostname"
  printf 'Hostname [%s]: ' "$HOSTNAME_VALUE"
  read -r answer
  HOSTNAME_VALUE="${answer:-$HOSTNAME_VALUE}"

  screen "Step 4/6: Theme"
  printf 'Theme dark/light [%s]: ' "$THEME"
  read -r answer
  THEME="${answer:-$THEME}"
  valid_theme "$THEME" || die "theme must be dark or light"

  screen "Source root"
  printf 'Source root [%s]: ' "$SOURCE"
  read -r answer
  SOURCE="${answer:-$SOURCE}"
fi

[ -n "$TARGET" ] || die "target required"
[ -n "$SOURCE" ] || die "source required"
[ -n "$USER_NAME" ] || die "user required"
[ -n "$HOSTNAME_VALUE" ] || die "hostname required"
valid_theme "$THEME" || die "theme must be dark or light"
confirm_root_target

if [ "$YES" -eq 0 ]; then
  screen "Step 5/6: Confirm install"
  printf 'Target: %s\n' "$TARGET"
  printf 'Source: %s\n' "$SOURCE"
  printf 'User: %s\n' "$USER_NAME"
  printf 'Hostname: %s\n' "$HOSTNAME_VALUE"
  printf 'Theme: %s\n' "$THEME"
  printf '\nThis erases target. Type INSTALL to continue: '
  read -r answer
  [ "$answer" = "INSTALL" ] || die "install cancelled"
fi

screen "Step 6/6: Installing"
run_installer
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
exec --no-startup-id sh -c 'sleep 2; echo "OOONANA_FULL_I3_OK" >/dev/console; i3-msg exit >/dev/null 2>&1 || true'
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
Exec=ooonana-gui-installer
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
}

write_full_init_script() {
  install -D -m 0755 /dev/stdin "$ROOTFS/etc/init.d/rcS" <<'EOF'
#!/bin/sh
mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mkdir -p /dev/pts
mount -t devpts devpts /dev/pts 2>/dev/null || true
mount -t tmpfs tmpfs /run 2>/dev/null || true
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
  if /usr/bin/ooonana version | grep -q 'ooonana 0.7.0' &&
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
  mkdir -p "$ROOTFS/etc/ooonana" "$ROOTFS/var/lib/ooonana/packages/installed" "$ROOTFS/var/log"
  printf '127.0.0.1 localhost ooonana\n' > "$ROOTFS/etc/hosts"
  printf 'full-i3\n' > "$ROOTFS/etc/ooonana/edition"
  install_full_i3_packages
  install_branding
  write_start_script
  write_theme_helpers
  write_gui_installer
  write_full_init_script
  printf 'packages-installed\n' > "$ROOTFS/etc/ooonana/edition-state"
  write_tarball
  chmod -R a+rwX "$ROOTFS" 2>/dev/null || true

  ooonana_log "full-i3 rootfs ready: $ROOTFS"
  ooonana_log "full-i3 rootfs tarball ready: $TARBALL"
}

main "$@"
