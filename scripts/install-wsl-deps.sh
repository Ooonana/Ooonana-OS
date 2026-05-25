#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

usage() {
  cat <<'USAGE'
Install WSL dependencies for Ooonana OS.

Usage:
  scripts/install-wsl-deps.sh

Installs:
  debootstrap qemu-system-x86 xorriso isolinux syslinux-common grub-pc-bin grub-common rsync e2fsprogs busybox-static cpio gzip python3 build-essential bc bison curl flex libelf-dev libssl-dev make perl tar
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

ooonana_require_linux
ooonana_reexec_as_root "$@"
ooonana_require_command apt-get

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  bc \
  bison \
  build-essential \
  busybox-static \
  cpio \
  curl \
  debootstrap \
  e2fsprogs \
  flex \
  gzip \
  grub-common \
  grub-pc-bin \
  isolinux \
  libelf-dev \
  libssl-dev \
  make \
  perl \
  python3 \
  qemu-system-x86 \
  qemu-utils \
  rsync \
  sudo \
  syslinux-common \
  tar \
  xorriso \
  xz-utils

ooonana_log "WSL dependencies installed"
