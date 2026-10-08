#!/bin/sh
# Same-version source sync through native package transactions, never raw overlays.
set -eu

usage() {
  printf '%s\n' 'Usage: update-installed-wsl.sh --repo DIR [--dry-run]' \
    'Build current core/runtime packages in a Linux build host first.' \
    'Include current OpenVINO package when already installed.' \
    'Versions must match installed packages; use ooonana upgrade for version changes.' \
    'Custom configs and rollback checkpoints stay under native package management.'
}
case "${1:-}" in -h|--help) usage; exit 0 ;; esac

target_root="${OOONANA_ROOT:-/}"
case "$target_root" in /*) ;; *) echo 'update-installed-wsl: target root must be absolute' >&2; exit 2 ;; esac
target_root="$(readlink -f "$target_root")"
[ -d "$target_root" ] || { echo 'update-installed-wsl: target root missing' >&2; exit 2; }
prefix="${target_root%/}"
case "${WSL_DISTRO_NAME:-}" in
  Ooonana|ooonana|"") ;;
  *) echo "update-installed-wsl: refusing non-Ooonana distro: $WSL_DISTRO_NAME" >&2; exit 2 ;;
esac
os_id="$(sed -n 's/^ID=//p' "$prefix/etc/os-release" 2>/dev/null | head -n 1 | tr -d '"')"
[ "$os_id" = ooonana ] || {
  echo "update-installed-wsl: refusing target OS: ${os_id:-unknown}" >&2; exit 2;
}
if [ "$target_root" = / ] && [ "$(id -u)" -ne 0 ]; then
  if command -v doas >/dev/null 2>&1; then
    exec doas sh "$0" "$@"
  elif command -v sudo >/dev/null 2>&1; then
    exec sudo sh "$0" "$@"
  fi
  echo 'update-installed-wsl: run as root' >&2
  exit 126
fi

repo=""
dry_run=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      repo="$2"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    *) usage >&2; exit 2 ;;
  esac
done
[ -n "$repo" ] && [ -d "$repo" ] || {
  echo 'update-installed-wsl: --repo with built packages required; raw source overlay retired' >&2
  exit 2
}
[ -z "${OOONANA_PERSONAL_CURSOR_DIR:-}" ] || {
  echo 'update-installed-wsl: personal cursor overlay retired; existing cursor settings are preserved' >&2
  exit 2
}
repo="$(readlink -f "$repo")"
resolved_repo="$repo"
pointer=""
if [ -f "$repo/CURRENT" ]; then pointer="$repo/CURRENT"
elif [ -f "$repo/current" ]; then pointer="$repo/current"; fi
if [ -n "$pointer" ]; then
  generation="$(tr -d '\r' <"$pointer")"
  case "$generation" in ""|*[!0-9a-f]*) echo 'update-installed-wsl: invalid generation' >&2; exit 2 ;; esac
  [ "${#generation}" -eq 64 ] || { echo 'update-installed-wsl: invalid generation' >&2; exit 2; }
  resolved_repo="$repo/generations/$generation"
  [ -s "$resolved_repo/index.tsv" ] && [ -s "$resolved_repo/SHA256SUMS" ] || {
    echo 'update-installed-wsl: incomplete generation' >&2; exit 2;
  }
fi
[ -d "$resolved_repo" ] || { echo 'update-installed-wsl: generation missing' >&2; exit 2; }
cli="$prefix/usr/bin/ooonana"
[ -x "$cli" ] || { echo 'update-installed-wsl: native CLI missing' >&2; exit 2; }
state="${OOONANA_STATE_DIR:-$prefix/var/lib/ooonana/packages}"
packages="ooonana-core-runtime ooonana-core"
if [ -f "$state/installed/openvino-chat.pkg" ]; then packages="$packages openvino-chat"; fi

# Inspect declarations without executing metadata. Native CLI verifies repository
# signatures/checksums again before loading metadata or changing package files.
for package in $packages; do
  case "$package" in
    ooonana-core|ooonana-core-runtime)
      # Core migration and health validation require the factory hooks.
      # Refuse incomplete staging before changing any installed payload.
      hook="$resolved_repo/hooks/$package.healthcheck"
      [ -s "$hook" ] && [ -x "$hook" ] || {
        echo "update-installed-wsl: required health hook missing/not executable: $package" >&2; exit 2;
      } ;;
  esac
  candidate="$resolved_repo/$package.pkg"
  installed="$state/installed/$package.pkg"
  [ -s "$candidate" ] && [ -s "$installed" ] || {
    echo "update-installed-wsl: package missing: $package" >&2; exit 2;
  }
  candidate_version="$(sed -n 's/^OOONANA_PKG_VERSION="\([^"]*\)"$/\1/p' "$candidate")"
  installed_version="$(sed -n 's/^OOONANA_PKG_VERSION="\([^"]*\)"$/\1/p' "$installed")"
  [ -n "$candidate_version" ] && [ "$candidate_version" = "$installed_version" ] || {
    echo "update-installed-wsl: version differs: $package; use ooonana upgrade" >&2; exit 2;
  }
  archive="$(sed -n 's/^OOONANA_PKG_ARCHIVE="\([^"]*\)"$/\1/p' "$candidate")"
  if [ -n "$archive" ]; then
    case "$archive" in /*|..|../*|*/../*|*/..) echo 'update-installed-wsl: unsafe archive path' >&2; exit 2 ;; esac
    expected="$(sed -n 's/^OOONANA_PKG_SHA256="\([^"]*\)"$/\1/p' "$candidate")"
    [ "${#expected}" -eq 64 ] || { echo 'update-installed-wsl: archive checksum missing' >&2; exit 2; }
    case "$expected" in *[!0-9a-fA-F]*) echo 'update-installed-wsl: invalid checksum' >&2; exit 2 ;; esac
    [ -s "$resolved_repo/$archive" ] || { echo "update-installed-wsl: archive missing: $package" >&2; exit 2; }
    actual="$(sha256sum "$resolved_repo/$archive" | awk '{print $1}')"
    [ "$actual" = "$expected" ] || { echo "update-installed-wsl: checksum mismatch: $package" >&2; exit 2; }
  elif [ "$package" != ooonana-core ]; then
    echo "update-installed-wsl: payload archive missing: $package" >&2; exit 2
  fi
done

work="$(mktemp -d "${TMPDIR:-/tmp}/ooonana-wsl-sync.XXXXXX")"
trap 'rm -rf "$work"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$work/cache" "$work/sources"
export OOONANA_ROOT="$target_root" OOONANA_STATE_DIR="$state"
# Pin preflight's snapshot even if CURRENT advances during synchronization.
export OOONANA_REPO_DIR="$resolved_repo" OOONANA_SOURCES_DIR="$work/sources" OOONANA_CACHE_DIR="$work/cache"
export OOONANA_KEEP_UPDATE_BACKUPS="${OOONANA_KEEP_UPDATE_BACKUPS:-all}"
# IDs come only from the fixed list above. Preserve CLI's trust/signature policy.
# shellcheck disable=SC2086
"$cli" reinstall $packages --dry-run
if [ "$dry_run" -eq 1 ]; then exit 0; fi
# shellcheck disable=SC2086
"$cli" reinstall $packages
for package in $packages; do "$cli" verify "$package"; done
echo 'Ooonana WSL packages synchronized; custom configuration retained'
