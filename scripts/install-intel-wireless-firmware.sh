#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${1:?usage: install-intel-wireless-firmware.sh ROOTFS [CACHE_DIR]}"
CACHE_DIR="${2:-${TMPDIR:-/tmp}/ooonana-firmware-cache}"
VERSION="20260622-r0"
APK="linux-firmware-intel-$VERSION.apk"
URL="https://dl-cdn.alpinelinux.org/alpine/edge/main/x86_64/$APK"
SHA256="ef55b4c4292d568b01fe796337991a44ba501aa99731b1f819b2754385fa4d63"
STAGE="$CACHE_DIR/linux-firmware-intel-$VERSION"

for command_name in wget tar sha256sum unzstd; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'missing command: %s\n' "$command_name" >&2
    exit 1
  }
done

mkdir -p "$CACHE_DIR" "$TARGET_ROOT/lib/firmware/intel/iwlwifi" "$TARGET_ROOT/usr/share/ooonana"

if [[ ! -f "$CACHE_DIR/$APK" ]] ||
  [[ "$(sha256sum "$CACHE_DIR/$APK" | awk '{print $1}')" != "$SHA256" ]]; then
  rm -f "$CACHE_DIR/$APK" "$CACHE_DIR/$APK.part"
  wget -q -O "$CACHE_DIR/$APK.part" "$URL"
  mv "$CACHE_DIR/$APK.part" "$CACHE_DIR/$APK"
fi

printf '%s  %s\n' "$SHA256" "$CACHE_DIR/$APK" | sha256sum -c - >/dev/null
rm -rf "$STAGE"
mkdir -p "$STAGE"
tar -xzf "$CACHE_DIR/$APK" -C "$STAGE" >/dev/null 2>&1

wifi_count=0
for source in \
  "$STAGE"/lib/firmware/intel/iwlwifi/iwlwifi-bz-*.zst \
  "$STAGE"/lib/firmware/intel/iwlwifi/iwlwifi-gl-*.zst \
  "$STAGE"/lib/firmware/intel/iwlwifi/iwlwifi-so-*.zst \
  "$STAGE"/lib/firmware/intel/iwlwifi/iwlwifi-ty-*.zst; do
  [[ -f "$source" ]] || continue
  name="$(basename "${source%.zst}")"
  destination="$TARGET_ROOT/lib/firmware/intel/iwlwifi/$name"
  unzstd -q -c "$source" > "$destination.part"
  mv "$destination.part" "$destination"
  ln -sfn "intel/iwlwifi/$name" "$TARGET_ROOT/lib/firmware/$name"
  wifi_count=$((wifi_count + 1))
done

bluetooth_count=0
for source in "$STAGE"/lib/firmware/intel/ibt-*.zst; do
  [[ -f "$source" ]] || continue
  name="$(basename "${source%.zst}")"
  destination="$TARGET_ROOT/lib/firmware/intel/$name"
  if [[ -L "$source" ]]; then
    link_target="$(readlink "$source")"
    ln -sfn "${link_target%.zst}" "$destination"
  else
    unzstd -q -c "$source" > "$destination.part"
    mv "$destination.part" "$destination"
  fi
  bluetooth_count=$((bluetooth_count + 1))
done

[[ "$wifi_count" -gt 0 ]] || { printf 'no Intel Wi-Fi firmware extracted\n' >&2; exit 1; }
[[ "$bluetooth_count" -gt 0 ]] || { printf 'no Intel Bluetooth firmware extracted\n' >&2; exit 1; }

cat > "$TARGET_ROOT/usr/share/ooonana/intel-wireless-firmware.version" <<EOF
source=$URL
version=$VERSION
sha256=$SHA256
wifi_files=$wifi_count
bluetooth_files=$bluetooth_count
EOF

rm -rf "$STAGE"
printf 'Intel wireless firmware %s: %s Wi-Fi, %s Bluetooth files\n' \
  "$VERSION" "$wifi_count" "$bluetooth_count"
