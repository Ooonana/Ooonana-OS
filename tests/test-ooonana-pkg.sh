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
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$tmp"
}
trap cleanup EXIT

export OOONANA_REPO_DIR="$REPO"
export OOONANA_STATE_DIR="$tmp/state"
export OOONANA_CACHE_DIR="$tmp/cache"

help="$("$CLI" help)"
assert_contains "$help" "ooonana get PACKAGE"
assert_contains "$help" "bunana --restart"
assert_contains "$help" "oonana"
assert_contains "$help" "ooonana install PACKAGE"
assert_contains "$help" "ooonana list"
assert_contains "$help" "ooonana search QUERY"
assert_contains "$help" "ooonana show PACKAGE"
assert_contains "$help" "ooonana depends PACKAGE"
assert_contains "$help" "ooonana files PACKAGE"
assert_contains "$help" "ooonana verify PACKAGE"
assert_contains "$help" "ooonana upgrade [PACKAGE...]"
assert_contains "$help" "ooonana repo index [--sign-key KEY] [PATH]"
assert_contains "$help" "ooonana repo build [options] [PACKAGE...]"
assert_contains "$help" "ooonana repo add NAME URI [PUBKEY]"
assert_contains "$help" "ooonana repo remove NAME"
assert_contains "$help" "ooonana repo doctor"
assert_contains "$help" "ooonana check [PACKAGE...]"
assert_contains "$help" "ooonana add PACKAGE"
assert_contains "$help" "ooonana uninstall PACKAGE"
assert_contains "$help" "ooonana sources"
assert_contains "$help" "ooonana remove PACKAGE"
assert_contains "$help" "ooonana purge PACKAGE"
assert_contains "$help" "ooonana fix [PACKAGE...]"
assert_contains "$help" "Examples:"
assert_contains "$help" "ooonana me"
assert_contains "$help" "ooonana setup"
assert_contains "$help" "ooonana wsl [doctor|status]"
assert_contains "$help" "Need more help:"
assert_contains "$help" "ooonana help packages"
assert_contains "$help" "ooonana help ai"
assert_contains "$help" "ooonana help ui"
assert_contains "$help" "ooonana help get"

sh_help="$(sh "$CLI" help)"
assert_contains "$sh_help" "ooonana get PACKAGE"
assert_contains "$sh_help" "ooonana me"

packages_help="$("$CLI" help packages)"
assert_contains "$packages_help" "Package flow:"
assert_contains "$packages_help" "1. ooonana update"
assert_contains "$packages_help" "2. ooonana search QUERY"
assert_contains "$packages_help" "3. ooonana get PACKAGE"
assert_contains "$packages_help" "Fix/removal:"
assert_contains "$packages_help" "ooonana check"
assert_contains "$packages_help" "ooonana repo doctor"

get_help="$("$CLI" help get)"
assert_contains "$get_help" "Install package:"
assert_contains "$get_help" "ooonana get nano"
assert_contains "$get_help" "Only Ooonana repos"

ai_help="$("$CLI" help ai)"
assert_contains "$ai_help" "AI flow:"
assert_contains "$ai_help" "ooonana-ai-app"

ui_help="$("$CLI" help ui)"
assert_contains "$ui_help" "Full i3 UI:"
assert_contains "$ui_help" "Mod+Shift+A"
assert_contains "$ui_help" "Mod+Shift+W"
assert_contains "$ui_help" "ooonana-installer-gui"
assert_contains "$ui_help" "ooonana-settings"
assert_contains "$ui_help" "ooonana-browser"
assert_contains "$ui_help" "ooonana-wallpaper"
assert_contains "$ui_help" "ooonana-screenshot"
assert_contains "$ui_help" "ooonana-editor"
assert_contains "$ui_help" "ooonana-music"
assert_contains "$ui_help" "ooonana-processes"
assert_contains "$ui_help" "ooonana-ranger"
assert_contains "$ui_help" "ooonana-brightness"
assert_contains "$ui_help" "custom partitions"
assert_contains "$ui_help" "OOONANA_THEME=light"

