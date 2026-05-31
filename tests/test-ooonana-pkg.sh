#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/packages/ooonana/usr/bin/ooonana"
REPO="$ROOT/packages/ooonana/usr/lib/ooonana/repo"
LOGO="$ROOT/docs/logo.txt"
CLI_SRC="$(<"$CLI")"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "missing: $needle"
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" != *"$needle"* ]] || fail "unexpected: $needle"
}

assert_not_contains "$CLI_SRC" "<("
assert_not_contains "$CLI_SRC" "[["
assert_not_contains "$CLI_SRC" "local -a"
assert_not_contains "$CLI_SRC" "mapfile"
assert_not_contains "$CLI_SRC" "packages=("
assert_not_contains "$CLI_SRC" "pipefail"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

export OOONANA_REPO_DIR="$REPO"
export OOONANA_STATE_DIR="$tmp/state"
export OOONANA_CACHE_DIR="$tmp/cache"

help="$("$CLI" help)"
assert_contains "$help" "ooonana get PACKAGE"
assert_contains "$help" "ooonana install PACKAGE"
assert_contains "$help" "ooonana list"
assert_contains "$help" "ooonana search QUERY"
assert_contains "$help" "ooonana show PACKAGE"
assert_contains "$help" "ooonana depends PACKAGE"
assert_contains "$help" "ooonana files PACKAGE"
assert_contains "$help" "ooonana verify PACKAGE"
assert_contains "$help" "ooonana upgrade [PACKAGE...]"
assert_contains "$help" "ooonana repo index [PATH]"
assert_contains "$help" "ooonana sources"
assert_contains "$help" "ooonana remove PACKAGE"
assert_contains "$help" "ooonana me"
assert_contains "$help" "ooonana wsl [doctor|status]"

sh_help="$(sh "$CLI" help)"
assert_contains "$sh_help" "ooonana get PACKAGE"
assert_contains "$sh_help" "ooonana me"

[[ -f "$LOGO" ]] || fail "missing docs/logo.txt"
logo="$(<"$LOGO")"
assert_contains "$logo" "Ooonana OS"
assert_contains "$logo" "_____________________"
assert_contains "$logo" "\\ ______/"

me="$("$CLI" me)"
assert_contains "$me" "Ooonana OS"
assert_contains "$me" "_____________________"
assert_contains "$me" "\\ ______/"

sh_me="$(sh "$CLI" me)"
assert_contains "$sh_me" "Ooonana OS"

wsl_status="$("$CLI" wsl status)"
assert_contains "$wsl_status" "wsl:"
assert_contains "$wsl_status" "qemu:"
assert_contains "$wsl_status" "build_dir:"

sh_wsl="$(sh "$CLI" wsl doctor)"
assert_contains "$sh_wsl" "wsl:"

bad_wsl="$("$CLI" wsl nope 2>&1 || true)"
assert_contains "$bad_wsl" "usage: ooonana wsl [doctor|status]"

list="$("$CLI" list)"
assert_contains "$list" "base"
assert_contains "$list" "gui"
assert_contains "$list" "ai"
assert_contains "$list" "hacker-tools"
assert_contains "$list" "available"

sh_list="$(sh "$CLI" list)"
assert_contains "$sh_list" "base"
assert_contains "$sh_list" "gui"
assert_contains "$sh_list" "available"

update="$("$CLI" update)"
assert_contains "$update" "ooonana repo: synced"
assert_contains "$update" "source(s)"
[[ -f "$OOONANA_CACHE_DIR/index.tsv" ]] || fail "missing synced index"
[[ -f "$OOONANA_CACHE_DIR/sources.tsv" ]] || fail "missing synced sources"

sources="$("$CLI" sources)"
assert_contains "$sources" "builtin"
assert_contains "$sources" "$REPO"

search="$("$CLI" search graphical)"
assert_contains "$search" "gui"
assert_contains "$search" "graphical"

show="$("$CLI" show gui)"
assert_contains "$show" "id: gui"
assert_contains "$show" "source: builtin"

dry_run="$("$CLI" get gui --dry-run)"
assert_contains "$dry_run" "would install gui"
assert_not_contains "$("$CLI" list --installed)" "gui"

