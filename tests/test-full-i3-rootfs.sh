#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/build-full-i3-rootfs.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" != *"$needle"* ]] || fail "unexpected: $needle"
}

[[ -x "$SCRIPT" ]] || fail "missing executable full-i3 rootfs builder"
script_src="$(<"$SCRIPT")"
firmware_script_src="$(<"$ROOT/scripts/install-intel-wireless-firmware.sh")"
patch_src="$(<"$ROOT/scripts/patch-full-i3-release-ui.sh")"
full_i3_packages="$(<"$ROOT/configs/packages/full-i3.list")"
assert_contains "$script_src" 'cp -a "$ROOT/packages/ooonana/." "$ROOTFS/"'
assert_not_contains "$script_src" 'cp -a "$REPO/." "$ROOTFS/usr/lib/ooonana/repo/"'
assert_contains "$script_src" 'ooonana" repo index "$REPO"'
assert_contains "$script_src" '[[ ! -s "$REPO/index.tsv" || ! -s "$REPO/SHA256SUMS" ]]'
assert_contains "$script_src" "stage_full_i3_repo_metadata"
assert_contains "$script_src" 'OOONANA_REPO_DIR="$STAGED_REPO"'
assert_contains "$script_src" "compile_glib_schemas()"
assert_contains "$script_src" 'glib-compile-schemas "$ROOTFS/usr/share/glib-2.0/schemas"'
assert_contains "$script_src" "refresh_gtk_caches()"
assert_contains "$script_src" 'update-mime-database "$ROOTFS/usr/share/mime"'
assert_contains "$script_src" "gdk-pixbuf-query-loaders"
assert_contains "$script_src" "normalize_rootfs_permissions()"
assert_contains "$script_src" 'chmod 4755 "$setuid_path"'
assert_contains "$script_src" "refresh_font_caches()"
assert_contains "$script_src" 'ln -s python3 "$ROOTFS/usr/bin/python"'
assert_contains "$script_src" "fix_blueman_activation()"
assert_contains "$script_src" "sed -i '/^SystemdService=/d'"
assert_not_contains "$script_src" "start_blueman_mechanism()"
assert_contains "$script_src" 'PRETTY_NAME="Ooonana OS $OS_VERSION"'
assert_contains "$script_src" "mkfontscale"
assert_contains "$script_src" "fc-cache -r /usr/share/fonts"
assert_contains "$script_src" "OOONANA_SKIP_INTEL_FIRMWARE"
assert_contains "$firmware_script_src" 'OOONANA_FIRMWARE_DOWNLOAD_TIMEOUT:-30'
assert_contains "$firmware_script_src" 'OOONANA_FIRMWARE_DOWNLOAD_TRIES:-3'
assert_contains "$patch_src" 'rcS|/etc/init.d/rcS|0100755'
assert_contains "$patch_src" 'ooonana-hardware-reprobe|/usr/bin/ooonana-hardware-reprobe|0100755'
assert_contains "$patch_src" 'ooonana-wireless-diagnose|/usr/bin/ooonana-wireless-diagnose|0100755'
assert_contains "$patch_src" 'ooonana-service-repair|/usr/bin/ooonana-service-repair|0100755'
assert_contains "$patch_src" 'ooonana-service-watchdog|/usr/bin/ooonana-service-watchdog|0100755'
assert_contains "$patch_src" 'ooonana-run-admin|/usr/bin/ooonana-run-admin|0100755'
assert_contains "$patch_src" 'ln -s ../run "$mount_dir/var/run"'
assert_contains "$patch_src" 'write_debugfs_symlink "$image" python3 /usr/bin/python'
assert_contains "$patch_src" 'org.blueman.Mechanism.service'
assert_contains "$patch_src" 'installed/ooonana-core.pkg'
assert_contains "$patch_src" 'start-ooonana-i3|/usr/bin/start-ooonana-i3|0100755'
assert_contains "$patch_src" 'ooonana-wifi|/usr/bin/ooonana-wifi|0100755'
assert_contains "$patch_src" 'ooonana-bluetooth|/usr/bin/ooonana-bluetooth|0100755'
assert_contains "$patch_src" 'ooonana-battery-status|/usr/bin/ooonana-battery-status|0100755'
assert_contains "$patch_src" 'oonana|/usr/bin/oonana|0100755'
assert_contains "$patch_src" 'oonana_game.py|/usr/lib/ooonana/oonana_game.py|0100755'
assert_contains "$patch_src" 'yad-wrapper|/usr/local/bin/yad|0100755'
assert_contains "$patch_src" 'gtk-settings.ini|/etc/gtk-3.0/settings.ini|0100644'
assert_contains "$patch_src" 'NetworkManager.conf|/etc/NetworkManager/NetworkManager.conf|0100644'
assert_contains "$patch_src" 'cp -a "$WORK/payload/root/lib/firmware/." "$tree/lib/firmware/"'
assert_contains "$patch_src" 'bluetooth-main.conf|/etc/bluetooth/main.conf|0100644'
assert_contains "$patch_src" 'sudoers-ooonana|/etc/sudoers.d/ooonana|0100440'
assert_contains "$patch_src" 'grub-logo.txt|/boot/grub/ooonana-logo.txt|0100644'
assert_contains "$patch_src" 'width = length($0)'
assert_contains "$patch_src" '> "$payload/grub-logo.txt"'
assert_contains "$patch_src" 'ooonana-i3-session|/usr/bin/ooonana-i3-session|0100755'
assert_contains "$patch_src" 'i3.config|/etc/i3/config|0100644'
assert_contains "$patch_src" 'i3.config.keycodes|/etc/i3/config.keycodes|0100644'
assert_contains "$patch_src" 'nm-applet.desktop|/etc/xdg/autostart/nm-applet.desktop|0100644'
assert_contains "$patch_src" 'blueman.desktop|/etc/xdg/autostart/blueman.desktop|0100644'
assert_contains "$patch_src" 'wget|/usr/bin/wget|0100755'
assert_not_contains "$patch_src" "losetup --find"
assert_contains "$patch_src" "OOONANA_EXTRA_ROOT"
assert_contains "$patch_src" "OOONANA_KERNEL_OVERRIDE"
assert_contains "$patch_src" "stage_kernel_override"
assert_contains "$patch_src" "patch_overlay_root"
assert_contains "$patch_src" "patch_identity_files"
assert_contains "$patch_src" "normalize_ext4_permissions"
assert_contains "$patch_src" "repair_ext4_image"
assert_contains "$patch_src" "need e2fsck"
assert_contains "$patch_src" "doas-6.8.2-r7.apk"
assert_contains "$patch_src" "dbus-daemon-launch-helper-1.14.10-r1.apk"
assert_contains "$patch_src" 'chmod 4750 "$mount_dir/usr/libexec/dbus-daemon-launch-helper"'
assert_contains "$patch_src" "sudo-1.9.15_p5-r0.apk"
assert_contains "$patch_src" "util-linux-login-2.40.1-r1.apk"
assert_contains "$patch_src" "alsa-ucm-conf-1.2.11-r1.apk"
assert_contains "$patch_src" "alsa-topology-conf-1.2.5.1-r1.apk"
assert_contains "$patch_src" 'payload/root/etc/doas.conf'
assert_contains "$patch_src" 'pulseaudio-17.0-r0.apk'
assert_contains "$patch_src" 'pulseaudio-bluez-17.0-r0.apk'
assert_contains "$patch_src" 'payload/root/etc/os-release'
assert_contains "$patch_src" "messagebus:x:81:"
for required_package in \
  python3 curl wget ca-certificates dbus dbus-daemon-launch-helper doas sudo util-linux-login py3-gobject3 gtk+3.0 eudev \
  networkmanager networkmanager-cli networkmanager-tui network-manager-applet \
  blueman bluez iw wireless-tools wpa_supplicant wireless-regdb \
  pciutils usbutils \
  linux-firmware-i915 linux-firmware-ath10k linux-firmware-ath11k \
  linux-firmware-ath12k linux-firmware-mediatek linux-firmware-rtw88 \
  linux-firmware-rtw89 linux-firmware-rtl_bt linux-firmware-rtl_nic \
  sof-firmware pulseaudio pipewire pipewire-alsa pipewire-pulse pipewire-spa-bluez wireplumber \
  alsa-ucm-conf alsa-topology-conf font-dejavu font-noto-cjk musl-locales; do
  assert_contains "$full_i3_packages" "$required_package"
done
for required_runtime_package in networkmanager-wifi networkmanager-bluetooth bluez-btmgmt bluez-hid2hci bluez-obexd pulseaudio pulseaudio-alsa pulseaudio-bluez libnotify xdg-utils; do
  assert_contains "$full_i3_packages" "$required_runtime_package"
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
scratch="$tmp/scratch-rootfs"
repo="$tmp/repo"
mkdir -p \
  "$scratch/bin" \
  "$scratch/etc/ooonana" \
  "$scratch/usr/bin" \
  "$scratch/usr/lib/ooonana/repo" \
  "$scratch/usr/share/ooonana" \
  "$scratch/var/lib/ooonana/packages/installed" \
  "$repo"
cat > "$scratch/bin/sh" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$scratch/bin/sh"
cat > "$scratch/bin/busybox" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$scratch/bin/busybox"
cat > "$scratch/usr/bin/ooonana" <<'EOF'
#!/bin/sh
echo ooonana 0.8.17
EOF
chmod +x "$scratch/usr/bin/ooonana"
cat > "$scratch/usr/bin/ooonana-setup" <<'EOF'
#!/bin/sh
echo OOONANA_SETUP_OK
EOF
chmod +x "$scratch/usr/bin/ooonana-setup"
printf 'OOONANA_PKG_ID="base"\nOOONANA_PKG_VERSION="0.1.0"\nOOONANA_PKG_SUMMARY="Base"\n' > "$scratch/var/lib/ooonana/packages/installed/base.pkg"
cp "$scratch/var/lib/ooonana/packages/installed/base.pkg" "$scratch/usr/lib/ooonana/repo/base.pkg"

