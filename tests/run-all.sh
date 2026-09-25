#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
count=0
for test_file in "$ROOT"/tests/test-*.sh "$ROOT"/tests/smoke-cli.sh; do
  bash "$test_file"
  count=$((count + 1))
done
printf 'ok %s suites\n' "$count"
