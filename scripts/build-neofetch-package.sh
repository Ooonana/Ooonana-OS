#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/lib/common.sh"
[[ "$#" -eq 2 && "$1" == --out-dir && -n "$2" ]] || ooonana_die 'usage: build-neofetch-package.sh --out-dir PATH'
out="$2"
version="7.1.0-r1.ooonana1"
archive="archives/neofetch-$version.tar.gz"
upstream="$ROOT/packages/neofetch/upstream"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stage="$work/root"
mkdir -p "$stage/usr/bin" "$stage/usr/lib/ooonana" "$stage/usr/share/licenses/neofetch" "$out/archives"

# Exact Bash payload from Alpine's neofetch-7.1.0-r1.apk in v3.20/community/x86_64.
# Archive SHA256: bc773cfb15c905d83dea05fe626982a86a3d7a01e6b48ce106b9b2f63aa5bd78.
gzip -dc "$upstream/neofetch-7.1.0-r1.gz" >"$work/neofetch"
printf '%s  %s\n' 3dc33493e54029fb1528251552093a9f9a2894fcf94f9c3a6f809136a42348c7 "$work/neofetch" |
  sha256sum -c - >/dev/null
python3 - "$work/neofetch" "$ROOT/packages/ooonana/usr/share/ooonana/logo.txt" \
  "$stage/usr/lib/ooonana/neofetch" <<'PY'
from pathlib import Path
import sys

source, logo, target = map(Path, sys.argv[1:])
program = source.read_text(encoding="utf-8")

# WSL appends its Windows host to the OS name. Select Ooonana when the
# distro is automatic, while leaving explicit Neofetch settings in charge.
select_distro = '    [[ ${ascii_distro:-auto} == auto ]] && \\\n        ascii_distro=$(trim "$distro")'
case_start = '    case $(trim "$ascii_distro") in\n'
if program.count(select_distro) != 1 or program.count(case_start) != 1:
    raise SystemExit("Cannot locate Neofetch distro selection")

program = program.replace(select_distro, '''    if [[ ${ascii_distro:-auto} == auto ]]; then
        if grep -Eq '^ID=(ooonana|"ooonana")$' /etc/os-release 2>/dev/null; then
            ascii_distro=Ooonana
        else
            ascii_distro=$(trim "$distro")
        fi
    fi''')

# Neofetch expands backslashes when printing ASCII art.
art = logo.read_text(encoding="utf-8").rstrip("\n").replace("\\", "\\\\")
brand = r"""        Ooonana*)
            local ooonana_theme
            ooonana_theme="$(ooonana-theme-env client-env 2>/dev/null |
                sed -n 's/^OOONANA_THEME="\(light\|dark\)"$/\1/p')"
            case "${ooonana_theme:-${OOONANA_THEME_OVERRIDE:-${OOONANA_THEME:-dark}}}" in
                light) set_colors 94 7 ;;
                *)     set_colors 214 7 ;;
            esac
            read -rd '' ascii_data <<'OOONANA_ASCII'
${c1}""" + art + """
OOONANA_ASCII
        ;;
"""
target.write_text(program.replace(case_start, case_start + brand), encoding="utf-8")
PY
chmod 0755 "$stage/usr/lib/ooonana/neofetch"
install -m 0755 "$ROOT/packages/ooonana/usr/bin/neofetch" "$stage/usr/bin/neofetch"
install -m 0644 "$upstream/LICENSE.md" "$stage/usr/share/licenses/neofetch/LICENSE.md"
find "$stage" -type d -exec chmod 0755 {} +
ooonana_tar_gzip_atomic "$out/$archive" --sort=name --mtime=@0 --numeric-owner --owner=0 --group=0 \
  --pax-option=delete=atime,delete=ctime -C "$stage" -cf - .
checksum="$(sha256sum "$out/$archive" | awk '{print $1}')"
cat >"$out/neofetch.pkg" <<EOF
OOONANA_PKG_ID="neofetch"
OOONANA_PKG_VERSION="$version"
OOONANA_PKG_KIND="archive"
OOONANA_PKG_SUMMARY="Neofetch system information with Ooonana logo and theme colors"
OOONANA_PKG_DEPS="bash"
OOONANA_PKG_ARCHIVE="$archive"
OOONANA_PKG_SHA256="$checksum"
OOONANA_PKG_NOTES="Neofetch 7.1.0 with Ooonana branding"
EOF
