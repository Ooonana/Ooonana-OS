#!/usr/bin/env python3
"""Bound PDF field IPC and CPU slices without changing guest Linux behavior."""
from pathlib import Path
import re
import sys


def replace_function(source, name, replacement):
    pattern = rf"function {name}\([^\n]*\) \{{.*?\n\}}"
    source, count = re.subn(pattern, lambda _: replacement, source, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f"Missing PDF runtime function: {name}")
    return source


def optimize(path):
    source = Path(path).read_text()
    source = replace_function(source, "print_msg", '''function print_msg(msg) {
  // Diagnostics stay bounded in memory; no invisible AcroForm repaint IPC.
  lines.push("" + msg);
  if (lines.length > 25) lines.shift();
}''')
    source = replace_function(source, "render_terminal", '''function render_terminal() {
  // OOONANA_PDF_RENDER_CACHE: resolve each terminal widget only once.
  if (typeof terminal_fields === "undefined") terminal_fields = [];
  for (let row = 0; row < terminal_height; row++) {
    if (terminal_rendered[row] === terminal_lines[row]) continue;
    if (!terminal_fields[row])
      terminal_fields[row] = globalThis.getField("field_" + (terminal_height-row-1));
    terminal_fields[row].value = terminal_lines[row];
    terminal_rendered[row] = terminal_lines[row];
  }
}''')
    # Keep parser/serial semantics; only defer painting until bounded VM tick.
    write = re.search(r"function terminal_write\([^\n]*\).*?\n\}", source, re.S)
    if not write:
        raise ValueError("Missing PDF serial parser")
    body, count = re.subn(
        r"  if \(saw_newline[^\n]*\n    render_terminal\(\);[^\n]*\n    terminal_dirty = 0;\n  \}",
        "  // OOONANA_PDF_DEFERRED_RENDER: never repaint for every character.",
        write.group(), count=1,
    )
    if count != 1 and "OOONANA_PDF_DEFERRED_RENDER" not in body:
        raise ValueError("PDF per-character render patch point missing")
    source = source[:write.start()] + body + source[write.end():]
    source = replace_function(source, "machine_tick", '''function machine_tick(m_ptr) {
  // OOONANA_PDF_BOUNDED_SLICE: reduce timer round trips without long UI stalls.
  let deadline = Date.now() + 12;
  for (let batch = 0; batch < 32; batch++) {
    let instructions = _virt_machine_run(m_ptr);
    total_instrs += instructions;
    if (!instructions || Date.now() >= deadline) break;
  }
  let now = Date.now();
  if (typeof terminal_last_paint === "undefined") terminal_last_paint = 0;
  if (terminal_dirty && now - terminal_last_paint >= 50) {
    render_terminal();
    terminal_dirty = 0;
    terminal_last_paint = now;
  }
  let interval = now - last_updated;
  if (interval > 1000) {
    let k_ips = Math.round(total_instrs / (interval / 1000) / 1000);
    if (typeof speed_field === "undefined")
      speed_field = globalThis.getField("speed_indicator");
    speed_field.value = `Speed: ${k_ips} kIPS`;
    if (!vm_serial_seen) {
      terminal_lines[1] = `Booting kernel... ${Math.round((now-vm_started_at)/1000)}s | ${k_ips} kIPS`;
      terminal_dirty = terminal_width;
    }
    total_instrs = 0;
    last_updated = now;
  }
}''')
    Path(path).write_text(source)


if __name__ == "__main__":
    optimize(sys.argv[1])
