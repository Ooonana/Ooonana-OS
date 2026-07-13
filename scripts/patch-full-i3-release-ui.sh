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
  local tmp group_name
  mkdir -p "$identity"

  debugfs -R "cat /etc/group" "$image" > "$identity/group" 2>/dev/null ||
    printf '%s\n' 'root:x:0:' > "$identity/group"
  grep -q '^messagebus:' "$identity/group" 2>/dev/null ||
    printf '%s\n' 'messagebus:x:81:' >> "$identity/group"
  for entry in \
    'wheel:x:10:' \
    'audio:x:29:' \
    'video:x:44:' \
    'input:x:97:' \
    'lp:x:7:' \
    'users:x:100:' \
    'netdev:x:101:' \
    'plugdev:x:102:' \
    'ooonana:x:1000:'; do
    group_name="${entry%%:*}"
    grep -q "^$group_name:" "$identity/group" 2>/dev/null ||
      printf '%s\n' "$entry" >> "$identity/group"
  done
  for group_name in wheel audio video input lp users netdev plugdev; do
    tmp="$identity/group.tmp"
    awk -F: -v OFS=: -v group_name="$group_name" '
      $1 == group_name {
        n = split($4, members, ",")
        found = 0
        for (i = 1; i <= n; i++) if (members[i] == "ooonana") found = 1
        if (!found) $4 = ($4 == "" ? "ooonana" : $4 ",ooonana")
      }
      { print }
    ' "$identity/group" > "$tmp"
    mv "$tmp" "$identity/group"
  done
  write_debugfs_file "$image" "$identity/group" /etc/group 0100644

  debugfs -R "cat /etc/passwd" "$image" > "$identity/passwd" 2>/dev/null ||
    printf '%s\n' 'root:x:0:0:root:/root:/bin/sh' > "$identity/passwd"
  grep -q '^messagebus:' "$identity/passwd" 2>/dev/null ||
    printf '%s\n' 'messagebus:x:81:81:DBus Message Bus:/run/dbus:/bin/false' >> "$identity/passwd"
  grep -q '^ooonana:' "$identity/passwd" 2>/dev/null ||
    printf '%s\n' 'ooonana:x:1000:1000:Ooonana Live User:/home/ooonana:/bin/sh' >> "$identity/passwd"
  write_debugfs_file "$image" "$identity/passwd" /etc/passwd 0100644

  debugfs -R "cat /etc/shadow" "$image" > "$identity/shadow" 2>/dev/null ||
    printf '%s\n' 'root:*:20000:0:99999:7:::' > "$identity/shadow"
  grep -q '^ooonana:' "$identity/shadow" 2>/dev/null ||
    printf '%s\n' 'ooonana:!:20000:0:99999:7:::' >> "$identity/shadow"
  write_debugfs_file "$image" "$identity/shadow" /etc/shadow 0100600

  printf '%s\n' 'ooonana' > "$identity/default-user"
  write_debugfs_file "$image" "$identity/default-user" /etc/ooonana/default-user 0100644

  for path in \
    /home /home/ooonana /home/ooonana/.config /home/ooonana/.config/ooonana \
    /home/ooonana/.cache /home/ooonana/.local /home/ooonana/.local/state \
    /home/ooonana/.local/state/ooonana /home/ooonana/Desktop \
    /home/ooonana/Downloads /home/ooonana/Pictures /home/ooonana/Pictures/Ooonana; do
    debugfs -w -R "mkdir \"$path\"" "$image" >/dev/null 2>&1 || true
  done
  for path in \
    /home/ooonana /home/ooonana/.config /home/ooonana/.config/ooonana \
    /home/ooonana/.cache /home/ooonana/.local /home/ooonana/.local/state \
    /home/ooonana/.local/state/ooonana /home/ooonana/Desktop \
    /home/ooonana/Downloads /home/ooonana/Pictures /home/ooonana/Pictures/Ooonana; do
    debugfs -w -R "sif \"$path\" uid 1000" "$image" >/dev/null
    debugfs -w -R "sif \"$path\" gid 1000" "$image" >/dev/null
    debugfs -w -R "sif \"$path\" mode 040755" "$image" >/dev/null
  done

  printf '%s\n' '11111111111111111111111111111111' > "$identity/machine-id"
  write_debugfs_file "$image" "$identity/machine-id" /etc/machine-id 0100644
  write_debugfs_file "$image" "$identity/machine-id" /var/lib/dbus/machine-id 0100644
}

