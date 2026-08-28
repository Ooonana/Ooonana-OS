#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${OPENVINO_PYTHON:-$ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="${OPENVINO_PYTHON:-python3}"
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OPENVINO_HOME="${OPENVINO_HOME:-$HOME/.openvino}"
exec "$PYTHON" -m openvino_chat "$@"
