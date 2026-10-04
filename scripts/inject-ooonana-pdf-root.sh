#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${1:-}"

usage() {
  cat <<'USAGE'
Inject minimal Ooonana OS files into a linuxpdf RISC-V rootfs tree.

Usage:
  scripts/inject-ooonana-pdf-root.sh ROOTFS_DIR
USAGE
}

if [[ "${TARGET_ROOT:-}" == "-h" || "${TARGET_ROOT:-}" == "--help" ]]; then
  usage
  exit 0
fi

[[ -n "$TARGET_ROOT" ]] || { usage >&2; exit 1; }
[[ -d "$TARGET_ROOT" ]] || { printf 'missing rootfs: %s\n' "$TARGET_ROOT" >&2; exit 1; }
if [[ ! -w "$TARGET_ROOT" ]]; then
  command -v sudo >/dev/null 2>&1 || {
    printf 'rootfs is not writable and sudo is missing: %s\n' "$TARGET_ROOT" >&2
    exit 1
  }
  exec sudo bash "$0" "$TARGET_ROOT"
fi

install -d \
  "$TARGET_ROOT/etc" \
  "$TARGET_ROOT/etc/ooonana/sources.d" \
  "$TARGET_ROOT/root" \
  "$TARGET_ROOT/sbin" \
  "$TARGET_ROOT/usr/bin" \
  "$TARGET_ROOT/usr/lib/ooonana/repo" \
  "$TARGET_ROOT/usr/share/ooonana/pdf-help" \
  "$TARGET_ROOT/etc/ooonana/trusted-keys" \
  "$TARGET_ROOT/usr/share/ooonana" \
  "$TARGET_ROOT/var/cache/ooonana" \
  "$TARGET_ROOT/var/lib/ooonana/packages/installed"

BUILD_REF="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || printf working-tree)"

# PDF has no GTK, wallpaper, icon, WSL, installer or Python/AI runtime.
# Copy only portable CLI, comparator, repo/trust inputs and terminal helper.
install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana" "$TARGET_ROOT/usr/bin/ooonana-pkg"
CORE_VERSION="$("$ROOT/packages/ooonana/usr/bin/ooonana" version | awk '{print $2}')"
sed "s/@CORE_VERSION@/$CORE_VERSION/" "$ROOT/scripts/pdf-shell-cli.sh" > "$TARGET_ROOT/usr/bin/ooonana"
chmod 0755 "$TARGET_ROOT/usr/bin/ooonana"
cp -a --remove-destination "$ROOT/packages/ooonana/usr/bin/clear" "$TARGET_ROOT/usr/bin/clear"
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/version-order.awk" "$TARGET_ROOT/usr/lib/ooonana/version-order.awk"
cp -a "$ROOT/packages/ooonana/usr/lib/ooonana/repo/." "$TARGET_ROOT/usr/lib/ooonana/repo/"
cp -a "$ROOT/packages/ooonana/etc/ooonana/trusted-keys/." "$TARGET_ROOT/etc/ooonana/trusted-keys/"
if [[ -d "$ROOT/packages/ooonana/etc/ooonana/sources.d" ]]; then
  cp -a "$ROOT/packages/ooonana/etc/ooonana/sources.d/." "$TARGET_ROOT/etc/ooonana/sources.d/"
fi
# Extract genuine CLI topic help once at build time, not on each PDF request.
for topic in packages get upgrade remove repo ai; do
  help_function="usage_$topic"; [[ "$topic" != repo && "$topic" != ai ]] || help_function="${help_function}_help"
  awk -v help_function="$help_function" '
    $0 == help_function "() {" { found=1; next }
    found && /^  cat <<./ { body=1; next }
    body && /^USAGE$/ { exit }
    body { print }
  ' "$ROOT/packages/ooonana/usr/bin/ooonana" > "$TARGET_ROOT/usr/share/ooonana/pdf-help/$topic"
done
install -m 0644 "$ROOT/docs/logo.txt" "$TARGET_ROOT/usr/share/ooonana/logo.txt"
cp "$TARGET_ROOT/usr/share/ooonana/logo.txt" "$TARGET_ROOT/etc/motd"
cp "$TARGET_ROOT/usr/share/ooonana/logo.txt" "$TARGET_ROOT/etc/issue"

# Seed named files into RAM: avoid runtime 9p directory enumeration and
# repeated full CLI reads. Preserve identical checksum/signature inputs.
printf '%s\n' usr/bin/ooonana-pkg usr/lib/ooonana/version-order.awk > "$TARGET_ROOT/etc/ooonana/pdf-runtime-seeds"
for directory in usr/lib/ooonana/repo etc/ooonana/trusted-keys usr/share/ooonana/pdf-help; do
  find "$TARGET_ROOT/$directory" -type f -printf '%P\n' | sort | while IFS= read -r relative; do
    printf '%s/%s\n' "$directory" "$relative"
  done >> "$TARGET_ROOT/etc/ooonana/pdf-runtime-seeds"
done