repo_help="$("$CLI" help repo)"
assert_contains "$repo_help" "Repo commands:"
assert_contains "$repo_help" "ooonana repo add NAME URI [PUBKEY]"
assert_contains "$repo_help" "ooonana repo remove NAME"
assert_contains "$repo_help" "ooonana repo doctor"
assert_contains "$repo_help" "OOONANA_REPO_URI="
assert_contains "$repo_help" "OOONANA_REPO_KEY="
assert_contains "$repo_help" "Signed repos:"
assert_contains "$repo_help" "OOONANA_REQUIRE_SIGNED_REPOS=1"
assert_contains "$repo_help" "release tarball"
assert_contains "$repo_help" "OOONANA_REPO_TOKEN"

[[ -f "$LOGO" ]] || fail "missing docs/logo.txt"
logo="$(<"$LOGO")"
assert_contains "$logo" "Ooonana OS"
assert_contains "$logo" "__________________"
assert_contains "$logo" "\\______/"

me="$("$CLI" me)"
assert_contains "$me" "Ooonana OS"
assert_contains "$me" "__________________"
assert_contains "$me" "\\______/"

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

clean_dry="$("$CLI" clean --dry-run)"
assert_contains "$clean_dry" "would clean ooonana cache"
clean_run="$("$CLI" clean)"
assert_contains "$clean_run" "ooonana cache cleaned"
[[ ! -e "$OOONANA_CACHE_DIR/index.tsv" ]] || fail "clean left index"
[[ ! -e "$OOONANA_CACHE_DIR/sources.tsv" ]] || fail "clean left sources"

sources="$("$CLI" sources)"
assert_contains "$sources" "builtin"
assert_contains "$sources" "$REPO"

search="$("$CLI" search graphical)"
assert_contains "$search" "gui"
assert_contains "$search" "graphical"

show="$("$CLI" show gui)"
assert_contains "$show" "id: gui"
assert_contains "$show" "source: builtin"

show_ai="$("$CLI" show ai)"
assert_contains "$show_ai" "Google Gemini"
assert_contains "$show_ai" "Jarvis-style"

dry_run="$("$CLI" get gui --dry-run)"
assert_contains "$dry_run" "would install gui"
assert_not_contains "$("$CLI" list --installed)" "gui"

install_alias="$("$CLI" install gui --dry-run)"
assert_contains "$install_alias" "would install gui"
add_alias="$("$CLI" add gui --dry-run)"
assert_contains "$add_alias" "would install gui"

install="$("$CLI" get ai)"
assert_contains "$install" "installed ai"
assert_contains "$("$CLI" list --installed)" "ai"
[[ -f "$OOONANA_STATE_DIR/installed/ai.pkg" ]] || fail "missing installed marker"

repeat="$("$CLI" get ai)"
assert_contains "$repeat" "already installed ai"

remove="$("$CLI" remove ai)"
assert_contains "$remove" "removed ai"
assert_not_contains "$("$CLI" list --installed)" "ai"

OOONANA_REPO_DIR="$REPO" "$CLI" get ai >/dev/null
check_ai="$(OOONANA_REPO_DIR="$REPO" "$CLI" check ai)"
assert_contains "$check_ai" "check ok ai"
uninstall_ai="$(OOONANA_REPO_DIR="$REPO" "$CLI" uninstall ai)"
assert_contains "$uninstall_ai" "removed ai"
check_all_empty="$(OOONANA_REPO_DIR="$REPO" "$CLI" check)"
assert_contains "$check_all_empty" "check ok: no packages installed"

purge_root="$tmp/purge-root"
mkdir -p "$purge_root/etc/ooonana/packages/ai" "$purge_root/var/lib/ooonana/packages/config/ai"
OOONANA_ROOT="$purge_root" "$CLI" get ai >/dev/null
purge_dry="$(OOONANA_ROOT="$purge_root" "$CLI" purge ai --dry-run)"
assert_contains "$purge_dry" "would purge ai"
assert_contains "$purge_dry" "would purge config ai"
purge_run="$(OOONANA_ROOT="$purge_root" "$CLI" purge ai)"
assert_contains "$purge_run" "purged config ai"
assert_contains "$purge_run" "purged ai"
[[ ! -e "$purge_root/etc/ooonana/packages/ai" ]] || fail "purge left etc config"
[[ ! -e "$purge_root/var/lib/ooonana/packages/config/ai" ]] || fail "purge left state config"

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

