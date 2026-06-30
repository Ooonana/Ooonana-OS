#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

OUT_DIR="$(ooonana_default_build_dir)/package-repo"
PACKAGE_PROFILE="$ROOT/configs/packages/ooonana-cloud.list"
ALPINE_REPOS="https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64 https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64"
CUSTOM_REPOS=0
PACKAGES=""
FULL_I3=0
CLOUD_URL=""
REPO_NAME="cloud"
CLEAN=0
DRY_RUN=0
SIGN_KEY="${OOONANA_REPO_SIGN_KEY:-}"
PUBLIC_KEY="${OOONANA_REPO_PUBLIC_KEY:-}"
IMPORT_APK_SCRIPT="${OOONANA_IMPORT_APK_SCRIPT:-$ROOT/scripts/import-apk-package.sh}"
IMPORT_I3_SCRIPT="${OOONANA_IMPORT_I3_SCRIPT:-$ROOT/scripts/import-i3-package-set.sh}"
KERNEL_PACKAGE_SCRIPT="${OOONANA_KERNEL_PACKAGE_SCRIPT:-$ROOT/scripts/build-kernel-package.sh}"
KERNEL_PACKAGE_PATH="${OOONANA_KERNEL_PACKAGE_PATH:-}"
KERNEL_PACKAGE_URL="${OOONANA_KERNEL_PACKAGE_URL:-}"
KERNEL_PACKAGE_VERSION="${OOONANA_KERNEL_VERSION:-6.18.37}"

usage() {
  cat <<'USAGE'
Build an Ooonana package repo from Alpine APK packages.

Usage:
  scripts/build-package-repo.sh [options] [PACKAGE...]

Options:
  --out-dir PATH          Repo output directory
  --package-profile PATH  Package profile list, comments allowed
  --packages "LIST"       Extra space-separated package names
  --repo-url URL          Alpine APK repo URL or path. Can repeat
  --full-i3               Build full-i3 wrapper packages and branding
  --cloud-url URL         Write cloud.repo and README.txt for this URL
  --repo-name NAME        Repo source name for cloud.repo (default: cloud)
  --sign-key PATH         Sign SHA256SUMS with an OpenSSL private key
  --public-key PATH       Copy public key to repo.pub for distribution
  --kernel PATH           Add Ooonana kernel package from local kernel image
  --kernel-url URL        Add Ooonana kernel package from remote kernel image
  --kernel-version VER    Kernel package version (default: 6.18.37)
  --clean                 Delete output dir before build
  --dry-run               Print resolved build command only
  -h, --help              Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --package-profile) PACKAGE_PROFILE="$2"; shift 2 ;;
    --packages) PACKAGES="$PACKAGES $2"; shift 2 ;;
    --repo-url)
      if [[ "$CUSTOM_REPOS" -eq 0 ]]; then
        ALPINE_REPOS=""
        CUSTOM_REPOS=1
      fi
      ALPINE_REPOS="$ALPINE_REPOS $2"
      shift 2
      ;;
    --full-i3) FULL_I3=1; shift ;;
    --cloud-url) CLOUD_URL="$2"; shift 2 ;;
    --repo-name) REPO_NAME="$2"; shift 2 ;;
    --sign-key) SIGN_KEY="$2"; shift 2 ;;
    --public-key) PUBLIC_KEY="$2"; shift 2 ;;
    --kernel) KERNEL_PACKAGE_PATH="$2"; shift 2 ;;
    --kernel-url) KERNEL_PACKAGE_URL="$2"; shift 2 ;;
    --kernel-version) KERNEL_PACKAGE_VERSION="$2"; shift 2 ;;
    --clean) CLEAN=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) ooonana_die "unknown option: $1" ;;
    *) PACKAGES="$PACKAGES $1"; shift ;;
  esac
done

for pkg in "$@"; do
  PACKAGES="$PACKAGES $pkg"
done

load_profile_packages() {
  local profile="$1"
  [[ -n "$profile" ]] || return 0
  [[ -r "$profile" ]] || ooonana_die "missing package profile: $profile"
  sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$profile"
}

normalize_package_list() {
  printf '%s\n' "$@" |
    tr ' ' '\n' |
    awk 'NF && !seen[$0]++ { print }' |
    tr '\n' ' ' |
    sed 's/[[:space:]]*$//'
}

safe_repo_name() {
  case "$1" in
    *[!A-Za-z0-9_.-]*|"") return 1 ;;
    *) return 0 ;;
  esac
}

write_cloud_hints() {
  [[ -n "$CLOUD_URL" ]] || return 0
  safe_repo_name "$REPO_NAME" || ooonana_die "bad repo name: $REPO_NAME"
  case "$CLOUD_URL" in
    http://*|https://*|file://*|/*) ;;
    *) ooonana_die "bad cloud repo URL: $CLOUD_URL" ;;
  esac

  cat > "$OUT_DIR/cloud.repo" <<EOF
