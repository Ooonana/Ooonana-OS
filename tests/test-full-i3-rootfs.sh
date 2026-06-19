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
assert_contains "$script_src" 'cp -a "$ROOT/packages/ooonana/." "$ROOTFS/"'
assert_contains "$script_src" 'cp -a "$REPO/." "$ROOTFS/usr/lib/ooonana/repo/"'
assert_contains "$script_src" 'ooonana" repo index "$ROOTFS/usr/lib/ooonana/repo"'
assert_contains "$script_src" 'ooonana" repo index "$REPO"'
assert_contains "$script_src" "compile_glib_schemas()"
assert_contains "$script_src" 'glib-compile-schemas "$ROOTFS/usr/share/glib-2.0/schemas"'
assert_contains "$script_src" "refresh_gtk_caches()"
assert_contains "$script_src" 'update-mime-database "$ROOTFS/usr/share/mime"'
assert_contains "$script_src" "gdk-pixbuf-query-loaders"
assert_contains "$script_src" "refresh_font_caches()"
assert_contains "$script_src" "mkfontscale"
assert_contains "$script_src" "fc-cache -r /usr/share/fonts"

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
echo ooonana 0.8.0
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
chmod +x "$tmp/payload-fake-i3-bin/usr/bin/fake-i3-bin" 2>/dev/null || true
tar -C "$tmp/payload-fake-i3-bin" -czf "$repo/fake-i3-bin.tar.gz" .
fake_i3_sha="$(sha256sum "$repo/fake-i3-bin.tar.gz" | awk '{print $1}')"
sed -i "s/^OOONANA_PKG_SHA256=.*/OOONANA_PKG_SHA256=\"$fake_i3_sha\"/" "$repo/fake-i3-bin.pkg"

cat > "$repo/i3.pkg" <<'EOF'
OOONANA_PKG_ID="i3"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="i3 profile"
OOONANA_PKG_DEPS="fake-i3-bin"
EOF

cat > "$repo/full-i3.pkg" <<'EOF'
OOONANA_PKG_ID="full-i3"
OOONANA_PKG_VERSION="0.1.0"
OOONANA_PKG_KIND="profile"
OOONANA_PKG_SUMMARY="full i3 profile"
OOONANA_PKG_DEPS="base branding i3"
EOF

"$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$repo" >/dev/null

bash "$SCRIPT" \
  --scratch-rootfs "$scratch" \
  --repo "$repo" \
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
[[ -x "$rootfs/usr/bin/ooonana-rofi-wifi" ]] || fail "missing rofi wifi applet"
[[ -x "$rootfs/usr/bin/ooonana-rofi-bluetooth" ]] || fail "missing rofi bluetooth applet"
[[ -x "$rootfs/usr/bin/ooonana-rofi-brightness" ]] || fail "missing rofi brightness applet"
[[ -x "$rootfs/usr/bin/ooonana-wifi-panel" ]] || fail "missing wifi panel"
[[ -x "$rootfs/usr/bin/ooonana-bluetooth-panel" ]] || fail "missing bluetooth panel"
[[ -x "$rootfs/usr/bin/ooonana-brightness-panel" ]] || fail "missing brightness panel"
[[ -x "$rootfs/usr/bin/ooonana-audio-panel" ]] || fail "missing audio panel"
[[ -x "$rootfs/usr/bin/ooonana-rofi-power" ]] || fail "missing rofi power applet"
[[ -x "$rootfs/usr/bin/ooonana-settings" ]] || fail "missing settings helper"
[[ -x "$rootfs/usr/bin/ooonana-settings-launch" ]] || fail "missing settings launch wrapper"
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
[[ -f "$rootfs/usr/share/ooonana/wallpapers/ooonana-wallpaper.png" ]] || fail "missing rootfs wallpaper"
[[ -f "$rootfs/etc/i3/config" ]] || fail "missing rootfs i3 config"
[[ -f "$rootfs/etc/ooonana/polybar.ini" ]] || fail "missing polybar config"
[[ -f "$rootfs/etc/ooonana/rofi.rasi" ]] || fail "missing rofi config"
[[ -f "$rootfs/etc/ooonana/picom.conf" ]] || fail "missing picom config"
[[ -f "$rootfs/etc/ooonana/dunstrc" ]] || fail "missing dunst config"
[[ -f "$rootfs/etc/ooonana/xsettingsd.conf" ]] || fail "missing xsettingsd config"
[[ -f "$rootfs/etc/neofetch/config.conf" ]] || fail "missing neofetch config"
[[ -f "$rootfs/etc/X11/xorg.conf.d/10-ooonana-input.conf" ]] || fail "missing Xorg input config"
[[ -f "$rootfs/usr/share/applications/ooonana-installer.desktop" ]] || fail "missing GUI installer desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-ai.desktop" ]] || fail "missing AI app desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-packages.desktop" ]] || fail "missing package app desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-setup.desktop" ]] || fail "missing setup desktop entry"
[[ -f "$rootfs/usr/share/applications/ooonana-settings.desktop" ]] || fail "missing settings desktop entry"
[[ -f "$rootfs/usr/share/applications/oonana.desktop" ]] || fail "missing game desktop entry"
[[ -d "$rootfs/var/log" ]] || fail "missing var log for Xorg"
[[ "$(readlink "$rootfs/bin/mkdir")" == "busybox" ]] || fail "init mkdir must use busybox"
[[ "$(readlink "$rootfs/bin/cat")" == "busybox" ]] || fail "init cat must use busybox"
[[ "$(readlink "$rootfs/bin/sleep")" == "busybox" ]] || fail "init sleep must use busybox"
[[ "$(readlink "$rootfs/usr/bin/env")" == "../../bin/busybox" ]] || fail "env must use busybox"
assert_contains "$(<"$rootfs/etc/group")" "tty:x:5:"
assert_contains "$(<"$rootfs/etc/group")" "input:x:97:"
assert_contains "$(<"$rootfs/etc/group")" "tape:x:26:"
assert_contains "$(<"$rootfs/etc/group")" "kvm:x:34:"
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
assert_contains "$start_script" 'HOME="/root"'
assert_contains "$start_script" 'touch "$HOME/.Xauthority"'
assert_contains "$start_script" 'exec /bin/sh -l'

