#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/scratch-rootfs"
IMAGE="$WORK_DIR/ooonana-scratch.ext4"
BUSYBOX="${OOONANA_BUSYBOX:-}"
IMAGE_SIZE_MB=64
FORCE=0
NO_IMAGE=0

usage() {
  cat <<'USAGE'
Build Ooonana scratch rootfs.

Usage:
  scripts/build-scratch-rootfs.sh [options]

Options:
  --work-dir PATH     Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH       Scratch rootfs path (default: WORK_DIR/scratch-rootfs)
  --image PATH        Ext4 image path (default: WORK_DIR/ooonana-scratch.ext4)
  --busybox PATH      BusyBox binary path (static or dynamic)
  --image-size MB     Ext4 image size (default: 64)
  --no-image          Build rootfs tree only
  --force             Delete existing scratch rootfs/image first
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/scratch-rootfs"; IMAGE="$2/ooonana-scratch.ext4"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --busybox) BUSYBOX="$2"; shift 2 ;;
    --image-size) IMAGE_SIZE_MB="$2"; shift 2 ;;
    --no-image) NO_IMAGE=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

find_busybox() {
  if [[ -n "$BUSYBOX" ]]; then
    [[ -x "$BUSYBOX" ]] || ooonana_die "busybox not executable: $BUSYBOX"
    printf '%s\n' "$BUSYBOX"
    return 0
  fi

  if command -v busybox >/dev/null 2>&1; then
    command -v busybox
    return 0
  fi

  ooonana_die "missing busybox. Install busybox-static or pass --busybox PATH"
}

write_file() {
  local path="$1"
  local mode="$2"
  install -D -m "$mode" /dev/stdin "$path"
}

create_base_dirs() {
  mkdir -p \
    "$ROOTFS/bin" \
    "$ROOTFS/dev" \
    "$ROOTFS/etc/init.d" \
    "$ROOTFS/mnt/install" \
    "$ROOTFS/proc" \
    "$ROOTFS/root" \
    "$ROOTFS/run" \
    "$ROOTFS/sbin" \
    "$ROOTFS/sys" \
    "$ROOTFS/tmp" \
    "$ROOTFS/usr/bin" \
    "$ROOTFS/usr/lib" \
    "$ROOTFS/var/cache/ooonana" \
    "$ROOTFS/var/lib/ooonana/packages/installed"
  chmod 1777 "$ROOTFS/tmp"
}

create_busybox_links() {
  local applet
  for applet in awk basename cat chmod cp cut date dd df dirname dmesg echo env free grep hostname ls mkdir mount mv ps pwd readlink rm rmdir sed sh sha256sum sleep sort sync tar touch tr umount uname wc; do
    ln -sf busybox "$ROOTFS/bin/$applet"
  done
  for applet in mdev reboot; do
    ln -sf ../bin/busybox "$ROOTFS/sbin/$applet"
  done
  ln -sf ../../bin/busybox "$ROOTFS/usr/bin/env"
}

create_device_nodes() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    [[ -e "$ROOTFS/dev/console" ]] || mknod -m 600 "$ROOTFS/dev/console" c 5 1
    [[ -e "$ROOTFS/dev/null" ]] || mknod -m 666 "$ROOTFS/dev/null" c 1 3
    [[ -e "$ROOTFS/dev/tty" ]] || mknod -m 666 "$ROOTFS/dev/tty" c 5 0
  else
    : > "$ROOTFS/dev/console"
    : > "$ROOTFS/dev/null"
    : > "$ROOTFS/dev/tty"
  fi
}

install_ooonana_payload() {
  cp -a "$ROOT/packages/ooonana/." "$ROOTFS/"
  chmod 0755 "$ROOTFS/usr/bin/ooonana" "$ROOTFS/usr/sbin/ooonana-install"
}

copy_busybox_deps() {
  local busybox_path="$1"
  local lib
  if ! ldd "$busybox_path" >/dev/null 2>&1; then
    return 0
  fi
  ldd "$busybox_path" |
    awk '/=> \// {print $3} $1 ~ /^\// {print $1}' |
    while IFS= read -r lib; do
      [[ -n "$lib" && -f "$lib" ]] || continue
      mkdir -p "$ROOTFS$(dirname "$lib")"
      cp -L "$lib" "$ROOTFS$lib"
    done
}