normalize_ext4_permissions() {
  local image="$1"
  local mount_dir="$WORK/normalize-mnt"
  mkdir -p "$mount_dir"
  if mountpoint -q "$mount_dir" 2>/dev/null; then
    umount "$mount_dir"
  fi
  mount -o loop "$image" "$mount_dir"
  rm -rf "$mount_dir/var/run"
  ln -s ../run "$mount_dir/var/run"
  if ! chmod -R go-w "$mount_dir"; then
    umount "$mount_dir" 2>/dev/null || true
    return 1
  fi
  chmod 1777 "$mount_dir/tmp" "$mount_dir/var/tmp" 2>/dev/null || true
  chmod 4755 "$mount_dir/usr/bin/doas" 2>/dev/null || true
  chmod 4755 "$mount_dir/usr/lib/chromium/chrome-sandbox" 2>/dev/null || true
  chown -R 1000:1000 "$mount_dir/home/ooonana" 2>/dev/null || true
  if [ -x "$mount_dir/usr/bin/fc-cache" ]; then
    chroot "$mount_dir" /usr/bin/fc-cache -r /usr/share/fonts >/dev/null 2>&1 || true
  fi
  sync
  umount "$mount_dir"
}

repair_ext4_image() {
  local image="$1"
  local rc
  set +e
  e2fsck -fy "$image" >/dev/null 2>&1
  rc=$?
  set -e
  if [ "$rc" -gt 1 ]; then
    printf 'e2fsck failed for %s (exit %s)\n' "$image" "$rc" >&2
    exit "$rc"
  fi
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
ooonana-hardware-reprobe|/usr/bin/ooonana-hardware-reprobe|0100755
ooonana-service-repair|/usr/bin/ooonana-service-repair|0100755
ooonana-run-admin|/usr/bin/ooonana-run-admin|0100755
start-ooonana-i3|/usr/bin/start-ooonana-i3|0100755
ooonana-apps|/usr/bin/ooonana-apps|0100755
ooonana-wifi|/usr/bin/ooonana-wifi|0100755
ooonana-wifi-panel|/usr/bin/ooonana-wifi-panel|0100755
ooonana-wifi-status|/usr/bin/ooonana-wifi-status|0100755
ooonana-bluetooth|/usr/bin/ooonana-bluetooth|0100755
ooonana-bluetooth-panel|/usr/bin/ooonana-bluetooth-panel|0100755
ooonana-bluetooth-status|/usr/bin/ooonana-bluetooth-status|0100755
ooonana-brightness-panel|/usr/bin/ooonana-brightness-panel|0100755
ooonana-audio-panel|/usr/bin/ooonana-audio-panel|0100755
ooonana-audio-status|/usr/bin/ooonana-audio-status|0100755
ooonana-battery-status|/usr/bin/ooonana-battery-status|0100755
ooonana-volume|/usr/bin/ooonana-volume|0100755
ooonana-rofi-power|/usr/bin/ooonana-rofi-power|0100755
ooonana-power-menu|/usr/bin/ooonana-power-menu|0100755
ooonana-brightness|/usr/bin/ooonana-brightness|0100755
ooonana-brightness-status|/usr/bin/ooonana-brightness-status|0100755
ooonana|/usr/bin/ooonana|0100755
oonana|/usr/bin/oonana|0100755
oonana_game.py|/usr/lib/ooonana/oonana_game.py|0100755
ooonana-packages-app|/usr/bin/ooonana-packages-app|0100755
ooonana-packages|/usr/bin/ooonana-packages|0100755
ooonana-settings|/usr/bin/ooonana-settings|0100755
ooonana-settings-launch|/usr/bin/ooonana-settings-launch|0100755
ooonana-theme-env|/usr/bin/ooonana-theme-env|0100755
yad-wrapper|/usr/local/bin/yad|0100755
gtk-settings.ini|/etc/gtk-3.0/settings.ini|0100644
gtk-root-settings.ini|/root/.config/gtk-3.0/settings.ini|0100644
gtk.css|/root/.config/gtk-3.0/gtk.css|0100644
NetworkManager.conf|/etc/NetworkManager/NetworkManager.conf|0100644
bluetooth-main.conf|/etc/bluetooth/main.conf|0100644
ooonana-setup|/usr/bin/ooonana-setup|0100755
wget|/usr/bin/wget|0100755
ooonana-gui-installer|/usr/bin/ooonana-gui-installer|0100755
ooonana-installer-gui|/usr/bin/ooonana-installer-gui|0100755
ooonana-install-wizard|/usr/bin/ooonana-install-wizard|0100755
ooonana-install|/usr/sbin/ooonana-install|0100755
ooonana-bunana|/usr/bin/bunana|0100755
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
  write_debugfs_symlink "$image" python3 /usr/bin/python
  patch_identity_files "$image"
  repair_ext4_image "$image"
  normalize_ext4_permissions "$image"
}

