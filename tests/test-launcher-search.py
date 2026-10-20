#!/usr/bin/env python3
"""Search selection/ranking policy without a display or application launches."""
import ast
from functools import cmp_to_key
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = ast.parse((root / "packages/ooonana/usr/lib/ooonana/ui/launcher_app.py").read_text())
app = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "LauncherWindow")
methods = [node for node in app.body if isinstance(node, ast.FunctionDef)
           and node.name in ("sort_rows", "search_changed", "filter_row")]
namespace = {}
exec(compile(ast.Module(body=methods, type_ignores=[]), "launcher-search", "exec"), namespace)
query = [""]
owner = SimpleNamespace(search=SimpleNamespace(get_text=lambda: query[0]))
rows = [SimpleNamespace(search_name=name.casefold(), search_text=(name + " " + detail).casefold(), default_order=index)
        for index, (name, detail) in enumerate([
            ("Wi-Fi", "Manage wireless profiles"), ("Files", "Browse directories"),
            ("Files utility", "Inspect files"), ("Other Files", "More tools"),
            ("MyFiles", "Another utility"), ("설정", "System preferences")])]
def ordered():
    return sorted((row for row in rows if namespace["filter_row"](owner, row)),
                  key=cmp_to_key(lambda left, right: namespace["sort_rows"](owner, left, right)))

assert ordered() == rows, "Empty query preserves native-first catalog order"
query[0] = "  fIlEs  "
assert [row.search_name for row in ordered()] == ["files", "files utility", "other files", "myfiles", "wi-fi"]
query[0] = "설"
assert [row.search_name for row in ordered()] == ["설정"]
query[0] = "no matching app"
assert ordered() == []
calls = []
owner.results = SimpleNamespace(invalidate_filter=lambda: calls.append("filter"),
                                invalidate_sort=lambda: calls.append("rank"))
owner.select_first = lambda: calls.append("select-current-results")
namespace["search_changed"](owner)
assert calls == ["filter", "rank", "select-current-results"], "Filter/rank/selection must finish before Return or idle"
print("ok launcher-search: immediate filter/selection, exact/prefix/word/name before description, stable defaults, Unicode/no-match")
