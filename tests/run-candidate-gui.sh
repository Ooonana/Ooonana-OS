#!/usr/bin/env bash
# Disposable candidate UI gate. Firefox opt-in downloads into owned ext4 only;
# rendered probes always have a private network. Never run installed WSL here.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
only="${OOONANA_GUI_ONLY:-all}"
gui_runtime=/home/ooonana/runtime
# Model the real Linux session's per-user runtime for document-portal fidelity.
if [[ "$only" == firefox-frame ]]; then gui_runtime=/run/user/1000; fi
geometry="${OOONANA_GUI_GEOMETRY:-1280x800}"
theme="${OOONANA_GUI_THEME:-dark}"
text_scale="${OOONANA_GUI_TEXT_SCALE:-1.25}"
device_scale="${OOONANA_GUI_DEVICE_SCALE:-1}"
qt_scale="${OOONANA_GUI_QT_SCALE:-1}"
case "$qt_scale" in 1|1.25|1.5|2) ;; *) printf 'Unsupported Qt test scale: %s\n' "$qt_scale" >&2; exit 2 ;; esac
case "$device_scale" in 1|2) ;; *) printf 'Unsupported device scale: %s\n' "$device_scale" >&2; exit 2 ;; esac
case "$text_scale" in 1.0|1.25|1.5|2.0) ;; *) printf 'Unsupported native text scale: %s\n' "$text_scale" >&2; exit 2 ;; esac
case "$theme" in dark|light) ;; *) printf 'Unsupported test appearance: %s\n' "$theme" >&2; exit 2 ;; esac
case "$geometry" in
  320x600) [[ "$only" == dock-edges-ui ]] || exit 2 ;;
  640x600|760x600|900x600|1000x600|1024x768|1100x600|1280x800|1600x900) ;;
  *) printf 'Unsupported disposable display geometry: %s\n' "$geometry" >&2; exit 2 ;;
esac
case "$only" in
  all|setup-details-ui|controls-details-ui|wireless-details-ui|workspace-ui|task-details-ui|ai-details-ui|control-density-ui|settings-details-ui|settings-storage-ui|settings-power-ui|native-ui-runtime|native-appearance|native-app-catalog|ui-details-runtime|ui-content-runtime|wireless-notification-ui|package-health-ui|admin-prompt-ui|installer-ui|ai-indicators|ai-chat-runtime|desktop-interactions|launcher-session-ui|notifications-runtime|notification-lifecycle|notification-auto-recovery|window-controls-runtime|dock-ui|dock-edges-ui|device-scale-ui|panel-ui|panel-media-runtime|portal-ui|geany-frame|nemo-frame|chromium-frame|qterminal-frame|firefox-frame) ;;
  *) printf 'Unknown GUI probe: %s\n' "$only" >&2; exit 2 ;;
esac

