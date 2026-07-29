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
INDEX_REPO=1

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
  --no-index       Leave repo indexing to caller
  -h, --help       Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_URLS="$REPO_URLS $2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --arch) ARCH="$2"; shift 2 ;;
    --no-index) INDEX_REPO=0; shift ;;
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
        curl -fsSL --retry 5 --retry-delay 3 --connect-timeout 30 --max-time 900 "$url" -o "$out" && return 0
      fi
      if command -v wget >/dev/null 2>&1; then
        wget -q --tries=5 --timeout=60 -O "$out" "$url" && return 0
      fi
      ooonana_die "download failed: $url"
      ;;
    *) cp "$url" "$out" ;;
  esac
}

repo_join() {
  local repo_url="$1"
  local rel="$2"
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
  local record="$INDEX_DIR/$name"
  [[ -f "$record" ]] || return 0
  awk -v key="$field:" '
    index($0, key) == 1 { print substr($0, length(key) + 1); exit }
  ' "$record"
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
  [[ -f "$INDEX_DIR/$name" ]]
}

provider_pkg() {
  local provider="$1"
  awk -F '\t' -v provider="$provider" '
    $1 == provider { print $2; exit }
  ' "$PROVIDER_INDEX"
}

build_index_cache() {
  INDEX_DIR="$WORK/index"
  PROVIDER_INDEX="$WORK/providers.tsv"
  mkdir -p "$INDEX_DIR"
  : > "$PROVIDER_INDEX"
  awk -v index_dir="$INDEX_DIR" -v provider_index="$PROVIDER_INDEX" '
    BEGIN { RS = ""; FS = "\n" }
    {
      pkg = ""
      for (i = 1; i <= NF; i++) {
        if (index($i, "P:") == 1) pkg = substr($i, 3)
      }
      if (pkg == "" || seen[pkg]++) next
      record = index_dir "/" pkg
      print $0 > record
      close(record)
      for (i = 1; i <= NF; i++) {
        if (index($i, "p:") != 1) continue
        provides = substr($i, 3)
        count = split(provides, fields, /[[:space:]]+/)
        for (j = 1; j <= count; j++) {
          candidate = fields[j]
          sub(/[<>=~].*$/, "", candidate)
          if (candidate != "") print candidate "\t" pkg >> provider_index
        }
      }
      close(provider_index)
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

metadata_value() {
  local file="$1"
  local key="$2"
  sed -n "s/^${key}=\"\([^\"]*\)\"$/\1/p" "$file" | head -n 1
}

reuse_cached_archive() {
  local pkg_file="$1"
  local archive_path="$2"
  local version="$3"
  local archive_rel="$4"
  local cached_version cached_archive cached_sha archive_sha

  [[ -f "$pkg_file" && -f "$archive_path" ]] || return 1
  cached_version="$(metadata_value "$pkg_file" OOONANA_PKG_VERSION)"
  cached_archive="$(metadata_value "$pkg_file" OOONANA_PKG_ARCHIVE)"
  cached_sha="$(metadata_value "$pkg_file" OOONANA_PKG_SHA256)"
  [[ "$cached_version" == "$version" ]] || return 1
  [[ "$cached_archive" == "$archive_rel" ]] || return 1
  [[ "$cached_sha" =~ ^[0-9a-f]{64}$ ]] || return 1
  archive_sha="$(sha256sum "$archive_path" | awk '{print $1}')"
  [[ "$archive_sha" == "$cached_sha" ]]
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
  if reuse_cached_archive "$OUT_DIR/$name.pkg" "$archive_path" "$version" "$archive_rel"; then
    archive_sha="$(sha256sum "$archive_path" | awk '{print $1}')"
    write_pkg_metadata "$name" "$version" "$summary" "$deps" "$archive_rel" "$archive_sha" "$origin"
    for dep in $deps; do
      printf '%s\n' "$dep"
    done
    return 0
  fi
  rm -f "$archive_path"
  fetch_url "$(repo_join "$apk_repo" "$archive_name")" "$WORK/$archive_name"
  rm -rf "$WORK/extract-$name"
  mkdir -p "$WORK/extract-$name"
  tar --warning=no-unknown-keyword -xzf "$WORK/$archive_name" -C "$WORK/extract-$name"
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
  LOCK_DIR="$OUT_DIR/.import.lock"
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [[ "$lock_pid" =~ ^[0-9]+$ ]] && kill -0 "$lock_pid" 2>/dev/null; then
      ooonana_die "package import already running for $OUT_DIR (pid $lock_pid)"
    fi
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR"
  fi
  printf '%s\n' "$$" > "$LOCK_DIR/pid"
  WORK="$(mktemp -d)"
  cleanup() {
    chmod -R u+rwX "$WORK" 2>/dev/null || true
    rm -rf "$WORK"
    rm -rf "$LOCK_DIR"
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
  build_index_cache

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

  if [[ "$INDEX_REPO" -eq 1 ]]; then
    "$ROOT/packages/ooonana/usr/bin/ooonana" repo index "$OUT_DIR" >/dev/null
  fi
  count="$(wc -l < "$imported" | tr -d ' ')"
  ooonana_log "imported $count apk package(s): $OUT_DIR"
}

main "$@"
