#!/usr/bin/env bash
# Private musl compiler overlay; never installs into host/installed Ooonana.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# == 2 && $EUID == 0 && "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ]] || exit 2
workspace="$(realpath "$1")"; image="$(realpath "$2")"
[[ "$workspace" == /var/tmp/ooonana-qt-portal-* && ! -L "$1" && ! -e "$workspace/out" ]] || exit 2
[[ "$image" == /mnt/winf/Ooonana/ooonana-os/qa-i3-controls-*/build-root.ext4 && -f "$image" && ! -L "$2" ]] || exit 2
[[ "$(blkid -p -s LABEL -o value "$image")" == OOONANA_I3_BUILD && "$(stat -c %s "$image")" == 3221225472 ]] || exit 2
[[ -z "$(losetup -j "$image")" ]] || { echo 'Build cache busy; preserved'; exit 2; }
if [[ -n "${OOONANA_QT_BUILD_REUSE:-}" ]]; then
  attempt="$(realpath "$OOONANA_QT_BUILD_REUSE")"
  [[ "$attempt" == /var/tmp/ooonana-qt-portal-builder.* && ! -L "$OOONANA_QT_BUILD_REUSE" ]] || exit 2
  for part in lower upper work rootfs; do [[ -d "$attempt/$part" && ! -L "$attempt/$part" ]] || exit 2; done
  [[ -f "$attempt/upper/opt/ooonana-qt-portal/main.cpp" && -f "$attempt/dependencies.txt" ]] || exit 2
else
  attempt="$(mktemp -d /var/tmp/ooonana-qt-portal-builder.XXXXXXXX)"
  mkdir "$attempt/"{lower,upper,work,rootfs}
fi
sandbox="$attempt/rootfs"
cleanup() {
  for part in proc dev tmp run; do mountpoint -q "$sandbox/$part" && umount "$sandbox/$part" || true; done
  mountpoint -q "$sandbox" && umount "$sandbox" || true
  mountpoint -q "$attempt/lower" && umount "$attempt/lower" || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mount -o loop,ro,noload "$image" "$attempt/lower"
mount -t overlay overlay -o "lowerdir=$attempt/lower,upperdir=$attempt/upper,workdir=$attempt/work" "$sandbox"
[[ "$(cat "$sandbox/etc/alpine-release")" == 3.24.2 ]]
mount -t proc proc "$sandbox/proc"
mount -t tmpfs -o size=8m tmpfs "$sandbox/dev"
for spec in 'null 1 3' 'zero 1 5' 'random 1 8' 'urandom 1 9'; do
  read -r name major minor <<<"$spec"; mknod -m 0666 "$sandbox/dev/$name" c "$major" "$minor"
done
ln -s /proc/self/fd "$sandbox/dev/fd"
mount -t tmpfs -o size=64m,mode=1777 tmpfs "$sandbox/tmp"
mount -t tmpfs -o size=8m tmpfs "$sandbox/run"
cp --remove-destination /etc/resolv.conf "$sandbox/etc/resolv.conf"
echo "Private Qt build overlay: $attempt"
chroot "$sandbox" /sbin/apk add --no-cache build-base cmake ninja qt6-qtbase-dev=6.11.1-r0 qt6-qtbase-private-dev=6.11.1-r0 >"$attempt/dependencies.log" 2>&1 || {
  tail -35 "$attempt/dependencies.log"; exit 1;
}
chroot "$sandbox" /sbin/apk info -v >"$attempt/dependencies.txt"
mkdir -p "$sandbox/opt/ooonana-qt-portal"
cp "$workspace/source/"* "$sandbox/opt/ooonana-qt-portal/"
python3 -B "$ROOT/scripts/patch-qt-portal.py" --source "$sandbox/opt/ooonana-qt-portal"
cp "$ROOT/packages/qt-portal/CMakeLists.txt" "$sandbox/opt/ooonana-qt-portal/CMakeLists.txt"
unshare --net chroot "$sandbox" /usr/bin/env -i HOME=/root PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  SOURCE_DATE_EPOCH=1722470400 TZ=UTC LANG=C.UTF-8 /bin/sh -ec '
    cmake -S /opt/ooonana-qt-portal -B /opt/ooonana-qt-portal-build -G Ninja -DCMAKE_BUILD_TYPE=Release
    cmake --build /opt/ooonana-qt-portal-build --parallel 2
  ' >"$attempt/compile.log" 2>&1 || { tail -50 "$attempt/compile.log"; exit 1; }
mkdir "$workspace/out"
cp "$sandbox/opt/ooonana-qt-portal-build/libqxdgdesktopportal.so" "$workspace/out/"
cp "$attempt/"{dependencies.txt,dependencies.log,compile.log} "$workspace/out/"
python3 -B - "$ROOT" "$workspace/out" <<'PY'
import hashlib, json, sys
from pathlib import Path
root, output = map(Path, sys.argv[1:])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = {'format': 1, 'component': 'qt-portal-live-palette-v1', 'compile_network': 'disabled',
            'source': json.loads((root / 'packages/qt-portal/source-pins.json').read_text()),
            'binary_sha256': sha(output / 'libqxdgdesktopportal.so'), 'gui_verified': False,
            'inputs': {p: sha(root / p) for p in ('scripts/patch-qt-portal.py', 'scripts/build-qt-portal-candidate.sh', 'packages/qt-portal/CMakeLists.txt')},
            'dependencies': (output / 'dependencies.txt').read_text().splitlines()}
(output / 'build-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
print('QT_PORTAL_CANDIDATE_BUILT', manifest['binary_sha256'], 'unpublished; not installed')
PY
