#!/usr/bin/env python3
"""Check AI header parses CLI fields rather than trailing help/config lines."""

import ast
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui/ai_app.py"
module = ast.parse(source.read_text())
function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "status_field")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
field = namespace["status_field"]
provider = "active: nim\nlabel: NVIDIA NIM\nkey: missing\nconfig: /private/ai.env\n"
model = "provider: nim\nactive: example/model\naliases:\n  default: example/model\nchange default: command help\n"
assert field(provider, "label") == "NVIDIA NIM"
assert field(provider, "active") == "nim"
assert field(model, "active") == "example/model"
assert field(model, "missing", "Default model") == "Default model"
print("ok ai-ui-status")
