#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="${OOONANA_RELEASE_DIR:-/mnt/f/Ooonana/ooonana-os/release-current}"
ISO="${OOONANA_ISO:-$RELEASE_DIR/ooonana-full-i3.iso}"
WORK="${OOONANA_PATCH_WORK:-$RELEASE_DIR/patch-full-i3-ui}"
OUT_ISO="${OOONANA_OUT_ISO:-$RELEASE_DIR/ooonana-full-i3.iso.new}"
VOLUME="${OOONANA_VOLUME:-OOONANAUSB}"
EXTRA_ROOT="${OOONANA_EXTRA_ROOT:-}"
KERNEL_OVERRIDE="${OOONANA_KERNEL_OVERRIDE:-}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing command: %s\n' "$1" >&2
    exit 1
  }
}

extract_block() {
  local marker="$1"
  local out="$2"
  awk -v marker="$marker" '
    index($0, marker) { on = 1; next }
    on && $0 == "EOF" { exit }
    on { print }
  ' "$ROOT/scripts/build-full-i3-rootfs.sh" > "$out"
  test -s "$out" || {
    printf 'empty payload for marker: %s\n' "$marker" >&2
    exit 1
  }
}

write_debugfs_file() {
  local image="$1"
  local src="$2"
  local dst="$3"
  local mode="$4"
  local parent="${dst%/*}"
  local path="" part
  local -a parts

  IFS='/' read -r -a parts <<< "${parent#/}"
  for part in "${parts[@]}"; do
    [ -n "$part" ] || continue
    path="$path/$part"
    debugfs -w -R "mkdir \"$path\"" "$image" >/dev/null 2>&1 || true
  done
  debugfs -w -R "rm \"$dst\"" "$image" >/dev/null 2>&1 || true
  debugfs -w -R "write \"$src\" \"$dst\"" "$image" >/dev/null
  debugfs -w -R "sif \"$dst\" mode $mode" "$image" >/dev/null
}

write_debugfs_symlink() {
  local image="$1"
  local target="$2"
  local dst="$3"
  local parent="${dst%/*}"
  local path="" part
  local -a parts

  IFS='/' read -r -a parts <<< "${parent#/}"
  for part in "${parts[@]}"; do
    [ -n "$part" ] || continue
    path="$path/$part"
    debugfs -w -R "mkdir \"$path\"" "$image" >/dev/null 2>&1 || true
  done
  debugfs -w -R "rm \"$dst\"" "$image" >/dev/null 2>&1 || true
  debugfs -w -R "symlink \"$dst\" \"$target\"" "$image" >/dev/null
  debugfs -w -R "sif \"$dst\" uid 0" "$image" >/dev/null 2>&1 || true
  debugfs -w -R "sif \"$dst\" gid 0" "$image" >/dev/null 2>&1 || true
}

patch_overlay_root() {
  local image="$1"
  local overlay="$2"
  local rel src dst mode target

  [ -n "$overlay" ] || return 0
  [ -d "$overlay" ] || {
    printf 'missing overlay root: %s\n' "$overlay" >&2
    exit 1
  }

  while IFS= read -r rel; do
    [ "$rel" = "." ] && continue
    dst="/${rel#./}"
    debugfs -w -R "mkdir \"$dst\"" "$image" >/dev/null 2>&1 || true
  done < <(cd "$overlay" && find . -type d | sort)

  while IFS= read -r -d '' rel; do
    src="$overlay/${rel#./}"
    dst="/${rel#./}"
    if [ -L "$src" ]; then
      target="$(readlink "$src")"
      write_debugfs_symlink "$image" "$target" "$dst"
    elif [ -f "$src" ]; then
      mode="$(stat -c '%a' "$src")"
      write_debugfs_file "$image" "$src" "$dst" "0100$mode"
    fi
  done < <(cd "$overlay" && find . \( -type f -o -type l \) -print0)
}

patch_identity_files() {
  local image="$1"
  local identity="$WORK/identity"
  mkdir -p "$identity"

  debugfs -R "cat /etc/group" "$image" > "$identity/group" 2>/dev/null ||
    printf '%s\n' 'root:x:0:' > "$identity/group"
  grep -q '^messagebus:' "$identity/group" 2>/dev/null ||
    printf '%s\n' 'messagebus:x:81:' >> "$identity/group"
  write_debugfs_file "$image" "$identity/group" /etc/group 0100644

  debugfs -R "cat /etc/passwd" "$image" > "$identity/passwd" 2>/dev/null ||
    printf '%s\n' 'root:x:0:0:root:/root:/bin/sh' > "$identity/passwd"
  grep -q '^messagebus:' "$identity/passwd" 2>/dev/null ||
    printf '%s\n' 'messagebus:x:81:81:DBus Message Bus:/run/dbus:/bin/false' >> "$identity/passwd"
  write_debugfs_file "$image" "$identity/passwd" /etc/passwd 0100644

  printf '%s\n' '11111111111111111111111111111111' > "$identity/machine-id"
  write_debugfs_file "$image" "$identity/machine-id" /etc/machine-id 0100644
  write_debugfs_file "$image" "$identity/machine-id" /var/lib/dbus/machine-id 0100644
}