i3_smoke_session="$(<"$rootfs/usr/bin/ooonana-i3-smoke-session")"
assert_contains "$i3_smoke_session" "i3-msg exit"
assert_contains "$i3_smoke_session" "OOONANA_FULL_I3_OK"
assert_contains "$i3_smoke_session" "/dev/ttyS0"
assert_contains "$i3_smoke_session" "# i3 config file (v4)"
assert_contains "$i3_smoke_session" "exec i3"

i3_session="$(<"$rootfs/usr/bin/ooonana-i3-session")"
assert_contains "$i3_session" "ooonana-setup --first-boot --gui"
assert_contains "$i3_session" "/var/log/ooonana-setup.log"
assert_contains "$i3_session" "ooonana-theme-env apply"
assert_contains "$i3_session" "exec i3"

i3_installer_session="$(<"$rootfs/usr/bin/ooonana-i3-installer-session")"
assert_contains "$i3_installer_session" "ooonana-gui-installer"
assert_contains "$i3_installer_session" "ooonana-install-wizard"
assert_contains "$i3_installer_session" "exec i3"

i3_config="$(<"$rootfs/etc/i3/config")"
assert_contains "$i3_config" 'bindsym $mod+Shift+a exec ooonana-ai-launch'
assert_contains "$i3_config" 'bindsym $mod+Shift+o exec ooonana-packages-app'
assert_contains "$i3_config" "polybar -c /etc/ooonana/polybar.ini ooonana"
assert_contains "$i3_config" "picom --config /etc/ooonana/picom.conf"
assert_contains "$i3_config" "dunst -config /etc/ooonana/dunstrc"
assert_contains "$i3_config" "xsettingsd -c /etc/ooonana/xsettingsd.conf"
assert_contains "$i3_config" "rofi -show drun -theme /etc/ooonana/rofi.rasi"
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

xorg_input="$(<"$rootfs/etc/X11/xorg.conf.d/10-ooonana-input.conf")"
assert_contains "$xorg_input" 'Option "AutoAddDevices" "true"'
assert_contains "$xorg_input" 'MatchIsKeyboard "on"'
assert_contains "$xorg_input" 'MatchIsPointer "on"'
assert_contains "$xorg_input" 'Driver "libinput"'

theme_helper="$(<"$rootfs/usr/bin/ooonana-theme-env")"
assert_contains "$theme_helper" 'OOONANA_BG="#050505"'
assert_contains "$theme_helper" 'OOONANA_BG="#ffb21a"'
assert_contains "$theme_helper" "/etc/ooonana/theme"
assert_contains "$theme_helper" ".config/ooonana/wallpaper"
assert_contains "$theme_helper" "hsetroot -cover"
assert_contains "$theme_helper" '-e /bin/sh -l'
assert_contains "$theme_helper" 'exec xterm -bg "$OOONANA_BG" -fg "$OOONANA_FG" -cr "$OOONANA_CURSOR"'
assert_not_contains "$theme_helper" 'XTERM_FONT_ARGS="-fa monospace -fs 10"'
assert_not_contains "$theme_helper" '$XTERM_FONT_ARGS -bg "$OOONANA_BG" -fg "$OOONANA_FG"'