repo_doctor="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" repo doctor)"
assert_contains "$repo_doctor" "builtin: ok"
assert_contains "$repo_doctor" "extra: ok"
assert_contains "$repo_doctor" "OOONANA_REPO_DOCTOR_OK"

repo_add_dir="$tmp/repo-add-sources"
repo_add_out="$(OOONANA_SOURCES_DIR="$repo_add_dir" "$CLI" repo add lab "$extra_repo")"
assert_contains "$repo_add_out" "repo added lab"
assert_contains "$(<"$repo_add_dir/lab.repo")" 'OOONANA_REPO_NAME="lab"'
assert_contains "$(<"$repo_add_dir/lab.repo")" "OOONANA_REPO_URI=\"$extra_repo\""
repo_remove_out="$(OOONANA_SOURCES_DIR="$repo_add_dir" "$CLI" repo remove lab)"
assert_contains "$repo_remove_out" "repo removed lab"
[[ ! -e "$repo_add_dir/lab.repo" ]] || fail "repo remove left source file"

if command -v openssl >/dev/null 2>&1; then
  sign_repo="$tmp/sign-repo"
  sign_root="$tmp/sign-root"
  sign_state="$tmp/sign-state"
  sign_cache="$tmp/sign-cache"
  sign_sources="$tmp/sign-sources"
  mkdir -p "$sign_repo" "$sign_root" "$sign_sources"
  openssl genrsa -out "$tmp/repo.key" 2048 >/dev/null 2>&1
  openssl rsa -in "$tmp/repo.key" -pubout -out "$tmp/repo.pub" >/dev/null 2>&1
  cat > "$sign_repo/signed.pkg" <<'EOF'
OOONANA_PKG_ID="signed"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Signed repo package"
OOONANA_PKG_DEPS=""
EOF
  signed_index="$("$CLI" repo index --sign-key "$tmp/repo.key" "$sign_repo")"
  assert_contains "$signed_index" "signed repo:"
  [[ -f "$sign_repo/SHA256SUMS.sig" ]] || fail "missing repo signature"
  signed_update="$(OOONANA_REPO_DIR="$sign_repo" \
    OOONANA_REPO_VERIFY_KEY="$tmp/repo.pub" \
    OOONANA_STATE_DIR="$sign_state" \
    OOONANA_CACHE_DIR="$sign_cache" \
    "$CLI" update)"
  assert_contains "$signed_update" "synced 1 package(s)"
  signed_install="$(OOONANA_REPO_DIR="$sign_repo" \
    OOONANA_REPO_VERIFY_KEY="$tmp/repo.pub" \
    OOONANA_STATE_DIR="$sign_state" \
    OOONANA_CACHE_DIR="$sign_cache" \
    OOONANA_ROOT="$sign_root" \
    "$CLI" get signed)"
  assert_contains "$signed_install" "installed signed"
  cat > "$sign_sources/signed.repo" <<EOF
OOONANA_REPO_NAME="signed"
OOONANA_REPO_URI="$sign_repo"
OOONANA_REPO_KEY="$tmp/repo.pub"
EOF
  signed_source_update="$(OOONANA_SOURCES_DIR="$sign_sources" \
    OOONANA_STATE_DIR="$tmp/sign-source-state" \
    OOONANA_CACHE_DIR="$tmp/sign-source-cache" \
    "$CLI" update)"
  assert_contains "$signed_source_update" "from 2 source(s)"
  printf '# tamper\n' >> "$sign_repo/SHA256SUMS"
  signed_bad="$(OOONANA_REPO_DIR="$sign_repo" \
    OOONANA_REPO_VERIFY_KEY="$tmp/repo.pub" \
    OOONANA_STATE_DIR="$tmp/sign-bad-state" \
    OOONANA_CACHE_DIR="$tmp/sign-bad-cache" \
    "$CLI" update 2>&1 || true)"
  assert_contains "$signed_bad" "repo signature mismatch"
  unsigned_required="$(OOONANA_REPO_DIR="$extra_repo" \
    OOONANA_REQUIRE_SIGNED_REPOS=1 \
    OOONANA_STATE_DIR="$tmp/unsigned-state" \
    OOONANA_CACHE_DIR="$tmp/unsigned-cache" \
    "$CLI" update 2>&1 || true)"
  assert_contains "$unsigned_required" "repo signature missing"