make_archive_pkg() {
  local id="$1"
  local payload_file="$2"
  local payload_text="$3"
  local payload_dir="$tmp/payload-$id"
  local archive="$repo/$id.tar.gz"
  rm -rf "$payload_dir"
  mkdir -p "$payload_dir/$(dirname "$payload_file")"
  printf '%s\n' "$payload_text" > "$payload_dir/$payload_file"
  tar -C "$payload_dir" -czf "$archive" .
  local archive_sha
  archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
  cat > "$repo/$id.pkg" <<EOF
OOONANA_PKG_ID="$id"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="$id payload"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="$id.tar.gz"
OOONANA_PKG_SHA256="$archive_sha"
EOF
}

make_archive_pkg branding usr/share/ooonana/pkg-branding.txt branding-installed
make_archive_pkg fake-i3-bin usr/bin/fake-i3-bin fake-i3-installed
make_archive_pkg dbus-daemon-launch-helper usr/libexec/dbus-daemon-launch-helper helper-installed
chmod +x "$tmp/payload-fake-i3-bin/usr/bin/fake-i3-bin" 2>/dev/null || true
tar -C "$tmp/payload-fake-i3-bin" -czf "$repo/fake-i3-bin.tar.gz" .
fake_i3_sha="$(sha256sum "$repo/fake-i3-bin.tar.gz" | awk '{print $1}')"
sed -i "s/^OOONANA_PKG_SHA256=.*/OOONANA_PKG_SHA256=\"$fake_i3_sha\"/" "$repo/fake-i3-bin.pkg"
chmod +x "$tmp/payload-dbus-daemon-launch-helper/usr/libexec/dbus-daemon-launch-helper"
tar -C "$tmp/payload-dbus-daemon-launch-helper" -czf "$repo/dbus-daemon-launch-helper.tar.gz" .
dbus_helper_sha="$(sha256sum "$repo/dbus-daemon-launch-helper.tar.gz" | awk '{print $1}')"
sed -i "s/^OOONANA_PKG_SHA256=.*/OOONANA_PKG_SHA256=\"$dbus_helper_sha\"/" "$repo/dbus-daemon-launch-helper.pkg"

cat > "$repo/i3.pkg" <<'EOF'
OOONANA_PKG_ID="i3"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="i3 profile"
OOONANA_PKG_DEPS="dbus-daemon-launch-helper fake-i3-bin"
EOF

cat > "$repo/full-i3.pkg" <<'EOF'
OOONANA_PKG_ID="full-i3"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="full i3 profile"
OOONANA_PKG_DEPS="base branding i3"
EOF

cp "$scratch/var/lib/ooonana/packages/installed/base.pkg" "$repo/base.pkg"
"$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$repo" >/dev/null
grep -q $'^full-i3\t' "$repo/index.tsv" || fail "fixture index missing full-i3"
grep -q '  full-i3.pkg$' "$repo/SHA256SUMS" || fail "fixture checksums missing full-i3"
printf '%s\n' base branding dbus-daemon-launch-helper fake-i3-bin i3 full-i3 >"$tmp/full-i3.list"
mkdir -p "$tmp/preflight/sources" "$tmp/preflight/state" "$tmp/preflight/cache"
OOONANA_ROOT="$tmp/preflight/root" \
  OOONANA_REPO_DIR="$repo" \
  OOONANA_SOURCES_DIR="$tmp/preflight/sources" \
  OOONANA_STATE_DIR="$tmp/preflight/state" \
  OOONANA_CACHE_DIR="$tmp/preflight/cache" \
  "$ROOT/packages/ooonana/usr/bin/ooonana" get full-i3 --dry-run >/dev/null

OOONANA_SKIP_INTEL_FIRMWARE=1 bash "$SCRIPT" \
  --scratch-rootfs "$scratch" \
  --repo "$repo" \
  --package-profile "$tmp/full-i3.list" \
  --rootfs "$tmp/full-rootfs" \
  --tarball "$tmp/ooonana-full-i3-rootfs.tar.gz" \
  --force

rootfs="$tmp/full-rootfs"
[[ -f "$tmp/ooonana-full-i3-rootfs.tar.gz" ]] || fail "missing full-i3 tarball"
[[ -f "$rootfs/etc/ooonana/edition" ]] || fail "missing edition marker"
[[ "$(<"$rootfs/etc/ooonana/edition")" == "full-i3" ]] || fail "wrong edition marker"
[[ -f "$rootfs/etc/ooonana/sources.d/cloud.repo" ]] || fail "missing default cloud repo source"
assert_contains "$(<"$rootfs/etc/ooonana/sources.d/cloud.repo")" "https://ooonana.gitlab.io/ooonana-repo"
if compgen -G "$rootfs/usr/lib/ooonana/repo/*.pkg" >/dev/null; then
  fail "full-i3 rootfs must not bundle full offline package repo after cloud source is written"
fi
[[ -x "$rootfs/usr/bin/start-ooonana-i3" ]] || fail "missing start script"
[[ -x "$rootfs/usr/bin/ooonana-gui-installer" ]] || fail "missing GUI installer"
[[ -x "$rootfs/usr/bin/ooonana-installer-gui" ]] || fail "missing yad GUI installer"
[[ -x "$rootfs/usr/bin/ooonana-install-wizard" ]] || fail "missing install wizard"
[[ -x "$rootfs/usr/bin/ooonana-ai-app" ]] || fail "missing AI app launcher"
[[ -x "$rootfs/usr/bin/ooonana-packages-app" ]] || fail "missing package app launcher"
[[ -x "$rootfs/usr/bin/ooonana-packages" ]] || fail "missing package app alias"
[[ -x "$rootfs/usr/bin/ooonana-setup" ]] || fail "missing setup command"
[[ -x "$rootfs/usr/bin/ooonana-i3-session" ]] || fail "missing i3 session"
[[ -x "$rootfs/usr/bin/ooonana-i3-installer-session" ]] || fail "missing i3 installer session"
[[ -x "$rootfs/usr/bin/ooonana-i3-smoke-session" ]] || fail "missing GUI smoke session"
[[ -x "$rootfs/usr/bin/ooonana-theme-env" ]] || fail "missing theme helper"
[[ -x "$rootfs/usr/bin/bunana" ]] || fail "missing bunana command"
[[ -x "$rootfs/usr/bin/oonana" ]] || fail "missing oonana game"
[[ -x "$rootfs/usr/lib/ooonana/oonana_game.py" ]] || fail "missing Python oonana game"
[[ -x "$rootfs/usr/bin/neofetch" ]] || fail "missing neofetch fallback"
[[ -x "$rootfs/usr/bin/ooonana-browser" ]] || fail "missing browser helper"
[[ -x "$rootfs/usr/bin/ooonana-files" ]] || fail "missing file manager helper"
[[ -x "$rootfs/usr/bin/ooonana-wifi" ]] || fail "missing wifi helper"
[[ -x "$rootfs/usr/bin/ooonana-bluetooth" ]] || fail "missing bluetooth helper"
[[ -x "$rootfs/usr/bin/ooonana-hardware-reprobe" ]] || fail "missing hardware reprobe helper"
[[ -x "$rootfs/usr/bin/ooonana-wireless-diagnose" ]] || fail "missing wireless diagnostic helper"
[[ -x "$rootfs/usr/bin/ooonana-service-repair" ]] || fail "missing service repair helper"
[[ -x "$rootfs/usr/bin/ooonana-service-watchdog" ]] || fail "missing service watchdog"
[[ -x "$rootfs/usr/bin/ooonana-run-admin" ]] || fail "missing admin helper"
[[ -x "$rootfs/usr/libexec/dbus-daemon-launch-helper" ]] || fail "missing D-Bus launch helper"
[[ -x "$rootfs/usr/bin/ooonana-apps" ]] || fail "missing app launcher"
[[ -x "$rootfs/usr/bin/ooonana-rofi-wifi" ]] || fail "missing rofi wifi applet"
[[ -x "$rootfs/usr/bin/ooonana-rofi-bluetooth" ]] || fail "missing rofi bluetooth applet"
[[ -x "$rootfs/usr/bin/ooonana-rofi-brightness" ]] || fail "missing rofi brightness applet"
[[ -x "$rootfs/usr/bin/ooonana-wifi-panel" ]] || fail "missing wifi panel"
[[ -x "$rootfs/usr/bin/ooonana-wifi-status" ]] || fail "missing wifi panel status"
[[ -x "$rootfs/usr/bin/ooonana-bluetooth-panel" ]] || fail "missing bluetooth panel"
[[ -x "$rootfs/usr/bin/ooonana-bluetooth-status" ]] || fail "missing bluetooth panel status"
[[ -x "$rootfs/usr/bin/ooonana-brightness-panel" ]] || fail "missing brightness panel"
[[ -x "$rootfs/usr/bin/ooonana-audio-panel" ]] || fail "missing audio panel"
[[ -x "$rootfs/usr/bin/ooonana-audio-status" ]] || fail "missing audio panel status"
[[ -x "$rootfs/usr/bin/ooonana-audio-start" ]] || fail "missing audio session starter"
[[ -x "$rootfs/usr/bin/which" ]] || fail "missing which helper"
[[ -x "$rootfs/usr/bin/strings" ]] || fail "missing strings helper"
[[ -x "$rootfs/usr/bin/ooonana-volume" ]] || fail "missing volume helper"
[[ -x "$rootfs/usr/bin/ooonana-rofi-power" ]] || fail "missing rofi power applet"
[[ -x "$rootfs/usr/bin/ooonana-power-menu" ]] || fail "missing power menu helper"
[[ -x "$rootfs/usr/bin/ooonana-settings" ]] || fail "missing settings helper"
[[ -x "$rootfs/usr/bin/ooonana-settings-launch" ]] || fail "missing settings launch wrapper"
[[ -x "$rootfs/usr/local/bin/yad" ]] || fail "missing themed yad wrapper"
[[ -x "$rootfs/usr/bin/wget" ]] || fail "missing wget fallback"
[[ -x "$rootfs/usr/bin/ooonana-wallpaper" ]] || fail "missing wallpaper helper"
[[ -x "$rootfs/usr/bin/hsetroot" ]] || fail "missing hsetroot fallback"
[[ -x "$rootfs/usr/bin/xsettingsd" ]] || fail "missing xsettingsd fallback"
[[ -x "$rootfs/usr/bin/ooonana-screenshot" ]] || fail "missing screenshot helper"
[[ -x "$rootfs/usr/bin/ooonana-editor" ]] || fail "missing editor helper"
[[ -x "$rootfs/usr/bin/ooonana-music" ]] || fail "missing music helper"
[[ -x "$rootfs/usr/bin/ooonana-processes" ]] || fail "missing processes helper"
[[ -x "$rootfs/usr/bin/ooonana-ranger" ]] || fail "missing ranger helper"
[[ -x "$rootfs/usr/bin/ooonana-brightness" ]] || fail "missing brightness helper"
[[ -f "$rootfs/usr/share/ooonana/logo.svg" ]] || fail "missing rootfs logo svg"
[[ -f "$rootfs/usr/share/ooonana/logo.png" ]] || fail "missing rootfs logo png"
[[ -f "$rootfs/usr/share/ooonana/boot-logo.txt" ]] || fail "missing rootfs boot logo"
[[ -f "$rootfs/usr/share/ooonana/wallpapers/ooonana-wallpaper.png" ]] || fail "missing rootfs wallpaper"
[[ -f "$rootfs/usr/share/ooonana/wallpapers/ooonana-notes.jpg" ]] || fail "missing Notes rootfs wallpaper"
assert_contains "$(<"$rootfs/etc/gtk-3.0/settings.ini")" "gtk-decoration-layout=menu:minimize,maximize,close"
[[ -f "$rootfs/etc/i3/config" ]] || fail "missing rootfs i3 config"
[[ -f "$rootfs/etc/ooonana/polybar.ini" ]] || fail "missing polybar config"
[[ -f "$rootfs/etc/ooonana/rofi.rasi" ]] || fail "missing rofi config"
[[ -f "$rootfs/etc/ooonana/picom.conf" ]] || fail "missing picom config"
[[ -f "$rootfs/etc/ooonana/dunstrc" ]] || fail "missing dunst config"
[[ -f "$rootfs/etc/ooonana/xsettingsd.conf" ]] || fail "missing xsettingsd config"
[[ -f "$rootfs/etc/gtk-3.0/settings.ini" ]] || fail "missing GTK system settings"
[[ -f "$rootfs/root/.config/gtk-3.0/settings.ini" ]] || fail "missing GTK root settings"
[[ -f "$rootfs/root/.config/gtk-3.0/gtk.css" ]] || fail "missing GTK root CSS"
[[ -f "$rootfs/etc/NetworkManager/NetworkManager.conf" ]] || fail "missing NetworkManager config"
[[ -f "$rootfs/etc/bluetooth/main.conf" ]] || fail "missing Bluetooth config"
[[ -f "$rootfs/etc/doas.d/ooonana.conf" ]] || fail "missing doas policy"
[[ -f "$rootfs/etc/doas.conf" ]] || fail "missing active doas policy"
[[ -f "$rootfs/etc/sudoers.d/ooonana" ]] || fail "missing sudo policy"
[[ -f "$rootfs/etc/ooonana/default-user" ]] || fail "missing default desktop user"
[[ -f "$rootfs/etc/profile.d/00-ooonana-locale.sh" ]] || fail "missing UTF-8 locale profile"
[[ -f "$rootfs/etc/environment" ]] || fail "missing desktop environment file"
[[ -d "$rootfs/home/ooonana" ]] || fail "missing live user home"
for native_app in common setup_app settings_app wifi_app bluetooth_app packages_app ai_app controls_app launcher_app; do
  [[ -f "$rootfs/usr/lib/ooonana/ui/$native_app.py" ]] || fail "missing native app: $native_app"
