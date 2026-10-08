#!/usr/bin/env node

const fs = require("fs");
const vm = require("vm");
const path = require("path");
const { execFileSync } = require("child_process");

const compiled = process.argv[2];
const timeoutMs = Number(process.argv[3] || 90000);
if (!compiled || (compiled !== "-" && !fs.existsSync(compiled))) {
  console.error("usage: test-ooonana-pdf-vm.js COMPILED_JS|PDF|- [TIMEOUT_MS]");
  process.exit(2);
}

const fields = new Map();
let shipped;
if (compiled === "-") {
  shipped = JSON.parse(fs.readFileSync(0, "utf8"));
} else if (compiled.toLowerCase().endsWith(".pdf")) {
  shipped = JSON.parse(execFileSync(process.env.OOONANA_PDF_PYTHON || "python3",
    [path.join(__dirname, "inspect-pdf-runtime.py"), compiled],
    { encoding: "utf8", maxBuffer: 32 * 1024 * 1024 }));
}
let fieldWrites = 0;
function getField(name) {
  if (shipped && !Object.hasOwn(shipped.fields, name))
    throw new Error(`Missing shipped PDF field: ${name}`);
  if (!fields.has(name)) {
    let value = shipped ? shipped.fields[name] : "";
    fields.set(name, {
      get value() { return value; },
      set value(next) {
        value = next;
        if (name.startsWith("field_")) fieldWrites++;
      },
    });
  }
  return fields.get(name);
}

const quiet = () => {};
const sandbox = {
  console: { log: quiet, warn: quiet, error: quiet },
  print: quiet,
  printErr: quiet,
  getField,
  // Keep native intrinsics in VM's own realm. Cross-realm Math/typed-array
  // constructors make V8 reject asm.js linking and distort performance QA.
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
};

vm.createContext(sandbox);
sandbox.app = {
  alert(message) {
    console.error(`PDF alert: ${message}`);
  },
  setTimeOut(code, delay) {
    return setTimeout(() => vm.runInContext(code, sandbox), delay);
  },
  setInterval(code, delay) {
    return setInterval(() => vm.runInContext(code, sandbox), Math.max(delay, 1));
  },
};

function terminalText() {
  const rows = [];
  for (let index = 29; index >= 0; index--) {
    rows.push(getField(`field_${index}`).value || "");
  }
  return rows.join("\n");
}

// PDF page-open code wraps functions in try/catch. Those block bindings are
// distinct from Annex-B global aliases: assigning sandbox.terminal_write alone
// cannot observe real serial writes. Capture lexical setters for QA hooks only.
let bindWrite, bindTick;
sandbox.__ooonana_pdf_bind = (write, tick) => { bindWrite = write; bindTick = tick; };
let source = shipped ? shipped.script : fs.readFileSync(compiled, "utf8");
if (shipped) {
  const suffix = "} catch (e) {app.alert(e.stack || e)}";
  if (!source.startsWith("try {") || !source.endsWith(suffix))
    throw new Error("Unrecognized shipped PDF wrapper; refusing instrumentation");
  source = source.slice(0, -suffix.length) + `
__ooonana_pdf_bind(
  function(wrap) { terminal_write = wrap(terminal_write); },
  function(wrap) { machine_tick = wrap(machine_tick); }
);
` + suffix;
}
vm.runInContext(source, sandbox, { filename: compiled });
bindWrite ||= wrap => { sandbox.terminal_write = wrap(sandbox.terminal_write); };
bindTick ||= wrap => { sandbox.machine_tick = wrap(sandbox.machine_tick); };
// Constrain interpreted instructions while retaining real wall-clock timers.
// This exposes interrupt starvation that fast developer machines can hide.
const maxIps = Number(process.env.OOONANA_PDF_MAX_IPS || 0);
if (maxIps > 0) {
  let run, tokens = 0, previous = Date.now();
  bindTick(tick => function (pointer) {
    if (!run) {
      run = sandbox._virt_machine_run;
      sandbox._virt_machine_run = function (machine) {
        const now = Date.now();
        tokens = Math.min(200000, tokens + (now - previous) * maxIps / 1000);
        previous = now;
        if (tokens < 100000) return 0;
        const instructions = run(machine);
        tokens -= instructions;
        return instructions;
      };
    }
    return tick(pointer);
  });
}
let inputStable = false;
getField("key_input").value = "PDF_INPUT_STABILITY_TEST";
setTimeout(() => {
  if (getField("key_input").value !== "PDF_INPUT_STABILITY_TEST") {
    console.error("FAIL: runtime overwrote editable input");
    process.exit(1);
  }
  getField("key_input").value = "";
  inputStable = true;
}, 2200);

