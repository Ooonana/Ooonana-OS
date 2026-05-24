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
  debootstrap qemu-system-x86 xorriso isolinux syslinux-common rsync e2fsprogs busybox-static
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
  busybox-static \
  debootstrap \
  e2fsprogs \
  isolinux \
  qemu-system-x86 \
  qemu-utils \
  rsync \
  sudo \
  syslinux-common \
  xorriso \
  xz-utils

ooonana_log "WSL dependencies installed"
