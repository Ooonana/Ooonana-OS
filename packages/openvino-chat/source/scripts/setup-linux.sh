#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/app/pyproject.toml" ]]; then
  DEFAULT_PROJECT_DIR="$SCRIPT_DIR/app"
else
  DEFAULT_PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
PROJECT_DIR="${OPENVINO_CHAT_PROJECT:-$DEFAULT_PROJECT_DIR}"
VENV_DIR="${OPENVINO_CHAT_VENV:-$HOME/.local/share/openvino-chat/venv}"
OPENVINO_HOME="${OPENVINO_HOME:-$HOME/.openvino}"
BIN_DIR="${OPENVINO_CHAT_BIN:-$HOME/.local/bin}"
ORNITH_ARCHIVE="${OPENVINO_ORNITH_ARCHIVE:-}"
MODEL_ROOT="${OPENVINO_MODEL_ROOT:-$OPENVINO_HOME/models}"
CONFIG_PATH="${OPENVINO_CHAT_CONFIG:-$OPENVINO_HOME/config.json}"
ORNITH_DIR="$MODEL_ROOT/ornith-1.5-9b-int4-ov"

if [[ "${1:-}" == --dry-run && $# -eq 1 ]]; then
  printf 'project: %s\nvenv: %s\nruntime: %s\nmodels: %s\nconfig: %s\nlauncher: %s/openvino\n' \
    "$PROJECT_DIR" "$VENV_DIR" "$OPENVINO_HOME" "$MODEL_ROOT" "$CONFIG_PATH" "$BIN_DIR"
  exit 0
fi
[[ $# -eq 0 ]] || { echo 'usage: setup-linux.sh [--dry-run]' >&2; exit 2; }

command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade "$PROJECT_DIR"

mkdir -p "$MODEL_ROOT" "$(dirname "$CONFIG_PATH")" "$BIN_DIR"
if [[ -z "$ORNITH_ARCHIVE" ]]; then
  for candidate in \
    "$SCRIPT_DIR/ornith-1.5-9b-int4-ov.zip" \
    "$SCRIPT_DIR/../ornith-1.5-9b-int4-ov.zip" \
    "$HOME/Downloads/ornith-1.5-9b-int4-ov.zip"; do
    if [[ -f "$candidate" ]]; then
      ORNITH_ARCHIVE="$candidate"
      break
    fi
  done
fi
if [[ ! -f "$ORNITH_DIR/config.json" ]]; then
  [[ -f "$ORNITH_ARCHIVE" ]] || {
    echo "Ornith installer payload missing. Put ornith-1.5-9b-int4-ov.zip beside this script." >&2
    exit 1
  }
  "$VENV_DIR/bin/python" - "$ORNITH_ARCHIVE" "$MODEL_ROOT" <<'PY'
from pathlib import Path
import sys
import zipfile

archive = Path(sys.argv[1])
destination = Path(sys.argv[2]).resolve()
with zipfile.ZipFile(archive) as model_zip:
    for member in model_zip.infolist():
        target = (destination / member.filename).resolve()
        if destination != target and destination not in target.parents:
            raise RuntimeError(f"unsafe archive member: {member.filename}")
    model_zip.extractall(destination)
PY
  [[ -f "$ORNITH_DIR/config.json" ]] || {
    echo "Ornith archive did not create expected model: $ORNITH_DIR" >&2
    exit 1
  }
  echo "model:     $ORNITH_DIR"
fi

"$VENV_DIR/bin/python" - "$CONFIG_PATH" <<'PY'
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
try:
    config = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    config = {}
config.setdefault("model", "ornith")
config.setdefault("thinking_effort", "on")
config.setdefault("generation_effort", "medium")
config.setdefault("duck_mode", "off")
config.setdefault("context_length", "4096")
config.setdefault("knowledge_mode", "auto")
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

printf -v home_arg '%q' "$OPENVINO_HOME"
printf -v model_arg '%q' "$MODEL_ROOT"
printf -v config_arg '%q' "$CONFIG_PATH"
printf -v venv_arg '%q' "$VENV_DIR/bin/openvino"
cat > "$BIN_DIR/openvino" <<EOF
#!/usr/bin/env bash
export OPENVINO_HOME=$home_arg
export OPENVINO_MODEL_ROOT=$model_arg
export OPENVINO_CHAT_CONFIG=$config_arg
exec $venv_arg "\$@"
EOF
chmod +x "$BIN_DIR/openvino" "$PROJECT_DIR/openvino.sh"

echo "installed: $BIN_DIR/openvino"
echo "runtime:   $OPENVINO_HOME"
echo "models:    $MODEL_ROOT"
echo "config:    $CONFIG_PATH"
[[ -f "$ORNITH_DIR/config.json" ]] && echo "ornith:    installed (default)"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "add to shell profile: export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