if [[ "${1:-}" != --worker ]]; then
  [[ $# -eq 2 && $EUID -eq 0 ]] || { printf 'Usage (root): %s CANDIDATE_ROOTFS OUTPUT_DIR\n' "$0" >&2; exit 2; }
  rootfs="$(realpath "$1")"
  output="$(realpath "$2")"
  [[ "$rootfs" == /var/tmp/* && "$output" == /var/tmp/* && "$rootfs" != "$output" ]] || exit 2
  grep -qx 'ID=ooonana' "$rootfs/etc/os-release"
  grep -qx 'OOONANA_USERLAND_BASE="alpine-v3.24"' "$rootfs/etc/os-release"
  [[ -x "$rootfs/usr/bin/python3" && -d "$rootfs/source" && -d "$rootfs/qa" ]] || exit 2
  if [[ -n "${OOONANA_GUI_REPO:-}" ]]; then
    OOONANA_GUI_REPO="$(realpath "$OOONANA_GUI_REPO")"
    export OOONANA_GUI_REPO
    [[ "$OOONANA_GUI_REPO" == /var/tmp/* && -f "$OOONANA_GUI_REPO/index.tsv" ]] || exit 2
    [[ "$rootfs$output" != *[:,]* ]] || { printf 'Unsafe overlay path separator\n' >&2; exit 2; }
    case "$output/" in "$rootfs/"*) printf 'Output cannot be inside candidate\n' >&2; exit 2 ;; esac
    # Never install supplemental packages into the preserved candidate cache.
    [[ ! -e "$output/overlay" ]] || { printf 'Overlay output must be fresh\n' >&2; exit 2; }
  fi
  network=(--net)
  limit=600
  if [[ "$only" == firefox-frame ]]; then
    [[ -n "${OOONANA_GUI_REPO:-}" && "${OOONANA_FIREFOX_DOWNLOAD:-0}" == 1 ]] || exit 2
    if [[ -n "${OOONANA_FIREFOX_REUSE_HOME:-}" ]]; then
      reused_home="$(realpath "$OOONANA_FIREFOX_REUSE_HOME")"
      [[ "$reused_home" == /var/tmp/ooonana-firefox-*/storage/home && -d "$reused_home/ooonana/.local/share/flatpak/app/org.mozilla.firefox" ]] || exit 2
      export OOONANA_FIREFOX_REUSE_HOME="$reused_home"
    fi
    if [[ "${OOONANA_FIREFOX_DIRECT_STORAGE:-0}" == 1 ]]; then
      [[ "$(findmnt -n -o FSTYPE -T "$output")" == ext4 ]] || exit 2
      [[ "$(df -B1 --output=avail "$output" | tail -n 1)" -ge 4294967296 ]] || exit 2
    else
    image="$(realpath "${OOONANA_FIREFOX_TEST_IMAGE:?Owned test image required}")"
    # Regular, bounded QA file only. Never a disk, symlink or user installation.
    [[ "$image" == /mnt/winf/Ooonana/ooonana-os/qa-firefox-*/flatpak.ext4 && -f "$image" && ! -L "$OOONANA_FIREFOX_TEST_IMAGE" ]] || exit 2
    [[ "$(stat -c %s "$image")" -le 8589934592 ]] || exit 2
    [[ "$(blkid -p -s TYPE -o value "$image")" == ext4 ]] || exit 2
    export OOONANA_FIREFOX_TEST_IMAGE="$image"
    fi
    if [[ -z "${OOONANA_FIREFOX_REUSE_HOME:-}" ]]; then
      network=()
      limit=1800
    fi
  fi
  for tool in unshare xvfb-run chroot mount timeout; do command -v "$tool" >/dev/null; done
  exec timeout --kill-after=5 "$limit" unshare --mount --pid --fork --kill-child --ipc "${network[@]}" --propagation private \
    bash "$0" --worker "$rootfs" "$output"
fi

rootfs="$2"; output="$3"
if [[ "$only" == firefox-frame ]]; then
  # Host bubblewrap sees worker PIDs, so /proc must match this private PID NS.
  mount -t proc proc /proc
fi
if [[ -n "${OOONANA_GUI_REPO:-}" ]]; then
  storage="$output"
  if [[ "$only" == firefox-frame ]]; then
    mkdir "$output/storage"
    if [[ "${OOONANA_FIREFOX_DIRECT_STORAGE:-0}" != 1 ]]; then
      mount -o loop "$OOONANA_FIREFOX_TEST_IMAGE" "$output/storage"
    fi
    storage="$output/storage"
    [[ ! -e "$storage/overlay" ]] || { printf 'Firefox image must be fresh\n' >&2; exit 2; }
  fi
  mkdir -p "$storage/overlay/"{upper,work,rootfs,empty-sources}
  mount -t overlay overlay -o "lowerdir=$rootfs,upperdir=$storage/overlay/upper,workdir=$storage/overlay/work" "$storage/overlay/rootfs"
  rootfs="$storage/overlay/rootfs"
  OOONANA_ROOT="$rootfs" OOONANA_REPO_DIR="$OOONANA_GUI_REPO" \
    OOONANA_REPO_VERIFY_KEY="$SOURCE/packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub" \
    OOONANA_SOURCES_DIR="$storage/overlay/empty-sources" \
    sh "$SOURCE/packages/ooonana/usr/bin/ooonana" install xdg-desktop-portal xdg-desktop-portal-gtk xdg-document-portal \
    >"$output/portal-install.log" 2>&1
  if [[ "$only" == all || "$only" == qterminal-frame ]]; then
    OOONANA_ROOT="$rootfs" OOONANA_REPO_DIR="$OOONANA_GUI_REPO" \
      OOONANA_REPO_VERIFY_KEY="$SOURCE/packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub" \
      OOONANA_SOURCES_DIR="$storage/overlay/empty-sources" \
      sh "$SOURCE/packages/ooonana/usr/bin/ooonana" install qterminal >"$output/qt-install.log" 2>&1
    for appearance in Dark Light; do
      install -D -m 0644 "$SOURCE/packages/ooonana/usr/share/qtermwidget6/color-schemes/Ooonana$appearance.colorscheme" \
        "$rootfs/usr/share/qtermwidget6/color-schemes/Ooonana$appearance.colorscheme"
    done
  fi
  if [[ "$only" == all || "$only" == dock-ui ]]; then
    # Old preserved QA roots may have rofi common data without X11 executable.
    OOONANA_ROOT="$rootfs" OOONANA_REPO_DIR="$OOONANA_GUI_REPO" \
      OOONANA_REPO_VERIFY_KEY="$SOURCE/packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub" \
      OOONANA_SOURCES_DIR="$storage/overlay/empty-sources" \
      sh "$SOURCE/packages/ooonana/usr/bin/ooonana" reinstall rofi-x11-wayland >"$output/rofi-install.log" 2>&1
  fi
  if [[ "$only" == firefox-frame ]]; then
    OOONANA_ROOT="$rootfs" OOONANA_REPO_DIR="$OOONANA_GUI_REPO" \
      OOONANA_REPO_VERIFY_KEY="$SOURCE/packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub" \
      OOONANA_SOURCES_DIR="$storage/overlay/empty-sources" \
      sh "$SOURCE/packages/ooonana/usr/bin/ooonana" install firefox >"$output/firefox-package-install.log" 2>&1
    cp --remove-destination /etc/resolv.conf "$rootfs/etc/resolv.conf"
  fi
  mkdir -p "$rootfs/etc/xdg-desktop-portal"
  cp "$SOURCE/packages/ooonana/etc/xdg-desktop-portal/i3-portals.conf" "$rootfs/etc/xdg-desktop-portal/i3-portals.conf"
  ln -sfn /proc/self/mounts "$rootfs/etc/mtab"
  # Mirror current builder fix in preserved pre-fix candidate's private upper.
  mkdir -p "$rootfs/var/tmp"
  chmod 1777 "$rootfs/var/tmp"
fi
# Private mounts vanish on namespace exit; candidate bytes/home remain intact.
mount --bind "$SOURCE" "$rootfs/source"
mount -o remount,bind,ro "$rootfs/source"
mount --bind "$output" "$rootfs/qa"
chromium_defaults="$(cat "$rootfs/etc/chromium/chromium.conf")"
mount -t tmpfs -o size=1m tmpfs "$rootfs/etc/chromium"
printf '%s\n' "$chromium_defaults" >"$rootfs/etc/chromium/chromium.conf"
cp "$SOURCE/packages/ooonana/etc/chromium/zz-ooonana.conf" "$rootfs/etc/chromium/zz-ooonana.conf"
mount -t proc proc "$rootfs/proc"
mount --rbind /sys "$rootfs/sys"
mount -o remount,bind,ro "$rootfs/sys"
for directory in tmp run home dev; do
  mount -t tmpfs -o size=64m tmpfs "$rootfs/$directory"
done
if [[ "$only" == firefox-frame ]]; then
  if [[ -n "${OOONANA_FIREFOX_REUSE_HOME:-}" ]]; then
    mount --bind "$OOONANA_FIREFOX_REUSE_HOME" "$rootfs/home"
  else
    mkdir "$storage/home"
    mount --bind "$storage/home" "$rootfs/home"
  fi
fi
chmod 1777 "$rootfs/tmp"
mkdir -p "$rootfs/dev/shm" "$rootfs/dev/pts" "$rootfs/home/ooonana"
chmod 1777 "$rootfs/dev/shm"
for device in null zero full random urandom; do
  case "$device" in null) minor=3 ;; zero) minor=5 ;; full) minor=7 ;; random) minor=8 ;; urandom) minor=9 ;; esac
  mknod -m 0666 "$rootfs/dev/$device" c 1 "$minor"
