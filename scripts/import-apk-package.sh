#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$ROOT/scripts/lib/common.sh"

DEFAULT_REPO_URLS="https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64 https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64"
REPO_URLS=""
OUT_DIR="$ROOT/packages/ooonana/usr/lib/ooonana/repo"
ARCH="x86_64"
PACKAGES=""

usage() {
  cat <<'USAGE'
Import Alpine apk packages into an Ooonana package repo.

Usage:
  scripts/import-apk-package.sh [options] PACKAGE...

Options:
  --repo-url URL   Alpine package repo URL or path. Can be repeated.
                   (default: Alpine v3.20 main and community x86_64)
  --out-dir PATH   Ooonana repo output directory
  --arch ARCH      Expected Alpine arch (default: x86_64)
  -h, --help       Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_URLS="$REPO_URLS $2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --arch) ARCH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) PACKAGES="$PACKAGES $1"; shift ;;
  esac
done

[[ -n "$PACKAGES" ]] || ooonana_die "usage: scripts/import-apk-package.sh [options] PACKAGE..."
[ -n "$REPO_URLS" ] || REPO_URLS="$DEFAULT_REPO_URLS"

fetch_url() {
  local url="$1"
  local out="$2"
  case "$url" in
    file://*) cp "${url#file://}" "$out" ;;
    http://*|https://*)
      if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$out"
      elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$out" "$url"
      else
        ooonana_die "missing downloader: curl or wget"
      fi
      ;;
    *) cp "$url" "$out" ;;
  esac
}

repo_join() {
  local repo_url="$1"
  local rel="$1"
  rel="$2"
  case "$repo_url" in
    http://*|https://*) printf '%s/%s\n' "${repo_url%/}" "$rel" ;;
    file://*) printf 'file://%s/%s\n' "${repo_url#file://}" "$rel" ;;
    *) printf '%s/%s\n' "${repo_url%/}" "$rel" ;;
  esac
}

shell_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

apk_field() {
  local name="$1"
  local field="$2"
  awk -v pkg="$name" -v key="$field" '
    BEGIN { RS = ""; FS = "\n" }
    {
      found = 0
      for (i = 1; i <= NF; i++) {
        if ($i == "P:" pkg) {
          found = 1
        }
      }
      if (!found) {
        next
      }
      for (i = 1; i <= NF; i++) {
        if (index($i, key ":") == 1) {
          print substr($i, length(key) + 2)
          exit
        }
      }
    }
  ' "$APKINDEX"
}