install_alias="$("$CLI" install gui --dry-run)"
assert_contains "$install_alias" "would install gui"

install="$("$CLI" get ai)"
assert_contains "$install" "installed ai"
assert_contains "$("$CLI" list --installed)" "ai"
[[ -f "$OOONANA_STATE_DIR/installed/ai.pkg" ]] || fail "missing installed marker"

repeat="$("$CLI" get ai)"
assert_contains "$repeat" "already installed ai"

remove="$("$CLI" remove ai)"
assert_contains "$remove" "removed ai"
assert_not_contains "$("$CLI" list --installed)" "ai"

missing="$("$CLI" get missing-package 2>&1 || true)"
assert_contains "$missing" "unknown package: missing-package"

sources_dir="$tmp/sources.d"
extra_repo="$tmp/extra-repo"
mkdir -p "$sources_dir" "$extra_repo"
cat > "$extra_repo/editor.pkg" <<'EOF'
OOONANA_PKG_ID="editor"
OOONANA_PKG_VERSION="1.2.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Tiny text editor"
OOONANA_PKG_DEPS=""
OOONANA_PKG_COMPONENTS="edit"
OOONANA_PKG_NOTES="Local test repo package"
EOF
cat > "$sources_dir/extra.repo" <<EOF
OOONANA_REPO_NAME="extra"
OOONANA_REPO_URI="$extra_repo"
EOF

multi_update="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" update)"
assert_contains "$multi_update" "from 2 source(s)"
assert_contains "$(<"$OOONANA_CACHE_DIR/index.tsv")" "extra"
assert_contains "$(<"$OOONANA_CACHE_DIR/index.tsv")" "editor"

multi_sources="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" sources)"
assert_contains "$multi_sources" "extra"
assert_contains "$multi_sources" "$extra_repo"

multi_search="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" search tiny)"
assert_contains "$multi_search" "editor"
assert_contains "$multi_search" "Tiny text editor"

multi_show="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" show editor)"
assert_contains "$multi_show" "id: editor"
assert_contains "$multi_show" "source: extra"

multi_install="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" install editor --dry-run)"
assert_contains "$multi_install" "would install editor 1.2.0"

index_repo="$tmp/index-repo"
index_payload="$tmp/index-payload"
mkdir -p "$index_repo" "$index_payload/usr/share/indexed"
printf 'indexed payload\n' > "$index_payload/usr/share/indexed/payload.txt"
tar -C "$index_payload" -czf "$index_repo/indexed.tar.gz" .
index_archive_sha="$(sha256sum "$index_repo/indexed.tar.gz" | awk '{print $1}')"
cat > "$index_repo/indexed.pkg" <<EOF
OOONANA_PKG_ID="indexed"
OOONANA_PKG_VERSION="2.1.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Indexed repo package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="indexed.tar.gz"
OOONANA_PKG_SHA256="$index_archive_sha"
EOF
repo_index="$("$CLI" repo index "$index_repo")"
assert_contains "$repo_index" "indexed 1 package(s)"
[[ -f "$index_repo/index.tsv" ]] || fail "missing repo index"
[[ -f "$index_repo/SHA256SUMS" ]] || fail "missing repo checksums"
assert_contains "$(<"$index_repo/index.tsv")" $'indexed\t2.1.0\tarchive\tIndexed repo package'
assert_contains "$(<"$index_repo/SHA256SUMS")" "indexed.pkg"
assert_contains "$(<"$index_repo/SHA256SUMS")" "indexed.tar.gz"

indexed_update="$(OOONANA_REPO_DIR="$index_repo" \
  OOONANA_CACHE_DIR="$tmp/index-cache" \
  "$CLI" update)"
assert_contains "$indexed_update" "synced 1 package(s)"
assert_contains "$(<"$tmp/index-cache/index.tsv")" "indexed"

printf '# tamper\n' >> "$index_repo/indexed.pkg"
indexed_bad="$(OOONANA_REPO_DIR="$index_repo" \
  OOONANA_CACHE_DIR="$tmp/index-bad-cache" \
  "$CLI" update 2>&1 || true)"