done
[[ -f "$rootfs/etc/neofetch/config.conf" ]] || fail "missing neofetch config"
[[ -f "$rootfs/etc/X11/xorg.conf.d/10-ooonana-input.conf" ]] || fail "missing Xorg input config"
[[ -f "$rootfs/usr/share/ooonana/xorg-fbdev.conf" ]] || fail "missing Xorg fbdev template"
[[ -f "$rootfs/usr/share/applications/ooonana-installer.desktop" ]] || fail "missing GUI installer desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-ai.desktop" ]] || fail "missing AI app desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-packages.desktop" ]] || fail "missing package app desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-setup.desktop" ]] || fail "missing setup desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-settings.desktop" ]] || fail "missing settings desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-apps.desktop" ]] || fail "missing app launcher desktop entry"
[[ -f "$rootfs/usr/share/applications/oonana.desktop" ]] || fail "missing game desktop entry"
[[ -x "$rootfs/usr/bin/ooonana-game-launch" ]] || fail "missing game terminal launcher"
[[ -d "$rootfs/var/log" ]] || fail "missing var log for Xorg"
[[ -L "$rootfs/var/run" ]] || fail "var/run must point at runtime tmpfs"
[[ "$(readlink "$rootfs/var/run")" == "../run" ]] || fail "var/run must point to ../run"
[[ "$(readlink "$rootfs/bin/mkdir")" == "busybox" ]] || fail "init mkdir must use busybox"
[[ "$(readlink "$rootfs/bin/cat")" == "busybox" ]] || fail "init cat must use busybox"
[[ "$(readlink "$rootfs/bin/sleep")" == "busybox" ]] || fail "init sleep must use busybox"
[[ "$(readlink "$rootfs/usr/bin/env")" == "../../bin/busybox" ]] || fail "env must use busybox"
assert_contains "$(<"$rootfs/etc/group")" "tty:x:5:"
assert_contains "$(<"$rootfs/etc/group")" "input:x:97:"
assert_contains "$(<"$rootfs/etc/group")" "tape:x:26:"
assert_contains "$(<"$rootfs/etc/group")" "kvm:x:34:"
assert_contains "$(<"$rootfs/etc/group")" "messagebus:x:81:"
dbus_helper_mode="$(stat -c %a "$rootfs/usr/libexec/dbus-daemon-launch-helper")"
[[ "$dbus_helper_mode" == "4750" || "$dbus_helper_mode" == "4755" ]] || fail "wrong D-Bus launch helper mode"
if [[ "$dbus_helper_mode" == "4750" ]]; then
  [[ "$(stat -c %g "$rootfs/usr/libexec/dbus-daemon-launch-helper")" == "81" ]] || fail "wrong D-Bus launch helper group"
fi
assert_contains "$(<"$rootfs/etc/group")" "pulse:x:70:"
assert_contains "$(<"$rootfs/etc/group")" "pulse-access:x:71:"
assert_contains "$(<"$rootfs/etc/group")" "wheel:x:10:ooonana"
assert_contains "$(<"$rootfs/etc/group")" "audio:x:29:ooonana"
assert_contains "$(<"$rootfs/etc/group")" "video:x:44:ooonana"
assert_contains "$(<"$rootfs/etc/passwd")" "ooonana:x:1000:1000:Ooonana Live User:/home/ooonana:/bin/sh"
assert_contains "$(<"$rootfs/etc/passwd")" "messagebus:x:81:81:DBus Message Bus:/run/dbus:/bin/false"
assert_contains "$(<"$rootfs/etc/passwd")" "pulse:x:70:70:PulseAudio:/run/pulse:/bin/false"
assert_contains "$(<"$rootfs/etc/doas.d/ooonana.conf")" "permit nopass keepenv :wheel"
assert_contains "$(<"$rootfs/etc/doas.conf")" "permit nopass keepenv :wheel"
assert_contains "$(<"$rootfs/etc/sudoers.d/ooonana")" '%wheel ALL=(ALL:ALL) NOPASSWD: ALL'
assert_contains "$(<"$rootfs/etc/wsl.conf")" "default=ooonana"
assert_contains "$(<"$rootfs/etc/wsl.conf")" "mountFsTab=false"
assert_contains "$(<"$rootfs/etc/os-release")" 'PRETTY_NAME="Ooonana OS 0.1.8"'
[[ "$(<"$rootfs/etc/ooonana/default-user")" == "ooonana" ]] || fail "wrong default desktop user"
[[ -s "$rootfs/etc/machine-id" ]] || fail "missing machine-id"
[[ -s "$rootfs/var/lib/dbus/machine-id" ]] || fail "missing dbus machine-id"
assert_contains "$(<"$rootfs/etc/hosts")" "127.0.0.1 localhost ooonana"
assert_contains "$(<"$rootfs/usr/share/applications/ooonana-ai.desktop")" "Exec=ooonana-ai-launch"
assert_contains "$(<"$rootfs/usr/share/applications/ooonana-packages.desktop")" "Exec=ooonana-packages-app"
assert_contains "$(<"$rootfs/usr/share/applications/ooonana-installer.desktop")" "Exec=ooonana-installer-gui"
assert_contains "$(<"$rootfs/usr/share/applications/ooonana-settings.desktop")" "Exec=ooonana-settings-launch"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/branding.pkg" ]] || fail "missing branding installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/i3.pkg" ]] || fail "missing i3 installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/full-i3.pkg" ]] || fail "missing full-i3 installed marker"
[[ -f "$rootfs/var/lib/ooonana/packages/installed/fake-i3-bin.pkg" ]] || fail "missing fake i3 installed marker"
[[ -f "$rootfs/usr/share/ooonana/pkg-branding.txt" ]] || fail "branding package payload not installed"
[[ -x "$rootfs/usr/bin/fake-i3-bin" ]] || fail "i3 package payload not installed"
[[ -f "$rootfs/var/lib/ooonana/packages/files/branding.list" ]] || fail "missing branding file manifest"
[[ "$(<"$rootfs/etc/ooonana/edition-state")" == "packages-installed" ]] || fail "full-i3 packages not installed through package manager"