const benchmark = process.env.OOONANA_PDF_BENCHMARK === "1";
let serialLog = "";
if (benchmark) {
  bindWrite(write => function (text, serial = false) {
    if (serial) serialLog = (serialLog + text).slice(-65536);
    return write(text, serial);
  });
}
const commands = [
  ["bare", "ooonana", "Usage: ooonana"],
  ["help", "ooonana help packages", "Package flow:"],
  ["version", "ooonana version", "ooonana 0.10.0"],
  ["list", "ooonana list", "base"],
  ["sync", "ooonana update", "ooonana repo: synced"],
];
let commandIndex = -1;
let commandStarted = 0;
let commandWrites = 0;
const timings = [];

let sentInput = false;
let sentEnter = false;
let sentVirtualBackspace = false;
let sentNativeBackspace = false;
let sentMiddleEdit = false;
let sentUpdate = false;
let sentVersion = false;
let phase = "boot";
const startedAt = Date.now();
let diagnosticAt = Date.now();
const monitor = setInterval(() => {
  const output = terminalText();
  if (benchmark) {
    if (process.env.OOONANA_PDF_DEBUG === "1" && Date.now() - diagnosticAt > 15000) {
      diagnosticAt = Date.now();
      console.error(`PDF benchmark: ${phase}; ${Date.now() - startedAt}ms; ${getField("speed_indicator").value}`);
      console.error(output.slice(-600));
    }
    const completed = commandIndex >= 0 &&
      serialLog.includes(`\nPDF_BENCH_${commandIndex}_DONE\r\n`);
    if (completed) {
      const [name, command, expected] = commands[commandIndex];
      if (!serialLog.includes(expected)) {
        console.error(`FAIL: ${command}: expected output missing`);
        process.exit(1);
      }
      timings.push({ command: name, ms: Date.now() - commandStarted,
        field_writes: fieldWrites - commandWrites });
      console.log(JSON.stringify(timings[timings.length - 1]));
    }
    if ((commandIndex < 0 && serialLog.includes("ooonana# ")) || completed) {
      commandIndex++;
      if (commandIndex === commands.length) {
        console.log(JSON.stringify({ benchmark: "Node VM, not browser", timings }));
        process.exit(0);
      }
      phase = commands[commandIndex][0];
      serialLog = "";
      commandStarted = Date.now();
      commandWrites = fieldWrites;
      const command = commandIndex === 0 && process.env.OOONANA_PDF_TRACE === "1"
        ? "sh -x /usr/bin/ooonana" : commands[commandIndex][1];
      sandbox.queue_console_text(command + `; printf '\\nPDF_BENCH_${commandIndex}_DONE\\n'\r`);
    }
    return;
  }
  if (process.env.OOONANA_PDF_DEBUG === "1" && Date.now() - diagnosticAt > 15000) {
    console.error(`PDF phase: ${phase}; elapsed: ${Math.round((Date.now() - startedAt) / 1000)}s; ${getField("speed_indicator").value}`);
    console.error(output.slice(-1600));
  }
  if (process.env.OOONANA_PDF_DEBUG === "1" && Date.now() - diagnosticAt > 15000 && sandbox.Module && sandbox.Module.ccall) {
    diagnosticAt = Date.now();
    try {
      const values = [0, 1, 2, 3, 4, 5].map(field => sandbox.Module.ccall("oo_vm_debug", "number", ["number"], [field]) >>> 0);
      console.error("VM CPU snapshot:", values.map(value => value.toString(16)).join(" "));
    } catch (_) {}
  }
  if (output.includes("Kernel panic") || output.includes("Function not implemented") || output.includes("can't rename") ||
      output.includes("Illegal instruction") || output.includes("cannot create private query cache")) {
    console.error(output);
    process.exit(1);
  }
  if (process.env.OOONANA_PDF_START_ONLY === "1" &&
      output.includes("OOONANA_PDF_BOOT_OK") && output.includes("ooonana# ")) {
    console.log(`PASS shipped boot: ${Date.now() - startedAt}ms; max IPS=${maxIps || "unlimited"}`);
    process.exit(0);
  }
  if (!sentInput && inputStable && output.includes("OOONANA_PDF_BOOT_OK")) {
    phase = "keyboard-input";
    sandbox.queue_console_text("echo $((12345+54321))");
    sentInput = true;
  }
  if (sentInput && !sentEnter && output.includes("echo $((12345+54321))")) {
    sandbox.queue_console_text("\r");
    sentEnter = true;
  }
  if (sentEnter && !sentVirtualBackspace && output.includes("66666")) {
    phase = "virtual-backspace";
    const command = "echo PDF_VIRTUAL_BACKSPACE_OKX";
    getField("key_input").value = command;
    sandbox.pdf_key_input({willCommit: false, change: command, selStart: 0, selEnd: 0});
    sandbox.button_down("Backspace");
    sandbox.button_up("Backspace");
    if (getField("key_input").value !== command.slice(0, -1)) {
      console.error("FAIL: virtual Backspace did not update input");
      process.exit(1);
    }
    sandbox.button_down("Enter");
    sandbox.button_up("Enter");
    sentVirtualBackspace = true;
  }
  if (sentVirtualBackspace && !sentNativeBackspace && output.includes("\nPDF_VIRTUAL_BACKSPACE_OK\n")) {
    phase = "native-backspace";
    const command = "echo PDF_NATIVE_BACKSPACE_OKX";
    sandbox.pdf_key_input({willCommit: false, change: command, selStart: 0, selEnd: 0});
    sandbox.pdf_key_input({willCommit: false, value: command, change: "", selStart: command.length - 1, selEnd: command.length});
    // Model the viewer's accepted deletion; handler forwards only the key byte.
    getField("key_input").value = command.slice(0, -1);
    sandbox.button_down("Enter");
    sandbox.button_up("Enter");
    sentNativeBackspace = true;
  }
  if (sentNativeBackspace && !sentMiddleEdit && output.includes("\nPDF_NATIVE_BACKSPACE_OK\n")) {
    phase = "middle-edit";
    const command = "echo PDF_MIDDLE_XBACKSPACE_OK";
    const index = command.indexOf("X");
    sandbox.pdf_key_input({willCommit: false, change: command, selStart: 0, selEnd: 0});
    sandbox.pdf_key_input({willCommit: false, value: command, change: "", selStart: index, selEnd: index + 1});
    getField("key_input").value = command.slice(0, index) + command.slice(index + 1);
    sandbox.button_down("Enter");
    sandbox.button_up("Enter");
    sentMiddleEdit = true;
  }
  if (sentMiddleEdit && !sentVersion && output.includes("\nPDF_MIDDLE_BACKSPACE_OK\n")) {
    phase = "version";
    sandbox.queue_console_text("ooonana version\r");
    sentVersion = true;
  }
  if (sentVersion && !sentUpdate && output.includes("ooonana 0.10.0")) {
    if (process.env.OOONANA_PDF_TMPFS_ONLY === "1") {
      phase = "tmpfs";
      sandbox.queue_console_text("grep -q 'tmpfs /tmp tmpfs' /proc/mounts && echo OOONANA_PDF_TMPFS_OK\r");
      sentUpdate = true;
      return;
    }
    if (process.env.OOONANA_PDF_BOOT_ONLY === "1") {
      console.log("ok ooonana-pdf-vm boot/stable-input/backspace/version (package sync not tested)");
      process.exit(0);
    }
    phase = "package-sync";
    const update = process.env.OOONANA_PDF_TRACE === "1" ? "sh -x /usr/bin/ooonana update" : "ooonana update";
    const prefix = process.env.OOONANA_PDF_RAM_SOURCES === "1"
      ? "mkdir -p /tmp/pdf-sources; OOONANA_SOURCES_DIR=/tmp/pdf-sources " : "";
    sandbox.queue_console_text(prefix + update + "\r");
    sentUpdate = true;
  }
  if (sentUpdate && phase === "tmpfs" && output.includes("OOONANA_PDF_TMPFS_OK\n")) {
    console.log("ok ooonana-pdf-vm boot/input/version/tmpfs");
    process.exit(0);
  }
  if (sentUpdate && output.includes("ooonana repo: synced")) {
    clearInterval(monitor);
    console.log(`ok ooonana-pdf-vm boot/stable-input/native-and-virtual-backspace/version/package-sync (${Math.round((Date.now() - startedAt) / 1000)}s)`);
    process.exit(0);
  }
}, 250);

setTimeout(() => {
  console.error(terminalText());
  console.error(`FAIL: Ooonana PDF VM ${phase} timeout`);
  process.exit(1);
}, timeoutMs);
