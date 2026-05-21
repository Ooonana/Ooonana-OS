#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

SUITE="bookworm"
ARCH="amd64"
MIRROR="http://deb.debian.org/debian"
WORK_DIR="$(ooonana_default_build_dir)"
ROOTFS="$WORK_DIR/rootfs"
IMAGE="$WORK_DIR/ooonana-rootfs.ext4"
PACKAGE_PROFILE="$ROOT/configs/packages/core.list"
FORCE=0

usage() {
  cat <<'USAGE'
Build Ooonana rootfs.

Usage:
  scripts/build-rootfs.sh [options]

Options:
  --suite NAME        Debian suite (default: bookworm)
  --arch NAME         Debian architecture (default: amd64)
  --mirror URL        Debian mirror
  --work-dir PATH     Build directory (default: /var/tmp/ooonana-os/build)
  --rootfs PATH       Rootfs directory (default: WORK_DIR/rootfs)
  --image PATH        Ext4 image path (default: WORK_DIR/ooonana-rootfs.ext4)
  --packages PATH     Package profile (default: configs/packages/core.list)
  --force             Delete existing rootfs and image first
  -h, --help          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite) SUITE="$2"; shift 2 ;;
    --arch) ARCH="$2"; shift 2 ;;
    --mirror) MIRROR="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; ROOTFS="$2/rootfs"; IMAGE="$2/ooonana-rootfs.ext4"; shift 2 ;;
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --packages) PACKAGE_PROFILE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

write_file() {
  local path="$1"
  local mode="$2"
  local dir
  dir="$(dirname "$path")"
  mkdir -p "$dir"
  cat > "$path"
  chmod "$mode" "$path"
}

configure_rootfs() {
  local packages=("$@")

  printf 'ooonana\n' > "$ROOTFS/etc/hostname"
  cat > "$ROOTFS/etc/hosts" <<'EOF'
127.0.0.1 localhost
127.0.1.1 ooonana
EOF

  cat > "$ROOTFS/etc/fstab" <<'EOF'
/dev/vda / ext4 defaults 0 1
proc /proc proc defaults 0 0
EOF

  mkdir -p "$ROOTFS/etc/apt/apt.conf.d"
  cat > "$ROOTFS/etc/apt/apt.conf.d/99ooonana" <<'EOF'
APT::Install-Recommends "false";
APT::Install-Suggests "false";
EOF

  chroot "$ROOTFS" apt-get update
  chroot "$ROOTFS" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"
  chroot "$ROOTFS" apt-get clean

  install -Dm755 "$ROOT/packages/ooonana/usr/bin/ooonana" "$ROOTFS/usr/bin/ooonana"

  mkdir -p "$ROOTFS/etc/systemd/system/getty.target.wants"
  ln -sf /lib/systemd/system/serial-getty@.service "$ROOTFS/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service"

  write_file "$ROOTFS/etc/systemd/system/ooonana-smoke.service" 0644 <<'EOF'
[Unit]
Description=Ooonana QEMU smoke boot marker
DefaultDependencies=no
After=local-fs.target sysinit.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo OOONANA_BOOT_OK >/dev/console; sleep 1; systemctl poweroff --force --force'
StandardOutput=journal+console
StandardError=journal+console
EOF

  write_file "$ROOTFS/etc/motd" 0644 <<'EOF'
Ooonana OS early rootfs

Run: ooonana doctor
EOF
}

make_ext4_image() {
  local used_mb image_mb
  used_mb="$(du -sm "$ROOTFS" | awk '{ print $1 }')"
  image_mb=$((used_mb * 2 + 1024))
  mkdir -p "$(dirname "$IMAGE")"
  rm -f "$IMAGE"
  truncate -s "${image_mb}M" "$IMAGE"
  mkfs.ext4 -F -d "$ROOTFS" -L OOONANA_ROOT "$IMAGE"
}

main() {
  ooonana_require_linux
  ooonana_reexec_as_root "$@"
  ooonana_require_commands debootstrap chroot mount umount mkfs.ext4 truncate du awk sed

  mapfile -t packages < <(ooonana_read_package_profile "$PACKAGE_PROFILE")
  [[ "${#packages[@]}" -gt 0 ]] || ooonana_die "empty package profile: $PACKAGE_PROFILE"

  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$ROOTFS" "$IMAGE"
  fi

  mkdir -p "$WORK_DIR"

  if [[ ! -x "$ROOTFS/bin/sh" ]]; then
    ooonana_log "debootstrap $SUITE $ROOTFS"
    debootstrap --variant=minbase --arch "$ARCH" "$SUITE" "$ROOTFS" "$MIRROR"
  else
    ooonana_log "reuse rootfs: $ROOTFS"
  fi

  configure_rootfs "${packages[@]}"
  make_ext4_image
  chmod a+rx "$(dirname "$WORK_DIR")" "$ROOTFS" "$ROOTFS/boot"
  chmod a+rwx "$WORK_DIR"
  chmod a+rw "$IMAGE"
  chmod a+r "$ROOTFS"/boot/vmlinuz-* "$ROOTFS"/boot/initrd.img-*

  ooonana_log "rootfs ready: $ROOTFS"
  ooonana_log "image ready: $IMAGE"
}

main "$@"