start_script="$(<"$rootfs/usr/bin/start-ooonana-i3")"
assert_contains "$start_script" "OOONANA_FULL_I3_OK"
assert_contains "$start_script" "startx"
assert_contains "$start_script" "ooonana.gui-smoke=1"
assert_contains "$start_script" "ooonana.install=1"
assert_contains "$start_script" "startx /usr/bin/ooonana-i3-installer-session"
assert_contains "$start_script" "ooonana-i3-session"
assert_contains "$start_script" "WSL_DISTRO_NAME"
assert_contains "$start_script" "grep -qi microsoft /proc/version"
assert_contains "$start_script" 'exec /usr/bin/ooonana-i3-session'
assert_contains "$start_script" 'exec startx /usr/bin/ooonana-i3-session --user "$SESSION_USER"'
assert_contains "$start_script" 'HOME="/root"'
assert_contains "$start_script" 'touch "$HOME/.Xauthority"'
assert_contains "$start_script" 'exec /bin/sh -l'
assert_contains "$start_script" 'prepare_xorg_video_config'
assert_contains "$start_script" '/sys/firmware/efi'
assert_contains "$start_script" '/dev/fb0'
assert_contains "$start_script" '/dev/dri/card0'
assert_contains "$start_script" '/usr/share/ooonana/xorg-fbdev.conf'
assert_contains "$start_script" 'rm -f /etc/X11/xorg.conf.d/20-ooonana-video.conf'

i3_smoke_session="$(<"$rootfs/usr/bin/ooonana-i3-smoke-session")"
assert_contains "$i3_smoke_session" "i3-msg exit"
assert_contains "$i3_smoke_session" "OOONANA_FULL_I3_OK"
assert_contains "$i3_smoke_session" "/dev/ttyS0"
assert_contains "$i3_smoke_session" "# i3 config file (v4)"
assert_contains "$i3_smoke_session" "exec i3"

i3_session="$(<"$rootfs/usr/bin/ooonana-i3-session")"
assert_contains "$i3_session" "ooonana-setup --first-boot --gui"
assert_contains "$i3_session" "setup.log"
assert_contains "$i3_session" '/bin/busybox su -m -s /bin/sh'
assert_contains "$i3_session" 'XDG_RUNTIME_DIR="/run/user/$desktop_uid"'
assert_contains "$i3_session" "--user-session"
assert_contains "$i3_session" "ooonana-audio-start"
assert_contains "$i3_session" 'export LANG="${LANG:-C.UTF-8}"'
assert_contains "$i3_session" 'source_authority="${XAUTHORITY:-${HOME:-/root}/.Xauthority}"'
assert_contains "$i3_session" 'export XAUTHORITY="$target_authority"'
assert_contains "$i3_session" "ooonana-theme-env apply"
assert_contains "$i3_session" "dbus-run-session"
assert_contains "$i3_session" "OOONANA_DBUS_SESSION"
assert_contains "$i3_session" "exec i3"

audio_start="$(<"$rootfs/usr/bin/ooonana-audio-start")"
assert_contains "$audio_start" "pipewire-pulse"
assert_contains "$audio_start" "wireplumber"
assert_contains "$audio_start" "alsactl restore"
assert_contains "$audio_start" 'if [ "${1:-}" = "--restart" ]'

i3_installer_session="$(<"$rootfs/usr/bin/ooonana-i3-installer-session")"
assert_contains "$i3_installer_session" "ooonana-gui-installer"
assert_contains "$i3_installer_session" "ooonana-install-wizard"
assert_contains "$i3_installer_session" "dbus-run-session"
assert_contains "$i3_installer_session" "OOONANA_DBUS_SESSION"
assert_contains "$i3_installer_session" "exec i3"

i3_config="$(<"$rootfs/etc/i3/config")"
assert_contains "$i3_config" 'bindsym $mod+Shift+a exec ooonana-ai-launch'
assert_contains "$i3_config" 'bindsym $mod+Shift+o exec ooonana-packages-app'
assert_contains "$i3_config" "polybar -c /etc/ooonana/polybar.ini ooonana"
assert_contains "$i3_config" "picom --config /etc/ooonana/picom.conf"
assert_contains "$i3_config" "dunst -config /etc/ooonana/dunstrc"
assert_contains "$i3_config" "xsettingsd -c /etc/ooonana/xsettingsd.conf"
assert_contains "$i3_config" "[ -S /run/dbus/system_bus_socket ] && nm-applet --indicator"
assert_contains "$i3_config" "ls /sys/class/bluetooth/hci*"
assert_contains "$i3_config" "then blueman-applet"
assert_contains "$i3_config" "rofi -show drun -theme /etc/ooonana/rofi.rasi"
assert_contains "$i3_config" 'bindsym $mod+d exec ooonana-apps'
assert_contains "$i3_config" 'bindsym $mod+Shift+d exec'
assert_contains "$i3_config" 'bindsym $mod+Shift+f exec ooonana-files'
assert_contains "$i3_config" 'bindsym $mod+Shift+w exec ooonana-browser'
assert_contains "$i3_config" 'bindsym $mod+n exec ooonana-wifi'
assert_contains "$i3_config" 'bindsym $mod+b exec ooonana-bluetooth'
assert_contains "$i3_config" 'bindsym $mod+Shift+p exec ooonana-wallpaper'
assert_contains "$i3_config" 'bindsym Print exec ooonana-screenshot'
assert_contains "$i3_config" 'bindsym $mod+Shift+g exec ooonana-editor'
assert_contains "$i3_config" 'bindsym $mod+Shift+m exec ooonana-music'
assert_contains "$i3_config" 'bindsym $mod+Shift+x exec ooonana-processes'
assert_contains "$i3_config" 'bindsym $mod+Shift+u exec ooonana-ranger'
assert_contains "$i3_config" 'bindsym XF86TouchpadToggle exec ooonana-touchpad toggle'
assert_contains "$i3_config" 'bindsym XF86TouchpadOn exec ooonana-touchpad on'
assert_contains "$i3_config" 'bindsym XF86TouchpadOff exec ooonana-touchpad off'
assert_contains "$i3_config" 'bindsym $mod+minus scratchpad show'
assert_contains "$i3_config" 'bindsym $mod+Shift+minus move scratchpad'
assert_contains "$i3_config" 'default_border normal 2'
assert_contains "$i3_config" 'tiling_drag modifier titlebar'
assert_contains "$i3_config" 'bindsym $mod+r mode "resize"'
assert_contains "$i3_config" 'bindsym $mod+m move scratchpad'

xorg_input="$(<"$rootfs/etc/X11/xorg.conf.d/10-ooonana-input.conf")"
assert_contains "$xorg_input" 'Option "AutoAddDevices" "true"'
assert_contains "$xorg_input" 'MatchIsKeyboard "on"'
assert_contains "$xorg_input" 'MatchIsPointer "on"'
assert_contains "$xorg_input" 'MatchIsTouchpad "on"'
assert_contains "$xorg_input" 'Option "Tapping" "on"'
assert_contains "$xorg_input" 'Option "ClickMethod" "clickfinger"'
assert_contains "$xorg_input" 'Driver "libinput"'

touchpad_helper="$(<"$rootfs/usr/bin/ooonana-touchpad")"
assert_contains "$touchpad_helper" 'Usage: ooonana-touchpad [status|diag|on|off|toggle]'
assert_contains "$touchpad_helper" "xinput set-prop"
assert_contains "$touchpad_helper" "Device Enabled"
assert_contains "$touchpad_helper" "cat /proc/bus/input/devices"

xorg_video="$(<"$rootfs/usr/share/ooonana/xorg-fbdev.conf")"
assert_contains "$xorg_video" 'Driver "fbdev"'
assert_contains "$xorg_video" 'Identifier "Ooonana framebuffer"'

theme_helper="$(<"$rootfs/usr/bin/ooonana-theme-env")"
assert_contains "$theme_helper" 'OOONANA_BG="#050505"'
assert_contains "$theme_helper" 'OOONANA_BG="#ffb21a"'
assert_contains "$theme_helper" "/etc/ooonana/theme"
assert_contains "$theme_helper" ".config/ooonana/wallpaper"
assert_contains "$theme_helper" "hsetroot -cover"
assert_contains "$theme_helper" '-e /bin/sh -l'
assert_contains "$theme_helper" 'exec xterm -bg "$OOONANA_BG" -fg "$OOONANA_FG" -cr "$OOONANA_CURSOR"'
assert_contains "$theme_helper" 'GTK_THEME="%s"'
assert_contains "$theme_helper" 'gtk-application-prefer-dark-theme=$OOONANA_GTK_DARK'
assert_contains "$theme_helper" 'PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"'
assert_not_contains "$theme_helper" 'XTERM_FONT_ARGS="-fa monospace -fs 10"'
assert_not_contains "$theme_helper" '$XTERM_FONT_ARGS -bg "$OOONANA_BG" -fg "$OOONANA_FG"'

yad_wrapper="$(<"$rootfs/usr/local/bin/yad")"
assert_contains "$yad_wrapper" "ooonana-theme-env env"
assert_contains "$yad_wrapper" "--window-icon=/usr/share/ooonana/logo.png"

