#!/usr/bin/env bash
# Disposable candidate UI gate. Firefox opt-in downloads into owned ext4 only;
# rendered probes always have a private network. Never run installed WSL here.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
only="${OOONANA_GUI_ONLY:-all}"
geometry="${OOONANA_GUI_GEOMETRY:-1280x800}"
theme="${OOONANA_GUI_THEME:-dark}"
text_scale="${OOONANA_GUI_TEXT_SCALE:-1.25}"
case "$text_scale" in 1.0|1.25|1.5|2.0) ;; *) printf 'Unsupported native text scale: %s\n' "$text_scale" >&2; exit 2 ;; esac
case "$theme" in dark|light) ;; *) printf 'Unsupported test appearance: %s\n' "$theme" >&2; exit 2 ;; esac
case "$geometry" in
  640x600|1024x768|1280x800|1600x900) ;;
  *) printf 'Unsupported disposable display geometry: %s\n' "$geometry" >&2; exit 2 ;;
esac
case "$only" in
  all|wireless-details-ui|workspace-ui|task-details-ui|ai-details-ui|control-density-ui|settings-details-ui|settings-power-ui|native-ui-runtime|native-appearance|native-app-catalog|ui-details-runtime|ui-content-runtime|wireless-notification-ui|package-health-ui|installer-ui|ai-indicators|ai-chat-runtime|desktop-interactions|notifications-runtime|window-controls-runtime|dock-ui|panel-ui|portal-ui|geany-frame|nemo-frame|chromium-frame|qterminal-frame|firefox-frame) ;;
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
if [[ "$only" == firefox-frame && -z "${OOONANA_FIREFOX_REUSE_HOME:-}" ]]; then
  mkdir -p "$rootfs/home/ooonana/runtime"
  chown 1000:1000 "$rootfs/home/ooonana/runtime"
  chmod 0700 "$rootfs/home/ooonana/runtime"
  timeout --kill-after=5 1200 chroot --userspec=1000:1000 "$rootfs" \
    /usr/bin/env -i HOME=/home/ooonana USER=ooonana LOGNAME=ooonana \
    PATH=/usr/bin:/bin:/usr/sbin:/sbin XDG_RUNTIME_DIR=/home/ooonana/runtime \
    OOONANA_FIREFOX_DOWNLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
    /usr/bin/dbus-run-session -- python3 /source/tests/probe-firefox-install.py \
    >"$output/firefox-install-update.log" 2>&1
fi
# Host Xvfb and candidate use the same private filesystem socket, no TCP.
mount --bind "$rootfs/tmp" /tmp
export rootfs output only theme text_scale
# Keep namespace init as Bash. Xvfb will not send its readiness signal to PID 1.
# shellcheck disable=SC2016 # Child shell expands exported paths/display.
unshare --net xvfb-run -a --server-args="-screen 0 ${geometry}x24 -nolisten tcp" bash -c '
  set -eu
  mkdir -p "$rootfs/home/ooonana/runtime"
  chown 1000:1000 "$rootfs/home/ooonana/runtime"
  chmod 0700 "$rootfs/home/ooonana/runtime"
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
    if timeout --kill-after=5 120 "${launch[@]}" \
      /usr/bin/env -i HOME=/home/ooonana USER=ooonana LOGNAME=ooonana \
      PATH=/usr/bin:/bin:/usr/sbin:/sbin DISPLAY="$DISPLAY" \
      XAUTHORITY=/home/ooonana/.Xauthority XDG_RUNTIME_DIR=/home/ooonana/runtime \
      XDG_CURRENT_DESKTOP=Ooonana:i3 XDG_SESSION_DESKTOP=ooonana DESKTOP_SESSION=ooonana \
      PYTHONDONTWRITEBYTECODE=1 OOONANA_GUI_TEST_DISPLAY=1 OOONANA_NOTIFICATION_TEST_SESSION=1 GDK_BACKEND=x11 \
      GTK_THEME="Adwaita:$theme" OOONANA_THEME="$theme" OOONANA_GUI_TEXT_SCALE="$text_scale" NO_AT_BRIDGE=1 \
      /usr/bin/dbus-run-session -- "$@" >"$output/$name.log" 2>&1; then
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
  probe ui-content-runtime python3 /source/tests/check-ui-content-runtime.py /qa/content
  probe wireless-notification-ui python3 /source/tests/check-wireless-notification-ui.py /qa/wireless-notification
  probe package-health-ui python3 /source/tests/check-package-health-ui.py /qa/package-health
  probe installer-ui python3 /source/tests/check-installer-ui.py /qa/installer
  probe settings-power-ui python3 /source/tests/check-settings-power-ui.py
  probe settings-details-ui python3 /source/tests/check-settings-details-ui.py /qa/settings-details
  probe ai-details-ui python3 /source/tests/check-ai-details-ui.py /qa/ai-details
  probe task-details-ui python3 /source/tests/check-task-details-ui.py /qa/task-details
  probe workspace-ui python3 /source/tests/check-workspace-ui.py /qa/workspaces
  probe wireless-details-ui python3 /source/tests/check-wireless-details-ui.py /qa/wireless-details
  probe control-density-ui python3 /source/tests/check-control-density-ui.py /qa/density
  probe notifications-runtime python3 /source/tests/check-notifications-runtime.py --output /qa/notifications.png
  probe window-controls-runtime python3 /source/tests/check-window-controls-runtime.py --own-i3
  probe dock-ui python3 /source/tests/check-dock-ui.py /qa/dock.png
  probe panel-ui python3 /source/tests/check-panel-ui.py /qa/panel.png --rootfs / --long-wifi --desktop-overview --appearance-output /qa/appearance.png
  probe portal-ui python3 /source/tests/check-portal-ui.py /qa/portal.png
  for app in geany nemo chromium qterminal; do
    compositor_options=(--compositor)
    if [ "${OOONANA_GUI_COMPOSITOR_OFF:-0}" = 1 ]; then compositor_options=(); fi
    if [ "${OOONANA_GUI_COMPOSITOR_NO_DAMAGE:-0}" = 1 ]; then compositor_options+=(--no-use-damage); fi
    if [ "$app" = geany ]; then
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --file-dialog "${compositor_options[@]}"
    elif [ "$app" = chromium ] && [ "${OOONANA_BROWSER_NO_SHADER_CACHE:-0}" = 1 ]; then
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --disable-shader-cache "${compositor_options[@]}"
    else
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" "${compositor_options[@]}"
    fi
  done
  if [ "$only" = firefox-frame ]; then
    if [ "${OOONANA_FIREFOX_PICKER:-1}" = 0 ]; then
      probe firefox-frame python3 /source/tests/check-third-party-frames.py firefox /qa/firefox.png --compositor
    else
      probe firefox-frame python3 /source/tests/check-third-party-frames.py firefox /qa/firefox.png --compositor --file-dialog
    fi
  fi
  exit "$failure"
'