# List source files at build time: modern 9p directory enumeration can stall
# in TinyEMU. Boot copies named files individually, preserving custom sources.
: > "$TARGET_ROOT/etc/ooonana/pdf-source-seeds"
for source_file in "$TARGET_ROOT/etc/ooonana/sources.d"/*.repo; do
  [[ -f "$source_file" ]] || continue
  source_name="$(basename "$source_file")"
  [[ "$source_name" =~ ^[A-Za-z0-9_.-]+\.repo$ ]] || {
    printf 'Unsupported PDF source filename: %s\n' "$source_name" >&2; exit 1;
  }
  printf '%s\n' "$source_name" >> "$TARGET_ROOT/etc/ooonana/pdf-source-seeds"
done

if [[ -f "$TARGET_ROOT/usr/lib/ooonana/repo/base.pkg" ]]; then
  cp "$TARGET_ROOT/usr/lib/ooonana/repo/base.pkg" "$TARGET_ROOT/var/lib/ooonana/packages/installed/base.pkg"
fi

cat > "$TARGET_ROOT/etc/os-release" <<'EOF'
NAME="Ooonana OS"
ID=ooonana
PRETTY_NAME="Ooonana OS PDF Minimal"
VERSION_ID="0.6-pdf"
EOF

cat > "$TARGET_ROOT/etc/ooonana/pdf-release" <<EOF
OOONANA_PDF_EDITION="minimal-riscv"
OOONANA_PDF_VERSION="0.6"
OOONANA_PDF_BUILD_REF="$BUILD_REF"
OOONANA_PDF_PACKAGE_MANAGER="0.9.8"
EOF

cat > "$TARGET_ROOT/etc/hostname" <<'EOF'
ooonana-pdf
EOF

cat > "$TARGET_ROOT/root/.profile" <<'EOF'
if [ -f /usr/share/ooonana/logo.txt ]; then
  cat /usr/share/ooonana/logo.txt
fi
echo "Ooonana OS PDF Minimal"
echo
echo "Commands:"
echo "  ooonana me"
echo "  ooonana version"
echo "  ooonana help packages"
echo "  ooonana list"
echo "  ooonana ai status"
echo
EOF

# BusyBox installs init as a link to its executable. Break that link first.
if [[ -L "$TARGET_ROOT/sbin/init" ]]; then rm -f "$TARGET_ROOT/sbin/init"; fi
cat > "$TARGET_ROOT/sbin/init" <<'EOF'
#!/bin/sh

export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin
export HOME=/root
export TERM=linux
export PS1='ooonana# '

mkdir -p /dev /proc /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mount -a 2>/dev/null || true
mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mkdir -p /tmp /run /dev/shm
mount -t tmpfs -o size=16m,mode=1777 tmpfs /tmp 2>/dev/null || true
mount -t tmpfs -o size=4m,mode=0755 tmpfs /run 2>/dev/null || true
mount -t tmpfs -o size=8m,mode=1777 tmpfs /dev/shm 2>/dev/null || true
# Package scratch/state/source enumeration stays on real RAM-backed tmpfs.
# Repository metadata and checksum/signature verification remain unchanged.
export OOONANA_SOURCES_DIR=/run/ooonana/sources.d
export OOONANA_CACHE_DIR=/run/ooonana/cache
export OOONANA_STATE_DIR=/run/ooonana/state
export OOONANA_REPO_DIR=/run/ooonana/usr/lib/ooonana/repo
mkdir -p "$OOONANA_SOURCES_DIR" "$OOONANA_CACHE_DIR" "$OOONANA_STATE_DIR/installed"
while IFS= read -r relative; do
  directory="${relative%/*}"
  mkdir -p "/run/ooonana/$directory"
  cp "/$relative" "/run/ooonana/$relative" || exit 1
done < /etc/ooonana/pdf-runtime-seeds
mkdir -p /run/ooonana/help
for topic in packages get upgrade remove repo ai; do
  cp "/run/ooonana/usr/share/ooonana/pdf-help/$topic" "/run/ooonana/help/$topic" || exit 1
done
while IFS= read -r source_name; do
  [ -n "$source_name" ] || continue
  cp "/etc/ooonana/sources.d/$source_name" "$OOONANA_SOURCES_DIR/$source_name" || exit 1
done < /etc/ooonana/pdf-source-seeds
if [ -f /var/lib/ooonana/packages/installed/base.pkg ]; then
  cp /var/lib/ooonana/packages/installed/base.pkg "$OOONANA_STATE_DIR/installed/base.pkg"
fi
if [ -c /dev/hvc1 ]; then
  # Native kernel exposes legacy SBI console first; keyboard FIFO is virtio.
  exec </dev/hvc1 >/dev/hvc1 2>&1
elif [ -c /dev/hvc0 ]; then
  exec </dev/hvc0 >/dev/hvc0 2>&1
fi
hostname ooonana-pdf 2>/dev/null || true
ifconfig lo 127.0.0.1 2>/dev/null || true

cd "$HOME" || cd /
stty cols 80 rows 30 2>/dev/null || true

while /bin/true; do
  printf '\n--- Ooonana userspace ready ---\n'
  if [ -f /usr/share/ooonana/logo.txt ]; then
    cat /usr/share/ooonana/logo.txt
  else
    echo "Ooonana OS"
  fi
  echo "PDF Minimal 0.6 | pkg 0.9.8"
  echo "OOONANA_PDF_BOOT_OK"
  echo "Run: ooonana help"
  if command -v cttyhack >/dev/null 2>&1; then
    setsid cttyhack sh
  else
    setsid sh
  fi
done
EOF
chmod 0755 "$TARGET_ROOT/sbin/init" "$TARGET_ROOT/root/.profile"

printf 'injected Ooonana PDF rootfs: %s\n' "$TARGET_ROOT"