fi

bad_repo_sources="$tmp/bad-repo-sources"
mkdir -p "$bad_repo_sources"
cat > "$bad_repo_sources/bad.repo" <<'EOF'
OOONANA_REPO_NAME="bad"
OOONANA_REPO_URI="/missing/ooonana/repo"
EOF
bad_repo_doctor="$(OOONANA_SOURCES_DIR="$bad_repo_sources" "$CLI" repo doctor 2>&1 || true)"
assert_contains "$bad_repo_doctor" "bad: missing"

multi_search="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" search tiny)"
assert_contains "$multi_search" "editor"
assert_contains "$multi_search" "Tiny text editor"

multi_show="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" show editor)"
assert_contains "$multi_show" "id: editor"
assert_contains "$multi_show" "source: extra"

multi_install="$(OOONANA_SOURCES_DIR="$sources_dir" "$CLI" install editor --dry-run)"
assert_contains "$multi_install" "would install editor 1.2.0"

http_root="$tmp/http-root"
http_repo="$http_root/repo"
http_payload="$tmp/http-payload"
http_sources="$tmp/http-sources"
http_state="$tmp/http-state"
http_cache="$tmp/http-cache"
http_install_root="$tmp/http-install-root"
mkdir -p "$http_repo/archives" "$http_payload/usr/bin" "$http_sources" "$http_install_root"
cat > "$http_payload/usr/bin/nano" <<'EOF'
#!/bin/sh
echo fake nano
EOF
chmod +x "$http_payload/usr/bin/nano"
tar -C "$http_payload" -czf "$http_repo/archives/nano-1.0-r0.tar.gz" .
http_archive_sha="$(sha256sum "$http_repo/archives/nano-1.0-r0.tar.gz" | awk '{print $1}')"
cat > "$http_repo/nano.pkg" <<EOF
OOONANA_PKG_ID="nano"
OOONANA_PKG_VERSION="1.0-r0"
OOONANA_PKG_KIND="apk"
OOONANA_PKG_SUMMARY="Remote nano package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_ARCHIVE="archives/nano-1.0-r0.tar.gz"
OOONANA_PKG_SHA256="$http_archive_sha"
EOF
"$CLI" repo index "$http_repo" >/dev/null
http_port="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)"
python3 -m http.server "$http_port" --bind 127.0.0.1 --directory "$http_root" > "$tmp/http.log" 2>&1 &
server_pid="$!"
sleep 1
cat > "$http_sources/cloud.repo" <<EOF
OOONANA_REPO_NAME="cloud"
OOONANA_REPO_URI="http://127.0.0.1:$http_port/repo"
EOF

http_update="$(OOONANA_SOURCES_DIR="$http_sources" \
  OOONANA_STATE_DIR="$http_state" \
  OOONANA_CACHE_DIR="$http_cache" \
  "$CLI" update)"
assert_contains "$http_update" "from 2 source(s)"
[[ -f "$http_cache/repos/cloud/index.tsv" ]] || fail "missing remote cached index"
[[ -f "$http_cache/repos/cloud/SHA256SUMS" ]] || fail "missing remote cached checksums"
assert_contains "$(<"$http_cache/index.tsv")" "cloud"
assert_contains "$(<"$http_cache/index.tsv")" "nano"

http_dry="$(OOONANA_SOURCES_DIR="$http_sources" \
  OOONANA_STATE_DIR="$http_state" \
  OOONANA_CACHE_DIR="$http_cache" \
  OOONANA_ROOT="$http_install_root" \
  "$CLI" get nano --dry-run)"
assert_contains "$http_dry" "would install nano 1.0-r0"
assert_contains "$http_dry" "would unpack archives/nano-1.0-r0.tar.gz"

http_install="$(OOONANA_SOURCES_DIR="$http_sources" \
  OOONANA_STATE_DIR="$http_state" \
  OOONANA_CACHE_DIR="$http_cache" \
  OOONANA_ROOT="$http_install_root" \
  "$CLI" get nano)"