normalize_deps() {
  local dep
  for dep in $1; do
    case "$dep" in
      ""|!*|/*) continue ;;
      provider_priority=*) continue ;;
    esac
    dep="${dep%%[<>=~]*}"
    [[ -n "$dep" ]] || continue
    case "$dep" in
      so:*|cmd:*|pc:*|pkgconfig:*)
        dep="$(provider_pkg "$dep")"
        [[ -n "$dep" ]] || continue
        ;;
      *)
        if ! apk_pkg_exists "$dep"; then
          dep="$(provider_pkg "$dep")"
          [[ -n "$dep" ]] || continue
        fi
        ;;
    esac
    printf '%s\n' "$dep"
  done | sort -u
}

apk_pkg_exists() {
  local name="$1"
  awk -v pkg="$name" '
    BEGIN { RS = ""; FS = "\n" }
    {
      for (i = 1; i <= NF; i++) {
        if ($i == "P:" pkg) {
          found = 1
          exit
        }
      }
    }
    END { exit found ? 0 : 1 }
  ' "$APKINDEX"
}

provider_pkg() {
  local provider="$1"
  awk -v provider="$provider" '
    BEGIN { RS = ""; FS = "\n" }
    {
      pkg = ""
      matched = 0
      for (i = 1; i <= NF; i++) {
        if (index($i, "P:") == 1) {
          pkg = substr($i, 3)
        }
        if (index($i, "p:") == 1) {
          provides = substr($i, 3)
          n = split(provides, fields, /[[:space:]]+/)
          for (j = 1; j <= n; j++) {
            candidate = fields[j]
            sub(/[<>=~].*$/, "", candidate)
            if (candidate == provider) {
              matched = 1
            }
          }
        }
      }
      if (matched && pkg != "") {
        print pkg
        exit
      }
    }
  ' "$APKINDEX"
}

write_pkg_metadata() {
  local name="$1"
  local version="$2"
  local summary="$3"
  local deps="$4"
  local archive_rel="$5"
  local archive_sha="$6"
  local origin="$7"
  local pkg_file="$OUT_DIR/$name.pkg"
  cat > "$pkg_file" <<EOF
OOONANA_PKG_ID="$(shell_escape "$name")"
OOONANA_PKG_VERSION="$(shell_escape "$version")"
OOONANA_PKG_KIND="apk"
OOONANA_PKG_SUMMARY="$(shell_escape "$summary")"
OOONANA_PKG_DEPS="$(shell_escape "$deps")"
OOONANA_PKG_ARCHIVE="$(shell_escape "$archive_rel")"
OOONANA_PKG_SHA256="$(shell_escape "$archive_sha")"
OOONANA_PKG_COMPONENTS="apk-import alpine $(shell_escape "$ARCH")"
OOONANA_PKG_NOTES="Imported from Alpine package $(shell_escape "$origin")"
EOF
}

import_one() {
  local name="$1"
  local version apk_arch origin summary raw_deps deps archive_name archive_rel archive_path apk_repo
  version="$(apk_field "$name" V)"
  [[ -n "$version" ]] || ooonana_die "package not found in APKINDEX: $name"
  apk_repo="$(apk_field "$name" X)"
  [[ -n "$apk_repo" ]] || ooonana_die "package repo missing in APKINDEX: $name"
  apk_arch="$(apk_field "$name" A)"
  [[ -z "$apk_arch" || "$apk_arch" == "$ARCH" ]] || ooonana_die "wrong arch for $name: $apk_arch"
  origin="$(apk_field "$name" o)"
  [[ -n "$origin" ]] || origin="$name"
  summary="$(apk_field "$name" T)"
  [[ -n "$summary" ]] || summary="Alpine $name package"
  raw_deps="$(apk_field "$name" D)"
  deps="$(normalize_deps "$raw_deps" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"

  archive_name="$name-$version.apk"
  archive_rel="archives/$name-$version.tar.gz"
  archive_path="$OUT_DIR/$archive_rel"
  mkdir -p "$OUT_DIR/archives" "$WORK/extract-$name"
  fetch_url "$(repo_join "$apk_repo" "$archive_name")" "$WORK/$archive_name"
  rm -rf "$WORK/extract-$name"
  mkdir -p "$WORK/extract-$name"
  tar -xzf "$WORK/$archive_name" -C "$WORK/extract-$name"
  find "$WORK/extract-$name" -maxdepth 1 \( \
    -name '.PKGINFO' -o \
    -name '.SIGN.*' -o \
    -name '.pre-*' -o \
    -name '.post-*' -o \
    -name '.trigger' \
  \) -exec rm -f {} +
  tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --numeric-owner \
    --owner=0 \
    --group=0 \
    --pax-option=delete=atime,delete=ctime \
    -C "$WORK/extract-$name" \
    -cf - \
    . | gzip -n > "$archive_path"
  chmod a+rw "$archive_path"
  archive_sha="$(sha256sum "$archive_path" | awk '{print $1}')"
  write_pkg_metadata "$name" "$version" "$summary" "$deps" "$archive_rel" "$archive_sha" "$origin"
  for dep in $deps; do
    printf '%s\n' "$dep"
  done
}

main() {
  ooonana_require_linux
  ooonana_require_commands awk basename chmod cp find gzip mkdir rm sed sha256sum sort tar tr
  mkdir -p "$OUT_DIR"
  WORK="$(mktemp -d)"
  cleanup() {
    chmod -R u+rwX "$WORK" 2>/dev/null || true
    rm -rf "$WORK"
  }
  trap cleanup EXIT
  APKINDEX="$WORK/APKINDEX"
  : > "$APKINDEX"
  repo_i=0
  for repo_url in $REPO_URLS; do
    repo_i=$((repo_i + 1))
    fetch_url "$(repo_join "$repo_url" APKINDEX.tar.gz)" "$WORK/APKINDEX.$repo_i.tar.gz"
    tar -xOzf "$WORK/APKINDEX.$repo_i.tar.gz" APKINDEX > "$WORK/APKINDEX.$repo_i"
    awk -v repo_url="$repo_url" '
      BEGIN { RS = ""; ORS = "\n\n" }
      NF { print $0 "\nX:" repo_url }
    ' "$WORK/APKINDEX.$repo_i" >> "$APKINDEX"
  done

  imported="$WORK/imported"
  queue="$WORK/queue"
  : > "$imported"
  for pkg in $PACKAGES; do
    printf '%s\n' "$pkg" >> "$queue"
  done

  while read -r pkg; do
    [[ -n "$pkg" ]] || continue
    if grep -qxF "$pkg" "$imported"; then
      continue
    fi
    printf '%s\n' "$pkg" >> "$imported"
    import_one "$pkg" >> "$queue"
  done < "$queue"

  "$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$OUT_DIR" >/dev/null
  count="$(wc -l < "$imported" | tr -d ' ')"
  ooonana_log "imported $count apk package(s): $OUT_DIR"
}

main "$@"