done
mknod -m 0666 "$rootfs/dev/tty" c 5 0
# Document portal uses FUSE; this exposes no host block devices.
if [[ -c /dev/fuse ]]; then mknod -m 0666 "$rootfs/dev/fuse" c 10 229; fi
ln -s /proc/self/fd "$rootfs/dev/fd"
ln -s /proc/self/fd/0 "$rootfs/dev/stdin"
ln -s /proc/self/fd/1 "$rootfs/dev/stdout"
ln -s /proc/self/fd/2 "$rootfs/dev/stderr"
mount -t devpts -o newinstance,ptmxmode=0666 devpts "$rootfs/dev/pts"
ln -s pts/ptmx "$rootfs/dev/ptmx"
chown 1000:1000 "$rootfs/home/ooonana" "$output"
admin_policy=0
if [[ "$only" == all || "$only" == admin-prompt-ui ]]; then
  # Only private mounts: cached/system sudo policy and askpass stay unchanged.
  [[ -f "$rootfs/etc/sudoers" && -d "$rootfs/etc/sudoers.d" && -f "$rootfs/usr/bin/ooonana-admin-askpass" ]]
  install -m 0440 "$SOURCE/tests/fixtures/admin-prompt.sudoers" "$rootfs/run/ooonana-qa-sudoers"
  mount --bind "$rootfs/run/ooonana-qa-sudoers" "$rootfs/etc/sudoers"
  mount -o remount,bind,ro "$rootfs/etc/sudoers"
  cmp -s "$SOURCE/tests/fixtures/admin-prompt.sudoers" "$rootfs/etc/sudoers"
  mount -t tmpfs -o size=1m tmpfs "$rootfs/etc/sudoers.d"
  # Live-media doas rules can independently authorize the same harmless check.
  # Require the sudo prompt here rather than accidentally testing that fallback.
  if [[ -f "$rootfs/etc/doas.conf" ]]; then
    install -m 0400 /dev/null "$rootfs/run/ooonana-qa-doas"
    mount --bind "$rootfs/run/ooonana-qa-doas" "$rootfs/etc/doas.conf"
    mount -o remount,bind,ro "$rootfs/etc/doas.conf"
  fi
  if [[ -d "$rootfs/etc/doas.d" ]]; then mount -t tmpfs -o size=1m tmpfs "$rootfs/etc/doas.d"; fi
  awk -v marker='"$ROOTFS/usr/bin/ooonana-run-admin"' '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$SOURCE/scripts/build-full-i3-rootfs.sh" > "$rootfs/run/ooonana-qa-run-admin"
  [[ -s "$rootfs/run/ooonana-qa-run-admin" ]]
  chmod 0755 "$rootfs/run/ooonana-qa-run-admin"
  mount --bind "$rootfs/run/ooonana-qa-run-admin" "$rootfs/usr/bin/ooonana-run-admin"
  mount -o remount,bind,ro "$rootfs/usr/bin/ooonana-run-admin"
  mount --bind "$SOURCE/packages/ooonana/usr/lib/ooonana/ui" "$rootfs/usr/lib/ooonana/ui"
  mount -o remount,bind,ro "$rootfs/usr/lib/ooonana/ui"
  mount --bind "$SOURCE/packages/ooonana/usr/bin/ooonana-admin-askpass" "$rootfs/usr/bin/ooonana-admin-askpass"
  mount -o remount,bind,ro "$rootfs/usr/bin/ooonana-admin-askpass"
  admin_policy=1
