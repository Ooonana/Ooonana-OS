#!/usr/bin/env bash
# Read-only task-owned musl build cache + private overlay. Never installs host/WSL.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# == 2 && $EUID == 0 && "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ]] || exit 2
workspace="$(realpath "$1")"; image="$(realpath "$2")"
[[ "$workspace" == /mnt/winf/Ooonana/ooonana-os/qa-i3lock-* && ! -L "$1" ]] || exit 2
[[ "$image" == /mnt/winf/Ooonana/ooonana-os/qa-i3-controls-*/build-root.ext4 && -f "$image" && ! -L "$2" ]] || exit 2
[[ "$(blkid -p -s LABEL -o value "$image")" == OOONANA_I3_BUILD && "$(stat -c %s "$image")" == 3221225472 ]] || exit 2
[[ -z "$(losetup -j "$image")" && ! -e "$workspace/out" ]] || { echo 'Build cache busy or candidate output already exists; preserve it' >&2; exit 2; }
archive="$workspace/i3lock-2.16.tar.xz"
[[ -f "$archive" && ! -L "$archive" && "$(sha256sum "$archive" | awk '{print $1}')" == a30a5ebead35cc78e5f337571df8c5de2bdd9141426034c74b17e4d3db15f024 ]] || exit 2
attempt="$(mktemp -d /var/tmp/ooonana-lock-builder.XXXXXXXX)"
mkdir "$attempt/"{lower,upper,work,rootfs}
sandbox="$attempt/rootfs"
cleanup() {
  for part in proc dev tmp run; do
    mountpoint -q "$sandbox/$part" && umount "$sandbox/$part" || true
  done
  mountpoint -q "$sandbox" && umount "$sandbox" || true
  mountpoint -q "$attempt/lower" && umount "$attempt/lower" || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mount -o loop,ro,noload "$image" "$attempt/lower"
mount -t overlay overlay -o "lowerdir=$attempt/lower,upperdir=$attempt/upper,workdir=$attempt/work" "$sandbox"
[[ "$(cat "$sandbox/etc/alpine-release")" == 3.24.2 ]]
for part in proc dev tmp run; do mkdir -p "$sandbox/$part"; done
mount -t proc proc "$sandbox/proc"
mount -t tmpfs -o size=8m tmpfs "$sandbox/dev"
for spec in 'null 1 3' 'zero 1 5' 'random 1 8' 'urandom 1 9'; do
  read -r name major minor <<<"$spec"
  mknod -m 0666 "$sandbox/dev/$name" c "$major" "$minor"
done
ln -s /proc/self/fd "$sandbox/dev/fd"
ln -s /proc/self/fd/0 "$sandbox/dev/stdin"
ln -s /proc/self/fd/1 "$sandbox/dev/stdout"
ln -s /proc/self/fd/2 "$sandbox/dev/stderr"
mount -t tmpfs -o size=64m,mode=1777 tmpfs "$sandbox/tmp"
mount -t tmpfs -o size=8m tmpfs "$sandbox/run"
cp --remove-destination /etc/resolv.conf "$sandbox/etc/resolv.conf"
echo "Private build overlay: $attempt; original build image read-only"
chroot "$sandbox" /sbin/apk add --no-cache linux-pam-dev xcb-util-image-dev >"$attempt/dependencies.log" 2>&1 || {
  tail -50 "$attempt/dependencies.log"; exit 1;
}
chroot "$sandbox" /sbin/apk info -v >"$attempt/dependencies.txt"
tar -xJf "$archive" -C "$sandbox/opt"
python3 -B "$ROOT/scripts/patch-i3lock-visuals.py" --source "$sandbox/opt/i3lock-2.16"
echo 'Compiling pinned locker; network disabled'
unshare --net chroot "$sandbox" /usr/bin/env -i HOME=/root PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  SOURCE_DATE_EPOCH=1722470400 TZ=UTC LANG=C.UTF-8 /bin/sh -ec '
    meson setup /opt/i3lock-build /opt/i3lock-2.16 --prefix=/usr --sysconfdir=/etc --buildtype=release
    ninja -C /opt/i3lock-build -j2
  ' >"$attempt/compile.log" 2>&1 || { tail -60 "$attempt/compile.log"; exit 1; }
mkdir "$workspace/out"
cp "$sandbox/opt/i3lock-build/i3lock" "$workspace/out/i3lock"
chmod 0755 "$workspace/out/i3lock"
cp "$attempt/"{dependencies.txt,dependencies.log,compile.log} "$workspace/out/"
python3 -B - "$ROOT" "$workspace/out" "$sandbox/opt/i3lock-2.16" "$archive" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path
root, output, source, archive = map(Path, sys.argv[1:])
sys.path.insert(0, str(root / 'scripts'))
import importlib.util
spec = importlib.util.spec_from_file_location('patcher', root / 'scripts/patch-i3lock-visuals.py')
patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)
with tarfile.open(archive) as original:
    main = original.extractfile('i3lock-2.16/i3lock.c').read()
patched = (source / 'i3lock.c').read_text()
restored = patched.replace(patcher.TICK, '').replace(patcher.START, '').encode()
assert restored == main, 'Authentication/input main source changed beyond redraw additions'
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {'format': 1, 'lock_visual_api': 1, 'source': json.loads((root / 'packages/i3lock/source-pins.json').read_text()),
    'binary_sha256': digest(output / 'i3lock'), 'auth_source_unchanged': True,
    'auth_source_sha256': hashlib.sha256(main).hexdigest(), 'compile_network': 'disabled', 'gui_verified': False,
    'dependencies': (output / 'dependencies.txt').read_text().splitlines(),
    'inputs': {name: digest(root / name) for name in ('scripts/patch-i3lock-visuals.py', 'packages/i3lock/ooonana_lock_visuals.h')}}
(output / 'build-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
print('LOCK_CANDIDATE_BUILT', manifest['binary_sha256'], 'unpublished; not installed')
PY
