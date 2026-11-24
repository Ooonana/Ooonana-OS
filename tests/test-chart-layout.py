#!/usr/bin/env python3
"""Theme plot roles and label placement, without GTK or a display."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def luminance(rgb):
    values = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
    return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), values))


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


themes = []
for light in (False, True):
    colors = extract(ROOT / "packages/ooonana/usr/lib/ooonana/ui/common.py", "chart_colors",
                     {"light_appearance": lambda: light})()
    themes.append(colors)
    assert contrast(colors["text"], colors["background"]) >= 4.5
    assert contrast(colors["muted"], colors["background"]) >= 4.5
    for role in ("accent", "blue", "green"):
        assert contrast(colors[role], colors["background"]) >= 3, (light, role)
assert themes[0]["background"] != themes[1]["background"]

print("CHART_LAYOUT_OK theme contrast")