patch_ext4() {
  local image="$1"
  local payload="$2"

  while IFS='|' read -r src dst mode; do
    [ -n "$src" ] || continue
    write_debugfs_file "$image" "$payload/$src" "$dst" "$mode"
  done <<EOF
ooonana-rofi-wifi|/usr/bin/ooonana-rofi-wifi|0100755
ooonana-rofi-bluetooth|/usr/bin/ooonana-rofi-bluetooth|0100755
ooonana-rofi-brightness|/usr/bin/ooonana-rofi-brightness|0100755
ooonana-wifi-panel|/usr/bin/ooonana-wifi-panel|0100755
ooonana-bluetooth-panel|/usr/bin/ooonana-bluetooth-panel|0100755
ooonana-brightness-panel|/usr/bin/ooonana-brightness-panel|0100755
ooonana-audio-panel|/usr/bin/ooonana-audio-panel|0100755
ooonana-rofi-power|/usr/bin/ooonana-rofi-power|0100755
ooonana-brightness|/usr/bin/ooonana-brightness|0100755
ooonana-brightness-status|/usr/bin/ooonana-brightness-status|0100755
ooonana|/usr/bin/ooonana|0100755
ooonana-settings|/usr/bin/ooonana-settings|0100755
ooonana-settings-launch|/usr/bin/ooonana-settings-launch|0100755
ooonana-theme-env|/usr/bin/ooonana-theme-env|0100755
ooonana-setup|/usr/bin/ooonana-setup|0100755
wget|/usr/bin/wget|0100755
ooonana-gui-installer|/usr/bin/ooonana-gui-installer|0100755
ooonana-i3-smoke-session|/usr/bin/ooonana-i3-smoke-session|0100755
ooonana-i3-session|/usr/bin/ooonana-i3-session|0100755
ooonana-i3-installer-session|/usr/bin/ooonana-i3-installer-session|0100755
i3.config|/etc/i3/config|0100644
i3.config.keycodes|/etc/i3/config.keycodes|0100644
nm-applet.desktop|/etc/xdg/autostart/nm-applet.desktop|0100644
blueman.desktop|/etc/xdg/autostart/blueman.desktop|0100644
polybar.ini|/etc/ooonana/polybar.ini|0100644
rofi.rasi|/etc/ooonana/rofi.rasi|0100644
dunstrc|/etc/ooonana/dunstrc|0100644
ooonana-ai-app|/usr/bin/ooonana-ai-app|0100755
ooonana-ai-launch|/usr/bin/ooonana-ai-launch|0100755
cloud.repo|/etc/ooonana/sources.d/cloud.repo|0100644
rcS|/etc/init.d/rcS|0100755
45-font-awesome.conf|/etc/fonts/conf.avail/45-font-awesome.conf|0100644
65-font-awesome.conf|/etc/fonts/conf.avail/65-font-awesome.conf|0100644
45-font-awesome.conf|/etc/fonts/conf.d/45-font-awesome.conf|0100644
65-font-awesome.conf|/etc/fonts/conf.d/65-font-awesome.conf|0100644
Font Awesome 6 Free-Regular-400.otf|/usr/share/fonts/font-awesome/Font Awesome 6 Free-Regular-400.otf|0100644
Font Awesome 6 Free-Solid-900.otf|/usr/share/fonts/font-awesome/Font Awesome 6 Free-Solid-900.otf|0100644
Font Awesome 6 Brands-Regular-400.otf|/usr/share/fonts/font-awesome/Font Awesome 6 Brands-Regular-400.otf|0100644
EOF

  patch_overlay_root "$image" "$payload/root"
  patch_overlay_root "$image" "$EXTRA_ROOT"
  patch_identity_files "$image"
}

