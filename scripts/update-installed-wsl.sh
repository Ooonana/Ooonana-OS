#!/bin/sh
set -eu

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
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

case "${WSL_DISTRO_NAME:-}" in
  Ooonana|ooonana) ;;
  "") ;;
  *)
    echo "update-installed-wsl: refusing non-Ooonana distro: $WSL_DISTRO_NAME" >&2
    exit 2
    ;;
esac

os_id="$(sed -n 's/^ID=//p' /etc/os-release 2>/dev/null | head -n 1 | tr -d '"')"
if [ "$os_id" != "ooonana" ]; then
  echo "update-installed-wsl: refusing target OS: ${os_id:-unknown}" >&2
  exit 2
fi

overlay_tree() {
  source_root="$1"
  for source in "$source_root"/*; do
    [ -e "$source" ] || [ -L "$source" ] || continue
    target="/${source##*/}"
    if [ -d "$source" ] && [ ! -L "$source" ]; then
      mkdir -p "$target"
      cp -a "$source/." "$target/"
    else
      cp -a "$source" "$target"
    fi
  done
}

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

extract_config() {
  marker="$1"
  output="$2"
  awk -v marker="$marker" '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$ROOT/scripts/build-full-i3-rootfs.sh" >"$output"
  [ -s "$output" ] || { echo "cannot extract $marker" >&2; exit 1; }
  chmod 0644 "$output"
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

install -d -m 0755 \
  /usr/lib/ooonana/ai \
  /usr/lib/ooonana/ui \
  /usr/share/applications \
  /usr/share/ooonana \
  /usr/share/ooonana/wallpapers \
  /var/lib/ooonana/packages/installed
for source in "$ROOT"/packages/ooonana/usr/bin/*; do
  [ -f "$source" ] || continue
  install -m 0755 "$source" "/usr/bin/${source##*/}"
done
install -m 0755 "$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py" /usr/lib/ooonana/oonana_game.py
install -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py" /usr/lib/ooonana/ai/ooonana_ai.py
for source in "$ROOT"/packages/ooonana/usr/lib/ooonana/ui/*.py; do
  install -m 0644 "$source" "/usr/lib/ooonana/ui/${source##*/}"
done
for source in "$ROOT"/packages/ooonana/usr/share/applications/*.desktop; do
  install -m 0644 "$source" "/usr/share/applications/${source##*/}"
done
for source in "$ROOT"/packages/ooonana/usr/share/ooonana/*.txt; do
  install -m 0644 "$source" "/usr/share/ooonana/${source##*/}"
done
for source in "$ROOT"/packages/ooonana/usr/share/ooonana/wallpapers/*; do
  [ -f "$source" ] || continue
  install -m 0644 "$source" "/usr/share/ooonana/wallpapers/${source##*/}"
done
install -m 0644 \
  "$ROOT/packages/ooonana/var/lib/ooonana/packages/installed/ooonana-core.pkg" \
  /var/lib/ooonana/packages/installed/ooonana-core.pkg
install -D -m 0644 "$ROOT/branding/i3/config" /etc/i3/config
install -D -m 0644 "$ROOT/packages/ooonana/etc/gtk-3.0/settings.ini" /etc/gtk-3.0/settings.ini

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
  overlay_tree "$unpack"
fi

for helper in \
  ooonana-theme-env \
  ooonana-open ooonana-apps ooonana-run-admin ooonana-browser ooonana-files \
  ooonana-hardware-reprobe ooonana-wireless-diagnose ooonana-service-repair \
  ooonana-service-watchdog ooonana-wifi ooonana-bluetooth ooonana-touchpad \
  ooonana-rofi-wifi ooonana-rofi-bluetooth ooonana-wifi-panel \
  ooonana-wifi-status ooonana-bluetooth-panel ooonana-bluetooth-status \
  ooonana-rofi-brightness ooonana-brightness-panel ooonana-audio-panel \
  ooonana-audio-status ooonana-battery-status ooonana-volume \
  ooonana-rofi-power ooonana-power-menu ooonana-screenshot ooonana-editor \
  ooonana-processes ooonana-process-kill ooonana-ranger ooonana-brightness \
  ooonana-brightness-status ooonana-packages-app ooonana-packages \
  ooonana-settings ooonana-settings-launch ooonana-installer-gui \
  ooonana-gui-installer ooonana-install-wizard ooonana-i3-smoke-session \
  ooonana-i3-session ooonana-i3-installer-session; do
  extract_block "ROOTFS/usr/bin/$helper" "$work/$helper"
  install -m 0755 "$work/$helper" "/usr/bin/$helper"
done

for config in \
  etc/NetworkManager/NetworkManager.conf \
  etc/bluetooth/main.conf \
  etc/ooonana/xsettingsd.conf \
  etc/ooonana/polybar.ini \
  etc/ooonana/rofi.rasi \
  etc/ooonana/picom.conf \
  etc/ooonana/dunstrc; do
  extract_config "ROOTFS/$config" "$work/config"
  install -D -m 0644 "$work/config" "/$config"
done

if ! command -v doas >/dev/null 2>&1 ||
  ! command -v sudo >/dev/null 2>&1 ||
  ! command -v su >/dev/null 2>&1; then
  for url in \
    "$ALPINE/main/x86_64/doas-6.8.2-r7.apk" \
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
    overlay_tree "$unpack"
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
