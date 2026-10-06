#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

OUT_DIR="$(ooonana_default_build_dir)/android-aarch64-repo"
PACKAGE_PROFILE="$ROOT/configs/packages/android-aarch64.list"
ARCH="aarch64"
ALPINE_VERSION="3.23"
REPO_URLS=""
SIGN_KEY="${OOONANA_REPO_SIGN_KEY:-}"
PUBLIC_KEY="${OOONANA_REPO_PUBLIC_KEY:-}"
TRUSTED_KEY="$ROOT/packages/ooonana/etc/ooonana/trusted-keys/repository-20261002.pub"
CLEAN=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
Build the Ooonana Android/AArch64 package repository.

The result is an Ooonana repository consumed by the Ooonana package manager.
For packages that need architecture-specific binaries, this builder imports
their AArch64 payloads from configured upstream package sources and converts
them into Ooonana repository entries. The normal desktop Ooonana repository
contains x86_64 payloads and must never be used by the Android APK.

Usage:
  scripts/build-android-package-repo.sh [options]

Options:
  --out-dir PATH          Output staging repository
  --package-profile PATH  Seed package list
  --arch ARCH             Alpine architecture (default: aarch64)
  --alpine-version VER    Alpine branch (default: 3.23)
  --repo-url URL          Alpine repository URL; repeatable
  --sign-key PATH         Sign SHA256SUMS
  --public-key PATH       Publish matching public key
  --clean                 Remove output before building
  --dry-run               Print the resolved plan only
  -h, --help              Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --package-profile) PACKAGE_PROFILE="$2"; shift 2 ;;
    --arch) ARCH="$2"; shift 2 ;;
    --alpine-version) ALPINE_VERSION="$2"; shift 2 ;;
    --repo-url) REPO_URLS="$REPO_URLS $2"; shift 2 ;;
    --sign-key) SIGN_KEY="$2"; shift 2 ;;
    --public-key) PUBLIC_KEY="$2"; shift 2 ;;
    --clean) CLEAN=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) ooonana_die "unknown option: $1" ;;
  esac
done

[[ "$ARCH" = "aarch64" ]] || ooonana_die "Android repo architecture must be aarch64"
case "$ALPINE_VERSION" in
  *[!0-9.]*|"") ooonana_die "bad Alpine version: $ALPINE_VERSION" ;;
esac
[[ -r "$PACKAGE_PROFILE" ]] || ooonana_die "missing package profile: $PACKAGE_PROFILE"
[[ -f "$TRUSTED_KEY" ]] || ooonana_die "bundled trusted repo key missing: $TRUSTED_KEY"
[[ -z "$SIGN_KEY" || -f "$SIGN_KEY" ]] || ooonana_die "sign key missing: $SIGN_KEY"
[[ -z "$PUBLIC_KEY" || -f "$PUBLIC_KEY" ]] || ooonana_die "public key missing: $PUBLIC_KEY"
ooonana_require_commands cmp

if [[ -z "$REPO_URLS" ]]; then
  REPO_URLS="https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/main/${ARCH} https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/community/${ARCH}"
fi

package_list="$(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$PACKAGE_PROFILE" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
[[ -n "$package_list" ]] || ooonana_die "package profile is empty: $PACKAGE_PROFILE"

repo_args=()
for repo in $REPO_URLS; do
  repo_args+=(--repo-url "$repo")
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'out: %s\n' "$OUT_DIR"
  printf 'arch: %s\n' "$ARCH"
  printf 'alpine: %s\n' "$ALPINE_VERSION"
  printf 'profile: %s\n' "$PACKAGE_PROFILE"
  printf 'packages: %s\n' "$package_list"
  printf 'repos: %s\n' "$REPO_URLS"
  [[ -n "$SIGN_KEY" ]] && printf 'sign-key: %s\n' "$SIGN_KEY"
  [[ -n "$PUBLIC_KEY" ]] && printf 'public-key: %s\n' "$PUBLIC_KEY"
  ooonana_print_command bash "$ROOT/scripts/import-apk-package.sh" --arch "$ARCH" "${repo_args[@]}" --out-dir "$OUT_DIR" $package_list
  exit 0
fi

[[ "$CLEAN" -eq 0 ]] || rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# Import only AArch64 compatibility payloads. Do not copy the PC repo's Ooonana core,
# kernel, OpenVINO, Wine, chat, or other native release packages.
# shellcheck disable=SC2086
bash "$ROOT/scripts/import-apk-package.sh" \
  --arch "$ARCH" \
  "${repo_args[@]}" \
  --out-dir "$OUT_DIR" \
  $package_list

# Every imported package must retain the source-architecture marker written by
# the importer. This is an additional guard against publishing x86_64 payloads.
for package in "$OUT_DIR"/*.pkg; do
  [[ -f "$package" ]] || continue
  grep -q '^OOONANA_PKG_KIND="apk"$' "$package" ||
    ooonana_die "unexpected non-APK metadata in Android repo: $package"
  grep -q "^OOONANA_PKG_COMPONENTS=.*alpine ${ARCH}" "$package" ||
    ooonana_die "package lacks AArch64 marker: $package"
done

for forbidden in \
  ooonana-core ooonana-core-runtime ooonana-kernel \
  openvino-chat wine wine-compat bunanachat devicechat; do
  [[ ! -e "$OUT_DIR/$forbidden.pkg" ]] ||
    ooonana_die "forbidden native/PC package entered Android repo: $forbidden"
done

# Re-index after all safety checks and optionally sign the final manifest.
rm -f "$OUT_DIR/SHA256SUMS.sig" "$OUT_DIR/repo.pub"
if [[ -n "$PUBLIC_KEY" ]]; then
  cp "$PUBLIC_KEY" "$OUT_DIR/repo.pub"
  chmod 0644 "$OUT_DIR/repo.pub" 2>/dev/null || true
elif [[ -n "$SIGN_KEY" ]]; then
  command -v openssl >/dev/null 2>&1 || ooonana_die "repo signing needs openssl"
  openssl pkey -in "$SIGN_KEY" -pubout -out "$OUT_DIR/repo.pub"
  chmod 0644 "$OUT_DIR/repo.pub"
fi

if [[ -f "$OUT_DIR/repo.pub" ]] && ! cmp -s "$OUT_DIR/repo.pub" "$TRUSTED_KEY"; then
  ooonana_die "Android repo public key does not match bundled Ooonana trusted key"
fi

if [[ -n "$SIGN_KEY" ]]; then
  "$ROOT/packages/ooonana/usr/bin/ooonana" repo index --sign-key "$SIGN_KEY" "$OUT_DIR" >/dev/null
else
  "$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$OUT_DIR" >/dev/null
fi

count="$(wc -l < "$OUT_DIR/index.tsv" | tr -d ' ')"
ooonana_log "Android AArch64 repo staging ready: $OUT_DIR ($count packages)"
