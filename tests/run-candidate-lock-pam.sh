#!/usr/bin/env bash
# Only disposable candidate namespace: no installed shadow/PAM/helper changes.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != --worker ]]; then
  [[ $# == 2 && $EUID == 0 ]] || exit 2
  rootfs="$(realpath "$1")"; output="$(realpath "$2")"
  [[ "$rootfs" == /var/tmp/*/full-i3-rootfs && "$output" == /var/tmp/ooonana-lock-pam-* ]] || exit 2
  grep -qx ID=ooonana "$rootfs/etc/os-release"
  [[ -d "$rootfs/source" && -x "$rootfs/usr/sbin/unix_chkpwd" && -f "$rootfs/usr/lib/pam.d/base-auth" ]] || exit 2
  before="$(sha256sum "$rootfs/etc/shadow" "$rootfs/usr/sbin/unix_chkpwd")"
  timeout --kill-after=3 90 unshare --mount --pid --fork --kill-child --net --propagation private \
    bash "$0" --worker "$rootfs" "$output"
  [[ "$(sha256sum "$rootfs/etc/shadow" "$rootfs/usr/sbin/unix_chkpwd")" == "$before" ]]
  echo 'LOCK_PAM_NAMESPACE_OK original credential/helper bytes unchanged'
  exit 0
fi
rootfs="$2"; output="$3"
for directory in run tmp dev; do mount -t tmpfs -o size=8m tmpfs "$rootfs/$directory"; done
mount -t proc proc "$rootfs/proc"
chmod 1777 "$rootfs/tmp"
mknod -m 666 "$rootfs/dev/null" c 1 3
mknod -m 666 "$rootfs/dev/urandom" c 1 9
mkdir "$rootfs/dev/pts"
ln -s /proc/self/fd "$rootfs/dev/fd"
ln -s /proc/self/fd/0 "$rootfs/dev/stdin"
ln -s /proc/self/fd/1 "$rootfs/dev/stdout"
ln -s /proc/self/fd/2 "$rootfs/dev/stderr"
mount --bind "$SOURCE" "$rootfs/source"
mount -o remount,bind,ro "$rootfs/source"
hash="$(printf %s 'Ooonana-private-lock-QA-20261023' | openssl passwd -6 -salt OoonanaLockQA -stdin)"
printf 'root:!:20000:0:99999:7:::\nooonana:%s:20000:0:99999:7:::\n' "$hash" >"$rootfs/run/qa-shadow"
chmod 0600 "$rootfs/run/qa-shadow"
mount --bind "$rootfs/run/qa-shadow" "$rootfs/etc/shadow"
mount -o remount,bind,ro "$rootfs/etc/shadow"
cp "$rootfs/usr/sbin/unix_chkpwd" "$rootfs/run/qa-unix_chkpwd"
chown 0:0 "$rootfs/run/qa-unix_chkpwd"
chmod 2755 "$rootfs/run/qa-unix_chkpwd"
mount --bind "$rootfs/run/qa-unix_chkpwd" "$rootfs/usr/sbin/unix_chkpwd"
probe() {
  chroot --userspec=1000:1000 "$rootfs" /usr/bin/env -i \
    HOME=/home/ooonana PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONDONTWRITEBYTECODE=1 OOONANA_LOCK_AUTH_QA=1 \
    python3 /source/tests/probe-lock-pam.py "$@"
}
probe --expect-denied >"$output/broken-helper.log" 2>&1
chmod 4755 "$rootfs/run/qa-unix_chkpwd"
probe --expect-denied --wrong >"$output/wrong-password.log" 2>&1
probe --expect-success >"$output/correct-password.log" 2>&1
echo 'LOCK_PAM_REAL_OK SGID-root denied correct credential; SUID-root rejected wrong and accepted correct via unchanged vendor PAM'