build_payload() {
  local payload="$1"
  rm -rf "$payload"
  mkdir -p "$payload/root"
  install -D -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/boot-logo.txt" "$payload/root/usr/share/ooonana/boot-logo.txt"
  install -D -m 0644 "$ROOT/packages/ooonana/var/lib/ooonana/packages/installed/ooonana-core.pkg" "$payload/root/var/lib/ooonana/packages/installed/ooonana-core.pkg"
  install -D -m 0644 /dev/stdin "$payload/root/usr/share/dbus-1/system-services/org.blueman.Mechanism.service" <<'EOF'
[D-BUS Service]
Name=org.blueman.Mechanism
Exec=/usr/libexec/blueman-mechanism
User=root
EOF
  install -D -m 0644 /dev/stdin "$payload/root/etc/os-release" <<'EOF'
NAME="Ooonana OS"
ID=ooonana
PRETTY_NAME="Ooonana OS 0.1.8"
VERSION="0.1.8"
VERSION_ID="0.1.8"
HOME_URL="https://github.com/Ooonana/Ooonana-OS"
SUPPORT_URL="https://github.com/Ooonana/Ooonana-OS/issues"
EOF

  if [ -n "$KERNEL_OVERRIDE" ]; then
    test -f "$KERNEL_OVERRIDE" || { printf 'missing kernel override: %s\n' "$KERNEL_OVERRIDE" >&2; exit 1; }
    install -D -m 0644 "$KERNEL_OVERRIDE" "$payload/root/boot/vmlinuz"
  fi

  extract_block '$ROOTFS/usr/bin/ooonana-rofi-wifi' "$payload/ooonana-rofi-wifi"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-bluetooth' "$payload/ooonana-rofi-bluetooth"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-brightness' "$payload/ooonana-rofi-brightness"
  extract_block '$ROOTFS/usr/bin/ooonana-hardware-reprobe' "$payload/ooonana-hardware-reprobe"
  extract_block '$ROOTFS/usr/bin/ooonana-service-repair' "$payload/ooonana-service-repair"
  extract_block '$ROOTFS/usr/bin/ooonana-run-admin' "$payload/ooonana-run-admin"
  extract_block '$ROOTFS/usr/bin/start-ooonana-i3' "$payload/start-ooonana-i3"
  extract_block '$ROOTFS/usr/bin/ooonana-apps' "$payload/ooonana-apps"
  extract_block '$ROOTFS/usr/bin/ooonana-wifi"' "$payload/ooonana-wifi"
  extract_block '$ROOTFS/usr/bin/ooonana-wifi-panel' "$payload/ooonana-wifi-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-wifi-status' "$payload/ooonana-wifi-status"
  extract_block '$ROOTFS/usr/bin/ooonana-bluetooth"' "$payload/ooonana-bluetooth"
  extract_block '$ROOTFS/usr/bin/ooonana-bluetooth-panel' "$payload/ooonana-bluetooth-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-bluetooth-status' "$payload/ooonana-bluetooth-status"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness-panel' "$payload/ooonana-brightness-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-audio-panel' "$payload/ooonana-audio-panel"
  extract_block '$ROOTFS/usr/bin/ooonana-audio-status' "$payload/ooonana-audio-status"
  extract_block '$ROOTFS/usr/bin/ooonana-battery-status' "$payload/ooonana-battery-status"
  extract_block '$ROOTFS/usr/bin/ooonana-volume' "$payload/ooonana-volume"
  extract_block '$ROOTFS/usr/bin/ooonana-rofi-power' "$payload/ooonana-rofi-power"
  extract_block '$ROOTFS/usr/bin/ooonana-power-menu' "$payload/ooonana-power-menu"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness"' "$payload/ooonana-brightness"
  extract_block '$ROOTFS/usr/bin/ooonana-brightness-status' "$payload/ooonana-brightness-status"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana" "$payload/ooonana"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/oonana" "$payload/oonana"
  install -m 0755 "$ROOT/packages/ooonana/usr/lib/ooonana/oonana_game.py" "$payload/oonana_game.py"
  extract_block '$ROOTFS/usr/bin/ooonana-packages-app' "$payload/ooonana-packages-app"
  extract_block '$ROOTFS/usr/bin/ooonana-packages"' "$payload/ooonana-packages"
  extract_block '$ROOTFS/usr/bin/ooonana-settings"' "$payload/ooonana-settings"
  extract_block '$ROOTFS/usr/bin/ooonana-settings-launch' "$payload/ooonana-settings-launch"
  extract_block '$ROOTFS/usr/bin/ooonana-theme-env' "$payload/ooonana-theme-env"
  extract_block '$ROOTFS/usr/local/bin/yad' "$payload/yad-wrapper"
  extract_block '$ROOTFS/etc/gtk-3.0/settings.ini' "$payload/gtk-settings.ini"
  extract_block '$ROOTFS/root/.config/gtk-3.0/settings.ini' "$payload/gtk-root-settings.ini"
  extract_block '$ROOTFS/root/.config/gtk-3.0/gtk.css' "$payload/gtk.css"
  extract_block '$ROOTFS/etc/NetworkManager/NetworkManager.conf' "$payload/NetworkManager.conf"
  extract_block '$ROOTFS/etc/bluetooth/main.conf' "$payload/bluetooth-main.conf"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/ooonana-setup" "$payload/ooonana-setup"
  cat > "$payload/wget" <<'EOF'
#!/bin/sh
exec /bin/busybox wget "$@"
EOF
  chmod 0755 "$payload/wget"
  extract_block '$ROOTFS/usr/bin/ooonana-gui-installer' "$payload/ooonana-gui-installer"
  extract_block '$ROOTFS/usr/bin/ooonana-installer-gui' "$payload/ooonana-installer-gui"
  extract_block '$ROOTFS/usr/bin/ooonana-install-wizard' "$payload/ooonana-install-wizard"
  install -m 0755 "$ROOT/packages/ooonana/usr/sbin/ooonana-install" "$payload/ooonana-install"
  install -m 0755 "$ROOT/packages/ooonana/usr/bin/bunana" "$payload/ooonana-bunana"
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
  install -D -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/__init__.py" "$payload/root/usr/lib/ooonana/ui/__init__.py"
  for app in common setup_app settings_app wifi_app bluetooth_app packages_app ai_app controls_app launcher_app; do
    install -D -m 0644 "$ROOT/packages/ooonana/usr/lib/ooonana/ui/$app.py" "$payload/root/usr/lib/ooonana/ui/$app.py"
  done
  install -D -m 0644 /dev/stdin "$payload/root/usr/share/applications/ooonana-apps.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Ooonana Applications
Comment=Search and launch installed applications
Exec=ooonana-apps
Icon=/usr/share/ooonana/logo.png
Terminal=false
Categories=System;Utility;
EOF
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
  rm -rf "${payload:?}/etc" "${payload:?}/usr"

  local doas_apk="$WORK/doas.apk"
  wget -q -O "$doas_apk" "https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/doas-6.8.2-r7.apk"
  tar -xzf "$doas_apk" -C "$payload/root" usr/bin/doas
  chmod 4755 "$payload/root/usr/bin/doas"

  local runtime_apk
  for runtime_url in "https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64/networkmanager-wifi-1.46.6-r0.apk" "https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/bluez-btmgmt-5.76-r0.apk" "https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/bluez-hid2hci-5.76-r0.apk" "https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/font-dejavu-2.37-r5.apk"; do
    runtime_apk="$WORK/${runtime_url##*/}"
    wget -q -O "$runtime_apk" "$runtime_url"
    tar -xzf "$runtime_apk" -C "$payload/root"
  done
  rm -f "$payload/root/.PKGINFO" "$payload/root"/.SIGN.* "$payload/root"/.INSTALL 2>/dev/null || true

  install -D -m 0400 /dev/stdin "$payload/root/etc/doas.d/ooonana.conf" <<'EOF'
permit nopass keepenv :wheel
EOF
  install -D -m 0400 /dev/stdin "$payload/root/etc/doas.conf" <<'EOF'
permit nopass keepenv :wheel
EOF
}