browser_helper="$(<"$rootfs/usr/bin/ooonana-browser")"
assert_contains "$browser_helper" "chromium --no-first-run"
files_helper="$(<"$rootfs/usr/bin/ooonana-files")"
assert_contains "$files_helper" 'exec nemo "$path"'
wifi_helper="$(<"$rootfs/usr/bin/ooonana-wifi")"
assert_contains "$wifi_helper" "nm-connection-editor"
assert_contains "$wifi_helper" "nmtui"
wifi_panel="$(<"$rootfs/usr/bin/ooonana-wifi-panel")"
assert_contains "$wifi_panel" 'yad --center --title "Wi-Fi"'
assert_contains "$wifi_panel" "--width=420 --height=280"
assert_contains "$wifi_panel" "nmcli dev wifi list"
bt_helper="$(<"$rootfs/usr/bin/ooonana-bluetooth")"
assert_contains "$bt_helper" "blueman-manager"
bt_panel="$(<"$rootfs/usr/bin/ooonana-bluetooth-panel")"
assert_contains "$bt_panel" 'yad --center --title "Bluetooth"'
assert_contains "$bt_panel" "--width=420 --height=280"
assert_contains "$bt_panel" "bluetoothctl devices"
settings_helper="$(<"$rootfs/usr/bin/ooonana-settings")"
settings_launcher="$(<"$rootfs/usr/bin/ooonana-settings-launch")"
assert_contains "$settings_helper" "yad --center --title \"Ooonana Settings\""
assert_contains "$settings_helper" "OOONANA_SETTINGS_GUI_OK"
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
brightness_status="$(<"$rootfs/usr/bin/ooonana-brightness-status")"
assert_contains "$brightness_status" "brightnessctl -m"
assert_contains "$brightness_status" ""
assert_contains "$brightness_status" "━"
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
assert_contains "$(<"$rootfs/usr/share/applications/oonana.desktop")" "Exec=oonana"

polybar_cfg="$(<"$rootfs/etc/ooonana/polybar.ini")"
assert_contains "$polybar_cfg" "Ooonana OS"
assert_contains "$polybar_cfg" "#ffb21a"
assert_contains "$polybar_cfg" "#10141a"
assert_contains "$polybar_cfg" "font-1 = \"Font Awesome"
assert_contains "$polybar_cfg" "Font Awesome 6 Brands"
assert_contains "$polybar_cfg" "[module/brand]"
assert_contains "$polybar_cfg" "[module/launcher]"
assert_contains "$polybar_cfg" "[module/terminal]"
assert_contains "$polybar_cfg" "[module/browser]"
assert_contains "$polybar_cfg" "[module/files]"
assert_contains "$polybar_cfg" "[module/editor]"
assert_contains "$polybar_cfg" "[module/media]"
assert_contains "$polybar_cfg" "modules-left = brand terminal browser files editor media title"
assert_contains "$polybar_cfg" "modules-right = audio brightness battery bluetooth network wifi date power"
assert_contains "$polybar_cfg" "tray-position = right"
assert_contains "$polybar_cfg" "wm-restack = i3"
assert_contains "$polybar_cfg" "content = Ooonana"
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "[module/wifi]"
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "click-left = ooonana-wifi-panel"
assert_contains "$polybar_cfg" "[module/bluetooth]"
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "click-left = ooonana-bluetooth-panel"
assert_contains "$polybar_cfg" "[module/audio]"
assert_contains "$polybar_cfg" "format-volume =  <label-volume>"
assert_contains "$polybar_cfg" "click-left = ooonana-audio-panel"
assert_contains "$polybar_cfg" "[module/brightness]"
assert_contains "$polybar_cfg" "exec = ooonana-brightness-status"
assert_contains "$polybar_cfg" "click-left = ooonana-brightness-panel"
assert_contains "$polybar_cfg" "[module/power]"
assert_contains "$polybar_cfg" "content = "
assert_contains "$polybar_cfg" "click-left = ooonana-rofi-power"
assert_contains "$polybar_cfg" "label = %time%"

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
assert_contains "$picom_cfg" "inactive-opacity = 0.94"

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
assert_contains "$installer_gui" "OOONANA_INSTALLER_GUI_OK"
assert_contains "$installer_gui" "OOONANA_INSTALL_ALLOW_ROOT_TARGET"
assert_contains "$installer_gui" "Target looks like the current root disk"

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

