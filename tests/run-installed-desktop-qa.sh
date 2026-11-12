#!/usr/bin/env bash
# Private installed candidate, not the user's Ooonana WSL or physical devices.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass="${OOONANA_INSTALLED_QA_PASS:-desktop}"
case "$pass" in desktop|notifications-packages|lock-sessions|lock-visuals|lock-extended|ui-10-15|task-live|input-method|installer-lifecycle|input-edges) ;; *) exit 2 ;; esac
export OOONANA_INSTALLED_QA_PASS="$pass"
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
qa_umask="$(umask)"
umask 077
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$output/qa-only.key" >/dev/null 2>&1
openssl pkey -in "$output/qa-only.key" -pubout -out "$output/qa-only.pub" >/dev/null 2>&1
openssl dgst -sha256 -sign "$output/qa-only.key" -out "$repo/SHA256SUMS.sig" "$repo/SHA256SUMS"
umask "$qa_umask"
cp "$root/etc/ooonana/polybar.ini" "$output/custom-polybar.before"
OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache" \
  OOONANA_SOURCES_DIR="$output/empty-sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" \
  OOONANA_REQUIRE_SIGNED_REPOS=1 OOONANA_KEEP_UPDATE_BACKUPS=all \
  bash "$SOURCE/packages/ooonana/usr/bin/ooonana" reinstall ooonana-core-runtime >"$output/core-reinstall.log" 2>&1
if [[ "$pass" == lock-* || "$pass" == ui-10-15 || "$pass" == input-method || "$pass" == input-edges ]]; then
  cp "$root/etc/pam.d/i3lock" "$output/locker-pam.before"
  OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache" \
    OOONANA_SOURCES_DIR="$output/empty-sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" \
    OOONANA_REQUIRE_SIGNED_REPOS=1 OOONANA_KEEP_UPDATE_BACKUPS=all \
    bash "$SOURCE/packages/ooonana/usr/bin/ooonana" upgrade i3lock >"$output/locker-upgrade.log" 2>&1
  cmp "$root/etc/pam.d/i3lock" "$output/locker-pam.before"
fi
if [[ ! -x "$root/usr/bin/rofi" ]]; then
  OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache" \
    OOONANA_SOURCES_DIR="$output/empty-sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" \
    OOONANA_REQUIRE_SIGNED_REPOS=1 OOONANA_KEEP_UPDATE_BACKUPS=all \
    bash "$SOURCE/packages/ooonana/usr/bin/ooonana" get rofi-x11-wayland >"$output/rofi-install.log" 2>&1
fi
if [[ "$pass" == input-method ]]; then
  OOONANA_ROOT="$root" OOONANA_REPO_DIR="$repo" OOONANA_CACHE_DIR="$output/cache" \
    OOONANA_SOURCES_DIR="$output/empty-sources" OOONANA_REPO_VERIFY_KEY="$output/qa-only.pub" \
    OOONANA_REQUIRE_SIGNED_REPOS=1 OOONANA_KEEP_UPDATE_BACKUPS=all \
    bash "$SOURCE/packages/ooonana/usr/bin/ooonana" get qterminal >"$output/qt-install.log" 2>&1
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
                 'usr/lib/ooonana/ui/packages_app.py','usr/lib/ooonana/ui/health_app.py',
                 'usr/lib/ooonana/ui/task_manager_app.py','usr/lib/ooonana/process_control.py',
                 'usr/lib/ooonana/input_method.py','usr/bin/ooonana-input-method',
                 'usr/share/ooonana/input-method-profile',
                 'usr/lib/ooonana/lock_screen.py','usr/lib/ooonana/session_control.py',
                 'usr/lib/ooonana/ui/ui_preferences.py','usr/bin/ooonana-lock',
                 'usr/bin/ooonana-session','usr/bin/ooonana-session-guard',
                 'usr/bin/ooonana','usr/bin/ooonana-shell','usr/bin/ooonana-panel-start',
                 'usr/share/icons/OoonanaTailless/cursors/left_ptr'):
        data = bundle.extractfile(members[name]).read()
        assert data == (root/name).read_bytes() == (source/'packages/ooonana'/name).read_bytes(), name
        verified[name] = hashlib.sha256(data).hexdigest()
    builder = (source/'scripts/build-full-i3-rootfs.sh').read_text()
    for helper in ('ooonana-i3-session', 'ooonana-installer-gui', 'ooonana-run-admin'):
        name = 'usr/bin/'+helper
        generated = builder.split('"$ROOTFS/'+name+'" <<\'EOF\'\n', 1)[1].split('\nEOF', 1)[0]+'\n'
        data = bundle.extractfile(members[name]).read()
        assert data == (root/name).read_bytes() == generated.encode(), name
        verified[name] = hashlib.sha256(data).hexdigest()