build_payload() {
  local payload="$1"
  rm -rf "$payload"
  mkdir -p "$payload/root"

  if [ -n "$KERNEL_OVERRIDE" ]; then
    test -f "$KERNEL_OVERRIDE" || { printf 'missing kernel override: %s\n' "$KERNEL_OVERRIDE" >&2; exit 1; }
    install -D -m 0644 "$KERNEL_OVERRIDE" "$payload/root/boot/vmlinuz"
  fi

  extract_block '$ROOTFS/usr/bin/ooonana-rofi-wifi' "$payload/ooonana-rofi-wifi"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-bluetooth' "$payload/ooonana-rofi-bluetooth"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-brightness' "$payload/ooonana-rofi-brightness"
  extract_block '$ROOTFS/usr/bin/ooonana-wifi-panel' "$payload/ooonana-wifi-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-bluetooth-panel' "$payload/ooonana-bluetooth-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness-panel' "$payload/ooonana-brightness-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-audio-panel' "$payload/ooonana-audio-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-power' "$payload/ooonana-rofi-power"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness"' "$payload/ooonana-brightness"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness-status' "$payload/ooonana-brightness-status"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana" "$payload/ooonana"
  extract_block '$ROOTFS/usr/bin/ooonana-settings"' "$payload/ooonana-settings"
  extract_block '$ROOTFS/usr/bin/ooonana-settings-launch' "$payload/ooonana-settings-launch"
  extract_block '$ROOTFS/usr/bin/ooonana-theme-env' "$payload/ooonana-theme-env"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-setup" "$payload/ooonana-setup"
  cat > "$payload/wget" <<'EOF'
#!/bin/sh
exec /bin/busybox wget "$@"
EOF
  chmod 0755 "$payload/wget"
  extract_block '$ROOTFS/usr/bin/ooonana-gui-installer' "$payload/ooonana-gui-installer"
  extract_block '$ROOTFS/usr/bin/ooonana-i3-smoke-session' "$payload/ooonana-i3-smoke-session"
  extract_block '$ROOTFS/usr/bin/ooonana-i3-session' "$payload/ooonana-i3-session"
  extract_block '$ROOTFS/usr/bin/ooonana-i3-installer-session' "$payload/ooonana-i3-installer-session"
  install -m 0644 "$ROOT/branding/i3/config" "$payload/i3.config"
  install -m 0644 "$ROOT/branding/i3/config" "$payload/i3.config.keycodes"
  cat > "$payload/nm-applet.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=NetworkManager Applet
Hidden=true
EOF
  cat > "$payload/blueman.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Blueman Applet
Hidden=true
EOF
  extract_block '$ROOTFS/etc/ooonana/polybar.ini' "$payload/polybar.ini"
  extract_block '$ROOTFS/etc/ooonana/rofi.rasi' "$payload/rofi.rasi"
  extract_block '$ROOTFS/etc/ooonana/dunstrc' "$payload/dunstrc"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-ai-app" "$payload/ooonana-ai-app"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-ai-launch" "$payload/ooonana-ai-launch"
  extract_block '$ROOTFS/etc/init.d/rcS' "$payload/rcS"
  cat > "$payload/cloud.repo" <<'EOF'
OOONANA_REPO_NAME="gitlab"
OOONANA_REPO_URI="https://ooonana.gitlab.io/ooonana-repo"
EOF

  local apk="$WORK/font-awesome-free.apk"
  wget -q -O "$apk" "https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64/font-awesome-free-6.4.2-r1.apk"
  tar -xzf "$apk" -C "$payload" \
    etc/fonts/conf.avail/45-font-awesome.conf \
    etc/fonts/conf.avail/65-font-awesome.conf \
    etc/fonts/conf.d/45-font-awesome.conf \
    etc/fonts/conf.d/65-font-awesome.conf \
    'usr/share/fonts/font-awesome/Font Awesome 6 Free-Regular-400.otf' \
    'usr/share/fonts/font-awesome/Font Awesome 6 Free-Solid-900.otf'
  mv "$payload/etc/fonts/conf.avail/45-font-awesome.conf" "$payload/45-font-awesome.conf"
  mv "$payload/etc/fonts/conf.avail/65-font-awesome.conf" "$payload/65-font-awesome.conf"
  mv "$payload/usr/share/fonts/font-awesome/Font Awesome 6 Free-Regular-400.otf" "$payload/Font Awesome 6 Free-Regular-400.otf"
  mv "$payload/usr/share/fonts/font-awesome/Font Awesome 6 Free-Solid-900.otf" "$payload/Font Awesome 6 Free-Solid-900.otf"

  local brands_apk="$WORK/font-awesome-brands.apk"
  wget -q -O "$brands_apk" "https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64/font-awesome-brands-6.4.2-r1.apk"
  tar -xzf "$brands_apk" -C "$payload" \
    'usr/share/fonts/font-awesome/Font Awesome 6 Brands-Regular-400.otf'
  mv "$payload/usr/share/fonts/font-awesome/Font Awesome 6 Brands-Regular-400.otf" "$payload/Font Awesome 6 Brands-Regular-400.otf"
  rm -rf "$payload/etc" "$payload/usr"
}

