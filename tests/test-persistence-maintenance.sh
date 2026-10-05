#!/bin/sh
set -eu
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tests/test-persistence-maintenance.py"
sh "$ROOT/packages/ooonana/usr/bin/ooonana-shutdown-cleanup" --dry-run >/dev/null
# Refuses direct host execution before any signal, swap or mount operation.
if sh "$ROOT/packages/ooonana/usr/bin/ooonana-shutdown-cleanup" --from-init 2>/dev/null; then
  echo 'FAIL: host shutdown cleanup accepted' >&2
  exit 1
fi