fi
if [[ "$only" == all || "$only" == launcher-session-ui ]]; then
  # Subprocess handoff must use current UI/wrappers, not cached candidate bytes.
  if [[ "$only" != all ]]; then
    mount --bind "$SOURCE/packages/ooonana/usr/lib/ooonana/ui" "$rootfs/usr/lib/ooonana/ui"
    mount -o remount,bind,ro "$rootfs/usr/lib/ooonana/ui"
  fi
  awk -v marker='"$ROOTFS/usr/bin/ooonana-settings"' '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$SOURCE/scripts/build-full-i3-rootfs.sh" >"$rootfs/run/ooonana-qa-settings"
  [[ -s "$rootfs/run/ooonana-qa-settings" ]]
  chmod 0755 "$rootfs/run/ooonana-qa-settings"
  mount --bind "$rootfs/run/ooonana-qa-settings" "$rootfs/usr/bin/ooonana-settings"
  mount -o remount,bind,ro "$rootfs/usr/bin/ooonana-settings"
  mount --bind "$SOURCE/packages/ooonana/usr/bin/ooonana-settings-launch" "$rootfs/usr/bin/ooonana-settings-launch"
  mount -o remount,bind,ro "$rootfs/usr/bin/ooonana-settings-launch"
  for helper in ooonana-theme-env ooonana-editor ooonana-files; do
    awk -v marker="\"\$ROOTFS/usr/bin/$helper\"" '
      index($0, marker) { capture=1; next }
      capture && $0 == "EOF" { exit }
      capture { print }
    ' "$SOURCE/scripts/build-full-i3-rootfs.sh" >"$rootfs/run/ooonana-qa-$helper"
    [[ -s "$rootfs/run/ooonana-qa-$helper" ]]
    chmod 0755 "$rootfs/run/ooonana-qa-$helper"
    mount --bind "$rootfs/run/ooonana-qa-$helper" "$rootfs/usr/bin/$helper"
    mount -o remount,bind,ro "$rootfs/usr/bin/$helper"
  done