assert_contains "$indexed_bad" "sha256 mismatch: indexed.pkg"

indexed_get_bad="$(OOONANA_REPO_DIR="$index_repo" \
  OOONANA_STATE_DIR="$tmp/index-bad-state" \
  OOONANA_CACHE_DIR="$tmp/index-bad-install-cache" \
  OOONANA_ROOT="$tmp/index-bad-root" \
  "$CLI" get indexed 2>&1 || true)"
assert_contains "$indexed_get_bad" "sha256 mismatch: indexed.pkg"

archive_only_repo="$tmp/archive-only-repo"
archive_only_payload="$tmp/archive-only-payload"
mkdir -p "$archive_only_repo" "$archive_only_payload/usr/share/archiveonly"
printf 'before\n' > "$archive_only_payload/usr/share/archiveonly/value.txt"
tar -C "$archive_only_payload" -czf "$archive_only_repo/archiveonly.tar.gz" .
cat > "$archive_only_repo/archiveonly.pkg" <<'EOF'
OOONANA_PKG_ID="archiveonly"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Archive checksum only package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="archiveonly.tar.gz"
EOF
"$CLI" repo index "$archive_only_repo" >/dev/null
rm -rf "$archive_only_payload"
mkdir -p "$archive_only_payload/usr/share/archiveonly"
printf 'after\n' > "$archive_only_payload/usr/share/archiveonly/value.txt"
tar -C "$archive_only_payload" -czf "$archive_only_repo/archiveonly.tar.gz" .
archive_only_bad="$(OOONANA_REPO_DIR="$archive_only_repo" \
  OOONANA_STATE_DIR="$tmp/archive-only-state" \
  OOONANA_CACHE_DIR="$tmp/archive-only-cache" \
  OOONANA_ROOT="$tmp/archive-only-root" \
  "$CLI" get archiveonly 2>&1 || true)"
assert_contains "$archive_only_bad" "sha256 mismatch: archiveonly.tar.gz"

dep_repo="$tmp/dep-repo"
mkdir -p "$dep_repo"
cat > "$dep_repo/libthing.pkg" <<'EOF'
OOONANA_PKG_ID="libthing"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="lib"
OOONANA_PKG_SUMMARY="Shared thing library"
OOONANA_PKG_DEPS=""
EOF
cat > "$dep_repo/appthing.pkg" <<'EOF'
OOONANA_PKG_ID="appthing"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="App using thing library"
OOONANA_PKG_DEPS="libthing"
EOF
depends="$(OOONANA_REPO_DIR="$dep_repo" "$CLI" depends appthing)"
assert_contains "$depends" "appthing depends: libthing"
nodeps="$(OOONANA_REPO_DIR="$dep_repo" "$CLI" depends libthing)"
assert_contains "$nodeps" "libthing has no dependencies"

custom_repo="$tmp/custom-repo"
custom_root="$tmp/custom-root"
mkdir -p "$custom_repo/hooks" "$custom_root"
cat > "$custom_repo/demo.pkg" <<'EOF'
OOONANA_PKG_ID="demo"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Demo hook package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_COMPONENTS="hook-test"
OOONANA_PKG_NOTES="Test package"
EOF
cat > "$custom_repo/hooks/demo.install" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$OOONANA_ROOT/opt/demo"
printf 'demo\n' > "$OOONANA_ROOT/opt/demo/installed"
EOF
cat > "$custom_repo/hooks/demo.remove" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
rm -f "$OOONANA_ROOT/opt/demo/installed"
rmdir "$OOONANA_ROOT/opt/demo" 2>/dev/null || true
EOF
chmod +x "$custom_repo/hooks/demo.install" "$custom_repo/hooks/demo.remove"

hook_install="$(OOONANA_REPO_DIR="$custom_repo" \
  OOONANA_STATE_DIR="$tmp/custom-state" \
  OOONANA_CACHE_DIR="$tmp/custom-cache" \
  OOONANA_ROOT="$custom_root" \
  "$CLI" get demo)"
assert_contains "$hook_install" "running install hook demo"
assert_contains "$hook_install" "installed demo"
[[ "$(cat "$custom_root/opt/demo/installed")" == "demo" ]] || fail "install hook did not write file"