OOONANA_REPO_NAME="$REPO_NAME"
OOONANA_REPO_URI="$CLOUD_URL"
EOF
  cat > "$OUT_DIR/README.txt" <<EOF
Ooonana cloud package repo

Add repo source:

install -D -m 0644 /dev/stdin /etc/ooonana/sources.d/$REPO_NAME.repo <<'REPO'
OOONANA_REPO_NAME="$REPO_NAME"
OOONANA_REPO_URI="$CLOUD_URL"
REPO

Then run:

ooonana update
ooonana list
ooonana get PACKAGE
EOF
}

main() {
  ooonana_require_linux
  ooonana_require_commands awk cat mkdir rm sed tr

  profile_packages="$(load_profile_packages "$PACKAGE_PROFILE" | tr '\n' ' ')"
  package_list="$(normalize_package_list "$profile_packages" "$PACKAGES")"
  [[ -n "$package_list" ]] || ooonana_die "no packages requested"

  repo_args=()
  for repo in $ALPINE_REPOS; do
    repo_args+=(--repo-url "$repo")
  done

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'out: %s\n' "$OUT_DIR"
    printf 'profile: %s\n' "${PACKAGE_PROFILE:-none}"
    printf 'packages: %s\n' "$package_list"
    printf 'full-i3: %s\n' "$FULL_I3"
    [[ -n "$CLOUD_URL" ]] && printf 'cloud: %s %s\n' "$REPO_NAME" "$CLOUD_URL"
    [[ -n "$SIGN_KEY" ]] && printf 'sign-key: %s\n' "$SIGN_KEY"
    [[ -n "$PUBLIC_KEY" ]] && printf 'public-key: %s\n' "$PUBLIC_KEY"
    [[ -n "$KERNEL_PACKAGE_PATH" ]] && printf 'kernel: %s\n' "$KERNEL_PACKAGE_PATH"
    [[ -n "$KERNEL_PACKAGE_URL" ]] && printf 'kernel-url: %s\n' "$KERNEL_PACKAGE_URL"
    if [[ -n "$KERNEL_PACKAGE_PATH$KERNEL_PACKAGE_URL" ]]; then
      printf 'kernel-version: %s\n' "$KERNEL_PACKAGE_VERSION"
    fi
    if [[ "$FULL_I3" -eq 1 ]]; then
      ooonana_print_command bash "$IMPORT_I3_SCRIPT" "${repo_args[@]}" --out-dir "$OUT_DIR" --packages "$package_list"
    else
      ooonana_print_command bash "$IMPORT_APK_SCRIPT" "${repo_args[@]}" --out-dir "$OUT_DIR" $package_list
    fi
    if [[ -n "$KERNEL_PACKAGE_PATH" || -n "$KERNEL_PACKAGE_URL" ]]; then
      kernel_source="$KERNEL_PACKAGE_PATH"
      [[ -n "$kernel_source" ]] || kernel_source="$KERNEL_PACKAGE_URL"
      ooonana_print_command bash "$KERNEL_PACKAGE_SCRIPT" --out-dir "$OUT_DIR" --kernel "$kernel_source" --version "$KERNEL_PACKAGE_VERSION"
    fi
    return 0
  fi

  [[ "$CLEAN" -eq 1 ]] && rm -rf "$OUT_DIR"
  mkdir -p "$OUT_DIR"
  if [[ "$FULL_I3" -eq 1 ]]; then
    bash "$IMPORT_I3_SCRIPT" "${repo_args[@]}" --out-dir "$OUT_DIR" --packages "$package_list"
  else
    # shellcheck disable=SC2086
    bash "$IMPORT_APK_SCRIPT" "${repo_args[@]}" --out-dir "$OUT_DIR" $package_list
  fi
  if [[ -n "$KERNEL_PACKAGE_PATH" || -n "$KERNEL_PACKAGE_URL" ]]; then
    kernel_source="$KERNEL_PACKAGE_PATH"
    [[ -n "$kernel_source" ]] || kernel_source="$KERNEL_PACKAGE_URL"
    bash "$KERNEL_PACKAGE_SCRIPT" \
      --out-dir "$OUT_DIR" \
      --kernel "$kernel_source" \
      --version "$KERNEL_PACKAGE_VERSION"
  fi
  if [[ -n "$PUBLIC_KEY" ]]; then
    [[ -f "$PUBLIC_KEY" ]] || ooonana_die "missing public key: $PUBLIC_KEY"
    cp "$PUBLIC_KEY" "$OUT_DIR/repo.pub"
    chmod 0644 "$OUT_DIR/repo.pub" 2>/dev/null || true
  fi
  if [[ -n "$SIGN_KEY" ]]; then
    "$ROOT/packages/ooonana/usr/bin/ooonana" repo index --sign-key "$SIGN_KEY" "$OUT_DIR" >/dev/null
  fi
  write_cloud_hints
  ooonana_log "package repo ready: $OUT_DIR"
}

main "$@"