assert_contains "$(<"$rootfs/etc/gtk-3.0/settings.ini")" "gtk-application-prefer-dark-theme=true"
assert_contains "$(<"$rootfs/root/.config/gtk-3.0/gtk.css")" "button { background: #171e27"
assert_contains "$(<"$rootfs/root/.config/gtk-3.0/gtk.css")" "headerbar"
network_manager_config="$(<"$rootfs/etc/NetworkManager/NetworkManager.conf")"
assert_contains "$network_manager_config" "wifi.scan-rand-mac-address=no"
assert_contains "$network_manager_config" "match-device=type:wifi"
assert_contains "$network_manager_config" "managed=1"
assert_contains "$network_manager_config" "wifi.backend=wpa_supplicant"
assert_contains "$network_manager_config" "auth-polkit=false"
assert_contains "$(<"$rootfs/etc/bluetooth/main.conf")" "AutoEnable = true"

browser_helper="$(<"$rootfs/usr/bin/ooonana-browser")"
assert_contains "$browser_helper" "chromium --no-first-run"
assert_contains "$browser_helper" "--disable-gpu"
assert_contains "$browser_helper" "--disable-software-rasterizer"
assert_contains "$browser_helper" "--disable-features=Vulkan"
assert_contains "$browser_helper" "dbus-run-session"
assert_contains "$browser_helper" "unset DBUS_SESSION_BUS_ADDRESS"
assert_contains "$browser_helper" "chromium.log"
files_helper="$(<"$rootfs/usr/bin/ooonana-files")"
assert_contains "$files_helper" 'exec nemo "$path"'
wifi_helper="$(<"$rootfs/usr/bin/ooonana-wifi")"
assert_contains "$wifi_helper" 'exec ooonana-wifi-panel "$@"'
assert_contains "$wifi_helper" "ooonana-service-repair wifi"
assert_contains "$wifi_helper" "nm-connection-editor"
assert_contains "$wifi_helper" "nmtui"
wifi_panel="$(<"$rootfs/usr/bin/ooonana-wifi-panel")"
assert_contains "$wifi_panel" "ooonana-service-repair wifi"
assert_contains "$wifi_panel" 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
assert_contains "$wifi_panel" "/usr/lib/ooonana/ui/wifi_app.py"
assert_contains "$wifi_panel" 'yad --center --title "Ooonana Wi-Fi"'
assert_contains "$wifi_panel" "--width=760 --height=500"
assert_contains "$wifi_panel" "--list --print-column=1"
assert_contains "$wifi_panel" "needs_repair"
assert_contains "$wifi_panel" "Repair Service"
assert_contains "$wifi_panel" "Open Editor"
assert_contains "$wifi_panel" "Scan Networks"
assert_contains "$wifi_panel" "Turn Wi-Fi On"
assert_not_contains "$wifi_panel" "--image=/usr/share/ooonana/logo.png"
assert_not_contains "$wifi_panel" "--text-info --filename="
assert_contains "$wifi_panel" "nmcli general status"
assert_contains "$wifi_panel" "rfkill list"
assert_contains "$wifi_panel" "nmcli dev wifi list"
bt_helper="$(<"$rootfs/usr/bin/ooonana-bluetooth")"
assert_contains "$bt_helper" 'exec ooonana-bluetooth-panel "$@"'
assert_contains "$bt_helper" "ooonana-service-repair bluetooth"
assert_contains "$bt_helper" "blueman-manager"
bt_panel="$(<"$rootfs/usr/bin/ooonana-bluetooth-panel")"
assert_contains "$bt_panel" "ooonana-service-repair bluetooth"
assert_contains "$bt_panel" 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
assert_contains "$bt_panel" "/usr/lib/ooonana/ui/bluetooth_app.py"
assert_contains "$bt_panel" 'yad --center --title "Ooonana Bluetooth"'
assert_contains "$bt_panel" "--width=760 --height=500"
assert_contains "$bt_panel" "--list --print-column=1"
assert_contains "$bt_panel" "needs_repair"
assert_contains "$bt_panel" "Repair Service"
assert_contains "$bt_panel" "Open Manager"
assert_contains "$bt_panel" "Power On"
assert_not_contains "$bt_panel" "--image=/usr/share/ooonana/logo.png"
assert_not_contains "$bt_panel" "--text-info --filename="
assert_contains "$bt_panel" "rfkill list bluetooth"
assert_contains "$bt_panel" "bluetoothctl devices"
hardware_reprobe="$(<"$rootfs/usr/bin/ooonana-hardware-reprobe")"
assert_contains "$hardware_reprobe" "rfkill unblock all"
assert_contains "$hardware_reprobe" "/sys/class/rfkill/rfkill*/soft"
assert_not_contains "$hardware_reprobe" "/sys/class/rfkill/rfkill*/hard"
assert_contains "$hardware_reprobe" "/sys/bus/pci/rescan"
assert_contains "$hardware_reprobe" "bind_unclaimed_intel_wifi"
assert_contains "$hardware_reprobe" "bind_unclaimed_intel_bluetooth"
assert_contains "$hardware_reprobe" 'printf '\''on'\'' >"$dev/power/control"'
assert_contains "$hardware_reprobe" 'printf '\''1'\'' >"$parent/authorized"'

