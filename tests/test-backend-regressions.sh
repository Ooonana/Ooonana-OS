#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-backend-regressions.py"
python3 "$ROOT/tests/test-service-regressions.py"
if /usr/bin/python3 -c 'from gi.repository import Gio, GLib' 2>/dev/null; then
  /usr/bin/python3 "$ROOT/tests/test-wifi-secrets.py"
else
  printf 'SKIP wifi-secrets: Python GI unavailable\n'
fi
