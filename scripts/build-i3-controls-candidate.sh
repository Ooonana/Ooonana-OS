#!/usr/bin/env bash
# Build-only musl sandbox. Never install into Ooonana/Ubuntu or touch real disks.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${1:-}"
resume="${2:-}"
if [[ "$workspace" == --help || -z "$workspace" ]]; then
  printf '%s\n' 'Usage (private mount/PID namespace, root): build-i3-controls-candidate.sh WORKSPACE [--resume|--refresh-source|--prepared-empty]' \
    'WORKSPACE: owned /mnt/winf/Ooonana/ooonana-os/qa-i3-controls-* directory.' \
    'On NTFS, prepare an empty sparse build-root.ext4 with fsutil before --prepared-empty.' \
    'Requires pinned source/rootfs archives. Build only; no ISO or installed changes.'
  exit 0
fi
[[ $EUID -eq 0 && "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ]] || {
  echo 'Use a private mount namespace; refusing host namespace' >&2; exit 2;
}
workspace="$(realpath "$workspace")"
case "$workspace" in /mnt/winf/Ooonana/ooonana-os/qa-i3-controls-*) ;; *) echo 'Unsafe candidate workspace' >&2; exit 2 ;; esac
[[ -d "$workspace" && ! -L "$workspace" && ( -z "$resume" || "$resume" == --resume || "$resume" == --refresh-source || "$resume" == --prepared-empty ) ]]
lock_id="$(printf '%s' "$workspace" | sha256sum | awk '{print $1}')"
exec 9>"/var/tmp/ooonana-i3-builder-$lock_id.lock"
flock -n 9 || { echo 'Candidate build already active' >&2; exit 2; }
[[ "$(df -Pk "$workspace" | awk 'NR==2 {print $4}')" -ge 2097152 ]] || { echo 'Candidate needs 2GiB free reserve' >&2; exit 2; }
archive="$workspace/i3-4.24.tar.xz"
bootstrap="$workspace/alpine-minirootfs-3.24.2-x86_64.tar.gz"
[[ -f "$archive" && ! -L "$archive" && -f "$bootstrap" && ! -L "$bootstrap" ]]
[[ "$(sha256sum "$archive" | awk '{print $1}')" == 5baefd0e5e78f1bafb7ac85deea42bcd3cbfe65f1279aa96f7e49661637ac981 ]]
[[ "$(sha256sum "$bootstrap" | awk '{print $1}')" == c5ca053cfe1d85c5b96dff8b9bc57045f7f184a30ffb6b65776409ca90388677 ]]
image="$workspace/build-root.ext4"
[[ ! -L "$image" ]]
if [[ "$resume" == --prepared-empty ]]; then
  [[ -f "$image" && "$(stat -c %s "$image")" == 0 ]] || { echo 'Prepared image must be empty regular file' >&2; exit 2; }
  truncate -s 3G "$image"
  mkfs.ext4 -q -F -E nodiscard,lazy_itable_init=1,lazy_journal_init=1 -L OOONANA_I3_BUILD "$image"
elif [[ -e "$image" ]]; then
  [[ ( "$resume" == --resume || "$resume" == --refresh-source ) && -f "$image" && "$(blkid -p -s LABEL -o value "$image")" == OOONANA_I3_BUILD && "$(blkid -p -s TYPE -o value "$image")" == ext4 ]] || {
    echo 'Refusing existing/unknown build image; use validated --resume' >&2; exit 2;
  }
else
  [[ -z "$resume" ]]
  # New regular sparse file only, never /dev, an existing image, or WSL disk.
  truncate -s 3G "$image"
  mkfs.ext4 -q -F -E nodiscard,lazy_itable_init=1,lazy_journal_init=1 -L OOONANA_I3_BUILD "$image"