wireless_diagnose="$(<"$rootfs/usr/bin/ooonana-wireless-diagnose")"
assert_contains "$wireless_diagnose" "intel-wireless-firmware.version"
assert_contains "$wireless_diagnose" "relevant kernel messages"
assert_contains "$wireless_diagnose" "run_limited 6 bluetoothctl show"
assert_contains "$wireless_diagnose" "run_limited 6 nmcli device status"
assert_contains "$hardware_reprobe" "/sys/class/rfkill"
assert_contains "$hardware_reprobe" "iwlwifi"
assert_contains "$hardware_reprobe" "modprobe \"\$module\""
assert_contains "$hardware_reprobe" 'if [ "$force" -eq 1 ]; then'
assert_contains "$hardware_reprobe" "--force-wifi"
assert_contains "$hardware_reprobe" "--force-bluetooth"
assert_contains "$hardware_reprobe" "btusb"
assert_contains "$hardware_reprobe" "uhid"
assert_contains "$hardware_reprobe" "uinput"
assert_contains "$hardware_reprobe" "udevadm trigger"
service_repair="$(<"$rootfs/usr/bin/ooonana-service-repair")"
service_watchdog="$(<"$rootfs/usr/bin/ooonana-service-watchdog")"
admin_helper="$(<"$rootfs/usr/bin/ooonana-run-admin")"
assert_contains "$admin_helper" "sudo -n /bin/true"
assert_contains "$admin_helper" 'exec sudo -n "$@"'
assert_contains "$admin_helper" "doas -n /bin/true"
assert_contains "$service_repair" 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
assert_contains "$service_repair" 'exec ooonana-run-admin "$0" "$@"'
assert_contains "$service_repair" "pulse:x:70"
assert_contains "$service_repair" "pulse-access:x:71"
assert_contains "$service_repair" "11111111111111111111111111111111"
assert_contains "$service_repair" "dbus-daemon --system"
assert_contains "$service_repair" "dbus_ready()"
assert_contains "$service_repair" "/bin/busybox cmp -s /etc/machine-id /var/lib/dbus/machine-id"
assert_not_contains "$(<"$rootfs/etc/init.d/rcS")" "grep -qx '11111111111111111111111111111111'"
assert_contains "$service_repair" "network_manager_daemon()"
assert_contains "$service_repair" "/usr/sbin/NetworkManager"
assert_contains "$service_repair" "network_manager_ready()"
assert_contains "$service_repair" "nmcli -t -f STATE general"
assert_contains "$service_repair" "force-wifi"
assert_contains "$service_repair" "force-bluetooth"
assert_contains "$service_repair" "deep-wifi"
assert_contains "$service_repair" "deep-bluetooth"
assert_contains "$service_repair" "REPROBE_WIFI=0"
assert_contains "$service_repair" "REPROBE_BLUETOOTH=0"
assert_contains "$service_repair" 'run_limited 20 ooonana-hardware-reprobe "$reprobe_mode"'
assert_contains "$service_repair" 'reprobe_mode="--force-wifi"'
assert_contains "$service_repair" 'reprobe_mode="--force-bluetooth"'
assert_contains "$wifi_panel" "ooonana-service-repair force-wifi"
assert_contains "$bt_panel" "ooonana-service-repair force-bluetooth"
assert_contains "$service_repair" "device_manager_running()"
assert_contains "$service_repair" "process_running()"
assert_contains "$service_repair" "/bin/busybox pidof"
assert_contains "$service_repair" "/run/udev/control"
assert_contains "$service_repair" "bluetooth_daemon"
assert_contains "$service_repair" "/usr/lib/bluetooth/bluetoothd"
assert_contains "$service_repair" '"$nm_daemon" --no-daemon'
assert_contains "$service_repair" '"$bt_daemon" -n'
assert_contains "$service_repair" "bluez_ready()"
assert_contains "$service_repair" "org.freedesktop.DBus.GetNameOwner"
assert_contains "$service_repair" "string:org.bluez"
assert_not_contains "$service_repair" "wait_for bluetoothd bluetoothctl show"
assert_contains "$service_repair" "nmcli radio wifi on"
assert_contains "$service_repair" "GENERAL.NM-MANAGED"
assert_contains "$service_repair" "start_wpa_supplicant"
assert_contains "$service_repair" "dbus_activation_helper_ready"
assert_contains "$service_repair" "expected 0:81:4750"
assert_contains "$service_repair" "wait_for_wifi_device"
assert_contains "$service_repair" "org.freedesktop.DBus.StartServiceByName"
assert_contains "$service_repair" "string:fi.w1.wpa_supplicant1"
assert_not_contains "$service_repair" " -f /var/log/wpa_supplicant.log"
assert_not_contains "$service_repair" '"$supplicant" -u'
assert_not_contains "$service_repair" 'nmcli device set "$interface" managed yes'
assert_contains "$service_repair" "/sys/class/rfkill/rfkill*/soft"
assert_not_contains "$service_repair" "/sys/class/rfkill/rfkill*/hard"
assert_not_contains "$service_repair" 'reprobe_mode="boot"'
assert_contains "$service_repair" "bluetoothctl power on"
assert_contains "$service_repair" "btmgmt power on"
assert_contains "$service_repair" "run_limited 20 ooonana-wireless-diagnose"
assert_contains "$service_watchdog" "OOONANA_SERVICE_WATCHDOG_INTERVAL"
assert_contains "$service_watchdog" "network_manager_ready()"
assert_contains "$service_watchdog" "bluez_ready()"
assert_contains "$service_watchdog" "ooonana-service-repair force-wifi"
assert_contains "$service_watchdog" "ooonana-service-repair force-bluetooth"
assert_contains "$service_watchdog" "org.freedesktop.DBus.ListNames"
assert_contains "$service_watchdog" "org.freedesktop.DBus.GetNameOwner"
rofi_power="$(<"$rootfs/usr/bin/ooonana-rofi-power")"
assert_contains "$rofi_power" "Lock"
assert_contains "$rofi_power" "Log out"
assert_contains "$rofi_power" "Restart i3"
assert_contains "$rofi_power" "Reboot"
assert_contains "$rofi_power" "Shut down"
assert_contains "$rofi_power" "Cancel"
assert_contains "$rofi_power" "OOONANA_POWER_MENU_OK"
assert_contains "$rofi_power" "exec bunana --shutdown"
assert_contains "$rofi_power" "exec bunana --restart"
[[ "$(OOONANA_POWER_ACTION=Cancel "$rootfs/usr/bin/ooonana-rofi-power" --dry-run)" == "OOONANA_POWER_MENU_OK" ]] || fail "power menu dry-run failed"
power_menu="$(<"$rootfs/usr/bin/ooonana-power-menu")"
assert_contains "$power_menu" "exec ooonana-rofi-power"
settings_helper="$(<"$rootfs/usr/bin/ooonana-settings")"
settings_launcher="$(<"$rootfs/usr/bin/ooonana-settings-launch")"
assert_contains "$settings_helper" "yad --center --title \"Ooonana Settings\""
assert_contains "$settings_helper" "OOONANA_SETTINGS_GUI_OK"
assert_contains "$settings_helper" "/usr/lib/ooonana/ui/settings_app.py"
assert_contains "$settings_helper" "OOONANA_SETTINGS_NATIVE_OK"
assert_contains "$settings_helper" "OOONANA_SETTINGS_THEME_OK"
assert_contains "$settings_helper" "theme_status"
assert_contains "$settings_helper" "icon grid"
assert_contains "$settings_helper" "--column Icon --column Action"
assert_contains "$settings_helper" "brightness scale"
assert_contains "$settings_helper" "repo"
assert_contains "$settings_helper" "arandr"
assert_contains "$settings_helper" "pavucontrol"
assert_contains "$settings_helper" "ooonana-packages-app"
assert_contains "$settings_helper" "ooonana-ai-app"
assert_contains "$settings_helper" "ooonana-browser"
assert_contains "$settings_helper" "ooonana-files"
assert_contains "$settings_helper" "ooonana-brightness"
assert_contains "$settings_helper" "ooonana-screenshot"
assert_contains "$settings_helper" "status cards"
assert_contains "$settings_helper" "control center layout"
assert_contains "$settings_helper" "settings tabs: Overview System Hardware Apps Ooonana Logs"
assert_contains "$settings_helper" "quick controls: theme wallpaper brightness volume wifi bluetooth display repo"
assert_contains "$settings_helper" "show_overview"
assert_contains "$settings_helper" "choose_settings_action"
assert_contains "$settings_helper" "show_settings_logs"
assert_contains "$settings_helper" "GitLab Pages repo"
assert_contains "$settings_helper" "https://ooonana.gitlab.io/ooonana-repo"
assert_contains "$settings_helper" "Network/Bluetooth/Audio ready"
assert_contains "$settings_helper" "System"
assert_contains "$settings_helper" "Hardware"
assert_contains "$settings_helper" "Applications"
assert_contains "$settings_helper" "Ooonana"
assert_contains "$settings_helper" "XFCE-style control center"
assert_contains "$settings_helper" "settings sidebar"
assert_contains "$settings_helper" "category screen"
assert_contains "$settings_helper" "System Hardware Network Appearance Apps Ooonana Logs"
assert_contains "$settings_helper" "show_category"
assert_contains "$settings_helper" "show_status_cards"
assert_contains "$settings_helper" "settings_status_text"
assert_contains "$settings_helper" "one-window settings hub"
assert_contains "$settings_helper" 'wifi_status="service not ready"'
assert_contains "$settings_helper" 'bluetooth_status="service not ready"'
assert_not_contains "$settings_helper" "show_status_cards || exit 0"
assert_not_contains "$settings_helper" "show_info()"
assert_contains "$settings_helper" "ooonana-wifi-panel"
assert_contains "$settings_helper" "ooonana-bluetooth-panel"
assert_contains "$settings_helper" "ooonana-brightness-panel"
assert_contains "$settings_helper" "ooonana-audio-panel"
assert_contains "$settings_helper" "ooonana-gui-installer"
assert_contains "$settings_launcher" "OOONANA_SETTINGS_LAUNCH_OK"
assert_contains "$settings_launcher" "ooonana-settings"
wallpaper_helper="$(<"$rootfs/usr/bin/ooonana-wallpaper")"
assert_contains "$wallpaper_helper" "feh --bg-fill"
assert_contains "$wallpaper_helper" "hsetroot -cover"
hsetroot_helper="$(<"$rootfs/usr/bin/hsetroot")"
assert_contains "$hsetroot_helper" "feh --bg-fill"
assert_contains "$hsetroot_helper" "xsetroot -solid"
xsettingsd_helper="$(<"$rootfs/usr/bin/xsettingsd")"
assert_contains "$xsettingsd_helper" "Ooonana xsettingsd compatibility daemon"
screenshot_helper="$(<"$rootfs/usr/bin/ooonana-screenshot")"
assert_contains "$screenshot_helper" "maim"
assert_contains "$screenshot_helper" "Pictures/Ooonana"
editor_helper="$(<"$rootfs/usr/bin/ooonana-editor")"
assert_contains "$editor_helper" "geany"
assert_contains "$editor_helper" "vim"
music_helper="$(<"$rootfs/usr/bin/ooonana-music")"
assert_contains "$music_helper" "ncmpcpp"
assert_contains "$music_helper" "mpc"
processes_helper="$(<"$rootfs/usr/bin/ooonana-processes")"
assert_contains "$processes_helper" "htop"
ranger_helper="$(<"$rootfs/usr/bin/ooonana-ranger")"
assert_contains "$ranger_helper" "ranger"
brightness_helper="$(<"$rootfs/usr/bin/ooonana-brightness")"
assert_contains "$brightness_helper" "brightnessctl"
brightness_panel="$(<"$rootfs/usr/bin/ooonana-brightness-panel")"
assert_contains "$brightness_panel" 'yad --scale --title "Brightness"'
assert_contains "$brightness_panel" "--min-value=0 --max-value=100"
audio_panel="$(<"$rootfs/usr/bin/ooonana-audio-panel")"
assert_contains "$audio_panel" 'yad --scale --title "Sound"'
assert_contains "$audio_panel" "pactl set-sink-volume"
audio_status="$(<"$rootfs/usr/bin/ooonana-audio-status")"
assert_contains "$audio_status" "pactl get-sink-volume"
assert_contains "$audio_status" "amixer get Master"
wifi_status="$(<"$rootfs/usr/bin/ooonana-wifi-status")"
assert_contains "$wifi_status" "nmcli -t -f WIFI radio"
bt_status="$(<"$rootfs/usr/bin/ooonana-bluetooth-status")"
assert_contains "$bt_status" "bluetoothctl show"
battery_status="$(<"$rootfs/usr/bin/ooonana-battery-status")"
assert_contains "$battery_status" "printf '%b %s%%"
assert_contains "$bt_status" '2>/dev/null | awk'
brightness_status="$(<"$rootfs/usr/bin/ooonana-brightness-status")"
assert_contains "$brightness_status" "brightnessctl -m"
assert_contains "$brightness_status" ""
assert_contains "$brightness_status" "#"
assert_contains "$brightness_status" "-"
packages_app="$(<"$rootfs/usr/bin/ooonana-packages-app")"
assert_contains "$packages_app" "Ooonana Packages"
assert_contains "$packages_app" "ooonana update"
assert_contains "$packages_app" "ooonana get"
assert_contains "$packages_app" "ooonana remove"

oonana_game="$(<"$rootfs/usr/lib/ooonana/oonana_game.py")"
assert_contains "$oonana_game" "Installer game engine"
assert_contains "$oonana_game" "BRICKS_MAP"
assert_contains "$oonana_game" "BALL_FACES"
assert_contains "$oonana_game" "LOGO_BALL"
assert_contains "$oonana_game" "DEFAULT_WIDTH = 112"
assert_contains "$oonana_game" "def decode_key("
assert_contains "$(<"$rootfs/usr/share/applications/oonana.desktop")" "Exec=ooonana-game-launch"