assert_contains "$http_install" "unpacked archives/nano-1.0-r0.tar.gz"
assert_contains "$http_install" "installed nano"
[[ -x "$http_install_root/usr/bin/nano" ]] || fail "remote package did not install executable"
[[ -f "$http_cache/repos/cloud/nano.pkg" ]] || fail "missing remote cached pkg"
[[ -f "$http_cache/repos/cloud/archives/nano-1.0-r0.tar.gz" ]] || fail "missing remote cached archive"

http_verify="$(OOONANA_SOURCES_DIR="$http_sources" \
  OOONANA_STATE_DIR="$http_state" \
  OOONANA_CACHE_DIR="$http_cache" \
  OOONANA_ROOT="$http_install_root" \
  "$CLI" verify nano)"
assert_contains "$http_verify" "verify ok nano"

release_sources="$tmp/release-sources"
release_state="$tmp/release-state"
release_cache="$tmp/release-cache"
release_root="$tmp/release-root"
mkdir -p "$release_sources" "$release_root"
tar -C "$http_repo" -czf "$http_root/ooonana-package-repo.tar.gz" .
cat > "$release_sources/release.repo" <<EOF
OOONANA_REPO_NAME="release"
OOONANA_REPO_URI="http://127.0.0.1:$http_port/ooonana-package-repo.tar.gz"
EOF

release_update="$(OOONANA_SOURCES_DIR="$release_sources" \
  OOONANA_STATE_DIR="$release_state" \
  OOONANA_CACHE_DIR="$release_cache" \
  "$CLI" update)"
assert_contains "$release_update" "from 2 source(s)"
[[ -f "$release_cache/repos/release/index.tsv" ]] || fail "missing release cached index"
[[ -f "$release_cache/repos/release/SHA256SUMS" ]] || fail "missing release cached checksums"
[[ -f "$release_cache/repos/release/nano.pkg" ]] || fail "missing release cached pkg"
[[ -f "$release_cache/repos/release/archives/nano-1.0-r0.tar.gz" ]] || fail "missing release cached archive"

release_dry="$(OOONANA_SOURCES_DIR="$release_sources" \
  OOONANA_STATE_DIR="$release_state" \
  OOONANA_CACHE_DIR="$release_cache" \
  OOONANA_ROOT="$release_root" \
  "$CLI" get nano --dry-run)"
assert_contains "$release_dry" "would install nano 1.0-r0"
assert_contains "$release_dry" "would unpack archives/nano-1.0-r0.tar.gz"

release_install="$(OOONANA_SOURCES_DIR="$release_sources" \
  OOONANA_STATE_DIR="$release_state" \
  OOONANA_CACHE_DIR="$release_cache" \
  OOONANA_ROOT="$release_root" \
  "$CLI" get nano)"
assert_contains "$release_install" "unpacked archives/nano-1.0-r0.tar.gz"
assert_contains "$release_install" "installed nano"
[[ -x "$release_root/usr/bin/nano" ]] || fail "release tarball package did not install executable"

private_sources="$tmp/private-release-sources"
private_state="$tmp/private-release-state"
private_cache="$tmp/private-release-cache"
fake_bin="$tmp/fake-bin"
fake_curl_log="$tmp/fake-curl.log"
mkdir -p "$private_sources" "$fake_bin"
cat > "$private_sources/private.repo" <<'EOF'
OOONANA_REPO_NAME="private"
OOONANA_REPO_URI="https://github.com/acme/lab/releases/download/packages-latest/ooonana-package-repo.tar.gz"
EOF
cat > "$fake_bin/curl" <<'EOF'
#!/bin/sh
set -eu
out=""
url=""
auth=0
accept_json=0
accept_octet=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -H)
      case "$2" in
        "Authorization: Bearer fake-token") auth=1 ;;
        "Accept: application/vnd.github+json") accept_json=1 ;;
        "Accept: application/octet-stream") accept_octet=1 ;;
      esac
      shift 2
      ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
