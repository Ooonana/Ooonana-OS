#!/usr/bin/env node

const fs = require("fs");
const vm = require("vm");

const compiled = process.argv[2];
const timeoutMs = Number(process.argv[3] || 90000);
if (!compiled || !fs.existsSync(compiled)) {
  console.error("usage: test-ooonana-pdf-vm.js COMPILED_JS [TIMEOUT_MS]");
  process.exit(2);
}

const fields = new Map();
function getField(name) {
  if (!fields.has(name)) fields.set(name, { value: "" });
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

vm.runInContext(fs.readFileSync(compiled, "utf8"), sandbox, { filename: compiled });

let sentInput = false;
let sentEnter = false;
let sentUpdate = false;
let sentVersion = false;
let phase = "boot";
const startedAt = Date.now();
let diagnosticAt = Date.now();
const monitor = setInterval(() => {
  const output = terminalText();
  if (process.env.OOONANA_PDF_DEBUG === "1" && Date.now() - diagnosticAt > 15000) {
    console.error(`PDF phase: ${phase}; elapsed: ${Math.round((Date.now() - startedAt) / 1000)}s; ${getField("speed_indicator").value}`);
    console.error(output.slice(-1600));
  }
  if (process.env.OOONANA_PDF_DEBUG === "1" && Date.now() - diagnosticAt > 15000 && sandbox.Module && sandbox.Module.ccall) {
    diagnosticAt = Date.now();
    try {
      const values = [0, 1, 2, 3].map(field => sandbox.Module.ccall("oo_vm_debug", "number", ["number"], [field]) >>> 0);
      console.error("VM CPU snapshot:", values.map(value => value.toString(16)).join(" "));
    } catch (_) {}
  }
  if (output.includes("Kernel panic") || output.includes("Function not implemented") || output.includes("can't rename")) {
    console.error(output);
    process.exit(1);
  }
  if (!sentInput && output.includes("OOONANA_PDF_BOOT_OK")) {
    phase = "keyboard-input";
    sandbox.queue_console_text("echo $((12345+54321))");
    sentInput = true;
  }
  if (sentInput && !sentEnter && output.includes("echo $((12345+54321))")) {
    sandbox.queue_console_text("\r");
    sentEnter = true;
  }
  if (sentEnter && !sentVersion && output.includes("66666")) {
    phase = "version";
    sandbox.queue_console_text("ooonana version\r");
    sentVersion = true;
  }
  if (sentVersion && !sentUpdate && output.includes("ooonana 0.9.7")) {
    if (process.env.OOONANA_PDF_TMPFS_ONLY === "1") {
      phase = "tmpfs";
      sandbox.queue_console_text("grep -q 'tmpfs /tmp tmpfs' /proc/mounts && echo OOONANA_PDF_TMPFS_OK\r");
      sentUpdate = true;
      return;
    }
    if (process.env.OOONANA_PDF_BOOT_ONLY === "1") {
      console.log("ok ooonana-pdf-vm boot/input/version (package sync not tested)");
      process.exit(0);
    }
    phase = "package-sync";
    sandbox.queue_console_text(process.env.OOONANA_PDF_TRACE === "1" ? "sh -x /usr/bin/ooonana update\r" : "ooonana update\r");
    sentUpdate = true;
  }
  if (sentUpdate && phase === "tmpfs" && output.includes("OOONANA_PDF_TMPFS_OK\n")) {
    console.log("ok ooonana-pdf-vm boot/input/version/tmpfs");
    process.exit(0);
  }
  if (sentUpdate && output.includes("ooonana repo: synced")) {
    clearInterval(monitor);
    console.log(`ok ooonana-pdf-vm boot/input/version/package-sync (${Math.round((Date.now() - startedAt) / 1000)}s)`);
    process.exit(0);
  }
}, 250);

setTimeout(() => {
  console.error(terminalText());
  console.error(`FAIL: Ooonana PDF VM ${phase} timeout`);
  process.exit(1);
}, timeoutMs);