write_init_files() {
  write_file "$ROOTFS/init" 0755 <<'EOF'
#!/bin/sh
exec /sbin/init
EOF

  write_file "$ROOTFS/sbin/init" 0755 <<'EOF'
#!/bin/sh
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
exec >/dev/console 2>&1 </dev/console
/etc/init.d/rcS
echo "Ooonana shell on console"
exec /bin/sh </dev/console >/dev/console 2>&1
EOF

  write_file "$ROOTFS/etc/inittab" 0644 <<'EOF'
::sysinit:/etc/init.d/rcS
ttyS0::respawn:/bin/sh
::ctrlaltdel:/sbin/reboot
::shutdown:/bin/umount -a -r
EOF

  write_file "$ROOTFS/etc/init.d/rcS" 0755 <<'EOF'
#!/bin/sh
mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mount -t tmpfs tmpfs /run 2>/dev/null || true
hostname ooonana 2>/dev/null || true

if [ -f /usr/share/ooonana/logo.txt ]; then
  cat /usr/share/ooonana/logo.txt
fi
echo "Ooonana scratch rootfs"
if grep -q 'ooonana.install=1' /proc/cmdline 2>/dev/null; then
  target="$(grep -o 'ooonana.install.target=[^ ]*' /proc/cmdline | cut -d= -f2 || true)"
  target="${target:-/dev/vda}"
  mkdir -p /mnt/install
  if [ ! -b "$target" ]; then
    echo "OOONANA_INSTALL_FAIL"
    sync
    sleep 1
    reboot -f
  fi
  if ! mount -t iso9660 /dev/sr0 /mnt/install 2>/dev/null; then
    echo "OOONANA_INSTALL_FAIL"
    sync
    sleep 1
    reboot -f
  fi
  install_image="/mnt/install/images/ooonana-scratch-disk.raw"
  if [ ! -f "$install_image" ]; then
    install_image="/mnt/install/images/ooonana-scratch.ext4"
  fi
  if [ ! -f "$install_image" ]; then
    echo "OOONANA_INSTALL_FAIL"
    sync
    sleep 1
    reboot -f
  fi
  dd if="$install_image" of="$target" bs=4M
  sync
  umount /mnt/install 2>/dev/null || true
  echo "OOONANA_INSTALL_OK"
  if grep -q 'ooonana.smoke=1' /proc/cmdline 2>/dev/null; then
    sync
    sleep 1
    reboot -f
  fi
fi

if grep -q 'ooonana.smoke=1' /proc/cmdline 2>/dev/null; then
  if /usr/bin/ooonana version | grep -q 'ooonana 0.3.0' &&
    /usr/bin/ooonana me | grep -q 'Ooonana OS' &&
    /usr/bin/ooonana list | grep -q 'gui'; then
    echo "OOONANA_CLI_OK"
  else
    echo "OOONANA_CLI_FAIL"
    sync
    sleep 1
    reboot -f
  fi
  echo "OOONANA_BOOT_OK"
  sync
  sleep 1
  reboot -f
fi
EOF

  write_file "$ROOTFS/etc/os-release" 0644 <<'EOF'
NAME="Ooonana OS"
ID=ooonana
PRETTY_NAME="Ooonana OS Scratch"
VERSION_ID="0.0.1-scratch"
EOF
  write_file "$ROOTFS/etc/passwd" 0644 <<'EOF'
root:x:0:0:root:/root:/bin/sh
EOF
  write_file "$ROOTFS/etc/group" 0644 <<'EOF'
root:x:0:
EOF
  write_file "$ROOTFS/etc/wsl.conf" 0644 <<'EOF'
[boot]
systemd=false

[automount]
mountFsTab=false

[user]
default=root

[interop]
appendWindowsPath=false
EOF
  if [[ -f "$ROOTFS/usr/share/ooonana/logo.txt" ]]; then
    cp "$ROOTFS/usr/share/ooonana/logo.txt" "$ROOTFS/etc/motd"
  fi
}

create_image() {
  [[ "$NO_IMAGE" -eq 0 ]] || return 0
  if [[ -e "$IMAGE" && "$FORCE" -ne 1 ]]; then
    ooonana_die "image exists: $IMAGE (use --force)"
  fi
  rm -f "$IMAGE"
  truncate -s "${IMAGE_SIZE_MB}M" "$IMAGE"
  mkfs.ext4 -F -L OOONANA_SCRATCH -d "$ROOTFS" "$IMAGE"
  chmod a+rw "$IMAGE"
}

main() {
  ooonana_require_linux
  ooonana_require_commands install cp chmod ln mkdir truncate mkfs.ext4

  local busybox_path
  busybox_path="$(find_busybox)"

  mkdir -p "$WORK_DIR"
  chmod a+rwx "$WORK_DIR" 2>/dev/null || true

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ROOTFS"
    rm -f "$IMAGE"
  elif [[ -e "$ROOTFS" ]]; then
    ooonana_die "scratch rootfs exists: $ROOTFS (use --force)"
  fi

  create_base_dirs
  install -m 0755 "$busybox_path" "$ROOTFS/bin/busybox"
  copy_busybox_deps "$busybox_path"
  create_busybox_links
  create_device_nodes
  install_ooonana_payload
  write_init_files
  create_image
  chmod -R a+rwX "$ROOTFS" 2>/dev/null || true

  ooonana_log "scratch rootfs ready: $ROOTFS"
  [[ "$NO_IMAGE" -eq 1 ]] || ooonana_log "scratch image ready: $IMAGE"
}

main "$@"
