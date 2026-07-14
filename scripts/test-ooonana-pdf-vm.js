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
  Uint8Array,
  Uint8ClampedArray,
  Int8Array,
  Uint16Array,
  Int16Array,
  Uint32Array,
  Int32Array,
  Float32Array,
  Float64Array,
  ArrayBuffer,
  Date,
  Math,
  JSON,
  String,
  Number,
  Boolean,
  Object,
  Array,
  RegExp,
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
const monitor = setInterval(() => {
  const output = terminalText();
  if (output.includes("Kernel panic")) {
    console.error(output);
    process.exit(1);
  }
  if (!sentInput && output.includes("OOONANA_PDF_BOOT_OK")) {
    sandbox.queue_console_text("echo OOONANA_PDF_INPUT_OK\r");
    sentInput = true;
  }
  if (output.includes("OOONANA_PDF_INPUT_OK")) {
    clearInterval(monitor);
    console.log("ok ooonana-pdf-vm");
    process.exit(0);
  }
}, 250);

setTimeout(() => {
  console.error(terminalText());
  console.error("FAIL: Ooonana PDF VM boot/input timeout");
  process.exit(1);
}, timeoutMs);