hook_remove="$(OOONANA_REPO_DIR="$custom_repo" \
  OOONANA_STATE_DIR="$tmp/custom-state" \
  OOONANA_CACHE_DIR="$tmp/custom-cache" \
  OOONANA_ROOT="$custom_root" \
  "$CLI" remove demo)"
assert_contains "$hook_remove" "running remove hook demo"
assert_contains "$hook_remove" "removed demo"
[[ ! -e "$custom_root/opt/demo/installed" ]] || fail "remove hook did not remove file"

archive_repo="$tmp/archive-repo"
archive_root="$tmp/archive-root"
mkdir -p "$archive_repo" "$archive_root" "$tmp/payload/usr/bin" "$tmp/payload/etc/ooonana"
cat > "$tmp/payload/usr/bin/hello-ooonana" <<'EOF'
#!/bin/sh
echo hello from ooonana
EOF
chmod +x "$tmp/payload/usr/bin/hello-ooonana"
printf 'archive-test\n' > "$tmp/payload/etc/ooonana/archive.txt"
tar -C "$tmp/payload" -czf "$archive_repo/hello.tar.gz" .
archive_sha="$(sha256sum "$archive_repo/hello.tar.gz" | awk '{print $1}')"
cat > "$archive_repo/hello.pkg" <<EOF
OOONANA_PKG_ID="hello"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Hello archive package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="hello.tar.gz"
OOONANA_PKG_SHA256="$archive_sha"
EOF

archive_dry="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" get hello --dry-run)"
assert_contains "$archive_dry" "would unpack hello.tar.gz"

archive_sh_dry="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-sh-state" \
  OOONANA_CACHE_DIR="$tmp/archive-sh-cache" \
  OOONANA_ROOT="$tmp/archive-sh-root" \
  sh "$CLI" get hello --dry-run)"
assert_contains "$archive_sh_dry" "would unpack hello.tar.gz"

archive_install="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" get hello)"
assert_contains "$archive_install" "unpacked hello.tar.gz"
assert_contains "$archive_install" "installed hello"
[[ -x "$archive_root/usr/bin/hello-ooonana" ]] || fail "archive did not install executable"
[[ "$(cat "$archive_root/etc/ooonana/archive.txt")" == "archive-test" ]] || fail "archive did not install data"
[[ -f "$tmp/archive-state/files/hello.list" ]] || fail "missing archive file manifest"

archive_files="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" files hello)"
assert_contains "$archive_files" "/usr/bin/hello-ooonana"
assert_contains "$archive_files" "/etc/ooonana/archive.txt"

archive_verify="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" verify hello)"
assert_contains "$archive_verify" "verify ok hello"

rm -f "$archive_root/usr/bin/hello-ooonana"
archive_verify_bad="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" verify hello 2>&1 || true)"
assert_contains "$archive_verify_bad" "missing /usr/bin/hello-ooonana"

archive_remove="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" remove hello)"
assert_contains "$archive_remove" "removed archive files hello"
assert_contains "$archive_remove" "removed hello"
[[ ! -e "$archive_root/usr/bin/hello-ooonana" ]] || fail "archive remove left executable"
[[ ! -e "$archive_root/etc/ooonana/archive.txt" ]] || fail "archive remove left data"

cat > "$archive_repo/bad.pkg" <<'EOF'
OOONANA_PKG_ID="bad"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Bad archive package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="hello.tar.gz"
OOONANA_PKG_SHA256="badbad"
EOF
bad_install="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/bad-state" \
  OOONANA_CACHE_DIR="$tmp/bad-cache" \
  OOONANA_ROOT="$tmp/bad-root" \
  "$CLI" get bad 2>&1 || true)"
assert_contains "$bad_install" "sha256 mismatch: bad"