polybar_cfg="$(<"$rootfs/etc/ooonana/polybar.ini")"
assert_contains "$polybar_cfg" "Ooonana OS"
assert_contains "$polybar_cfg" "#ffb21a"
assert_contains "$polybar_cfg" "#080a0d"
assert_contains "$polybar_cfg" "modules-left = brand workspaces"
assert_contains "$polybar_cfg" "font-1 = \"Font Awesome"
assert_contains "$polybar_cfg" "Font Awesome 6 Brands"
assert_contains "$polybar_cfg" "[module/brand]"
assert_contains "$polybar_cfg" "[module/launcher]"
assert_contains "$polybar_cfg" "[module/terminal]"
assert_contains "$polybar_cfg" "[module/browser]"
assert_contains "$polybar_cfg" "[module/files]"
assert_contains "$polybar_cfg" "[module/editor]"
assert_contains "$polybar_cfg" "[module/media]"
assert_contains "$polybar_cfg" "[module/win-close]"
assert_contains "$polybar_cfg" "click-left = i3-msg kill"
assert_contains "$polybar_cfg" "[module/win-min]"
assert_contains "$polybar_cfg" "click-left = i3-msg move scratchpad"
assert_contains "$polybar_cfg" "click-right = i3-msg scratchpad show"
assert_contains "$polybar_cfg" "[module/win-full]"
assert_contains "$polybar_cfg" "click-left = i3-msg fullscreen toggle"
assert_contains "$polybar_cfg" "modules-left = brand workspaces terminal browser files editor media title win-min win-full win-close"
assert_contains "$polybar_cfg" "modules-right = audio brightness battery bluetooth wifi date power"
assert_contains "$polybar_cfg" "exec = ooonana-audio-status"
assert_contains "$polybar_cfg" "exec = ooonana-wifi-status"
assert_contains "$polybar_cfg" "exec = ooonana-bluetooth-status"
assert_contains "$polybar_cfg" "tray-position = right"
assert_contains "$polybar_cfg" "wm-restack = i3"
assert_contains "$polybar_cfg" "content = Ooonana"
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "[module/wifi]"
assert_contains "$polybar_cfg" "exec = ooonana-wifi-status"
assert_contains "$polybar_cfg" "click-left = ooonana-wifi-panel"
assert_contains "$polybar_cfg" "[module/bluetooth]"
assert_contains "$polybar_cfg" "exec = ooonana-bluetooth-status"
assert_contains "$polybar_cfg" "click-left = ooonana-bluetooth-panel"
assert_contains "$polybar_cfg" "[module/audio]"
assert_contains "$polybar_cfg" "exec = ooonana-audio-status"
assert_contains "$polybar_cfg" "click-left = ooonana-audio-panel"
assert_contains "$polybar_cfg" "[module/brightness]"
assert_contains "$polybar_cfg" "exec = ooonana-brightness-status"
assert_contains "$polybar_cfg" "click-left = ooonana-brightness-panel"
assert_contains "$polybar_cfg" "[module/power]"
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "click-left = ooonana-power-menu"
assert_contains "$polybar_cfg" "label = %time%"

power_menu="$(<"$rootfs/usr/bin/ooonana-power-menu")"
assert_contains "$power_menu" "controls_app.py"
assert_contains "$power_menu" 'exec /usr/bin/python3 "$NATIVE_APP" power'
assert_contains "$power_menu" "ooonana-rofi-power"

i3_keycodes="$(<"$rootfs/etc/i3/config.keycodes")"
assert_contains "$i3_keycodes" "Ooonana OS"
assert_contains "$i3_keycodes" "[ -S /run/dbus/system_bus_socket ] && nm-applet"
assert_contains "$i3_keycodes" "ls /sys/class/bluetooth/hci*"
assert_not_contains "$i3_keycodes" "exec --no-startup-id nm-applet"
assert_contains "$(<"$rootfs/etc/xdg/autostart/nm-applet.desktop")" "Hidden=true"
assert_contains "$(<"$rootfs/etc/xdg/autostart/blueman.desktop")" "Hidden=true"

rofi_cfg="$(<"$rootfs/etc/ooonana/rofi.rasi")"
assert_contains "$rofi_cfg" "show-icons: true"
assert_contains "$rofi_cfg" "Ooonana"
assert_contains "$rofi_cfg" 'display-run: "Ooonana"'
assert_contains "$rofi_cfg" "selected-normal-background: #ffb21a"
assert_contains "$rofi_cfg" "textbox-prompt-colon"
assert_contains "$rofi_cfg" "mode-switcher"
assert_contains "$rofi_cfg" "element selected.active"
assert_contains "$rofi_cfg" "element alternate.normal"
assert_contains "$rofi_cfg" "border-color: #ffb21a"

picom_cfg="$(<"$rootfs/etc/ooonana/picom.conf")"
assert_contains "$picom_cfg" "shadow-radius = 16"
assert_contains "$picom_cfg" "use-damage = true"
assert_contains "$picom_cfg" "unredir-if-possible = true"
assert_contains "$picom_cfg" "shadow = false"
assert_contains "$picom_cfg" "fading = false"
assert_contains "$picom_cfg" "inactive-opacity = 1.0"

dunst_cfg="$(<"$rootfs/etc/ooonana/dunstrc")"
assert_contains "$dunst_cfg" 'origin = top-right'
assert_contains "$dunst_cfg" 'highlight = "#ffb21a"'

gui_installer="$(<"$rootfs/usr/bin/ooonana-gui-installer")"
assert_contains "$gui_installer" "ooonana-installer-gui --dry-run"
assert_contains "$gui_installer" "/usr/bin/ooonana-installer-gui"
assert_contains "$gui_installer" "OOONANA_INSTALL_WIZARD_IN_TERMINAL"
assert_contains "$gui_installer" 'xterm -title "Ooonana Installer"'
assert_contains "$gui_installer" 'OOONANA_THEME:-dark'
assert_contains "$gui_installer" 'XTERM_BG="#050505"'
assert_contains "$gui_installer" '-cr "$XTERM_CURSOR"'
assert_not_contains "$gui_installer" 'XTERM_FONT_ARGS="-fa monospace -fs 10"'
assert_contains "$gui_installer" "ooonana-install-wizard --dry-run"

installer_gui="$(<"$rootfs/usr/bin/ooonana-installer-gui")"
assert_contains "$installer_gui" "yad --center --title \"Install Ooonana OS\""
assert_contains "$installer_gui" "custom-existing-partitions"
assert_contains "$installer_gui" "--home-part"
assert_contains "$installer_gui" "--swap-part"
assert_contains "$installer_gui" "--efi-part"
assert_contains "$installer_gui" "--keep-root"
assert_contains "$installer_gui" "--format-efi"
assert_contains "$installer_gui" "--bootloader grub"
assert_contains "$installer_gui" "Custom partition mode needs an EFI partition"
assert_not_contains "$installer_gui" 'set -- "$@" --bootloader none'
assert_contains "$installer_gui" "OOONANA_INSTALLER_GUI_OK"
assert_contains "$installer_gui" "OOONANA_INSTALL_ALLOW_ROOT_TARGET"
assert_contains "$installer_gui" "Target looks like the current root disk"
assert_contains "$installer_gui" 'set -- ooonana-run-admin "$@"'

install_wizard="$(<"$rootfs/usr/bin/ooonana-install-wizard")"
assert_contains "$install_wizard" "Step 1/8: Target disk"
assert_contains "$install_wizard" "Step 2/8: User account"
assert_contains "$install_wizard" "Step 3/8: Hostname"
assert_contains "$install_wizard" "Step 4/8: Theme"
assert_contains "$install_wizard" "Step 5/8: Package repo"
assert_contains "$install_wizard" "Step 6/8: Source root"
assert_contains "$install_wizard" "Step 7/8: Confirm install"
assert_contains "$install_wizard" "Step 8/8: Installing"
assert_contains "$install_wizard" "Repo picker"
assert_contains "$install_wizard" "Package repo:"
assert_contains "$install_wizard" "https://ooonana.gitlab.io/ooonana-repo"
assert_contains "$install_wizard" "Progress log"
assert_contains "$install_wizard" "OOONANA_INSTALL_WIZARD_FAIL"
assert_contains "$install_wizard" "Fallback shell"
assert_contains "$install_wizard" "Press Enter to reboot"
assert_contains "$install_wizard" "--password-stdin"
assert_contains "$install_wizard" "--cloud-repo"
assert_contains "$install_wizard" "OOONANA_INSTALL_ALLOW_ROOT_TARGET"
assert_contains "$install_wizard" "/usr/sbin/ooonana-install --target"
assert_contains "$install_wizard" "/var/log/ooonana-install-wizard.log"
assert_contains "$install_wizard" 'set -- ooonana-run-admin "$@"'

wizard_dry="$("$rootfs/usr/bin/ooonana-install-wizard" --dry-run --target /dev/vdb --source / --user ryan --hostname ooonana-lab --theme dark --cloud-repo https://example.test/repo)"
assert_contains "$wizard_dry" "Step 1/8 choose target disk: /dev/vdb"
assert_contains "$wizard_dry" "Step 2/8 create user: ryan"
assert_contains "$wizard_dry" "Step 3/8 set hostname: ooonana-lab"
assert_contains "$wizard_dry" "Step 4/8 choose theme: dark"
assert_contains "$wizard_dry" "Step 5/8 choose package repo: https://example.test/repo"
assert_contains "$wizard_dry" "Step 6/8 choose source root: /"
assert_contains "$wizard_dry" "Step 7/8 confirm erase: INSTALL"
assert_contains "$wizard_dry" "Step 8/8 install, log, reboot"
assert_contains "$wizard_dry" "Progress log: "
assert_contains "$wizard_dry" "ooonana-install-wizard.log"
assert_contains "$wizard_dry" "/usr/sbin/ooonana-install --target /dev/vdb --source / --hostname ooonana-lab --user ryan --theme dark --cloud-repo https://example.test/repo --yes"
assert_contains "$wizard_dry" "OOONANA_INSTALL_WIZARD_OK"

gui_dry="$("$rootfs/usr/bin/ooonana-gui-installer" --dry-run)"
assert_contains "$gui_dry" "ooonana-installer-gui --dry-run"
assert_contains "$gui_dry" "xterm -title Ooonana Installer"
assert_contains "$gui_dry" "default theme: dark background, orange cursor"
assert_contains "$gui_dry" "ooonana-install-wizard --dry-run"
assert_contains "$gui_dry" "OOONANA_GUI_INSTALLER_OK"

