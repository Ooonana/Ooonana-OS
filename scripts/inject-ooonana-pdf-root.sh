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

install -d \
  "$TARGET_ROOT/etc" \
  "$TARGET_ROOT/etc/ooonana/sources.d" \
  "$TARGET_ROOT/root" \
  "$TARGET_ROOT/sbin" \
  "$TARGET_ROOT/usr/bin" \
  "$TARGET_ROOT/usr/share/ooonana" \
  "$TARGET_ROOT/var/cache/ooonana" \
  "$TARGET_ROOT/var/lib/ooonana/packages/installed"

cp -a "$ROOT/packages/ooonana/." "$TARGET_ROOT/"
chmod 0755 "$TARGET_ROOT/usr/bin/ooonana" "$TARGET_ROOT/usr/bin/ooonana-ai" "$TARGET_ROOT/usr/sbin/ooonana-install" 2>/dev/null || true
install -m 0644 "$ROOT/docs/logo.txt" "$TARGET_ROOT/usr/share/ooonana/logo.txt"
cp "$TARGET_ROOT/usr/share/ooonana/logo.txt" "$TARGET_ROOT/etc/motd"
cp "$TARGET_ROOT/usr/share/ooonana/logo.txt" "$TARGET_ROOT/etc/issue"

if [[ -f "$TARGET_ROOT/usr/lib/ooonana/repo/base.pkg" ]]; then
  cp "$TARGET_ROOT/usr/lib/ooonana/repo/base.pkg" "$TARGET_ROOT/var/lib/ooonana/packages/installed/base.pkg"
fi

cat > "$TARGET_ROOT/etc/os-release" <<'EOF'
NAME="Ooonana OS"
ID=ooonana
PRETTY_NAME="Ooonana OS PDF Minimal"
VERSION_ID="0.1-pdf"
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
echo
EOF

cat > "$TARGET_ROOT/sbin/init" <<'EOF'
#!/bin/sh

export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin
export HOME=/root
export TERM=linux

mount -a 2>/dev/null || true
mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
hostname ooonana-pdf 2>/dev/null || true
ifconfig lo 127.0.0.1 2>/dev/null || true

cd "$HOME" || cd /

while /bin/true; do
  clear 2>/dev/null || true
  if [ -f /usr/share/ooonana/logo.txt ]; then
    cat /usr/share/ooonana/logo.txt
  else
    echo "Ooonana OS"
  fi
  echo
  echo "Ooonana OS PDF Minimal"
  echo "RISC-V TinyEMU PDF live system"
  echo
  /usr/bin/ooonana version 2>/dev/null || true
  /usr/bin/ooonana me >/dev/null 2>&1 || true
  echo
  echo "Try: ooonana help"
  echo "Type exit to redraw this screen."
  echo
  setsid sh
done
EOF
chmod 0755 "$TARGET_ROOT/sbin/init" "$TARGET_ROOT/root/.profile"

printf 'injected Ooonana PDF rootfs: %s\n' "$TARGET_ROOT"
