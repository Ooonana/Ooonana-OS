#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="${OOONANA_RELEASE_DIR:-/mnt/f/Ooonana/ooonana-os/release-current}"
ISO="${OOONANA_ISO:-$RELEASE_DIR/ooonana-full-i3.iso}"
WORK="${OOONANA_PATCH_WORK:-$RELEASE_DIR/patch-full-i3-ui}"
OUT_ISO="${OOONANA_OUT_ISO:-$RELEASE_DIR/ooonana-full-i3.iso.new}"
VOLUME="${OOONANA_VOLUME:-OOONANAUSB}"

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
ooonana-rofi-power|/usr/bin/ooonana-rofi-power|0100755
ooonana-brightness|/usr/bin/ooonana-brightness|0100755
ooonana-brightness-status|/usr/bin/ooonana-brightness-status|0100755
ooonana-settings|/usr/bin/ooonana-settings|0100755
ooonana-settings-launch|/usr/bin/ooonana-settings-launch|0100755
polybar.ini|/etc/ooonana/polybar.ini|0100644
rofi.rasi|/etc/ooonana/rofi.rasi|0100644
dunstrc|/etc/ooonana/dunstrc|0100644
ooonana-ai-app|/usr/bin/ooonana-ai-app|0100755
ooonana-ai-launch|/usr/bin/ooonana-ai-launch|0100755
45-font-awesome.conf|/etc/fonts/conf.avail/45-font-awesome.conf|0100644
65-font-awesome.conf|/etc/fonts/conf.avail/65-font-awesome.conf|0100644
45-font-awesome.conf|/etc/fonts/conf.d/45-font-awesome.conf|0100644
65-font-awesome.conf|/etc/fonts/conf.d/65-font-awesome.conf|0100644
Font Awesome 6 Free-Regular-400.otf|/usr/share/fonts/font-awesome/Font Awesome 6 Free-Regular-400.otf|0100644
Font Awesome 6 Free-Solid-900.otf|/usr/share/fonts/font-awesome/Font Awesome 6 Free-Solid-900.otf|0100644
EOF
}

build_payload() {
  local payload="$1"
  rm -rf "$payload"
  mkdir -p "$payload"

  extract_block '$ROOTFS/usr/bin/ooonana-rofi-wifi' "$payload/ooonana-rofi-wifi"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-bluetooth' "$payload/ooonana-rofi-bluetooth"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-brightness' "$payload/ooonana-rofi-brightness"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-power' "$payload/ooonana-rofi-power"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness"' "$payload/ooonana-brightness"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness-status' "$payload/ooonana-brightness-status"
  extract_block '$ROOTFS/usr/bin/ooonana-settings"' "$payload/ooonana-settings"
  extract_block '$ROOTFS/usr/bin/ooonana-settings-launch' "$payload/ooonana-settings-launch"
  extract_block '$ROOTFS/etc/ooonana/polybar.ini' "$payload/polybar.ini"
  extract_block '$ROOTFS/etc/ooonana/rofi.rasi' "$payload/rofi.rasi"
  extract_block '$ROOTFS/etc/ooonana/dunstrc' "$payload/dunstrc"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-ai-app" "$payload/ooonana-ai-app"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-ai-launch" "$payload/ooonana-ai-launch"

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
  rm -rf "$payload/etc" "$payload/usr"
}

patch_disk_image() {
  local raw="$1"
  local payload="$2"
  local info start_bytes end_bytes size_bytes
  local loopdev

  info="$(parted -sm "$raw" unit B print | awk -F: '$1 == "1" { print $2 " " $3 }')"
  read -r start_bytes end_bytes <<EOF
$info
EOF
  start_bytes="${start_bytes%B}"
  end_bytes="${end_bytes%B}"
  size_bytes=$((end_bytes - start_bytes + 1))

  loopdev="$(losetup --find --show --offset "$start_bytes" --sizelimit "$size_bytes" "$raw")"
  trap 'losetup -d "$loopdev" >/dev/null 2>&1 || true' RETURN
  patch_ext4 "$loopdev" "$payload"
  losetup -d "$loopdev"
  trap - RETURN
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
  need losetup

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
  extract_iso_file_by_lba /images/ooonana-full-i3-live-rootfs.ext4 "$WORK/live-rootfs.ext4"
  extract_iso_file_by_lba /images/ooonana-full-i3-disk.raw.gz "$WORK/disk.raw.gz"

  patch_ext4 "$WORK/live-rootfs.ext4" "$WORK/payload"
  gzip -dc "$WORK/disk.raw.gz" > "$WORK/disk.raw"
  patch_disk_image "$WORK/disk.raw" "$WORK/payload"
  build_iso_from_work
}

main "$@"
