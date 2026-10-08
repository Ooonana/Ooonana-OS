#!/usr/bin/env python3
"""QA hooks must reach page-open lexical bindings, not Annex-B aliases."""
import json
import os
from pathlib import Path
import shutil
import subprocess

node = shutil.which("node")
if not node:
    print("SKIP pdf-vm-harness: node unavailable")
    raise SystemExit(0)
root = Path(__file__).resolve().parents[1]
body = r'''
var calls = 0;
var _virt_machine_run = function() { calls++; return 100000; };
function terminal_write(text, serial = false) {
  globalThis.getField("field_29").value += text;
}
function machine_tick(pointer) {
  _virt_machine_run(pointer);
}
function queue_console_text(text) {
  var index = Number(text.match(/PDF_BENCH_(\d+)_DONE/)[1]);
  var replies = ["Usage: ooonana", "Package flow:", "ooonana 0.10.0", "base", "ooonana repo: synced"];
  terminal_write(replies[index] + "\nPDF_BENCH_" + index + "_DONE\r\n", true);
}
if (__probe_mode === "benchmark") {
  setTimeout(function() { terminal_write("ooonana# ", true); }, 100);
} else {
  setInterval(function() { machine_tick(0); }, 10);
  setTimeout(function() {
    terminal_write(calls > 5 ? "Kernel panic: rate hook bypassed"
      : "OOONANA_PDF_BOOT_OK\nooonana# ", true);
  }, 2800);
}
'''
fields = {**{f"field_{row}": "" for row in range(30)},
          "key_input": "", "key_status": "", "speed_indicator": ""}
for mode in ("benchmark", "rate"):
    script = "try {var __probe_mode = " + json.dumps(mode) + ";\n" + body + "} catch (e) {app.alert(e.stack || e)}"
    env = {key: value for key, value in os.environ.items() if not key.startswith("OOONANA_PDF_")}
    env.update(OOONANA_PDF_BENCHMARK="1" if mode == "benchmark" else "0",
               OOONANA_PDF_START_ONLY="1" if mode == "rate" else "0",
               OOONANA_PDF_MAX_IPS="100000" if mode == "rate" else "0")
    result = subprocess.run([node, str(root / "scripts/test-ooonana-pdf-vm.js"), "-", "6000"],
        input=json.dumps(dict(script=script, fields=fields)), env=env,
        capture_output=True, text=True, timeout=9)
    assert result.returncode == 0, (mode, result.stdout, result.stderr)
print("ok pdf-vm-harness: lexical serial observation and real instruction throttling")