receipt = dict(archive_verified=True, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
               source_hashes=verified, config_preserved=True, qa_default_session=True,
               production_signing=False, physical_devices_exposed=False)
import os
if os.environ.get('OOONANA_INSTALLED_QA_PASS') in ('lock-sessions', 'lock-visuals', 'lock-extended', 'ui-10-15', 'input-method', 'input-edges'):
    import importlib.util
    spec = importlib.util.spec_from_file_location('release', source/'scripts/check-release-repo.py')
    release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
    package = release.metadata(stage/'i3lock.pkg')
    release.validate_native_lock(stage, package)
    with tarfile.open(stage/package['ARCHIVE']) as bundle:
        members = {m.name.removeprefix('./'): m for m in bundle}
        data = bundle.extractfile(members['usr/bin/i3lock']).read()
    assert data == (root/'usr/bin/i3lock').read_bytes(), 'Installed locker differs from verified candidate'
    receipt['native_locker'] = dict(version=package['VERSION'], sha256=hashlib.sha256(data).hexdigest(), pam_preserved=True)
marker=root/'var/lib/ooonana/qa-installed-receipt.json'
marker.write_text(json.dumps(receipt,indent=2)+'\n')
(root.parent.parent/'installed-receipt.json').write_text(marker.read_text())
print('INSTALLED_CANDIDATE_BYTES_OK verified archive/source/installed files; custom config preserved',flush=True)
PY
failure=0
normal=(desktop-assets-ui live-theme-ui panel-live-ui panel-media-runtime dock-ui workspace-ui settings-storage-ui settings-details-ui setup-details-ui admin-prompt-ui settings-admin-ui shell-flyout-ui audio-runtime)
scaled=(settings-storage-ui settings-details-ui setup-details-ui shell-flyout-ui audio-runtime)
if [[ "$pass" == notifications-packages ]]; then
  normal=(shell-flyout-ui audio-runtime notifications-runtime notification-lifecycle notification-auto-recovery notification-stale-ui package-health-ui package-transactions-ui)
  scaled=(shell-flyout-ui package-health-ui)
fi
if [[ "$pass" == lock-sessions ]]; then
  normal=(session-control-ui settings-power-ui settings-storage-ui shell-flyout-ui lock-ui)
  scaled=(session-control-ui settings-power-ui settings-storage-ui shell-flyout-ui)
fi
if [[ "$pass" == lock-visuals ]]; then
  normal=(lock-ui)
  scaled=()
fi
if [[ "$pass" == lock-extended ]]; then
  normal=()
  scaled=()
fi
if [[ "$pass" == ui-10-15 ]]; then
  normal=(package-health-ui package-transactions-ui task-details-ui task-live-ui wireless-details-ui controls-details-ui installer-ui session-control-ui)
  scaled=(package-health-ui task-details-ui wireless-details-ui controls-details-ui installer-ui settings-power-ui)
fi
if [[ "$pass" == task-live ]]; then
  normal=(task-live-ui)
  scaled=(task-live-ui)
fi
if [[ "$pass" == input-method ]]; then
  normal=(input-method-ui)
  scaled=(input-method-ui)
fi
lock_edges=0
if [[ "$pass" == input-edges ]]; then
  normal=(lock-ui)
  scaled=(lock-ui)
  lock_edges=1
fi
if [[ "$pass" == installer-lifecycle ]]; then
  normal=(installer-lifecycle-ui)
  scaled=(installer-lifecycle-ui)
fi
for probe in "${normal[@]}"; do
  mkdir "$output/$probe"
  OOONANA_GUI_LOCK_EDGES="$lock_edges" OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY="$probe" OOONANA_GUI_GEOMETRY=1280x800 \
    OOONANA_GUI_THEME=dark OOONANA_GUI_TEXT_SCALE=1.0 \
    bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$output/$probe" >"$output/$probe/driver.log" 2>&1 || {
      tail -22 "$output/$probe/$probe.log"; tail -12 "$output/$probe/driver.log"; failure=1;
    }
  if grep -qx "PASS $probe" "$output/$probe/driver.log"; then echo "INSTALLED_GUI_PASS $probe"; fi