fi
if [[ "$only" == all || "$only" == panel-media-runtime ]]; then
  for helper in ooonana-media-control ooonana-media-status; do
    mount --bind "$SOURCE/packages/ooonana/usr/bin/$helper" "$rootfs/usr/bin/$helper"
    mount -o remount,bind,ro "$rootfs/usr/bin/$helper"
  done
fi
if [[ "$only" == all || "$only" == dock-ui ]]; then
  # Real chooser must use current shipped theme, never preserved cached bytes.
  awk -v marker='"$ROOTFS/etc/ooonana/rofi.rasi"' '
    index($0, marker) { capture=1; next }
    capture && $0 == "EOF" { exit }
    capture { print }
  ' "$SOURCE/scripts/build-full-i3-rootfs.sh" >"$rootfs/run/ooonana-qa-rofi.rasi"
  [[ -s "$rootfs/run/ooonana-qa-rofi.rasi" ]]
  mount --bind "$rootfs/run/ooonana-qa-rofi.rasi" "$rootfs/etc/ooonana/rofi.rasi"
  mount -o remount,bind,ro "$rootfs/etc/ooonana/rofi.rasi"
fi
if [[ "$only" == all || "$only" == qterminal-frame ]]; then
  # Exercise the real source session prefix before its bus/theme/daemon setup;
  # the GUI probe owns the subsequent WM. Never fake cwd via a test-only cd.
  awk -v marker='"$ROOTFS/usr/bin/ooonana-i3-session"' '
    index($0, marker) { capture=1; next }
    capture && /^export XDG_CURRENT_DESKTOP=/ { finished=1; exit }
    capture { print }
    END { if (!capture || !finished) exit 1; print "exec \"$@\"" }
  ' "$SOURCE/scripts/build-full-i3-rootfs.sh" >"$rootfs/run/ooonana-qa-session-prefix"
  chmod 0555 "$rootfs/run/ooonana-qa-session-prefix"
fi
if [[ "$only" == firefox-frame && -z "${OOONANA_FIREFOX_REUSE_HOME:-}" ]]; then
  mkdir -p "$rootfs$gui_runtime"
  chown 1000:1000 "$rootfs$gui_runtime"
  chmod 0700 "$rootfs$gui_runtime"
  timeout --kill-after=5 1200 chroot --userspec=1000:1000 "$rootfs" \
    /usr/bin/env -i HOME=/home/ooonana USER=ooonana LOGNAME=ooonana \
    PATH=/usr/bin:/bin:/usr/sbin:/sbin XDG_RUNTIME_DIR="$gui_runtime" \
    OOONANA_FIREFOX_DOWNLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
    /usr/bin/dbus-run-session -- python3 /source/tests/probe-firefox-install.py \
    >"$output/firefox-install-update.log" 2>&1