upgrade_repo="$tmp/upgrade-repo"
upgrade_root="$tmp/upgrade-root"
upgrade_state="$tmp/upgrade-state"
upgrade_cache="$tmp/upgrade-cache"
mkdir -p "$upgrade_repo" "$upgrade_root" "$tmp/upgrade-payload/usr/share/updemo"
printf 'one\n' > "$tmp/upgrade-payload/usr/share/updemo/version.txt"
tar -C "$tmp/upgrade-payload" -czf "$upgrade_repo/updemo.tar.gz" .
upgrade_sha="$(sha256sum "$upgrade_repo/updemo.tar.gz" | awk '{print $1}')"
cat > "$upgrade_repo/updemo.pkg" <<EOF
OOONANA_PKG_ID="updemo"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Upgrade demo package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="updemo.tar.gz"
OOONANA_PKG_SHA256="$upgrade_sha"
EOF
OOONANA_REPO_DIR="$upgrade_repo" \
  OOONANA_STATE_DIR="$upgrade_state" \
  OOONANA_CACHE_DIR="$upgrade_cache" \
  OOONANA_ROOT="$upgrade_root" \
  "$CLI" get updemo >/dev/null

rm -rf "$tmp/upgrade-payload"
mkdir -p "$tmp/upgrade-payload/usr/share/updemo"
printf 'two\n' > "$tmp/upgrade-payload/usr/share/updemo/version.txt"
tar -C "$tmp/upgrade-payload" -czf "$upgrade_repo/updemo.tar.gz" .
upgrade_sha="$(sha256sum "$upgrade_repo/updemo.tar.gz" | awk '{print $1}')"
cat > "$upgrade_repo/updemo.pkg" <<EOF
OOONANA_PKG_ID="updemo"
OOONANA_PKG_VERSION="2.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Upgrade demo package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="updemo.tar.gz"
OOONANA_PKG_SHA256="$upgrade_sha"
EOF

upgradeable="$(OOONANA_REPO_DIR="$upgrade_repo" \
  OOONANA_STATE_DIR="$upgrade_state" \
  OOONANA_CACHE_DIR="$upgrade_cache" \
  OOONANA_ROOT="$upgrade_root" \
  "$CLI" list --upgradeable)"
assert_contains "$upgradeable" "updemo 1.0.0 -> 2.0.0"

upgrade_dry="$(OOONANA_REPO_DIR="$upgrade_repo" \
  OOONANA_STATE_DIR="$upgrade_state" \
  OOONANA_CACHE_DIR="$upgrade_cache" \
  OOONANA_ROOT="$upgrade_root" \
  "$CLI" upgrade --dry-run)"
assert_contains "$upgrade_dry" "would upgrade updemo 1.0.0 -> 2.0.0"

upgrade_run="$(OOONANA_REPO_DIR="$upgrade_repo" \
  OOONANA_STATE_DIR="$upgrade_state" \
  OOONANA_CACHE_DIR="$upgrade_cache" \
  OOONANA_ROOT="$upgrade_root" \
  "$CLI" upgrade)"
assert_contains "$upgrade_run" "upgraded updemo 1.0.0 -> 2.0.0"
[[ "$(cat "$upgrade_root/usr/share/updemo/version.txt")" == "two" ]] || fail "upgrade did not replace package files"
assert_contains "$(<"$upgrade_state/installed/updemo.pkg")" 'OOONANA_PKG_VERSION="2.0.0"'

cat > "$upgrade_repo/updemo.pkg" <<'EOF'
OOONANA_PKG_ID="updemo"
OOONANA_PKG_VERSION="3.0.0"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Upgrade demo package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="updemo.tar.gz"
OOONANA_PKG_SHA256="badbad"
EOF
upgrade_bad="$(OOONANA_REPO_DIR="$upgrade_repo" \
  OOONANA_STATE_DIR="$upgrade_state" \
  OOONANA_CACHE_DIR="$upgrade_cache" \
  OOONANA_ROOT="$upgrade_root" \
  "$CLI" upgrade updemo 2>&1 || true)"
assert_contains "$upgrade_bad" "sha256 mismatch: updemo"
[[ "$(cat "$upgrade_root/usr/share/updemo/version.txt")" == "two" ]] || fail "failed upgrade damaged installed files"
assert_contains "$(<"$upgrade_state/installed/updemo.pkg")" 'OOONANA_PKG_VERSION="2.0.0"'

printf 'ok ooonana-pkg\n'