done
for probe in "${scaled[@]}"; do
  mkdir "$output/scaled-$probe"
  OOONANA_GUI_LOCK_EDGES="$lock_edges" OOONANA_GUI_SESSION_LAYOUT_ONLY=1 OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY="$probe" OOONANA_GUI_GEOMETRY=760x600 \
    OOONANA_GUI_THEME=light OOONANA_GUI_TEXT_SCALE=2.0 \
    bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$output/scaled-$probe" >"$output/scaled-$probe/driver.log" 2>&1 || {
      tail -22 "$output/scaled-$probe/$probe.log"; tail -12 "$output/scaled-$probe/driver.log"; failure=1;
    }
  if grep -qx "PASS $probe" "$output/scaled-$probe/driver.log"; then echo "INSTALLED_GUI_PASS scaled-$probe"; fi
done
if [[ "$pass" == lock-* ]]; then
  if [[ "$pass" != lock-extended ]]; then
  for appearance in light:1 dark:2 light:2; do
    theme="${appearance%:*}"; scale="${appearance#*:}"
    dir="$output/lock-$theme-$scale"; mkdir "$dir"
    OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY=lock-ui OOONANA_GUI_GEOMETRY=1280x800 \
      OOONANA_GUI_THEME="$theme" OOONANA_GUI_DEVICE_SCALE="$scale" OOONANA_GUI_TEXT_SCALE=1.0 \
      bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$dir" >"$dir/driver.log" 2>&1 || {
        tail -20 "$dir/lock-ui.log"; failure=1;
      }
    if grep -qx 'PASS lock-ui' "$dir/driver.log"; then echo "INSTALLED_GUI_PASS lock-$theme-$scale"; fi
  done
  fi
  if [[ "$pass" == lock-visuals ]]; then
    for theme in dark light; do
      dir="$output/lock-compact-$theme"; mkdir "$dir"
      OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY=lock-ui OOONANA_GUI_GEOMETRY=760x600 \
        OOONANA_GUI_THEME="$theme" OOONANA_GUI_DEVICE_SCALE=2 OOONANA_GUI_TEXT_SCALE=1.0 \
        bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$dir" >"$dir/driver.log" 2>&1 || {
          tail -20 "$dir/lock-ui.log"; failure=1;
        }
      if grep -qx 'PASS lock-ui' "$dir/driver.log"; then echo "INSTALLED_GUI_PASS lock-compact-$theme"; fi
    done
    for theme in dark light; do
      dir="$output/lock-small-$theme"; mkdir "$dir"
      OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY=lock-ui OOONANA_GUI_GEOMETRY=640x480 \
        OOONANA_GUI_THEME="$theme" OOONANA_GUI_DEVICE_SCALE=2 OOONANA_GUI_TEXT_SCALE=1.0 \
        bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$dir" >"$dir/driver.log" 2>&1 || {
          tail -20 "$dir/lock-ui.log"; failure=1;
        }
      if grep -qx 'PASS lock-ui' "$dir/driver.log"; then echo "INSTALLED_GUI_PASS lock-small-$theme"; fi
    done
  fi
  dir="$output/lock-extended"; mkdir "$dir"
  OOONANA_GUI_INSTALLED_ONLY=1 OOONANA_GUI_ONLY=lock-ui OOONANA_GUI_GEOMETRY=1280x800 \
    OOONANA_GUI_THEME=dark OOONANA_GUI_DEVICE_SCALE=1 OOONANA_GUI_TEXT_SCALE=1.0 \
    OOONANA_GUI_LOCK_EXTENDED=1 OOONANA_GUI_LOCK_VIRTUAL_MONITORS=1 OOONANA_GUI_LOCK_CLOCK_WAIT=1 \
    bash "$SOURCE/tests/run-candidate-gui.sh" "$root" "$dir" >"$dir/driver.log" 2>&1 || {
      tail -25 "$dir/lock-ui.log"; failure=1;
    }
  if grep -qx 'PASS lock-ui' "$dir/driver.log"; then echo 'INSTALLED_GUI_PASS lock-extended'; fi
fi
[ "$failure" = 0 ] || exit 1
echo 'INSTALLED_DESKTOP_QA_OK candidate default session; physical/WSLg gates remain unverified'
