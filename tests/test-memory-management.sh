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
mkdir -p "$tmp/zram/zram0"
printf '4294967296\n' >"$tmp/zram/zram0/disksize"
printf '1073741824 268435456 335544320 0 0 0 0\n' >"$tmp/zram/zram0/mm_stat"
status="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" OOONANA_MEMORY_ZRAM_ROOT="$tmp/zram" sh "$HELPER" status)"
[[ "$status" == *'4096 MiB logical capacity, 1024 MiB data, 256 MiB compressed, 320 MiB physical RAM used'* ]]
[[ "$status" == *'3.20:1'* ]]
cat >"$tmp/memory.conf" <<'EOF'
OOONANA_ZRAM_PERCENT=25
OOONANA_DISK_SWAP=off
EOF
plan="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" OOONANA_MEMORY_CONFIG="$tmp/memory.conf" sh "$HELPER" --dry-run)"
[[ "$plan" == *'zram size: 2048 MiB (25% RAM'* ]] || { echo "bad configured plan: $plan" >&2; exit 1; }
status="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" OOONANA_MEMORY_CONFIG="$tmp/memory.conf" sh "$HELPER" status)"
[[ "$status" == *'Zram policy: 25%; disk swap: off'* ]]
disk_off="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" OOONANA_MEMORY_CONFIG="$tmp/memory.conf" sh "$HELPER" disk-start)"
[[ "$disk_off" == 'OOONANA_DISK_SWAP_DISABLED' ]]
printf 'OOONANA_ZRAM_PERCENT=0\nOOONANA_DISK_SWAP=off\n' >"$tmp/memory.conf"
zram_off="$(OOONANA_MEMORY_MEMINFO="$tmp/meminfo" OOONANA_MEMORY_CONFIG="$tmp/memory.conf" sh "$HELPER" start)"
[[ "$zram_off" == 'OOONANA_ZRAM_DISABLED' ]]

printf 'ok memory-management\n'