: "${OOONANA_FAKE_CURL_LOG:?}"
: "${OOONANA_FAKE_RELEASE_TARBALL:?}"
printf '%s auth=%s json=%s octet=%s out=%s\n' "$url" "$auth" "$accept_json" "$accept_octet" "$out" >> "$OOONANA_FAKE_CURL_LOG"
[ "$auth" -eq 1 ] || exit 22
case "$url" in
  https://api.github.com/repos/acme/lab/releases/tags/packages-latest)
    [ "$accept_json" -eq 1 ] || exit 23
    printf '%s\n' '{"assets":[{"url":"https://api.github.com/repos/acme/lab/releases/assets/42","name":"ooonana-package-repo.tar.gz","uploader":{"url":"https://api.github.com/users/bot"}}]}'> "$out"
    ;;
  https://api.github.com/repos/acme/lab/releases/assets/42)
    [ "$accept_octet" -eq 1 ] || exit 24
    cp "$OOONANA_FAKE_RELEASE_TARBALL" "$out"
    ;;
  *)
    exit 25
    ;;
esac
EOF
chmod +x "$fake_bin/curl"

private_update="$(PATH="$fake_bin:$PATH" \
  OOONANA_REPO_TOKEN="fake-token" \
  OOONANA_FAKE_CURL_LOG="$fake_curl_log" \
  OOONANA_FAKE_RELEASE_TARBALL="$http_root/ooonana-package-repo.tar.gz" \
  OOONANA_SOURCES_DIR="$private_sources" \
  OOONANA_STATE_DIR="$private_state" \
  OOONANA_CACHE_DIR="$private_cache" \
  "$CLI" update 2>&1 || true)"
assert_contains "$private_update" "from 2 source(s)"
assert_contains "$(<"$fake_curl_log")" "https://api.github.com/repos/acme/lab/releases/tags/packages-latest auth=1 json=1"
assert_contains "$(<"$fake_curl_log")" "https://api.github.com/repos/acme/lab/releases/assets/42 auth=1"
[[ -f "$private_cache/repos/private/index.tsv" ]] || fail "missing private release cached index"
[[ -f "$private_cache/repos/private/nano.pkg" ]] || fail "missing private release cached pkg"

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
cat > "$dep_repo/left.pkg" <<'EOF'
OOONANA_PKG_ID="left"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Left side package"
OOONANA_PKG_DEPS=""
OOONANA_PKG_CONFLICTS="right"
EOF
cat > "$dep_repo/right.pkg" <<'EOF'
OOONANA_PKG_ID="right"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Right side package"
OOONANA_PKG_DEPS=""
EOF
cat > "$dep_repo/cyclea.pkg" <<'EOF'
OOONANA_PKG_ID="cyclea"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Cycle A"
OOONANA_PKG_DEPS="cycleb"
EOF
cat > "$dep_repo/cycleb.pkg" <<'EOF'
OOONANA_PKG_ID="cycleb"
OOONANA_PKG_VERSION="1.0.0"
OOONANA_PKG_KIND="tool"
OOONANA_PKG_SUMMARY="Cycle B"
OOONANA_PKG_DEPS="cyclea"
EOF
depends="$(OOONANA_REPO_DIR="$dep_repo" "$CLI" depends appthing)"
assert_contains "$depends" "appthing depends: libthing"
nodeps="$(OOONANA_REPO_DIR="$dep_repo" "$CLI" depends libthing)"
assert_contains "$nodeps" "libthing has no dependencies"
left_info="$(OOONANA_REPO_DIR="$dep_repo" "$CLI" show left)"
assert_contains "$left_info" "conflicts: right"

cycle_dry="$(OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/cycle-state-dry" \
  OOONANA_CACHE_DIR="$tmp/cycle-cache-dry" \
  OOONANA_ROOT="$tmp/cycle-root-dry" \
  "$CLI" get cyclea --dry-run 2>&1 || true)"
assert_contains "$cycle_dry" "dependency cycle:"
assert_contains "$cycle_dry" "cyclea cycleb cyclea"

OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/dep-state" \
  OOONANA_CACHE_DIR="$tmp/dep-cache" \
  OOONANA_ROOT="$tmp/dep-root" \
  "$CLI" get appthing >/dev/null
dep_remove_blocked="$(OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/dep-state" \
  OOONANA_CACHE_DIR="$tmp/dep-cache" \
  OOONANA_ROOT="$tmp/dep-root" \
  "$CLI" remove libthing --dry-run 2>&1 || true)"
assert_contains "$dep_remove_blocked" "required by installed package: appthing"
dep_remove_force="$(OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/dep-state" \
  OOONANA_CACHE_DIR="$tmp/dep-cache" \
  OOONANA_ROOT="$tmp/dep-root" \
  "$CLI" remove libthing --force --dry-run)"
