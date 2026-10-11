#!/usr/bin/env bash
# Proper disposable mount root; chroot forbids userns, outer bwrap forbids
# setuid FUSE helper. Neither restriction belongs to normal desktop session.
set -euo pipefail
if [[ "${1:-}" != --worker ]]; then
  [[ $EUID -eq 0 && $# -ge 2 ]] || exit 2
  rootfs="$(realpath "$1")"; shift
  [[ "$rootfs" == /var/tmp/ooonana-firefox-*/storage/overlay/rootfs ]] || exit 2
  [[ -d "$rootfs/source" && -d "$rootfs/qa" && -c "$rootfs/dev/fuse" ]] || exit 2
  grep -qx ID=ooonana "$rootfs/etc/os-release"
  [[ "$(findmnt -n -o FSTYPE -T "$rootfs")" == overlay ]] || exit 2
  exec unshare --mount --fork --propagation private bash "$0" --worker "$rootfs" "$@"
fi
rootfs="$2"; shift 2
mount --rbind "$rootfs" "$rootfs"
mkdir "$rootfs/.qa-old-root"
cd "$rootfs"
pivot_root . .qa-old-root
umount -l /.qa-old-root
rmdir /.qa-old-root
# Drop to real host UID1000 before any app/service. Browser and Flatpak still
# create their own normal namespaces/seccomp/privilege locks; none disabled.
exec /bin/su -p -s /bin/sh -c 'exec "$@"' -- ooonana ooonana-probe "$@"
