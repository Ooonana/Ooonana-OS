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

target="${1:-/dev/vda}"

if [ "${1:-}" = "--dry-run" ]; then
  echo "xmessage Ooonana installer"
  echo "/usr/sbin/ooonana-install --target $target --source / --yes"
  echo "OOONANA_GUI_INSTALLER_OK"
  exit 0
fi

confirm_text="Install Ooonana OS full i3 to $target? This erases the target."
if [ -n "${DISPLAY:-}" ] && command -v xmessage >/dev/null 2>&1; then
  if ! xmessage -center -buttons Install:0,Cancel:1 "$confirm_text"; then
    exit 1
  fi
else
  printf '%s\nType INSTALL to continue: ' "$confirm_text"
  read -r answer
  [ "$answer" = "INSTALL" ] || exit 1
fi

/usr/sbin/ooonana-install --target "$target" --source / --yes
if [ -n "${DISPLAY:-}" ] && command -v xmessage >/dev/null 2>&1; then
  xmessage -center "Ooonana install complete. Reboot now."
fi
EOF

  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-i3-smoke-session" <<'EOF'
#!/bin/sh
set -eu

if command -v feh >/dev/null 2>&1 && [ -f /usr/share/ooonana/wallpapers/ooonana-wallpaper.png ]; then
  xsetroot -solid "#ffb21a" 2>/dev/null || true
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
  xsetroot -solid "#ffb21a" 2>/dev/null || true
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