stage_kernel_override() {
  [ -n "$KERNEL_OVERRIDE" ] || return 0
  test -f "$KERNEL_OVERRIDE" || { printf 'missing kernel override: %s\n' "$KERNEL_OVERRIDE" >&2; exit 1; }
  install -m 0644 "$KERNEL_OVERRIDE" "$WORK/vmlinuz"
}

patch_disk_image() {
  local raw="$1"
  local payload="$2"
  local info start_bytes end_bytes size_bytes part_image

  info="$(parted -sm "$raw" unit B print | awk -F: '$1 == "1" { print $2 " " $3 }')"
  read -r start_bytes end_bytes <<EOF
$info
EOF
  start_bytes="${start_bytes%B}"
  end_bytes="${end_bytes%B}"
  size_bytes=$((end_bytes - start_bytes + 1))

  part_image="$WORK/disk-rootfs-partition.ext4"
  dd if="$raw" of="$part_image" bs=16M iflag=skip_bytes,count_bytes \
    skip="$start_bytes" count="$size_bytes" status=none
  patch_ext4 "$part_image" "$payload"
  dd if="$part_image" of="$raw" bs=16M oflag=seek_bytes conv=notrunc \
    seek="$start_bytes" status=none
  rm -f "$part_image"
}

extract_iso_file_by_lba() {
  local iso_path="$1"
  local out="$2"
  local dir="${iso_path%/*}"
  local name="${iso_path##*/}"
  local start blocks

  read -r start blocks < <(
    xorriso -indev "$ISO" -find "$dir" -name "$name" -exec report_lba -- 2>/dev/null |
      awk '/File data lba:/ { print $6, $8; exit }'
  )
  [ -n "${start:-}" ] && [ -n "${blocks:-}" ] || {
    printf 'could not find ISO LBA for %s\n' "$iso_path" >&2
    exit 1
  }
  dd if="$ISO" of="$out" bs=16M iflag=skip_bytes,count_bytes \
    skip="$((start * 2048))" count="$((blocks * 2048))" status=none
}

build_iso_from_work() {
  rm -f "$OUT_ISO"
  bash "$ROOT/scripts/build-full-i3-iso.sh" \
    --kernel "$WORK/vmlinuz" \
    --initramfs "$WORK/install-initramfs.cpio.gz" \
    --live-initramfs "$WORK/live-initramfs.cpio.gz" \
    --live-rootfs-image "$WORK/live-rootfs.ext4" \
    --disk-image "$WORK/disk.raw" \
    --iso-tree "$WORK/iso-tree" \
    --iso "$OUT_ISO" \
    --volume "$VOLUME" \
    --uefi \
    --force
  sha256sum "$OUT_ISO" > "$OUT_ISO.sha256"
  printf 'patched ISO: %s\n' "$OUT_ISO"
}

resume_after_extract() {
  build_payload "$WORK/payload"
  test -f "$WORK/live-rootfs.ext4" || { printf 'missing live-rootfs.ext4 in %s\n' "$WORK" >&2; exit 1; }
  test -f "$WORK/disk.raw" || { printf 'missing disk.raw in %s\n' "$WORK" >&2; exit 1; }
  stage_kernel_override
  patch_ext4 "$WORK/live-rootfs.ext4" "$WORK/payload"
  patch_disk_image "$WORK/disk.raw" "$WORK/payload"
  build_iso_from_work
}

main() {
  need xorriso
  need debugfs
  need grub-mkrescue
  need parted
  need wget
  need tar
  need gzip
  need dd

  test -f "$ISO" || {
    printf 'missing ISO: %s\n' "$ISO" >&2
    exit 1
  }

  if [ "${1:-}" = "--resume-after-extract" ]; then
    resume_after_extract
    exit 0
  fi

  rm -rf "$WORK"
  mkdir -p "$WORK/payload"

  build_payload "$WORK/payload"

  xorriso -osirrox on -indev "$ISO" \
    -extract /boot/vmlinuz "$WORK/vmlinuz" \
    -extract /boot/install-initramfs.cpio.gz "$WORK/install-initramfs.cpio.gz" \
    -extract /boot/live-initramfs.cpio.gz "$WORK/live-initramfs.cpio.gz" >/dev/null
  stage_kernel_override
  extract_iso_file_by_lba /images/ooonana-full-i3-live-rootfs.ext4 "$WORK/live-rootfs.ext4"
  extract_iso_file_by_lba /images/ooonana-full-i3-disk.raw.gz "$WORK/disk.raw.gz"

  patch_ext4 "$WORK/live-rootfs.ext4" "$WORK/payload"
  gzip -dc "$WORK/disk.raw.gz" > "$WORK/disk.raw"
  patch_disk_image "$WORK/disk.raw" "$WORK/payload"
  build_iso_from_work
}

main "$@"