fi
# Host Xvfb and candidate use the same private filesystem socket, no TCP.
mount --bind "$rootfs/tmp" /tmp
export rootfs output only theme text_scale device_scale qt_scale gui_runtime admin_policy
# Keep namespace init as Bash. Xvfb will not send its readiness signal to PID 1.
# shellcheck disable=SC2016 # Child shell expands exported paths/display.
unshare --net xvfb-run -a --server-args="-screen 0 ${geometry}x24 -nolisten tcp" bash -c '
  set -eu
  mkdir -p "$rootfs$gui_runtime"
  chown 1000:1000 "$rootfs$gui_runtime"
  chmod 0700 "$rootfs$gui_runtime"
  cp "$XAUTHORITY" "$rootfs/home/ooonana/.Xauthority"
  chown 1000:1000 "$rootfs/home/ooonana/.Xauthority"
  chmod 0600 "$rootfs/home/ooonana/.Xauthority"
  failure=0
  probe() {
    name="$1"; shift
    [ "$only" = all ] || [ "$only" = "$name" ] || return 0
    launch=(chroot --userspec=1000:1000 "$rootfs")
    if [ "$name" = firefox-frame ]; then
      # Plain chroot cannot create nested user namespaces. Use a proper mount
      # namespace root, retaining host UID1000 and every browser sandbox.
      launch=(bash "$rootfs/source/tests/run-firefox-mount-root.sh" "$rootfs")
    fi
    session=(/usr/bin/dbus-run-session)
    if [ "$name" = notification-auto-recovery ]; then
      session+=(--config-file=/source/tests/fixtures/session-no-activation.conf)
    fi
    if [ "$name" = qterminal-frame ]; then
      session=(/bin/sh /run/ooonana-qa-session-prefix "${session[@]}")
    fi
    if timeout --kill-after=5 120 "${launch[@]}" \
      /usr/bin/env -i HOME=/home/ooonana USER=ooonana LOGNAME=ooonana \
      PATH=/usr/bin:/bin:/usr/sbin:/sbin DISPLAY="$DISPLAY" \
      LANG=C.UTF-8 LC_CTYPE=C.UTF-8 \
      XAUTHORITY=/home/ooonana/.Xauthority XDG_RUNTIME_DIR="$gui_runtime" \
      XDG_CURRENT_DESKTOP=Ooonana:i3 XDG_SESSION_DESKTOP=ooonana DESKTOP_SESSION=ooonana \
      PYTHONDONTWRITEBYTECODE=1 OOONANA_GUI_TEST_DISPLAY=1 OOONANA_NOTIFICATION_TEST_SESSION=1 GDK_BACKEND=x11 \
      OOONANA_GUI_TEST_ADMIN_POLICY="$admin_policy" \
      GTK_THEME="Adwaita:$theme" OOONANA_THEME="$theme" OOONANA_GUI_TEXT_SCALE="$text_scale" NO_AT_BRIDGE=1 \
      GDK_SCALE="$device_scale" QT_SCALE_FACTOR="$qt_scale" \
      "${session[@]}" -- "$@" >"$output/$name.log" 2>&1; then
      printf "PASS %s\n" "$name"
    else
      printf "FAIL %s (exit %s; log retained)\n" "$name" "$?"
      failure=1
    fi
  }
  for name in native-ui-runtime native-appearance ai-indicators ai-chat-runtime desktop-interactions; do
    probe "$name" python3 "/source/tests/check-$name.py"
  done
  probe native-app-catalog python3 /source/tests/check-native-app-catalog.py
  probe ui-details-runtime python3 /source/tests/check-ui-details-runtime.py /qa/details
  probe ui-content-runtime python3 /source/tests/check-ui-content-runtime.py /qa/content --text-scale "$text_scale"
  probe wireless-notification-ui python3 /source/tests/check-wireless-notification-ui.py /qa/wireless-notification
  probe package-health-ui python3 /source/tests/check-package-health-ui.py /qa/package-health
  probe admin-prompt-ui python3 /source/tests/check-admin-prompt-ui.py /qa/admin-prompt
  probe installer-ui python3 /source/tests/check-installer-ui.py /qa/installer
  probe settings-power-ui python3 /source/tests/check-settings-power-ui.py
  probe settings-details-ui python3 /source/tests/check-settings-details-ui.py /qa/settings-details
  probe settings-storage-ui python3 /source/tests/check-settings-storage-ui.py /qa/settings-storage
  probe ai-details-ui python3 /source/tests/check-ai-details-ui.py /qa/ai-details
  probe task-details-ui python3 /source/tests/check-task-details-ui.py /qa/task-details
  probe workspace-ui python3 /source/tests/check-workspace-ui.py /qa/workspaces
  probe launcher-session-ui python3 /source/tests/check-launcher-session-ui.py /qa/launcher-session
  probe wireless-details-ui python3 /source/tests/check-wireless-details-ui.py /qa/wireless-details
  probe controls-details-ui python3 /source/tests/check-controls-details-ui.py /qa/controls-details
  probe setup-details-ui python3 /source/tests/check-setup-details-ui.py /qa/setup-details
  probe control-density-ui python3 /source/tests/check-control-density-ui.py /qa/density
  probe notifications-runtime python3 /source/tests/check-notifications-runtime.py --output /qa/notifications.png
  probe notification-lifecycle python3 /source/tests/check-notification-lifecycle.py /qa/notification-lifecycle
  probe notification-auto-recovery python3 /source/tests/check-notification-auto-recovery.py /qa/notification-auto
  probe window-controls-runtime python3 /source/tests/check-window-controls-runtime.py --own-i3
  probe dock-ui python3 /source/tests/check-dock-ui.py /qa/dock.png
  probe dock-edges-ui python3 /source/tests/check-dock-edges-ui.py /qa/dock-edges
  probe device-scale-ui python3 /source/tests/check-device-scale-ui.py /qa/device-scale
  panel_options=()
  if [ "${OOONANA_PANEL_WIDE_LABELS:-0}" = 1 ]; then panel_options+=(--wide-labels); fi
  probe panel-ui python3 /source/tests/check-panel-ui.py /qa/panel.png --rootfs / --long-wifi --desktop-overview --appearance-output /qa/appearance.png "${panel_options[@]}"
  probe panel-media-runtime python3 /source/tests/check-panel-media-runtime.py /qa/media-runtime
  probe portal-ui python3 /source/tests/check-portal-ui.py /qa/portal.png
  for app in geany nemo chromium qterminal; do
    compositor_options=(--compositor)
    if [ "${OOONANA_GUI_COMPOSITOR_OFF:-0}" = 1 ]; then compositor_options=(); fi
    if [ "${OOONANA_GUI_COMPOSITOR_NO_DAMAGE:-0}" = 1 ]; then compositor_options+=(--no-use-damage); fi
    if [ "$app" = geany ]; then
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --file-dialog "${compositor_options[@]}"
    elif [ "$app" = chromium ] && [ "${OOONANA_BROWSER_NO_SHADER_CACHE:-0}" = 1 ]; then
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --disable-shader-cache "${compositor_options[@]}"
    elif [ "$app" = qterminal ] && [ "${OOONANA_QT_DETAILS:-0}" = 1 ]; then
      qt_options=(--qt-details)
      if [ "${OOONANA_QT_PICKERS:-0}" = 1 ]; then qt_options+=(--qt-pickers); fi
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" "${qt_options[@]}" "${compositor_options[@]}"
    else
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" "${compositor_options[@]}"
    fi
  done
  if [ "$only" = firefox-frame ]; then
    first_run_options=()
    case "${OOONANA_FIREFOX_QA_FIRST_RUN:-}" in
      "") ;;
      inspect) first_run_options+=(--inspect-firefox-first-run) ;;
      accept) first_run_options+=(--accept-firefox-qa-terms) ;;
      *) printf "Unsupported QA first-run mode\n" >&2; exit 2 ;;
    esac
    if [ "${OOONANA_FIREFOX_QA_TRACE:-0}" = 1 ]; then first_run_options+=(--wait-for-file-trace); fi
    firefox_compositor=(--compositor)
    if [ "${OOONANA_GUI_COMPOSITOR_NO_DAMAGE:-0}" = 1 ]; then firefox_compositor+=(--no-use-damage); fi
    if [ "${OOONANA_FIREFOX_PICKER:-1}" = 0 ]; then
      probe firefox-frame python3 /source/tests/check-third-party-frames.py firefox /qa/firefox.png "${firefox_compositor[@]}" "${first_run_options[@]}"
    else
      probe firefox-frame python3 /source/tests/check-third-party-frames.py firefox /qa/firefox.png "${firefox_compositor[@]}" --file-dialog "${first_run_options[@]}"
    fi
  fi
  exit "$failure"
'