wizard_dry="$("$rootfs/usr/bin/ooonana-install-wizard" --dry-run --target /dev/vdb --source / --user ryan --hostname ooonana-lab --theme dark --cloud-repo https://example.test/repo)"
assert_contains "$wizard_dry" "Step 1/8 choose target disk: /dev/vdb"
assert_contains "$wizard_dry" "Step 2/8 create user: ryan"
assert_contains "$wizard_dry" "Step 3/8 set hostname: ooonana-lab"
assert_contains "$wizard_dry" "Step 4/8 choose theme: dark"
assert_contains "$wizard_dry" "Step 5/8 choose package repo: https://example.test/repo"
assert_contains "$wizard_dry" "Step 6/8 choose source root: /"
assert_contains "$wizard_dry" "Step 7/8 confirm erase: INSTALL"
assert_contains "$wizard_dry" "Step 8/8 install, log, reboot"
assert_contains "$wizard_dry" "Progress log: /var/log/ooonana-install-wizard.log"
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
assert_contains "$installer_gui_dry" "OOONANA_INSTALLER_GUI_OK"

settings_dry="$("$rootfs/usr/bin/ooonana-settings" --dry-run)"
assert_contains "$settings_dry" "yad settings menu"
assert_contains "$settings_dry" "packages brightness screenshot editor music processes ranger"
assert_contains "$settings_dry" "ai terminal browser files"
assert_contains "$settings_dry" "status cards: theme wallpaper network bluetooth audio display repo"
assert_contains "$settings_dry" "safe launchers: terminal browser files ai packages"
assert_contains "$settings_dry" "OOONANA_SETTINGS_GUI_OK"
settings_launch_dry="$("$rootfs/usr/bin/ooonana-settings-launch" --dry-run)"
assert_contains "$settings_launch_dry" "OOONANA_SETTINGS_LAUNCH_OK"
packages_dry="$("$rootfs/usr/bin/ooonana-packages-app" --dry-run)"
assert_contains "$packages_dry" "yad packages app"
assert_contains "$packages_dry" "actions: update search install remove upgrade sources doctor"
assert_contains "$packages_dry" "OOONANA_PACKAGES_APP_OK"

rcs="$(<"$rootfs/etc/init.d/rcS")"
assert_contains "$rcs" "Ooonana full i3 rootfs"
assert_contains "$rcs" "mount -t devpts devpts /dev/pts"
assert_contains "$rcs" "read -r host </etc/hostname"
assert_contains "$rcs" "start_device_manager()"
assert_contains "$rcs" "udevd --daemon"
assert_contains "$rcs" "udevadm trigger"
assert_contains "$rcs" "udevadm settle"
assert_contains "$rcs" "mdev -s"
assert_contains "$rcs" "start_persistence()"
assert_contains "$rcs" "ooonana.persistence=1"
assert_contains "$rcs" "OOONANA_PERSIST"
assert_contains "$rcs" "OOONANA_PERSISTENCE_OK"
assert_contains "$rcs" "ensure_glib_schemas()"
assert_contains "$rcs" "gschemas.compiled"
assert_contains "$rcs" "glib-compile-schemas /usr/share/glib-2.0/schemas"
assert_contains "$rcs" "refresh_gtk_caches()"
assert_contains "$rcs" "update-mime-database /usr/share/mime"
assert_contains "$rcs" "gdk-pixbuf-query-loaders"
assert_contains "$rcs" "loaders.cache"
assert_contains "$rcs" "/usr/bin/start-ooonana-i3"
assert_contains "$rcs" "OOONANA_FULL_I3_FAIL"
assert_contains "$rcs" "OOONANA_BOOT_OK"
assert_contains "$rcs" "exec /bin/sh -l"

contents="$(tar -tzf "$tmp/ooonana-full-i3-rootfs.tar.gz" | sort)"
assert_contains "$contents" "./etc/init.d/rcS"
assert_contains "$contents" "./etc/ooonana/edition"
assert_contains "$contents" "./etc/ooonana/sources.d/cloud.repo"
assert_contains "$contents" "./usr/bin/ooonana-gui-installer"
assert_contains "$contents" "./usr/bin/ooonana-packages-app"
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
assert_contains "$contents" "./usr/lib/ooonana/oonana_game.py"
assert_contains "$contents" "./usr/share/applications/oonana.desktop"
assert_contains "$contents" "./usr/share/applications/ooonana-ai.desktop"
assert_contains "$contents" "./usr/share/applications/ooonana-packages.desktop"
assert_contains "$contents" "./usr/bin/ooonana-setup"
assert_contains "$contents" "./usr/bin/ooonana-settings-launch"
assert_contains "$contents" "./usr/bin/ooonana-i3-session"
assert_contains "$contents" "./usr/bin/start-ooonana-i3"
assert_contains "$contents" "./usr/share/ooonana/wallpapers/ooonana-wallpaper.png"

printf 'ok full-i3-rootfs\n'
