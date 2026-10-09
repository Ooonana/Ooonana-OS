#!/usr/bin/env bash
# Existing QA caches only; no downloads, production state, or weight compilation.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != --worker ]]; then
  [[ $# -eq 4 && $EUID -eq 0 ]] || {
    printf 'Usage (root): %s UBUNTU_QA_ROOTFS CACHED_VENV EMPTY_QA_DIR MODEL_ROOT\n' "$0" >&2; exit 2;
  }
  base=$(realpath "$1"); venv=$(realpath "$2"); qa=$(realpath "$3"); models=$(realpath "$4")
  for path in "$base" "$venv" "$qa"; do [[ "$path" == /var/tmp/* && "$path" != *[:,]* ]]; done
  [[ "$base" != "$qa" && "$venv" != "$qa" && -d "$qa" ]]
  for cached in "$base" "$venv" "$models"; do
    [[ "$qa" != "$cached" && "$qa" != "$cached/"* && "$cached" != "$qa/"* ]]
  done
  [[ -z "$(find "$qa" -mindepth 1 -maxdepth 1 -print -quit)" ]]
  grep -qx 'VERSION_ID="24.04"' "$base/etc/os-release"
  [[ -x "$venv/bin/python" && -x "$venv/bin/openvino" ]]
  export OOONANA_TRANSPORT_WORKER=1
  exec timeout --kill-after=5 180 unshare --mount --pid --fork --kill-child --net --ipc --mount-proc \
    --propagation private bash "$0" --worker "$base" "$venv" "$qa" "$models"
fi
[[ $# -eq 5 && $EUID -eq 0 && $$ -eq 1 && "${OOONANA_TRANSPORT_WORKER:-0}" == 1 ]] || {
  printf 'Require owned private namespace worker\n' >&2; exit 2;
}
base=$2; venv=$3; qa=$4; models=$5
mount --bind "$SOURCE" "$SOURCE"
mount -o remount,bind,ro "$SOURCE"
rootfs=$qa/state/.runtime-generations/runtime.QAcheck1/rootfs
mkdir -p "$qa/base" "$qa/upper" "$qa/work" "$rootfs" "$qa/home/.openvino" "$qa/workspace/models"
ln -s .runtime-generations/runtime.QAcheck1/rootfs "$qa/state/rootfs"
mount --bind "$base" "$qa/base"
mount -o remount,bind,ro "$qa/base"
mount -t overlay overlay -o "lowerdir=$qa/base,upperdir=$qa/upper,workdir=$qa/work" "$rootfs"
mkdir -p "$rootfs/opt/openvino-venv" "$rootfs/opt/openvino-chat" "$rootfs$venv" \
  "$rootfs/workspace" "$rootfs/root/.openvino" "$rootfs/root/.cache"
chown 1000:1000 "$rootfs/root"
mount --bind "$venv" "$rootfs/opt/openvino-venv"
mount -o remount,bind,ro "$rootfs/opt/openvino-venv"
# Cached console script shebang refers to its original venv path.
mount --bind "$venv" "$rootfs$venv"
mount -o remount,bind,ro "$rootfs$venv"
sha256sum "$SOURCE/packages/openvino-chat/source/pyproject.toml" | awk '{print $1}' >"$rootfs/.ooonana-openvino-ready"
mount --bind "$models" "$qa/workspace/models"
mount -o remount,bind,ro "$qa/workspace/models"
chown 1000:1000 "$qa/home" "$qa/home/.openvino"
chmod 0755 "$qa"
chmod 0700 "$qa/home"
ip link set lo up
setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
  env -i HOME="$qa/home" PATH=/usr/bin:/bin OPENVINO_HOME="$qa/home/.openvino" \
  OOONANA_TRANSPORT_ISOLATED=1 PYTHONDONTWRITEBYTECODE=1 \
  "$venv/bin/python" "$SOURCE/tests/probe-openvino-transport.py" --source "$SOURCE" --qa "$qa"
