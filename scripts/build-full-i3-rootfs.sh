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

export HOME="${HOME:-/root}"
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

if command -v startx >/dev/null 2>&1 && command -v i3 >/dev/null 2>&1; then
  exec startx /usr/bin/ooonana-i3-session
fi

echo "Ooonana full-i3"
echo "Missing startx or i3. Build/publish the full-i3 package repo, then run: ooonana get full-i3"
exec /bin/sh
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
YES=0
DRY_RUN=0
LOG_FILE="/var/log/ooonana-install-wizard.log"

usage() {
  cat <<'USAGE'
Ooonana graphical installer wizard.

Usage:
  ooonana-install-wizard [TARGET] [options]

Options:
  --target PATH  Target disk or ext4 image
  --source PATH  Source root (default: /)
  --yes          Skip wizard prompts
  --dry-run      Print installer command only
  -h, --help     Show help
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
  printf 'Log: %s\n\n' "$LOG_FILE"
  if /usr/sbin/ooonana-install --target "$TARGET" --source "$SOURCE" --yes >"$LOG_FILE" 2>&1; then
    cat "$LOG_FILE"
  else
    status="$?"
    cat "$LOG_FILE" 2>/dev/null || true
    return "$status"
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
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
  printf 'Step 1/4 target: %s\n' "$target"
  printf 'Step 2/4 source: %s\n' "$SOURCE"
  printf 'Step 3/4 confirm: INSTALL\n'
  printf '/usr/sbin/ooonana-install --target %s --source %s --yes\n' "$target" "$SOURCE"
  printf 'OOONANA_INSTALL_WIZARD_OK\n'
  exit 0
fi

if [ "$YES" -eq 0 ]; then
  screen "Step 1/4: Target disk"
  printf 'Known target disks:\n'
  list_targets || true
  default_target="$(suggest_target)"
  printf '\nTarget disk [%s]: ' "$default_target"
  read -r answer
  TARGET="${answer:-$default_target}"

  screen "Step 2/4: Source root"
  printf 'Source root [%s]: ' "$SOURCE"
  read -r answer
  SOURCE="${answer:-$SOURCE}"
fi

[ -n "$TARGET" ] || die "target required"
[ -n "$SOURCE" ] || die "source required"
confirm_root_target

if [ "$YES" -eq 0 ]; then
  screen "Step 3/4: Confirm install"
  printf 'Target: %s\n' "$TARGET"
  printf 'Source: %s\n' "$SOURCE"
  printf '\nThis erases target. Type INSTALL to continue: '
  read -r answer
  [ "$answer" = "INSTALL" ] || die "install cancelled"
fi

screen "Step 4/4: Installing"
run_installer
printf '\nOOONANA_INSTALL_WIZARD_OK\n'

if [ "$YES" -eq 0 ]; then
  printf '\nInstall complete. Press Enter to close.'
  read -r _answer
fi
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-i3-smoke-session" <<'EOF'
#!/bin/sh
set -eu

if command -v feh >/dev/null 2>&1 && [ -f /usr/share/ooonana/wallpapers/ooonana-wallpaper.png ]; then
  xsetroot -solid "#050505" 2>/dev/null || true
  feh --bg-fill /usr/share/ooonana/wallpapers/ooonana-wallpaper.png || true
fi

i3 &
sleep 3
echo "OOONANA_FULL_I3_OK" >/dev/console
sleep 1
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-i3-session" <<'EOF'
#!/bin/sh
set -eu

if command -v feh >/dev/null 2>&1 && [ -f /usr/share/ooonana/wallpapers/ooonana-wallpaper.png ]; then
  xsetroot -solid "#050505" 2>/dev/null || true
  feh --bg-fill /usr/share/ooonana/wallpapers/ooonana-wallpaper.png || true
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
hostname ooonana 2>/dev/null || true

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
  write_gui_installer
  write_full_init_script
  printf 'packages-installed\n' > "$ROOTFS/etc/ooonana/edition-state"
  write_tarball
  chmod -R a+rwX "$ROOTFS" 2>/dev/null || true

  ooonana_log "full-i3 rootfs ready: $ROOTFS"
  ooonana_log "full-i3 rootfs tarball ready: $TARBALL"
}

main "$@"
