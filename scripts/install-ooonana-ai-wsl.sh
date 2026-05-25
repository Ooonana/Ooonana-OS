#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${OOONANA_WSL_BIN_DIR:-$HOME/.local/bin}"

mkdir -p "$BIN_DIR"
ln -sf "$ROOT/packages/ooonana/usr/bin/ooonana" "$BIN_DIR/ooonana"
ln -sf "$ROOT/packages/ooonana/usr/bin/ooonana-ai" "$BIN_DIR/ooonana-ai"

printf 'installed ooonana -> %s/ooonana\n' "$BIN_DIR"
printf 'installed ooonana-ai -> %s/ooonana-ai\n' "$BIN_DIR"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf 'warning: %s is not in PATH\n' "$BIN_DIR" >&2 ;;
esac
