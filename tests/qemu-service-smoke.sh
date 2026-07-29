#!/bin/sh
set -eu

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
ISO="$ROOT/../release-current/ooonana-full-i3.iso"
WORK="${TMPDIR:-/var/tmp}/ooonana-qemu-service-smoke.$$"
ALPINE="https://dl-cdn.alpinelinux.org/alpine/v3.20"
USE_ISO_RUNTIME=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --iso-runtime) USE_ISO_RUNTIME=1; shift ;;
    -h|--help)
      echo "usage: tests/qemu-service-smoke.sh [--iso-runtime] [ISO]"
      exit 0
      ;;
    -*) echo "FAIL: unknown option: $1" >&2; exit 1 ;;
    *) ISO="$1"; shift ;;
  esac
done

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

cleanup() {
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

command -v qemu-system-x86_64 >/dev/null 2>&1 || fail "qemu-system-x86_64 missing"
command -v xorriso >/dev/null 2>&1 || fail "xorriso missing"
command -v cpio >/dev/null 2>&1 || fail "cpio missing"
[ -f "$ISO" ] || fail "ISO missing: $ISO"

mkdir -p "$WORK/patch/smoke-root"
xorriso -osirrox on -indev "$ISO" \
  -extract /boot/live-initramfs.cpio.gz "$WORK/live-initramfs.cpio.gz" \
  -extract /boot/vmlinuz "$WORK/vmlinuz" >/dev/null 2>&1
gzip -dc "$WORK/live-initramfs.cpio.gz" |
  cpio -i --to-stdout init >"$WORK/patch/init" 2>/dev/null

extract_block() {
  marker="$1"
  output="$2"
  awk -v marker="$marker" '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$ROOT/scripts/build-full-i3-rootfs.sh" >"$output"
  [ -s "$output" ] || fail "cannot extract $marker"
  chmod 0755 "$output"
}

if [ "$USE_ISO_RUNTIME" -eq 0 ]; then
  mkdir -p "$WORK/patch/smoke-root/usr/bin" \
    "$WORK/patch/smoke-root/usr/lib/ooonana" \
    "$WORK/patch/smoke-root/etc/sudoers.d"
  cp -a "$ROOT/packages/ooonana/usr/lib/ooonana/ui" \
    "$WORK/patch/smoke-root/usr/lib/ooonana/ui"
  extract_block 'ROOTFS/usr/bin/ooonana-service-repair' "$WORK/patch/smoke-root/usr/bin/ooonana-service-repair"
  extract_block 'ROOTFS/usr/bin/ooonana-run-admin' "$WORK/patch/smoke-root/usr/bin/ooonana-run-admin"
  extract_block 'ROOTFS/usr/bin/ooonana-rofi-power' "$WORK/patch/smoke-root/usr/bin/ooonana-rofi-power"
  extract_block 'ROOTFS/usr/bin/ooonana-power-menu' "$WORK/patch/smoke-root/usr/bin/ooonana-power-menu"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/bunana" "$WORK/patch/smoke-root/usr/bin/bunana"

  for url in \
    "$ALPINE/community/x86_64/sudo-1.9.15_p5-r0.apk" \
    "$ALPINE/main/x86_64/util-linux-login-2.40.1-r1.apk" \
    "$ALPINE/community/x86_64/pulseaudio-17.0-r0.apk" \
    "$ALPINE/community/x86_64/pulseaudio-utils-17.0-r0.apk" \
    "$ALPINE/community/x86_64/pulseaudio-alsa-17.0-r0.apk" \
    "$ALPINE/community/x86_64/pulseaudio-bluez-17.0-r0.apk"; do
    apk="$WORK/${url##*/}"
    wget -q -O "$apk" "$url"
    tar --warning=no-unknown-keyword --exclude=.PKGINFO --exclude='.SIGN.*' \
      -xzf "$apk" -C "$WORK/patch/smoke-root"
  done
  printf '%%wheel ALL=(ALL:ALL) NOPASSWD: ALL\n' >"$WORK/patch/smoke-root/etc/sudoers.d/ooonana"
  chmod 0440 "$WORK/patch/smoke-root/etc/sudoers.d/ooonana"
  chmod 4755 "$WORK/patch/smoke-root/usr/bin/sudo" "$WORK/patch/smoke-root/bin/su"
fi

awk '
  $0 == "exec switch_root /newroot /sbin/init" {
    print "/bin/busybox cp -a /smoke-root/. /newroot/"
    print "/bin/busybox cp /ooonana-service-smoke /newroot/usr/bin/ooonana-service-smoke"
    print "/bin/busybox chmod 0755 /newroot/usr/bin/ooonana-service-smoke"
    print "exec switch_root /newroot /usr/bin/ooonana-service-smoke"
    next
  }
  { print }
' "$WORK/patch/init" >"$WORK/patch/init.new"
mv "$WORK/patch/init.new" "$WORK/patch/init"
chmod 0755 "$WORK/patch/init"

cat >"$WORK/patch/ooonana-service-smoke" <<'SMOKE'
#!/bin/sh
set -u
exec </dev/ttyS0 >/dev/ttyS0 2>&1
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

fail() {
  echo "OOONANA_SERVICE_SMOKE_FAIL: $*"
  echo '--- services.log ---'
  cat /var/log/ooonana-services.log 2>/dev/null || true
  echo '--- NetworkManager.log ---'
  tail -100 /var/log/NetworkManager.log 2>/dev/null || true
  echo '--- bluetoothd.log ---'
  tail -100 /var/log/bluetoothd.log 2>/dev/null || true
  /sbin/poweroff -f
  exit 1
}

echo OOONANA_SERVICE_SMOKE_BEGIN
for command in \
  dbus-daemon dbus-run-session NetworkManager nmcli bluetoothd bluetoothctl \
  doas sudo su aplay pulseaudio pactl chromium \
  python3 Xorg startx i3 rofi polybar alacritty xterm nemo; do
  command -v "$command" >/dev/null 2>&1 || fail "missing $command"
done
[ "$(stat -c %a /usr/bin/doas)" = 4755 ] || fail "doas mode"
[ "$(stat -c %a /usr/bin/sudo)" = 4755 ] || fail "sudo mode"
[ "$(stat -c %a /bin/su)" = 4755 ] || fail "su mode"

/usr/bin/ooonana-service-repair boot || fail "service repair"
/usr/bin/ooonana-service-repair force-wifi || fail "forced Wi-Fi repair"
/usr/bin/ooonana-service-repair force-bluetooth || fail "forced Bluetooth repair"
/usr/bin/ooonana-service-repair status
grep -q '^pulse:' /etc/passwd || fail "PulseAudio service identity"
grep -q '^pulse-access:' /etc/group || fail "PulseAudio access group"
if grep -q 'Unknown username' /var/log/ooonana-services.log 2>/dev/null; then
  fail "D-Bus configuration references missing user"
fi
/bin/busybox pidof NetworkManager >/dev/null 2>&1 || fail "NetworkManager stopped"
/bin/busybox pidof bluetoothd >/dev/null 2>&1 || fail "bluetoothd stopped"

nmcli connection add type wifi con-name Ooonana-WiFi-Smoke ssid Ooonana-WiFi-Smoke >/dev/null ||
  fail "Wi-Fi profile creation"
nmcli connection modify Ooonana-WiFi-Smoke \
  connection.autoconnect yes \
  ipv4.method auto \
  ipv6.method auto \
  802-11-wireless.mode infrastructure \
  802-11-wireless.hidden no \
  802-11-wireless.powersave 2 \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.psk ooonana-smoke >/dev/null ||
  fail "Wi-Fi profile settings"
wifi_uuid="$(nmcli -g connection.uuid connection show Ooonana-WiFi-Smoke)"
[ -n "$wifi_uuid" ] || fail "Wi-Fi profile UUID"
nmcli connection delete uuid "$wifi_uuid" >/dev/null || fail "Wi-Fi profile cleanup"

nmcli connection add type wifi con-name Ooonana-EAP-Smoke ssid Ooonana-EAP-Smoke >/dev/null ||
  fail "enterprise Wi-Fi profile creation"
nmcli connection modify Ooonana-EAP-Smoke \
  802-11-wireless-security.key-mgmt wpa-eap \
  802-1x.eap peap \
  802-1x.identity ooonana \
  802-1x.phase2-auth mschapv2 \
  802-1x.password ooonana-smoke >/dev/null ||
  fail "enterprise Wi-Fi profile settings"
nmcli connection delete Ooonana-EAP-Smoke >/dev/null || fail "enterprise Wi-Fi profile cleanup"

nmcli connection add type wifi con-name Ooonana-OWE-Smoke ssid Ooonana-OWE-Smoke >/dev/null ||
  fail "OWE Wi-Fi profile creation"
nmcli connection modify Ooonana-OWE-Smoke \
  802-11-wireless-security.key-mgmt owe >/dev/null ||
  fail "OWE Wi-Fi profile settings"
nmcli connection delete Ooonana-OWE-Smoke >/dev/null || fail "OWE Wi-Fi profile cleanup"

[ -r /proc/asound/cards ] || fail "ALSA cards file missing"
grep -Eq '^[[:space:]]*[0-9]+[[:space:]]+\[' /proc/asound/cards || fail "Intel HDA card not detected"
aplay -l >/dev/null 2>&1 || fail "ALSA playback device unavailable"

mkdir -p /run/user/1000 /home/ooonana/.config /home/ooonana/.cache
chown -R 1000:1000 /run/user/1000 /home/ooonana
chmod 0700 /run/user/1000
/bin/su -s /bin/sh -c 'HOME=/home/ooonana XDG_RUNTIME_DIR=/run/user/1000 pulseaudio --start --exit-idle-time=-1' ooonana ||
  fail "PulseAudio start"
/bin/su -s /bin/sh -c 'HOME=/home/ooonana XDG_RUNTIME_DIR=/run/user/1000 pactl info' ooonana >/dev/null ||
  fail "PulseAudio control"
/bin/su -s /bin/sh -c 'HOME=/home/ooonana XDG_RUNTIME_DIR=/run/user/1000 pactl get-sink-volume @DEFAULT_SINK@' ooonana >/dev/null ||
  fail "PulseAudio default sink"

/bin/su -s /bin/sh -c 'HOME=/home/ooonana XDG_RUNTIME_DIR=/run/user/1000 /bin/busybox timeout 60 dbus-run-session -- chromium --headless=new --no-first-run --disable-default-apps --disable-dev-shm-usage --disable-gpu --use-gl=disabled --user-data-dir=/tmp/ooonana-chromium-smoke --dump-dom "data:text/html,<title>Ooonana</title><p>chromium-ok</p>"' ooonana >/tmp/ooonana-chromium-smoke.html 2>/tmp/ooonana-chromium-smoke.log ||
  fail "Chromium headless launch: $(tail -20 /tmp/ooonana-chromium-smoke.log 2>/dev/null)"
if ! grep -q 'chromium-ok' /tmp/ooonana-chromium-smoke.html; then
  echo '--- chromium output ---'
  cat /tmp/ooonana-chromium-smoke.html 2>/dev/null || true
  echo '--- chromium log ---'
  tail -100 /tmp/ooonana-chromium-smoke.log 2>/dev/null || true
  fail "Chromium rendered output"
fi

python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk; assert Gtk.MAJOR_VERSION == 3' ||
  fail "Python GTK import"
for app in wifi_app.py bluetooth_app.py settings_app.py; do
  python3 "/usr/lib/ooonana/ui/$app" --dry-run >/tmp/"$app".log 2>&1 ||
    fail "$app dry-run: $(tail -20 /tmp/"$app".log 2>/dev/null)"
done
python3 /usr/lib/ooonana/ui/controls_app.py audio --dry-run >/tmp/controls_app.py.log 2>&1 ||
  fail "controls app dry-run: $(tail -20 /tmp/controls_app.py.log 2>/dev/null)"
i3 -C -c /etc/i3/config >/tmp/ooonana-i3-check.log 2>&1 ||
  fail "i3 config: $(tail -40 /tmp/ooonana-i3-check.log 2>/dev/null)"
rofi -version >/dev/null 2>&1 || fail "rofi dynamic libraries"
polybar --version >/dev/null 2>&1 || fail "polybar dynamic libraries"
alacritty --version >/dev/null 2>&1 || fail "alacritty dynamic libraries"
xterm -version >/dev/null 2>&1 || fail "xterm dynamic libraries"
loader=/lib/ld-musl-x86_64.so.1
[ -x "$loader" ] || fail "musl dynamic loader missing"
Xorg -version >/tmp/ooonana-xorg-version.log 2>&1 ||
  fail "Xorg runtime: $(tail -40 /tmp/ooonana-xorg-version.log)"
for binary in /usr/bin/Xorg /usr/bin/i3 /usr/bin/rofi /usr/bin/polybar \
  /usr/bin/alacritty /usr/bin/xterm /usr/bin/nemo /usr/bin/chromium; do
  magic="$(/bin/busybox od -An -tx1 -N4 "$binary" 2>/dev/null | tr -d ' \n')"
  [ "$magic" = 7f454c46 ] || continue
  "$loader" --list "$binary" >/tmp/ooonana-loader.log 2>&1 ||
    fail "dynamic libraries for $binary: $(tail -40 /tmp/ooonana-loader.log)"
  if grep -Eq 'not found|Error loading|Error relocating' /tmp/ooonana-loader.log; then
    fail "dynamic libraries for $binary: $(tail -40 /tmp/ooonana-loader.log)"
  fi
done

doas_result="$(/bin/su -s /bin/sh -c '/usr/bin/doas /usr/bin/id -u' ooonana)"
[ "$doas_result" = 0 ] || fail "doas elevation"
sudo_result="$(/bin/su -s /bin/sh -c '/usr/bin/sudo /usr/bin/id -u' ooonana)"
[ "$sudo_result" = 0 ] || fail "sudo elevation"
admin_result="$(/bin/su -s /bin/sh -c '/usr/bin/ooonana-run-admin /usr/bin/id -u' ooonana)"
[ "$admin_result" = 0 ] || fail "admin helper elevation"

[ "$(OOONANA_POWER_ACTION=Cancel /usr/bin/ooonana-power-menu --dry-run)" = OOONANA_POWER_MENU_OK ] ||
  fail "power menu"
/usr/bin/bunana --help | grep -q -- '--shutdown' || fail "bunana help"
echo OOONANA_SERVICE_SMOKE_OK
echo OOONANA_BUNANA_SHUTDOWN_BEGIN
/usr/bin/bunana --shutdown
fail "bunana shutdown returned"
SMOKE
chmod 0755 "$WORK/patch/ooonana-service-smoke"

(
  cd "$WORK/patch"
  find . -print0 | cpio --null -o -H newc 2>/dev/null | gzip -9 >"$WORK/patch.cpio.gz"
)
cat "$WORK/live-initramfs.cpio.gz" "$WORK/patch.cpio.gz" >"$WORK/smoke-initramfs.cpio.gz"

set +e
timeout 240 qemu-system-x86_64 \
  -machine q35 -m 2048 -smp 2 \
  -kernel "$WORK/vmlinuz" -initrd "$WORK/smoke-initramfs.cpio.gz" \
  -append 'console=ttyS0 loglevel=4 ooonana.live=1' \
  -cdrom "$ISO" -nic user,model=e1000 \
  -audiodev none,id=ooonana-audio \
  -device intel-hda -device hda-duplex,audiodev=ooonana-audio \
  -display none -serial stdio -monitor none -no-reboot >"$WORK/qemu.log" 2>&1
qemu_rc=$?
set -e

cat "$WORK/qemu.log"
grep -q 'OOONANA_SERVICE_SMOKE_OK' "$WORK/qemu.log" || fail "QEMU service smoke did not finish (rc=$qemu_rc)"
grep -q 'OOONANA_BUNANA_SHUTDOWN_BEGIN' "$WORK/qemu.log" || fail "bunana shutdown not reached"
! grep -q 'OOONANA_SERVICE_SMOKE_FAIL' "$WORK/qemu.log" || fail "QEMU service assertion failed"
echo "ok qemu-service-smoke"