installer_gui_dry="$("$rootfs/usr/bin/ooonana-installer-gui" --dry-run)"
assert_contains "$installer_gui_dry" "yad installer gui"
assert_contains "$installer_gui_dry" "custom-existing-partitions"
assert_contains "$installer_gui_dry" "custom bootloader: UEFI GRUB requires an EFI partition"
assert_contains "$installer_gui_dry" "OOONANA_INSTALLER_GUI_OK"

settings_dry="$("$rootfs/usr/bin/ooonana-settings" --dry-run)"
assert_contains "$settings_dry" "yad settings menu"
assert_contains "$settings_dry" "packages brightness screenshot editor music processes ranger"
assert_contains "$settings_dry" "ai terminal browser files"
assert_contains "$settings_dry" "status cards: theme wallpaper network bluetooth audio display repo"
assert_contains "$settings_dry" "safe launchers: terminal browser files ai packages"
assert_contains "$settings_dry" "XFCE-style control center"
assert_contains "$settings_dry" "settings sidebar: System Hardware Network Appearance Apps Ooonana Logs"
assert_contains "$settings_dry" "category screens: status cards actions details"
assert_contains "$settings_dry" "OOONANA_SETTINGS_GUI_OK"
assert_contains "$settings_dry" "OOONANA_SETTINGS_NATIVE_OK"
settings_launch_dry="$("$rootfs/usr/bin/ooonana-settings-launch" --dry-run)"
assert_contains "$settings_launch_dry" "OOONANA_SETTINGS_LAUNCH_OK"
packages_dry="$("$rootfs/usr/bin/ooonana-packages-app" --dry-run)"
assert_contains "$packages_dry" "yad packages app"
assert_contains "$packages_dry" "actions: update search install remove upgrade sources doctor"
assert_contains "$packages_dry" "OOONANA_PACKAGES_APP_OK"
assert_contains "$packages_dry" "OOONANA_PACKAGES_NATIVE_OK"
packages_alias_dry="$("$rootfs/usr/bin/ooonana-packages" --dry-run)"
assert_contains "$packages_alias_dry" "OOONANA_PACKAGES_APP_OK"

rcs="$(<"$rootfs/etc/init.d/rcS")"
assert_contains "$rcs" "Ooonana full i3 rootfs"
assert_contains "$rcs" 'installed_output="$(/usr/bin/ooonana list --installed 2>&1)" || cli_ok=0'
assert_contains "$rcs" "mount -t devpts devpts /dev/pts"
assert_contains "$rcs" "mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /dev/shm"
assert_contains "$rcs" "ln -s /run /var/run"
assert_contains "$rcs" "read -r host </etc/hostname"
assert_contains "$rcs" "start_device_manager()"
assert_contains "$rcs" "udevd --daemon"
assert_contains "$rcs" "udevadm trigger"
assert_contains "$rcs" "udevadm settle"
assert_contains "$rcs" "mdev -s"
assert_contains "$rcs" "start_system_services()"
assert_contains "$rcs" "ooonana-service-repair boot"
assert_contains "$rcs" "start_service_watchdog()"
assert_contains "$rcs" "ooonana-service-watchdog"
assert_not_contains "$rcs" "ooonana-service-repair force"
assert_not_contains "$rcs" "dbus-daemon --system --fork --nopidfile"
assert_not_contains "$rcs" "NetworkManager --no-daemon"
assert_not_contains "$rcs" "org.freedesktop.DBus.StartServiceByName"
assert_not_contains "$rcs" '"$wpa_daemon" -u'
assert_not_contains "$rcs" " -f /var/log/wpa_supplicant.log"
assert_contains "$rcs" "start_network_fallback()"
assert_contains "$rcs" "pidof NetworkManager"
assert_contains "$rcs" "udhcpc -q -n -i"
assert_contains "$rcs" "nameserver 1.1.1.1"
assert_contains "$rcs" "configure_cpu_scaling()"
assert_contains "$rcs" 'scaling_available_governors'
assert_contains "$rcs" 'governor="schedutil"'
assert_contains "$rcs" 'governor="ondemand"'
assert_contains "$rcs" 'sched_autogroup_enabled'
assert_contains "$rcs" "start_persistence()"
assert_contains "$rcs" "ooonana.persistence=1"
assert_contains "$rcs" "OOONANA_PERSIST"
assert_contains "$rcs" "OOONANA_PERSISTENCE_OK"
assert_contains "$rcs" "udevadm settle --timeout=1"
assert_contains "$rcs" "/mnt/persist/network-connections"
assert_contains "$rcs" "/etc/NetworkManager/system-connections"
assert_contains "$rcs" "/mnt/persist/var-lib-bluetooth"
assert_contains "$rcs" "seed_persistent_dir()"
assert_contains "$rcs" 'persist_wait" -lt 12'
assert_contains "$rcs" "blkid -L OOONANA_PERSIST"
assert_contains "$rcs" "seed_persistent_dir etc-ooonana /etc/ooonana /mnt/persist/etc-ooonana"
assert_contains "$rcs" "seed_persistent_dir package-state /var/lib/ooonana /mnt/persist/var-lib-ooonana"
assert_contains "$rcs" '.ooonana-seeded-$key'
assert_contains "$rcs" "ensure_glib_schemas()"
assert_contains "$rcs" "gschemas.compiled"
assert_contains "$rcs" "glib-compile-schemas /usr/share/glib-2.0/schemas"
assert_contains "$rcs" "refresh_gtk_caches()"
assert_contains "$rcs" "update-mime-database /usr/share/mime"
assert_contains "$rcs" "gdk-pixbuf-query-loaders"
assert_contains "$rcs" "loaders.cache"
assert_contains "$rcs" '[ ! -s /usr/share/mime/mime.cache ]'
assert_contains "$rcs" '[ ! -s /usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache ]'
assert_contains "$rcs" '[ -s "$theme/icon-theme.cache" ] && continue'
assert_contains "$rcs" '/var/cache/fontconfig/*.cache-*'
assert_not_contains "$rcs" 'fc-cache -r /usr/share/fonts'
assert_contains "$rcs" "/usr/bin/start-ooonana-i3"
assert_contains "$rcs" '/usr/bin/start-ooonana-i3 --user "$desktop_user"'
assert_contains "$rcs" "OOONANA_FULL_I3_FAIL"
assert_contains "$rcs" "OOONANA_BOOT_OK"
assert_contains "$rcs" "OOONANA_DOWNLOADERS_OK"
assert_contains "$rcs" "python3 curl wget"
assert_contains "$rcs" "exec /bin/sh -l"

contents="$(tar -tzf "$tmp/ooonana-full-i3-rootfs.tar.gz" | sort)"
assert_contains "$contents" "./etc/init.d/rcS"
assert_contains "$contents" "./etc/ooonana/edition"
assert_contains "$contents" "./etc/ooonana/sources.d/cloud.repo"
assert_contains "$contents" "./usr/bin/ooonana-gui-installer"
assert_contains "$contents" "./usr/bin/ooonana-packages-app"
assert_contains "$contents" "./usr/bin/ooonana-packages"
assert_contains "$contents" "./usr/bin/ooonana-hardware-reprobe"
assert_contains "$contents" "./usr/bin/ooonana-service-repair"
assert_contains "$contents" "./usr/bin/ooonana-install-wizard"
assert_contains "$contents" "./usr/bin/ooonana-ai-app"
assert_contains "$contents" "./usr/bin/ooonana-ai-launch"
assert_contains "$contents" "./usr/bin/hsetroot"
assert_contains "$contents" "./usr/bin/xsettingsd"
assert_contains "$contents" "./usr/bin/ooonana-screenshot"
assert_contains "$contents" "./usr/bin/ooonana-editor"
assert_contains "$contents" "./usr/bin/ooonana-music"
assert_contains "$contents" "./usr/bin/ooonana-processes"
assert_contains "$contents" "./usr/bin/ooonana-ranger"
assert_contains "$contents" "./usr/bin/ooonana-brightness"
assert_contains "$contents" "./usr/bin/ooonana-volume"
assert_contains "$contents" "./usr/bin/ooonana-power-menu"
assert_contains "$contents" "./usr/lib/ooonana/oonana_game.py"
assert_contains "$contents" "./usr/share/applications/oonana.desktop"
assert_contains "$contents" "./usr/share/applications/ooonana-ai.desktop"
assert_contains "$contents" "./usr/share/applications/ooonana-packages.desktop"
assert_contains "$contents" "./usr/bin/ooonana-setup"
assert_contains "$contents" "./usr/bin/ooonana-settings-launch"
assert_contains "$contents" "./usr/bin/ooonana-i3-session"
assert_contains "$contents" "./usr/bin/start-ooonana-i3"
assert_contains "$contents" "./usr/share/ooonana/wallpapers/ooonana-wallpaper.png"
assert_contains "$contents" "./usr/share/ooonana/wallpapers/ooonana-notes.jpg"

shell_script_count=0
while IFS= read -r -d '' generated; do
  interpreter="$(head -n 1 "$generated")"
  case "$interpreter" in
    '#!'*/bash|'#!'*'env bash') bash -n "$generated" ;;
    '#!'*/sh) sh -n "$generated" ;;
    *) continue ;;
  esac
  if [[ "${OOONANA_SHELLCHECK_GENERATED:-0}" = "1" ]] && command -v shellcheck >/dev/null 2>&1; then
    shellcheck -S warning "$generated"
  fi
  shell_script_count=$((shell_script_count + 1))
done < <(find "$rootfs" -type f -perm /111 -print0)
[[ "$shell_script_count" -ge 20 ]] || fail "too few generated shell scripts checked: $shell_script_count"

printf 'ok full-i3-rootfs\n'
