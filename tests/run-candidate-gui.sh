#!/usr/bin/env bash
# Disposable, network-isolated candidate UI gate. Never run installed WSL here.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
only="${OOONANA_GUI_ONLY:-all}"
geometry="${OOONANA_GUI_GEOMETRY:-1280x800}"
case "$geometry" in
  1024x768|1280x800|1600x900) ;;
  *) printf 'Unsupported disposable display geometry: %s\n' "$geometry" >&2; exit 2 ;;
esac
case "$only" in
  all|native-ui-runtime|ai-indicators|ai-chat-runtime|desktop-interactions|notifications-runtime|window-controls-runtime|dock-ui|panel-ui|geany-frame|nemo-frame|chromium-frame) ;;
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
  for tool in unshare xvfb-run chroot mount timeout; do command -v "$tool" >/dev/null; done
  exec timeout --kill-after=5 600 unshare --mount --pid --fork --kill-child --ipc --net --propagation private \
    bash "$0" --worker "$rootfs" "$output"
fi

rootfs="$2"; output="$3"
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
chmod 1777 "$rootfs/tmp"
mkdir -p "$rootfs/dev/shm" "$rootfs/dev/pts" "$rootfs/home/ooonana"
chmod 1777 "$rootfs/dev/shm"
for device in null zero random urandom; do
  case "$device" in null) minor=3 ;; zero) minor=5 ;; random) minor=8 ;; urandom) minor=9 ;; esac
  mknod -m 0666 "$rootfs/dev/$device" c 1 "$minor"
done
mknod -m 0666 "$rootfs/dev/tty" c 5 0
ln -s /proc/self/fd "$rootfs/dev/fd"
ln -s /proc/self/fd/0 "$rootfs/dev/stdin"
ln -s /proc/self/fd/1 "$rootfs/dev/stdout"
ln -s /proc/self/fd/2 "$rootfs/dev/stderr"
mount -t devpts -o newinstance,ptmxmode=0666 devpts "$rootfs/dev/pts"
ln -s pts/ptmx "$rootfs/dev/ptmx"
chown 1000:1000 "$rootfs/home/ooonana" "$output"
# Host Xvfb and candidate use the same private filesystem socket, no TCP.
mount --bind "$rootfs/tmp" /tmp
export rootfs output only
# Keep namespace init as Bash. Xvfb will not send its readiness signal to PID 1.
xvfb-run -a --server-args="-screen 0 ${geometry}x24 -nolisten tcp" bash -c '
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
    if timeout --kill-after=5 120 chroot --userspec=1000:1000 "$rootfs" \
      /usr/bin/env -i HOME=/home/ooonana USER=ooonana LOGNAME=ooonana \
      PATH=/usr/bin:/bin:/usr/sbin:/sbin DISPLAY="$DISPLAY" \
      XAUTHORITY=/home/ooonana/.Xauthority XDG_RUNTIME_DIR=/home/ooonana/runtime \
      PYTHONDONTWRITEBYTECODE=1 OOONANA_GUI_TEST_DISPLAY=1 OOONANA_NOTIFICATION_TEST_SESSION=1 GDK_BACKEND=x11 \
      GTK_THEME=Adwaita:dark NO_AT_BRIDGE=1 \
      /usr/bin/dbus-run-session -- "$@" >"$output/$name.log" 2>&1; then
      printf "PASS %s\n" "$name"
    else
      printf "FAIL %s (log retained)\n" "$name"
      failure=1
    fi
  }
  for name in native-ui-runtime ai-indicators ai-chat-runtime desktop-interactions; do
    probe "$name" python3 "/source/tests/check-$name.py"
  done
  probe notifications-runtime python3 /source/tests/check-notifications-runtime.py --output /qa/notifications.png
  probe window-controls-runtime python3 /source/tests/check-window-controls-runtime.py --own-i3
  probe dock-ui python3 /source/tests/check-dock-ui.py /qa/dock.png
  probe panel-ui python3 /source/tests/check-panel-ui.py /qa/panel.png --rootfs / --long-wifi --desktop-overview
  for app in geany nemo chromium; do
    if [ "$app" = geany ]; then
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --compositor --file-dialog
    elif [ "$app" = chromium ] && [ "${OOONANA_BROWSER_NO_SHADER_CACHE:-0}" = 1 ]; then
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --compositor --disable-shader-cache
    else
      probe "$app-frame" python3 /source/tests/check-third-party-frames.py "$app" "/qa/$app.png" --compositor
    fi
  done
  exit "$failure"
'