assert_contains "$dep_remove_force" "would remove libthing"
dep_remove_batch="$(OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/dep-state" \
  OOONANA_CACHE_DIR="$tmp/dep-cache" \
  OOONANA_ROOT="$tmp/dep-root" \
  "$CLI" remove appthing libthing --dry-run)"
assert_contains "$dep_remove_batch" "would remove appthing"
assert_contains "$dep_remove_batch" "would remove libthing"

OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/conflict-state" \
  OOONANA_CACHE_DIR="$tmp/conflict-cache" \
  OOONANA_ROOT="$tmp/conflict-root" \
  "$CLI" get right >/dev/null
conflict_install="$(OOONANA_REPO_DIR="$dep_repo" \
  OOONANA_STATE_DIR="$tmp/conflict-state" \
  OOONANA_CACHE_DIR="$tmp/conflict-cache" \
  OOONANA_ROOT="$tmp/conflict-root" \
  "$CLI" get left --dry-run 2>&1 || true)"
assert_contains "$conflict_install" "left conflicts with installed package: right"

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
mkdir -p "$archive_repo" "$archive_root" "$tmp/payload/usr/bin" "$tmp/payload/etc/ooonana" "$tmp/payload/usr/share/ca-certificates/mozilla"
cat > "$tmp/payload/usr/bin/hello-ooonana" <<'EOF'
#!/bin/sh
echo hello from ooonana
EOF
chmod +x "$tmp/payload/usr/bin/hello-ooonana"
printf 'archive-test\n' > "$tmp/payload/etc/ooonana/archive.txt"
unicode_cert="$(printf 'NetLock_Arany_=Class_Gold=_F\305\221tan\303\272s\303\255tv\303\241ny.crt')"
printf 'unicode-cert\n' > "$tmp/payload/usr/share/ca-certificates/mozilla/$unicode_cert"
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
[[ -f "$archive_root/usr/share/ca-certificates/mozilla/$unicode_cert" ]] || fail "archive did not install unicode filename"
[[ -f "$tmp/archive-state/files/hello.list" ]] || fail "missing archive file manifest"
assert_not_contains "$(<"$tmp/archive-state/files/hello.list")" '\305'

archive_files="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" files hello)"
assert_contains "$archive_files" "/usr/bin/hello-ooonana"
assert_contains "$archive_files" "/etc/ooonana/archive.txt"
assert_contains "$archive_files" "/usr/share/ca-certificates/mozilla/$unicode_cert"

archive_verify="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" verify hello)"
assert_contains "$archive_verify" "verify ok hello"
archive_check="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" check)"
assert_contains "$archive_check" "check ok hello"

rm -f "$archive_root/usr/bin/hello-ooonana"
archive_verify_bad="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" verify hello 2>&1 || true)"
assert_contains "$archive_verify_bad" "missing /usr/bin/hello-ooonana"

archive_fix_dry="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" fix hello --dry-run 2>&1)"
assert_contains "$archive_fix_dry" "would update repos"
assert_contains "$archive_fix_dry" "missing /usr/bin/hello-ooonana"
assert_contains "$archive_fix_dry" "would reinstall hello"

archive_fix="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" fix hello 2>&1)"
assert_contains "$archive_fix" "ooonana repo: synced"
assert_contains "$archive_fix" "fixed hello"
[[ -x "$archive_root/usr/bin/hello-ooonana" ]] || fail "fix did not reinstall executable"

archive_remove="$(OOONANA_REPO_DIR="$archive_repo" \
  OOONANA_STATE_DIR="$tmp/archive-state" \
  OOONANA_CACHE_DIR="$tmp/archive-cache" \
  OOONANA_ROOT="$archive_root" \
  "$CLI" remove hello)"
assert_contains "$archive_remove" "removed archive files hello"
assert_contains "$archive_remove" "removed hello"
[[ ! -e "$archive_root/usr/bin/hello-ooonana" ]] || fail "archive remove left executable"
[[ ! -e "$archive_root/etc/ooonana/archive.txt" ]] || fail "archive remove left data"
[[ ! -e "$archive_root/usr/share/ca-certificates/mozilla/$unicode_cert" ]] || fail "archive remove left unicode filename"

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
