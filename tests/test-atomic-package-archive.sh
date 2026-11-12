#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/lib/common.sh"

work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/source" "$work/out dir"
archive="$work/out dir/package.tar.gz"
saved="$work/out dir/saved.tar.gz"
args=(--sort=name --mtime='UTC 1970-01-01' --numeric-owner --owner=0 --group=0
      '--pax-option=delete=atime,delete=ctime' -C "$work/source" -cf - .)
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
no_temps() {
  [[ -z "$(find "$work/out dir" -name '*.tmp.*' -print -quit)" ]] || fail 'temporary archive leaked'
}

printf 'original\n' >"$work/source/payload"
tar "${args[@]}" | gzip -n >"$work/reference.tar.gz"
(umask 027; ooonana_tar_gzip_atomic "$archive" "${args[@]}")
cmp "$archive" "$work/reference.tar.gz" || fail 'reproducible archive bytes changed'
[[ "$(stat -c %a "$archive")" == 640 ]] || fail 'fresh archive ignores umask'
ln "$archive" "$saved"
saved_hash="$(sha256sum "$saved")"
saved_inode="$(stat -c %i "$saved")"

printf 'rebuilt\n' >"$work/source/payload"
(umask 077; ooonana_tar_gzip_atomic "$archive" "${args[@]}")
[[ "$(tar -xOzf "$archive" ./payload)" == rebuilt ]] || fail 'replacement payload missing'
[[ "$(stat -c %a "$archive")" == 640 ]] || fail 'existing archive mode changed'
[[ "$(stat -c %i "$archive")" != "$saved_inode" ]] || fail 'saved inode overwritten'
[[ "$(sha256sum "$saved")" == "$saved_hash" ]] || fail 'saved hardlink bytes changed'

ooonana_write_atomic "$archive" cat -- "$work/reference.tar.gz"
cmp "$archive" "$work/reference.tar.gz" || fail 'copied archive bytes changed'
[[ "$(stat -c %i "$archive")" != "$saved_inode" ]] || fail 'copy wrote through saved hardlink'

before="$(sha256sum "$archive")"
before_inode="$(stat -c %i "$archive")"
for failure in tar gzip chmod mv; do
  if (
    case "$failure" in
      tar) tar() { printf 'partial tar'; return 43; } ;;
      gzip) gzip() { cat >/dev/null; printf 'partial gzip'; return 44; } ;;
      chmod) chmod() { return 45; } ;;
      mv) mv() { return 46; } ;;
    esac
    ooonana_tar_gzip_atomic "$archive" "${args[@]}"
  ); then
    fail "$failure failure was accepted"
  fi
  [[ "$(sha256sum "$archive")" == "$before" ]] || fail "$failure changed old archive"
  [[ "$(stat -c %i "$archive")" == "$before_inode" ]] || fail "$failure replaced old inode"
  [[ "$(sha256sum "$saved")" == "$saved_hash" ]] || fail "$failure changed saved snapshot"
  no_temps
done

if ooonana_tar_gzip_atomic "$work/out dir/new.tar.gz" -C "$work/missing" -cf - . 2>/dev/null; then
  fail 'missing source accepted'
fi
[[ ! -e "$work/out dir/new.tar.gz" ]] || fail 'failed first build published archive'
ln -s "$saved" "$work/out dir/linked.tar.gz"
if ooonana_tar_gzip_atomic "$work/out dir/linked.tar.gz" "${args[@]}" 2>/dev/null; then
  fail 'linked destination accepted'
fi
[[ -L "$work/out dir/linked.tar.gz" && "$(sha256sum "$saved")" == "$saved_hash" ]] || fail 'symlink target changed'
mkdir "$work/out dir/directory.tar.gz"
if ooonana_tar_gzip_atomic "$work/out dir/directory.tar.gz" "${args[@]}" 2>/dev/null; then
  fail 'directory destination accepted'
fi
no_temps
printf 'ok atomic package archives: reproducibility, hardlinks, failed writes, modes and path guards\n'
