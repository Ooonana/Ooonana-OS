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
assert_contains "$help" "ooonana list"
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
[[ -f "$OOONANA_CACHE_DIR/index.tsv" ]] || fail "missing synced index"

dry_run="$("$CLI" get gui --dry-run)"
assert_contains "$dry_run" "would install gui"
assert_not_contains "$("$CLI" list --installed)" "gui"

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

printf 'ok ooonana-pkg\n'
