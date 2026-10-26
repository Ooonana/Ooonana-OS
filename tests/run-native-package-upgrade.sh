#!/usr/bin/env bash
# Actual candidate packages; private COW installation and ephemeral QA trust only.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != --worker ]]; then
  [[ $# == 3 && $EUID == 0 ]] || { echo 'Usage (root): run-native-package-upgrade.sh ROOTFS UNPUBLISHED_STAGE OUTPUT'; exit 2; }
  rootfs="$(realpath "$1")"; stage="$(realpath "$2")"; output="$(realpath "$3")"
  [[ "$rootfs" == /var/tmp/ooonana-*/rootfs-stage/full-i3-rootfs && "$output" == /var/tmp/ooonana-native-upgrade-* &&
     "$stage" == /mnt/winf/Ooonana/ooonana-os/build/native-source-stage-* && ! -e "$stage/CURRENT" &&
     -f "$stage/STAGING-ONLY.txt" && -f "$stage/SHA256SUMS" && ! -e "$output/root" ]] || exit 2
  grep -qx 'ID=ooonana' "$rootfs/etc/os-release"
  unshare --mount --net --pid --fork --kill-child bash "$0" --worker "$rootfs" "$stage" "$output"
  exit
fi
shift; rootfs="$1"; stage="$2"; output="$3"
mount --make-rprivate /
mkdir "$output/upper" "$output/work" "$output/root" "$output/repo"
root="$output/root"; repo="$output/repo"
cleanup() {
  mountpoint -q "$repo/archives" && umount "$repo/archives" || true
  mountpoint -q "$root/dev" && umount "$root/dev" || true
  mountpoint -q "$root" && umount "$root" || true
}
trap cleanup EXIT
mount -t overlay overlay -o "lowerdir=$rootfs,upperdir=$output/upper,workdir=$output/work" "$root"
mount -t tmpfs -o nosuid,noexec,size=1m tmpfs "$root/dev"
for node in null:3 zero:5 random:8 urandom:9; do mknod -m 666 "$root/dev/${node%:*}" c 1 "${node#*:}"; done
cp "$stage"/*.pkg "$stage/index.tsv" "$stage/SHA256SUMS" "$repo/"
cp -a "$stage/hooks" "$repo/"
mkdir "$repo/archives"
mount --bind "$stage/archives" "$repo/archives"; mount -o remount,bind,ro "$repo/archives"
umask 077
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$output/qa-only.key" >/dev/null 2>&1
openssl pkey -in "$output/qa-only.key" -pubout -out "$output/qa-only.pub" >/dev/null 2>&1
sign_qa() {
  cp "$stage/SHA256SUMS" "$repo/SHA256SUMS"
  if [[ -f "$repo/hooks/i3wm.healthcheck" ]]; then
    (cd "$repo"; sha256sum hooks/i3wm.healthcheck) >>"$repo/SHA256SUMS"
  fi
  openssl dgst -sha256 -sign "$output/qa-only.key" -out "$repo/SHA256SUMS.sig" "$repo/SHA256SUMS"
}
export OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache"
export OOONANA_SOURCES_DIR="$output/sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" OOONANA_REQUIRE_SIGNED_REPOS=1
export OOONANA_KEEP_UPDATE_BACKUPS=all
cli() { bash "$SOURCE/packages/ooonana/usr/bin/ooonana" "$@"; }
sign_qa
original=/var/tmp/ooonana-repo-repair-20261011.iA9JyBvt/repo
# Cached full desktop predates Qt installation. Install original pinned Qt first,
# exercising native dependency installation before its real versioned upgrade.
OOONANA_REPO_DIR="$original" \
OOONANA_REPO_VERIFY_KEY="$SOURCE/packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub" \
cli get qt6-qtbase-x11 >"$output/install-original-qt.log" 2>&1
sha256sum "$root/usr/bin/i3" >"$output/i3-before.sha256"
cp "$root/var/lib/ooonana/packages/installed/i3wm.pkg" "$output/i3-before.pkg"
printf '#!/bin/sh\necho deliberate-QA-health-failure >&2\nexit 17\n' >"$repo/hooks/i3wm.healthcheck"
chmod 755 "$repo/hooks/i3wm.healthcheck"; sign_qa
if cli upgrade i3wm >"$output/rollback.log" 2>&1; then echo 'FAIL expected private health failure'; exit 1; fi
grep -q deliberate-QA-health-failure "$output/rollback.log"
sha256sum -c "$output/i3-before.sha256"
cmp "$root/var/lib/ooonana/packages/installed/i3wm.pkg" "$output/i3-before.pkg"
rm "$repo/hooks/i3wm.healthcheck"; sign_qa
cli upgrade i3wm linux-pam i3lock qt6-qtbase-x11 >"$output/upgrade.log" 2>&1
config="$root/etc/ooonana/polybar.ini"
printf '\n; owned-QA-custom-config-preserved\n' >>"$config"
cp "$config" "$output/custom-config.before"
cli reinstall ooonana-core-runtime >"$output/core-reinstall.log" 2>&1
cmp "$config" "$output/custom-config.before"
grep -q OOONANA_CORE_HEALTHCHECK_OK "$output/core-reinstall.log"
[[ "$(stat -c '%u:%g:%a' "$root/usr/sbin/unix_chkpwd")" == 0:0:4755 ]]
chroot "$root" /usr/bin/i3 --version >"$output/i3-version.log"
chroot "$root" /usr/bin/i3lock --version >"$output/locker-version.log" 2>&1
chroot "$root" /lib/ld-musl-x86_64.so.1 --list /usr/lib/qt6/plugins/platformthemes/libqxdgdesktopportal.so >"$output/qt-loader.log" 2>&1
! grep -Ei 'not found|error loading|error relocating' "$output/qt-loader.log"
python3 -B - "$root" "$stage" "$SOURCE" <<'PY'
import hashlib, importlib.util, json, sys, tarfile
from pathlib import Path
root, stage, source = map(Path, sys.argv[1:])
spec=importlib.util.spec_from_file_location('release',source/'scripts/check-release-repo.py')
release=importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
payloads={'i3wm':'usr/bin/i3','i3lock':'usr/bin/i3lock','qt6-qtbase-x11':release.QT_PLUGIN,'linux-pam':'usr/sbin/unix_chkpwd'}
receipt={}
for package, name in payloads.items():
    metadata=release.metadata(stage/(package+'.pkg'))
    with tarfile.open(stage/metadata['ARCHIVE']) as bundle:
        member=next(item for item in bundle if item.name.removeprefix('./')==name)
        expected=hashlib.sha256(bundle.extractfile(member).read()).hexdigest()
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,package
    installed=release.metadata(root/'var/lib/ooonana/packages/installed'/(package+'.pkg'))
    assert installed['VERSION']==metadata['VERSION'],package
    receipt[package]={'version':installed['VERSION'],'binary_sha256':expected}
for name in ('legacy_tray.py','ui/tray_app.py','oonana_game.py','ui/launcher_app.py'):
    relative='packages/ooonana/usr/lib/ooonana/'+name
    assert (root/'usr/lib/ooonana'/name).read_bytes()==(source/relative).read_bytes(),name
assert (root/'usr/bin/ooonana').read_bytes()==(source/'packages/ooonana/usr/bin/ooonana').read_bytes()
(root.parent/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
PY
echo 'NATIVE_PACKAGE_UPGRADE_OK original Qt installation; signed QA native upgrades; real failed-health rollback; custom config preserved; installed ELF/dependencies/source match'
