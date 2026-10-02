#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/branding/cursors/ooonana-tailless.svg"
THEME="$ROOT/packages/ooonana/usr/share/icons/OoonanaTailless/cursors"
command -v convert >/dev/null 2>&1 || { echo 'build-cursor-theme: missing ImageMagick convert' >&2; exit 1; }
command -v xcursorgen >/dev/null 2>&1 || { echo 'build-cursor-theme: missing xcursorgen' >&2; exit 1; }
[[ -f "$SOURCE" ]] || { echo 'build-cursor-theme: missing cursor SVG' >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
for size in 17 19 24 28 32 48 64; do
  convert -background none "$SOURCE" -resize "${size}x${size}" "PNG32:$work/$size.png"
  hot=$((size / 8))
  printf '%s %s %s %s\n' "$size" "$hot" "$hot" "$work/$size.png" >>"$work/cursor.in"
done

mkdir -p "$THEME"
xcursorgen "$work/cursor.in" "$THEME/left_ptr"
cp "$THEME/left_ptr" "$THEME/default"
cp "$THEME/left_ptr" "$THEME/arrow"
cp "$THEME/left_ptr" "$THEME/top_left_arrow"
echo "built OoonanaTailless cursor theme"
