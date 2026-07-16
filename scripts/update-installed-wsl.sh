#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ALPINE="https://dl-cdn.alpinelinux.org/alpine/v3.20"
APK_DIR="${OOONANA_RUNTIME_APK_DIR:-}"

if [ "$(id -u)" -ne 0 ]; then
  if command -v doas >/dev/null 2>&1; then
    exec doas sh "$0"
  elif command -v sudo >/dev/null 2>&1; then
    exec sudo sh "$0"
  fi
  echo "update-installed-wsl: run as root" >&2
  exit 126
fi

extract_block() {
  marker="$1"
  output="$2"
  awk -v marker="$marker" '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$ROOT/scripts/build-full-i3-rootfs.sh" >"$output"
  [ -s "$output" ] || { echo "cannot extract $marker" >&2; exit 1; }
  chmod 0755 "$output"
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

install -m 0755 "$ROOT/packages/ooonana/usr/bin/bunana" /usr/bin/bunana
install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana" /usr/bin/ooonana
install -m 0755 "$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py" /usr/lib/ooonana/oonana_game.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/common.py" /usr/lib/ooonana/ui/common.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wifi_app.py" /usr/lib/ooonana/ui/wifi_app.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/bluetooth_app.py" /usr/lib/ooonana/ui/bluetooth_app.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/wireless_utils.py" /usr/lib/ooonana/ui/wireless_utils.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/signal_map.py" /usr/lib/ooonana/ui/signal_map.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/controls_app.py" /usr/lib/ooonana/ui/controls_app.py
install -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/grub-logo.txt" /usr/share/ooonana/grub-logo.txt

if ! python3 -c 'import cairo' >/dev/null 2>&1; then
  url="$ALPINE/main/x86_64/py3-cairo-1.26.0-r1.apk"
  apk="$work/${url##*/}"
  unpack="$work/unpack-${url##*/}"
  mkdir -p "$unpack"
  if [ -n "$APK_DIR" ] && [ -f "$APK_DIR/${url##*/}" ]; then
    cp "$APK_DIR/${url##*/}" "$apk"
  else
    wget -q -O "$apk" "$url"
  fi
  tar -xzf "$apk" -C "$unpack"
  rm -f "$unpack/.PKGINFO" "$unpack"/.SIGN.*
  cp -a "$unpack/." /
fi

for helper in \
  ooonana-hardware-reprobe ooonana-wireless-diagnose ooonana-service-repair \
  ooonana-run-admin ooonana-wifi ooonana-wifi-panel ooonana-wifi-status \
  ooonana-audio-panel ooonana-audio-status ooonana-rofi-power ooonana-power-menu; do
  extract_block "ROOTFS/usr/bin/$helper" "$work/$helper"
  install -m 0755 "$work/$helper" "/usr/bin/$helper"
done

if ! command -v sudo >/dev/null 2>&1 || ! command -v su >/dev/null 2>&1; then
  for url in \
    "$ALPINE/community/x86_64/sudo-1.9.15_p5-r0.apk" \
    "$ALPINE/main/x86_64/util-linux-login-2.40.1-r1.apk"; do
    apk="$work/${url##*/}"
    unpack="$work/unpack-${url##*/}"
    mkdir -p "$unpack"
    if [ -n "$APK_DIR" ] && [ -f "$APK_DIR/${url##*/}" ]; then
      cp "$APK_DIR/${url##*/}" "$apk"
    else
      wget -q -O "$apk" "$url"
    fi
    tar -xzf "$apk" -C "$unpack"
    rm -f "$unpack/.PKGINFO" "$unpack"/.SIGN.*
    cp -a "$unpack/." /
  done
fi

install -d -m 0755 /etc/sudoers.d
printf '%%wheel ALL=(ALL:ALL) NOPASSWD: ALL\n' >/etc/sudoers.d/ooonana
chmod 0440 /etc/sudoers.d/ooonana
chmod 4755 /usr/bin/doas /usr/bin/sudo /bin/su

command -v sudo >/dev/null
command -v su >/dev/null
command -v doas >/dev/null
OOONANA_POWER_ACTION=Cancel /usr/bin/ooonana-power-menu --dry-run | grep -q OOONANA_POWER_MENU_OK
echo "Ooonana WSL runtime updated"