patch_live_initramfs() {
  local initramfs="$1"
  local tree="$WORK/live-init-tree"
  local fresh="$WORK/live-initramfs.patched.cpio.gz"
  rm -rf "$tree"
  mkdir -p "$tree"
  (
    cd "$tree"
    gzip -dc "$initramfs" | cpio -idm --quiet
  )
  awk '
    index($0, "cat > \"$LIVE_INIT_TREE/init\" <<") { on = 1; next }
    on && $0 == "EOF" { exit }
    on { print }
  ' "$ROOT/scripts/build-full-i3-live-initramfs.sh" > "$tree/init"
  chmod 0755 "$tree/init"
  install -D -m 0644 "$ROOT/packages/ooonana/usr/share/ooonana/boot-logo.txt" "$tree/usr/share/ooonana/boot-logo.txt"
  ln -sf busybox "$tree/bin/stty"
  ln -sf busybox "$tree/bin/wc"
  (
    cd "$tree"
    find . -print0 | cpio --null -o --format=newc --quiet | gzip -n > "$fresh"
  )
  mv "$fresh" "$initramfs"
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
  patch_live_initramfs "$WORK/live-initramfs.cpio.gz"
  patch_ext4 "$WORK/live-rootfs.ext4" "$WORK/payload"
  patch_disk_image "$WORK/disk.raw" "$WORK/payload"
  build_iso_from_work
}

