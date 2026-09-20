#!/usr/bin/env python3
import ast
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = (root / "packages/ooonana/usr/lib/ooonana/ui/ai_app.py").read_text(encoding="utf-8")
method = next(node for node in ast.walk(ast.parse(source))
              if isinstance(node, ast.FunctionDef) and node.name == "start_offline_api")
# Exercise asynchronous orchestration without creating a GTK window or runtime.
commands, messages = [], []
start_rc = 0


def run_async(command, done, **_kwargs):
    commands.append(command)
    done(start_rc, "API result")


def run(command, **_kwargs):
    commands.append(command)
    return 0, "configured"


namespace = dict(run_async=run_async, run=run,
                 run_async_task=lambda task, done: done(*task()))
exec(compile(ast.Module(body=[method], type_ignores=[]), "ai-flow", "exec"), namespace)
target = SimpleNamespace(activity=SimpleNamespace(start=lambda: None, stop=lambda: None),
                         append=lambda *args: messages.append(args), ai_tag="ai", meta_tag="meta",
                         refresh_model=lambda: None)
namespace["start_offline_api"](target, "CPU")
assert commands == [
    ["openvino", "--model-dir", "/root/.openvino/models/qwen3.5-9b-int4-ov", "api", "start", "--device", "CPU"],
    ["ooonana-ai", "provider", "set", "openvino"],
    ["ooonana-ai", "model", "set", "qwen3.5-9b-int4-ov"],
], commands
commands.clear()
start_rc = 1
namespace["start_offline_api"](target, "GPU")
assert len(commands) == 1, "failed startup must not change provider settings"
assert '"openvino download qwen3.5"' in source
assert "openvino download tiny" not in source
print("ok offline-ai-flow")
