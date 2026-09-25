#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/packages/ooonana/usr/bin/ooonana-memory"
[[ -f "$HELPER" ]] || { echo 'missing memory helper' >&2; exit 1; }
sh -n "$HELPER"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat >"$tmp/meminfo" <<'EOF'
MemTotal:        8388608 kB
MemAvailable:    6291456 kB
SwapTotal:       4194304 kB
SwapFree:        4194304 kB
EOF

plan="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" sh "$HELPER" --dry-run)"
[[ "$plan" == *'zram size: 4096 MiB'* ]] || { echo "bad zram plan: $plan" >&2; exit 1; }
short="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" sh "$HELPER" --short)"
[[ "$short" == 'RAM 25%' ]] || { echo "bad memory label: $short" >&2; exit 1; }
status="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" sh "$HELPER" status)"
[[ "$status" == *'RAM: 8192 MiB total, 6144 MiB available'* ]]
[[ "$status" == *'Swap: 4096 MiB total, 4096 MiB free'* ]]

printf 'ok memory-management\n'