resume_after_live_rootfs() {
  build_payload "$WORK/payload"
  test -f "$WORK/live-rootfs.ext4" || { printf 'missing live-rootfs.ext4 in %s\n' "$WORK" >&2; exit 1; }
  test -f "$WORK/disk.raw" || { printf 'missing disk.raw in %s\n' "$WORK" >&2; exit 1; }
  test -f "$WORK/live-initramfs.cpio.gz" || { printf 'missing live-initramfs.cpio.gz in %s\n' "$WORK" >&2; exit 1; }
  stage_kernel_override
  patch_disk_image "$WORK/disk.raw" "$WORK/payload"
  build_iso_from_work
}

main() {
  need xorriso
  need debugfs
  need e2fsck
  need grub-mkrescue
  need parted
  need wget
  need tar
  need gzip
  need dd
  need mount
  need mountpoint
  need umount
  need cpio
  need chroot

  test -f "$ISO" || {
    printf 'missing ISO: %s\n' "$ISO" >&2
    exit 1
  }

  if [ "${1:-}" = "--resume-after-extract" ]; then
    resume_after_extract
    exit 0
  fi
  if [ "${1:-}" = "--resume-after-live-rootfs" ]; then
    resume_after_live_rootfs
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
  patch_live_initramfs "$WORK/live-initramfs.cpio.gz"
  extract_iso_file_by_lba /images/ooonana-full-i3-live-rootfs.ext4 "$WORK/live-rootfs.ext4"
  extract_iso_file_by_lba /images/ooonana-full-i3-disk.raw.gz "$WORK/disk.raw.gz"

  patch_ext4 "$WORK/live-rootfs.ext4" "$WORK/payload"
  gzip -dc "$WORK/disk.raw.gz" > "$WORK/disk.raw"
  patch_disk_image "$WORK/disk.raw" "$WORK/payload"
  build_iso_from_work
}

main "$@"
