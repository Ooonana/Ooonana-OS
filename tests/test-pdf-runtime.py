#!/usr/bin/env python3
"""Fixture-only PDF IPC/CPU bounds and patch idempotence, no VM boot needed."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pdf_runtime", root / "scripts/optimize-pdf-runtime.py")
optimizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimizer)
fixture = '''var lines = [], terminal_height = 2, terminal_lines = ["", ""];
var terminal_rendered = [null, null], terminal_dirty = 0;
var vm_serial_seen = true, vm_started_at = 0, total_instrs = 0, last_updated = 0;
var input_bytes = "", input_timers = [];
function set_interval(callback, interval) { input_timers.push(callback); }
function queue_console_text(text) { input_bytes += text; }
function key_pressed(text) { queue_console_text(text); }
function serial_button(key) {
  queue_console_text(key === "Backspace" ? "\\x7f" : key === "Enter" ? "\\r" : key);
}
function button_down(key_str) {
  serial_button(key_str);
}
set_interval(() => {
  globalThis.getField("key_input").value = "Type here for keyboard inputs.";
}, 1000)
function print_msg(msg) {
  globalThis.getField("console_0").value = msg;
}
function render_terminal() {
  globalThis.getField("field_0").value = terminal_lines[0];
}
function terminal_write(str, serial_output = false) {
  let saw_newline = str.includes("\\n");
  terminal_lines[0] += str;
  terminal_dirty += str.length;
  if (saw_newline || terminal_dirty > 0) {
    render_terminal(); // old immediate renderer
    terminal_dirty = 0;
  }
}
function machine_tick(m_ptr) {
  total_instrs += _virt_machine_run(m_ptr);
}
'''
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "runtime.js"
    path.write_text(fixture)
    optimizer.optimize(path)
    first = path.read_text()
    assert "Type here for keyboard inputs." not in first
    optimizer.optimize(path)
    assert first == path.read_text(), "Optimization not idempotent"
    checks = '''
let calls = 0, writes = 0, lookups = 0, clock = 100;
Date.now = () => clock;
globalThis.getField = name => {
  lookups++;
  if (name.startsWith("console_")) throw Error("Hidden loader IPC");
  return {set value(text) { writes++; }};
};
globalThis._virt_machine_run = () => { calls++; return 1; };
for (let i = 0; i < 1000; i++) terminal_write("x", true);
if (writes) throw Error("Per-character repaint remains");
machine_tick(0);
if (calls !== 32 || writes !== 2 || lookups !== 2) throw Error("Batch bounds/cache failed");
terminal_write("y", true);
clock += 25; machine_tick(0);
if (writes !== 2) throw Error("Paint throttle failed");
clock += 25; machine_tick(0);
if (writes !== 3 || lookups !== 2) throw Error("Dirty-row cache failed");
for (let i = 0; i < 100; i++) print_msg("diagnostic");
if (lines.length !== 25 || writes !== 3) throw Error("Loader bound failed");
calls = 0;
globalThis._virt_machine_run = () => { calls++; clock += 5; return 1; };
machine_tick(0);
if (calls !== 3) throw Error("CPU wall-time bound failed");
let input = {value: "echo abcX"};
globalThis.getField = name => input;
if (input_timers.length) throw Error("Input-reset timer remains");
pdf_key_input({willCommit: false, value: "echo abcX", change: "", selStart: 8, selEnd: 9});
if (input_bytes !== "\\x7f") throw Error("Native Backspace ignored");
input_bytes = "";
pdf_key_input({willCommit: true, change: "duplicate", selStart: 0, selEnd: 9});
if (input_bytes) throw Error("Commit duplicated input");
pdf_key_input({willCommit: false, value: "echo abcX", change: "Z", selStart: 7, selEnd: 9});
if (input_bytes !== "\\x7f\\x7fZ") throw Error("Tail selection replacement failed");
input_bytes = "";
pdf_key_input({willCommit: false, value: "abc", change: "", selStart: 3, selEnd: 4});
if (input_bytes) throw Error("Delete past end erased previous character");
pdf_key_input({willCommit: false, value: "aXbc", change: "", selStart: 1, selEnd: 2});
if (input_bytes !== "\\x1b[F\\x1b[D\\x1b[D\\x7f\\x1b[F") throw Error("Middle edit positioning failed");
input_bytes = "";
button_down("Backspace");
if (input_bytes !== "\\x7f" || input.value !== "echo abc") throw Error("Virtual Backspace failed");
button_down("Enter");
if (input_bytes !== "\\x7f\\r" || input.value !== "") throw Error("Virtual Enter failed");
console.log("ok pdf-runtime: stable input, native/virtual Backspace, batched fields, 20Hz paint, CPU bounds, idempotence");
'''
    subprocess.run(["node", "-e", first + checks], check=True)
