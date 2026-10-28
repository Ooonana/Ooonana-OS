#!/usr/bin/env bash
# Private installed candidate, not the user's Ooonana WSL or physical devices.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != --worker ]]; then
  [[ $# == 4 && $EUID == 0 ]] || { echo 'Usage: ROOTFS PREVIOUS_QA_UPPER UNSIGNED_STAGE OUTPUT'; exit 2; }
  base="$(realpath "$1")"; previous="$(realpath "$2")"; stage="$(realpath "$3")"; output="$(realpath "$4")"
  [[ "$base" == /var/tmp/ooonana-*/rootfs-stage/full-i3-rootfs &&
     "$previous" == /var/tmp/ooonana-native-upgrade-*/upper &&
     "$stage" == /mnt/winf/Ooonana/ooonana-os/build/native-source-stage-* &&
     "$output" == /var/tmp/ooonana-installed-desktop-* && ! -e "$output/rootfs-stage" &&
     -f "$stage/STAGING-ONLY.txt" && ! -e "$stage/CURRENT" ]] || exit 2
  exec unshare --mount --net --pid --fork --kill-child --propagation private \
    bash "$0" --worker "$base" "$previous" "$stage" "$output"
fi
shift; base="$1"; previous="$2"; stage="$3"; output="$4"
mkdir -p "$output/"{upper,work,repo/archives,rootfs-stage/full-i3-rootfs,empty-sources}
root="$output/rootfs-stage/full-i3-rootfs"; repo="$output/repo"
cleanup() {
  mountpoint -q "$repo/archives" && umount "$repo/archives" || true
  mountpoint -q "$root" && umount "$root" || true
}
trap cleanup EXIT
mount -t overlay overlay -o "lowerdir=$previous:$base,upperdir=$output/upper,workdir=$output/work" "$root"
cp "$stage"/*.pkg "$stage/index.tsv" "$stage/SHA256SUMS" "$repo/"
cp -a "$stage/hooks" "$repo/"
mount --bind "$stage/archives" "$repo/archives"
mount -o remount,bind,ro "$repo/archives"
umask 077
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$output/qa-only.key" >/dev/null 2>&1
openssl pkey -in "$output/qa-only.key" -pubout -out "$output/qa-only.pub" >/dev/null 2>&1
openssl dgst -sha256 -sign "$output/qa-only.key" -out "$repo/SHA256SUMS.sig" "$repo/SHA256SUMS"
cp "$root/etc/ooonana/polybar.ini" "$output/custom-polybar.before"
OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache" \
  OOONANA_SOURCES_DIR="$output/empty-sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" \
  OOONANA_REQUIRE_SIGNED_REPOS=1 OOONANA_KEEP_UPDATE_BACKUPS=all \
  bash "$SOURCE/packages/ooonana/usr/bin/ooonana" reinstall ooonana-core-runtime >"$output/core-reinstall.log" 2>&1
if [[ ! -x "$root/usr/bin/rofi" ]]; then
  OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache" \
    OOONANA_SOURCES_DIR="$output/empty-sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" \
    OOONANA_REQUIRE_SIGNED_REPOS=1 OOONANA_KEEP_UPDATE_BACKUPS=all \
    bash "$SOURCE/packages/ooonana/usr/bin/ooonana" get rofi-x11-wayland >"$output/rofi-install.log" 2>&1
fi
cmp "$root/etc/ooonana/polybar.ini" "$output/custom-polybar.before"
python3 -B - "$root" "$stage" "$SOURCE" <<'PY'
from pathlib import Path
import hashlib, json, sys, tarfile
root, stage, source = map(Path, sys.argv[1:])
archive = stage/'archives/ooonana-core-runtime-0.10.0.tar.gz'
verified = {}
with tarfile.open(archive) as bundle:
    members = {m.name.removeprefix('./'): m for m in bundle}
    # Explicit candidate-default session. Custom config preservation was proved
    # above; the archived copy remains in the receipt, never silently migrated.
    for name in ('etc/ooonana/polybar.ini', 'etc/i3/config', 'etc/i3/config.keycodes'):
        (root/name).write_bytes(bundle.extractfile(members[name]).read())
    for name in ('usr/lib/ooonana/ui/common.py','usr/lib/ooonana/ui/shell_flyout.py',
                 'usr/lib/ooonana/ui/controls_app.py','usr/lib/ooonana/ui/settings_app.py',
                 'usr/lib/ooonana/ui/dock_app.py','usr/lib/ooonana/ui/setup_app.py',
                 'usr/bin/ooonana','usr/bin/ooonana-shell','usr/bin/ooonana-panel-start',
                 'usr/share/icons/OoonanaTailless/cursors/left_ptr'):
        data = bundle.extractfile(members[name]).read()
        assert data == (root/name).read_bytes() == (source/'packages/ooonana'/name).read_bytes(), name
        verified[name] = hashlib.sha256(data).hexdigest()
receipt = dict(archive_verified=True, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
               source_hashes=verified, config_preserved=True, qa_default_session=True,
               production_signing=False, physical_devices_exposed=False)
marker=root/'var/lib/ooonana/qa-installed-receipt.json'
marker.write_text(json.dumps(receipt,indent=2)+'\n')
(root.parent.parent/'installed-receipt.json').write_text(marker.read_text())
print('INSTALLED_CANDIDATE_BYTES_OK verified archive/source/installed files; custom config preserved',flush=True)
PY
failure=0
for probe in desktop-assets-ui live-theme-ui panel-live-ui panel-media-runtime dock-ui workspace-ui settings-storage-ui settings-details-ui setup-details-ui admin-prompt-ui settings-admin-ui shell-flyout-ui audio-runtime; do
  mkdir "$output/$probe"
  OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY="$probe" OOONANA_GUI_GEOMETRY=1280x800 \
    OOONANA_GUI_THEME=dark OOONANA_GUI_TEXT_SCALE=1.0 \
    bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$output/$probe" >"$output/$probe/driver.log" 2>&1 || {
      tail -22 "$output/$probe/$probe.log"; tail -12 "$output/$probe/driver.log"; failure=1;
    }
  if grep -qx "PASS $probe" "$output/$probe/driver.log"; then echo "INSTALLED_GUI_PASS $probe"; fi
done
for probe in settings-storage-ui settings-details-ui setup-details-ui shell-flyout-ui audio-runtime; do
  mkdir "$output/scaled-$probe"
  OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY="$probe" OOONANA_GUI_GEOMETRY=760x600 \
    OOONANA_GUI_THEME=light OOONANA_GUI_TEXT_SCALE=2.0 \
    bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$output/scaled-$probe" >"$output/scaled-$probe/driver.log" 2>&1 || {
      tail -22 "$output/scaled-$probe/$probe.log"; tail -12 "$output/scaled-$probe/driver.log"; failure=1;
    }
  if grep -qx "PASS $probe" "$output/scaled-$probe/driver.log"; then echo "INSTALLED_GUI_PASS scaled-$probe"; fi
done
[ "$failure" = 0 ] || exit 1
echo 'INSTALLED_DESKTOP_QA_OK candidate default session; physical/WSLg gates remain unverified'