fi
[[ -z "$(losetup -j "$image")" ]] || { echo 'Candidate image already attached; refusing second mount' >&2; exit 2; }
mountpoint="$(mktemp -d /var/tmp/ooonana-i3-builder.XXXXXXXX)"
cleanup() {
  for directory in proc dev tmp run; do
    mountpoint -q "$mountpoint/$directory" && umount "$mountpoint/$directory" || true
  done
  mountpoint -q "$mountpoint" && umount "$mountpoint" || true
  rmdir "$mountpoint" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mount -o loop "$image" "$mountpoint"
if [[ ! -e "$mountpoint/etc/alpine-release" ]]; then
  tar -xzf "$bootstrap" -C "$mountpoint"
fi
[[ "$(cat "$mountpoint/etc/alpine-release")" == 3.24.2 ]]
for directory in proc dev tmp run; do mkdir -p "$mountpoint/$directory"; done
mount -t proc proc "$mountpoint/proc"
mount -t tmpfs -o size=16m,mode=755 tmpfs "$mountpoint/dev"
for spec in 'null 1 3' 'zero 1 5' 'full 1 7' 'random 1 8' 'urandom 1 9'; do
  read -r name major minor <<<"$spec"
  mknod -m 0666 "$mountpoint/dev/$name" c "$major" "$minor"
done
ln -s /proc/self/fd "$mountpoint/dev/fd"
ln -s /proc/self/fd/0 "$mountpoint/dev/stdin"
ln -s /proc/self/fd/1 "$mountpoint/dev/stdout"
ln -s /proc/self/fd/2 "$mountpoint/dev/stderr"
mount -t tmpfs -o size=256m,mode=1777 tmpfs "$mountpoint/tmp"
mount -t tmpfs -o size=16m,mode=755 tmpfs "$mountpoint/run"
cp --remove-destination /etc/resolv.conf "$mountpoint/etc/resolv.conf"
[[ ! -L "$workspace/out" ]]
mkdir -p "$workspace/out"
if [[ ! -f "$mountpoint/etc/ooonana-i3-build-deps.ready" || ! -x "$mountpoint/bin/bash" ]]; then
  [[ ! -L "$mountpoint/etc/apk/repositories" ]]
  printf '%s\n' 'https://dl-cdn.alpinelinux.org/alpine/v3.24/main' \
    'https://dl-cdn.alpinelinux.org/alpine/v3.24/community' >"$mountpoint/etc/apk/repositories"
  printf 'Fetching signed build dependencies into isolated image\n'
  chroot "$mountpoint" /sbin/apk add --no-cache bash build-base meson ninja pkgconf perl git \
    cairo-dev pango-dev libev-dev yajl-dev startup-notification-dev libxcb-dev \
    xcb-util-dev xcb-util-cursor-dev xcb-util-keysyms-dev xcb-util-wm-dev xcb-util-xrm-dev \
    libxkbcommon-dev pcre2-dev >"$workspace/out/build-dependencies.log" 2>&1 || {
      tail -60 "$workspace/out/build-dependencies.log"; exit 1;
    }
  chroot "$mountpoint" /sbin/apk info -v >"$workspace/out/build-dependencies.txt"
  touch "$mountpoint/etc/ooonana-i3-build-deps.ready"
fi
inputs="$(sha256sum "$ROOT/scripts/patch-i3-controls.py" "$ROOT/packages/i3wm/ooonana_controls.h" | awk '{print $1}' | sha256sum | awk '{print $1}')"
if [[ "$resume" == --refresh-source && -d "$mountpoint/opt/i3-4.24" && -f "$mountpoint/etc/ooonana-i3-build-inputs" && "$(cat "$mountpoint/etc/ooonana-i3-build-inputs")" != "$inputs" ]]; then
  old_inputs="$(cat "$mountpoint/etc/ooonana-i3-build-inputs")"
  [[ "$old_inputs" =~ ^[a-f0-9]{64}$ && ! -e "$mountpoint/opt/i3-4.24.$old_inputs" && ! -e "$mountpoint/opt/i3-build.$old_inputs" ]]
  # Keep exact prior source/build history inside this owned image, never erase.
  for name in i3-4.24 i3-build; do
    [[ ! -L "$mountpoint/opt/$name" && "$(realpath -m "$mountpoint/opt/$name")" == "$mountpoint/opt/$name" ]]
    if [[ -e "$mountpoint/opt/$name" ]]; then mv -- "$mountpoint/opt/$name" "$mountpoint/opt/$name.$old_inputs"; fi
  done
fi
if [[ -e "$mountpoint/opt/i3-4.24" ]]; then
  [[ -f "$mountpoint/etc/ooonana-i3-build-inputs" && "$(cat "$mountpoint/etc/ooonana-i3-build-inputs")" == "$inputs" ]] || {
    echo 'Build source inputs changed; preserve image and start fresh candidate' >&2; exit 2;
  }
else
  mkdir -p "$mountpoint/opt"
  tar -xJf "$archive" -C "$mountpoint/opt"
  python3 -B "$ROOT/scripts/patch-i3-controls.py" --source "$mountpoint/opt/i3-4.24"
  printf '%s\n' "$inputs" >"$mountpoint/etc/ooonana-i3-build-inputs"
fi
printf 'Building isolated candidate; network disabled during compilation\n'
unshare --net chroot "$mountpoint" /usr/bin/env -i HOME=/root \
  PATH=/usr/bin:/bin:/usr/sbin:/sbin SOURCE_DATE_EPOCH=1730914033 TZ=UTC LANG=C.UTF-8 \
  /bin/sh -ec '
    if [ ! -f /opt/i3-build/build.ninja ]; then
      meson setup /opt/i3-build /opt/i3-4.24 --prefix=/usr --buildtype=release -Ddocs=false -Dmans=false
    fi
    ninja -C /opt/i3-build -j2 i3
    /opt/i3-build/i3 --version
  ' >"$workspace/out/compile.log" 2>&1 || { tail -80 "$workspace/out/compile.log"; exit 1; }
cp "$mountpoint/opt/i3-build/i3" "$workspace/out/i3"
chmod 0755 "$workspace/out/i3"
sha256sum "$workspace/out/i3" >"$workspace/out/SHA256SUMS"
python3 -B - "$ROOT" "$workspace/out" <<'PY_MANIFEST'
import hashlib
import json
from pathlib import Path
import sys
root, output = map(Path, sys.argv[1:])
inputs = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
          ("scripts/patch-i3-controls.py", "packages/i3wm/ooonana_controls.h")}
manifest = {"format": 1, "control_api": 1,
            "binary_sha256": hashlib.sha256((output / "i3").read_bytes()).hexdigest(),
            "inputs": inputs,
            "source": json.loads((root / "packages/i3wm/source-pins.json").read_text()),
            "dependencies": (output / "build-dependencies.txt").read_text().splitlines(),
            "compile_network": "disabled", "gui_verified": False}
(output / "build-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY_MANIFEST
printf 'I3_CONTROLS_CANDIDATE_BUILT %s; not installed or GUI-certified\n' "$workspace/out/i3"
