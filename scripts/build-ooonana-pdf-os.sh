#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${OOONANA_PDF_WORK_DIR:-/var/tmp/ooonana-os/linuxpdf}"
LINUXPDF_REPO="${OOONANA_LINUXPDF_REPO:-https://github.com/ading2210/linuxpdf.git}"
LINUXPDF_REF="${OOONANA_LINUXPDF_REF:-main}"
OUT="$ROOT/docs/ooonana.pdf"
BITS="32"
FORCE=0
DRY_RUN=0
PREPARE_ONLY=0

usage() {
  cat <<'USAGE'
Build bootable Ooonana OS PDF from linuxpdf.

This builds a TinyEMU RISC-V PDF and injects the minimal Ooonana shell OS
payload. It writes docs/ooonana.pdf. The docs-only guide is docs/ooonana-guide.pdf.

Usage:
  scripts/build-ooonana-pdf-os.sh [options]

Options:
  --work-dir PATH   Work dir outside repo (default: /var/tmp/ooonana-os/linuxpdf)
  --out PATH        Output PDF (default: docs/ooonana.pdf)
  --bits 32|64      linuxpdf machine width (default: 32, faster)
  --prepare-only    Clone/patch/inject but do not run old Emscripten build
  --dry-run         Print actions only
  --force           Rebuild linuxpdf out/files and overwrite output
  -h, --help        Show help

Notes:
  linuxpdf is GPLv3 and downloads old Emscripten 1.39.20 plus TinyEMU assets.
  Keep work dir in /var/tmp or another big Linux filesystem, not C:.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --bits) BITS="$2"; shift 2 ;;
    --prepare-only) PREPARE_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'build-ooonana-pdf-os: unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

case "$BITS" in
  32|64) ;;
  *) printf 'build-ooonana-pdf-os: --bits must be 32 or 64\n' >&2; exit 1 ;;
esac

SRC="$WORK_DIR/linuxpdf"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

patch_linuxpdf() {
  local build_sh="$SRC/build.sh"
  local gen_pdf="$SRC/gen_pdf.py"
  local display_js="$SRC/pdflinux.js"
  local vm_cfg="$SRC/vm_32.cfg"
  local tinyemu_lib="$SRC/tinyemu/js/lib.js"
  python3 - "$build_sh" "$gen_pdf" "$display_js" "$vm_cfg" "$tinyemu_lib" <<'PY'
from pathlib import Path
import re
import sys

build = Path(sys.argv[1])
text = build.read_text()
text = text.replace('BITS="32"', 'BITS="${OOONANA_PDF_BITS:-32}"')
if 'OOONANA_SOURCE_ROOT' not in text:
    needle = "build_files\ncp vm_$BITS.cfg build/vm/bbl$BITS.bin build/vm/kernel-riscv$BITS.bin build/files\n"
    insert = """build_files
if [ -n "${OOONANA_SOURCE_ROOT:-}" ]; then
  sudo bash "$OOONANA_SOURCE_ROOT/scripts/inject-ooonana-pdf-root.sh" "$root_dir"
  sudo rm -rf build/files
  sudo mkdir -p build/files/root
  sudo build/build_files "$root_dir" build/files/root
fi
sudo cp vm_$BITS.cfg build/vm/bbl$BITS.bin build/vm/kernel-riscv$BITS.bin build/files
"""
    if needle not in text:
        raise SystemExit("linuxpdf build.sh patch point missing")
    text = text.replace(needle, insert)
text = text.replace(
    '  bash "$OOONANA_SOURCE_ROOT/scripts/inject-ooonana-pdf-root.sh" "$root_dir"',
    '  sudo bash "$OOONANA_SOURCE_ROOT/scripts/inject-ooonana-pdf-root.sh" "$root_dir"',
)
text = text.replace(
    '  rm -rf build/files\n  mkdir -p build/files/root\n',
    '  sudo rm -rf build/files\n  sudo mkdir -p build/files/root\n',
)
text = re.sub(
    r'^(?:sudo )*cp vm_\$BITS\.cfg build/vm/bbl\$BITS\.bin build/vm/kernel-riscv\$BITS\.bin build/files$',
    'sudo cp vm_$BITS.cfg build/vm/bbl$BITS.bin build/vm/kernel-riscv$BITS.bin build/files',
    text,
    flags=re.MULTILINE,
)
build.write_text(text)

gen = Path(sys.argv[2])
pdf = gen.read_text()
pdf = pdf.replace('"LinuxPDF"', '"OoonanaPDF"')
pdf = pdf.replace('"Source code: https://github.com/ading2210/linuxpdf"', '"Ooonana OS in PDF | based on linuxpdf"')
pdf = pdf.replace('"Note: This PDF only works in Chromium-based browsers."', '"Works best in Chromium PDF viewer. Boot can take 30-60s."')
if "OOONANA_MONO_FRAMEBUFFER" not in pdf:
    pdf = pdf.replace(
        "from pdfrw.objects.pdfarray import PdfArray\n",
        "from pdfrw.objects.pdfarray import PdfArray\nfrom pdfrw.objects.pdfobject import PdfObject\n",
    )
    pdf = pdf.replace(
        'def create_field(name, x, y, width, height, value="", f_type=PdfName.Tx):',
        'def create_field(name, x, y, width, height, value="", f_type=PdfName.Tx, display=False):',
    )
    pdf = pdf.replace(
        "  annotation.BS.W = 0\n\n  appearance = PdfDict()",
        """  annotation.BS.W = 0

  # OOONANA_MONO_FRAMEBUFFER: fixed metrics stop Chromium glyph drift.
  if display:
    annotation.Ff = 1
    annotation.DA = PdfString.encode(\"/FMono 8 Tf 1 0.62 0 rg\")
    annotation.Q = 0
    annotation.MK = PdfDict()
    annotation.MK.BG = PdfArray([0.015, 0.015, 0.015])

  appearance = PdfDict()""",
    )
    pdf = pdf.replace(
        'field = create_field(f"field_{i}", 0, i*scale + 220, width*scale-8, scale, "")',
        'field = create_field(f"field_{i}", 0, i*scale + 220, width*scale-8, scale, "", display=True)',
    )
    pdf = pdf.replace(
        "  page.Annots = PdfArray(fields)\n  writer.addpage(page)\n  writer.write(sys.argv[2])",
        """  page.Contents.stream = (
    f\"0.015 0.015 0.015 rg\\n0 220 {width*scale-8} {height*scale} re f\\n\"
    + page.Contents.stream
  )
  page.Annots = PdfArray(fields)
  writer.addpage(page)

  mono_font = PdfDict(
    Type=PdfName.Font,
    Subtype=PdfName.Type1,
    BaseFont=PdfName.Courier,
  )
  writer.trailer.Root.AcroForm = PdfDict(
    Fields=PdfArray(fields),
    NeedAppearances=PdfObject(\"true\"),
    DA=PdfString.encode(\"/FMono 10 Tf 0 g\"),
    DR=PdfDict(Font=PdfDict(FMono=mono_font)),
  )
  writer.write(sys.argv[2])""",
    )
if "OOONANA_INDIRECT_WIDGETS" not in pdf:
    needle = "  annotation = PdfDict()\n"
    if needle not in pdf:
        raise SystemExit("linuxpdf annotation patch point missing")
    pdf = pdf.replace(
        needle,
        "  annotation = PdfDict()\n  annotation.indirect = True  # OOONANA_INDIRECT_WIDGETS\n",
        1,
    )
if "OOONANA_SERIAL_TERMINAL_LAYOUT" not in pdf:
    pdf = pdf.replace(
        'annotation.DA = PdfString.encode("/FMono 2 Tf 185 Tz 1 0.55 0 rg")',
        'annotation.DA = PdfString.encode("/FMono 8 Tf 1 0.62 0 rg")',
    )
    old_layout = '''  fields = []
  for i in range(0, height):
    field = create_field(f"field_{i}", 0, i*scale + 220, width*scale-8, scale, "", display=True)
    fields.append(field)
'''
    new_layout = '''  fields = []
  terminal_rows = 30  # OOONANA_SERIAL_TERMINAL_LAYOUT
  for i in range(0, terminal_rows):
    initial = ""
    if i == terminal_rows - 1:
      initial = "Ooonana OS PDF 0.5"
    elif i == terminal_rows - 2:
      initial = "Starting JavaScript..."
    field = create_field(f"field_{i}", 8, 225 + i*13, width*scale-24, 13, initial, display=True)
    fields.append(field)
'''
    if old_layout not in pdf:
        raise SystemExit("linuxpdf terminal field patch point missing")
    pdf = pdf.replace(old_layout, new_layout)
gen.write_text(pdf)

display = Path(sys.argv[3])
js = display.read_text()
if "OOONANA_FRAMEBUFFER_CACHE" not in js:
    js = js.replace(
        'var line_buffer = "";\n',
        'var line_buffer = "";\nvar framebuffer_rows = []; // OOONANA_FRAMEBUFFER_CACHE\n',
    )
    js = js.replace(
        '    let old_row = row.join("");',
        '    let old_row = framebuffer_rows[y] || "";',
    )
    old_palette = """      //note - these ascii characters were all picked because they have the same width in the sans-serif font that chrome decided to use for text fields
      if (avg > 200)
        row[x] = "_";
      else if (avg > 150)
        row[x] = "::";
      else if (avg > 100)
        row[x] = "?";
      else if (avg > 50)
        row[x] = "//";
      else if (avg > 25)
        row[x] = "b";
      else
        row[x] = "#";"""
    new_palette = """      // OOONANA_AMBER_PALETTE: one monospaced glyph per framebuffer pixel.
      if (avg > 224)
        row[x] = "@";
      else if (avg > 192)
        row[x] = "O";
      else if (avg > 160)
        row[x] = "o";
      else if (avg > 128)
        row[x] = "*";
      else if (avg > 96)
        row[x] = "+";
      else if (avg > 64)
        row[x] = ":";
      else if (avg > 32)
        row[x] = ".";
      else
        row[x] = " ";"""
    if old_palette not in js:
        raise SystemExit("linuxpdf framebuffer palette patch point missing")
    js = js.replace(old_palette, new_palette)
    js = js.replace(
        "    if (row_str !== old_row)\n      globalThis.getField(\"field_\"+(height-y-1)).value = row_str;",
        """    if (row_str !== old_row) {
      framebuffer_rows[y] = row_str;
      globalThis.getField(\"field_\"+(height-y-1)).value = row_str;
    }""",
    )
if "OOONANA_SERIAL_TERMINAL" not in js:
    terminal_js = r'''
var terminal_width = 80;
var terminal_height = 30;
var terminal_lines = Array(terminal_height).fill("");
var terminal_rendered = Array(terminal_height).fill(null);
var terminal_row = 0;
var terminal_col = 0;
var terminal_escape = "";
var terminal_dirty = 0;
var vm_serial_seen = false;
var vm_boot_complete = false;
var vm_serial_tail = "";
var vm_started_at = null;

function render_terminal() {
  for (let row = 0; row < terminal_height; row++) {
    if (terminal_rendered[row] === terminal_lines[row])
      continue;
    terminal_rendered[row] = terminal_lines[row];
    globalThis.getField("field_" + (terminal_height-row-1)).value = terminal_lines[row];
  }
}

function terminal_scroll() {
  while (terminal_row >= terminal_height) {
    terminal_lines.shift();
    terminal_lines.push("");
    terminal_row--;
  }
}

function terminal_clear() {
  terminal_lines = Array(terminal_height).fill("");
  terminal_row = 0;
  terminal_col = 0;
  terminal_dirty = terminal_width;
}

function terminal_csi(sequence) {
  let match = sequence.match(/^\x1b\[([0-9;?]*)([A-Za-z~])$/);
  if (!match)
    return;
  let raw = match[1].replace(/^\?/, "");
  let params = raw === "" ? [] : raw.split(";").map(Number);
  let command = match[2];
  let amount = params[0] || 1;
  if (command === "J") {
    terminal_clear();
  } else if (command === "H" || command === "f") {
    terminal_row = Math.max(0, Math.min(terminal_height-1, (params[0] || 1)-1));
    terminal_col = Math.max(0, Math.min(terminal_width-1, (params[1] || 1)-1));
  } else if (command === "K") {
    terminal_lines[terminal_row] = terminal_lines[terminal_row].slice(0, terminal_col);
  } else if (command === "A") {
    terminal_row = Math.max(0, terminal_row-amount);
  } else if (command === "B") {
    terminal_row = Math.min(terminal_height-1, terminal_row+amount);
  } else if (command === "C") {
    terminal_col = Math.min(terminal_width-1, terminal_col+amount);
  } else if (command === "D") {
    terminal_col = Math.max(0, terminal_col-amount);
  }
}

function terminal_put(char) {
  if (char === "\r") {
    terminal_col = 0;
    return;
  }
  if (char === "\n") {
    terminal_row++;
    terminal_col = 0;
    terminal_scroll();
    return;
  }
  if (char === "\b" || char.charCodeAt(0) === 127) {
    terminal_col = Math.max(0, terminal_col-1);
    terminal_lines[terminal_row] = terminal_lines[terminal_row].slice(0, terminal_col);
    return;
  }
  if (char === "\t") {
    terminal_col = Math.min(terminal_width-1, (Math.floor(terminal_col/8)+1)*8);
    return;
  }
  let code = char.charCodeAt(0);
  if (code < 32 || code > 126)
    return;
  let line = terminal_lines[terminal_row];
  if (line.length < terminal_col)
    line += " ".repeat(terminal_col-line.length);
  terminal_lines[terminal_row] = line.slice(0, terminal_col) + char + line.slice(terminal_col+1);
  terminal_col++;
  if (terminal_col >= terminal_width) {
    terminal_col = 0;
    terminal_row++;
    terminal_scroll();
  }
}

function terminal_write(str, serial_output = false) { // OOONANA_SERIAL_TERMINAL
  if (serial_output) {
    vm_serial_seen = true;
    vm_serial_tail = (vm_serial_tail + str).slice(-256);
    if (vm_serial_tail.indexOf("OOONANA_PDF_BOOT_OK") >= 0)
      vm_boot_complete = true;
  }
  let saw_newline = false;
  for (let char of str) {
    if (terminal_escape !== "") {
      terminal_escape += char;
      if (/[@-~]/.test(char) && terminal_escape.length > 2) {
        terminal_csi(terminal_escape);
        terminal_escape = "";
      } else if (terminal_escape.length > 24) {
        terminal_escape = "";
      }
    } else if (char === "\x1b") {
      terminal_escape = char;
    } else {
      terminal_put(char);
      terminal_dirty++;
      if (char === "\n")
        saw_newline = true;
    }
  }
  if (saw_newline || terminal_dirty >= terminal_width) {
    render_terminal(); // OOONANA_TERMINAL_RENDER_BATCH
    terminal_dirty = 0;
  }
}

function queue_console_text(text) {
  for (let char of text)
    _console_queue_char(char.charCodeAt(0));
}

function serial_button(key) {
  let special = {
    "Esc": "\x1b", "Backspace": "\x7f", "Tab": "\t", "Enter": "\r",
    "Space": " ", "ArrowUp": "\x1b[A", "ArrowDown": "\x1b[B",
    "ArrowRight": "\x1b[C", "ArrowLeft": "\x1b[D", "Home": "\x1b[H",
    "End": "\x1b[F", "Delete": "\x1b[3~", "Insert": "\x1b[2~",
    "PgUp": "\x1b[5~", "PgDn": "\x1b[6~"
  };
  if (special[key]) {
    queue_console_text(special[key]);
    return;
  }
  if (key.length === 1)
    queue_console_text(key);
}
'''
    if "\nfunction start() {" not in js:
        raise SystemExit("linuxpdf terminal insertion point missing")
    js = js.replace("\nfunction start() {", terminal_js + "\nfunction start() {")
    js = re.sub(
        r'function update_framebuffer\(width, height, data, start_y, updated_height\) \{.*?\n\}\n\nvar key_to_input_map',
        '''function update_framebuffer(width, height, data, start_y, updated_height) {
  // Serial terminal owns display; simplefb updates are intentionally ignored.
}

var key_to_input_map''',
        js,
        flags=re.DOTALL,
    )
    js = re.sub(
        r'function button_down\(key_str\) \{.*?\n\}\n\nfunction button_up\(key_str\) \{.*?\n\}',
        '''function button_down(key_str) {
  serial_button(key_str);
}

function button_up(key_str) {
}''',
        js,
        flags=re.DOTALL,
    )
    js = re.sub(
        r'var pressed_list = \[\];\nfunction button_toggle\(key_str\) \{.*?\n\}',
        '''var pressed_list = [];
function button_toggle(key_str) {
  let index = pressed_list.indexOf(key_str);
  if (index >= 0)
    pressed_list.splice(index, 1);
  else
    pressed_list.push(key_str);
  globalThis.getField("key_status").value = "Pressed: " + pressed_list.join(", ");
}''',
        js,
        flags=re.DOTALL,
    )
    js = re.sub(
        r'function key_pressed\(key_str\) \{.*?\n\}',
        '''function key_pressed(key_str) {
  queue_console_text(key_str);
}''',
        js,
        flags=re.DOTALL,
    )
if "OOONANA_TERMINAL_RENDER_BATCH" not in js:
    js = js.replace(
        'var terminal_escape = "";\n',
        'var terminal_escape = "";\nvar terminal_dirty = 0;\n',
    )
    js = js.replace(
        '''function terminal_clear() {
  terminal_lines = Array(terminal_height).fill("");
  terminal_row = 0;
  terminal_col = 0;
}''',
        '''function terminal_clear() {
  terminal_lines = Array(terminal_height).fill("");
  terminal_row = 0;
  terminal_col = 0;
  terminal_dirty = terminal_width;
}''',
    )
    batched_terminal = r'''function terminal_write(str, serial_output = false) { // OOONANA_SERIAL_TERMINAL
  if (serial_output) {
    vm_serial_seen = true;
    vm_serial_tail = (vm_serial_tail + str).slice(-256);
    if (vm_serial_tail.indexOf("OOONANA_PDF_BOOT_OK") >= 0)
      vm_boot_complete = true;
  }
  let saw_newline = false;
  for (let char of str) {
    if (terminal_escape !== "") {
      terminal_escape += char;
      if (/[@-~]/.test(char) && terminal_escape.length > 2) {
        terminal_csi(terminal_escape);
        terminal_escape = "";
      } else if (terminal_escape.length > 24) {
        terminal_escape = "";
      }
    } else if (char === "\x1b") {
      terminal_escape = char;
    } else {
      terminal_put(char);
      terminal_dirty++;
      if (char === "\n")
        saw_newline = true;
    }
  }
  if (saw_newline || terminal_dirty >= terminal_width) {
    render_terminal(); // OOONANA_TERMINAL_RENDER_BATCH
    terminal_dirty = 0;
  }
}

function queue_console_text'''
    js = re.sub(
        r'function terminal_write\(str\) \{ // OOONANA_SERIAL_TERMINAL\n.*?\n\}\n\nfunction queue_console_text',
        lambda _match: batched_terminal,
        js,
        flags=re.DOTALL,
    )
if "OOONANA_BOOT_MESSAGE" not in js:
    needle = "function start() {\n  update_framebuffer"
    replacement = '''function start() {
  terminal_write("Ooonana OS PDF 0.5\\nBooting kernel... 0s\\n"); // OOONANA_BOOT_MESSAGE
  update_framebuffer'''
    if needle not in js:
        raise SystemExit("linuxpdf boot message patch point missing")
    js = js.replace(needle, replacement)
if "OOONANA_VM_BATCH" not in js:
    needle = "  total_instrs += _virt_machine_run(m_ptr);"
    replacement = '''  // OOONANA_VM_BATCH: accelerate boot, then preserve shell responsiveness.
  let batches = vm_boot_complete ? 2 : 8;
  for (let batch = 0; batch < batches; batch++)
    total_instrs += _virt_machine_run(m_ptr);'''
    if needle not in js:
        raise SystemExit("linuxpdf VM batch patch point missing")
    js = js.replace(needle, replacement)
js = js.replace(
    '''  // OOONANA_VM_BATCH: fewer PDF timer round trips during boot.
  for (let batch = 0; batch < 4; batch++)
    total_instrs += _virt_machine_run(m_ptr);''',
    '''  // OOONANA_VM_BATCH: accelerate boot, then preserve shell responsiveness.
  let batches = vm_boot_complete ? 2 : 8;
  for (let batch = 0; batch < batches; batch++)
    total_instrs += _virt_machine_run(m_ptr);''',
)
js = js.replace(
    '''  // OOONANA_VM_BATCH: bounded VM slice keeps PDF controls responsive.
  total_instrs += _virt_machine_run(m_ptr);''',
    '''  // OOONANA_VM_BATCH: accelerate boot, then preserve shell responsiveness.
  let batches = vm_boot_complete ? 2 : 8;
  for (let batch = 0; batch < batches; batch++)
    total_instrs += _virt_machine_run(m_ptr);''',
)
if "OOONANA_BOOT_HEARTBEAT" not in js:
    if "var vm_serial_seen" not in js:
        js = js.replace(
            'var terminal_dirty = 0;\n',
            '''var terminal_dirty = 0;
var vm_serial_seen = false;
var vm_boot_complete = false;
var vm_serial_tail = "";
var vm_started_at = null;
''',
            1,
        )
    js = js.replace(
        'function terminal_write(str) { // OOONANA_SERIAL_TERMINAL',
        'function terminal_write(str, serial_output = false) { // OOONANA_SERIAL_TERMINAL',
    )
    js = js.replace(
        '''function terminal_write(str, serial_output = false) { // OOONANA_SERIAL_TERMINAL
  let saw_newline = false;''',
        '''function terminal_write(str, serial_output = false) { // OOONANA_SERIAL_TERMINAL
  if (serial_output) {
    vm_serial_seen = true;
    vm_serial_tail = (vm_serial_tail + str).slice(-256);
    if (vm_serial_tail.indexOf("OOONANA_PDF_BOOT_OK") >= 0)
      vm_boot_complete = true;
  }
  let saw_newline = false;''',
    )
    js = js.replace(
        '''    globalThis.getField("speed_indicator").value = `Speed: ${k_ips} kIPS`;
    total_instrs = 0;''',
        '''    globalThis.getField("speed_indicator").value = `Speed: ${k_ips} kIPS`;
    if (!vm_serial_seen) {
      let elapsed = Math.max(0, Math.round((now - vm_started_at) / 1000));
      terminal_lines[1] = `Booting kernel... ${elapsed}s | ${k_ips} kIPS`;
      terminal_dirty = terminal_width;
      render_terminal(); // OOONANA_BOOT_HEARTBEAT
    }
    total_instrs = 0;''',
    )
    js = js.replace(
        '''  print_msg("starting the machine. please be patient...")
  last_updated = Date.now();''',
        '''  print_msg("starting the machine. please be patient...")
  vm_started_at = Date.now();
  last_updated = vm_started_at;''',
    )
js = js.replace('Ooonana OS PDF 0.4\\nBooting kernel...\\n', 'Ooonana OS PDF 0.5\\nBooting kernel... 0s\\n')
display.write_text(js)

vm = Path(sys.argv[4])
cfg = vm.read_text()
cfg = cfg.replace(
    'cmdline: "loglevel=6 swiotlb=1 console=tty0',
    'cmdline: "loglevel=7 ignore_loglevel printk.time=1 consoleblank=0 swiotlb=1 console=hvc0',
)
cfg = cfg.replace('console=tty0', 'console=hvc0')
cfg = cfg.replace(
    'quiet loglevel=3 vt.global_cursor_default=0 consoleblank=0 swiotlb=1 console=hvc0',
    'loglevel=7 ignore_loglevel printk.time=1 consoleblank=0 swiotlb=1 console=hvc0',
)
vm.write_text(cfg)

tinyemu = Path(sys.argv[5])
lib = tinyemu.read_text()
if "OOONANA_SERIAL_CONSOLE_WRITE" not in lib:
    old_console = '''      var str = String.fromCharCode.apply(String, HEAPU8.subarray(buf, buf + len));
      for (let char of str) {
        if (str === "\\n") {
          Module.print(line_buffer);
          line_buffer = "";
        }
        else {
          line_buffer += char;
        }
      }
      //term.write(str);'''
    new_console = '''      var str = String.fromCharCode.apply(String, HEAPU8.subarray(buf, buf + len));
      terminal_write(str, true); // OOONANA_SERIAL_CONSOLE_WRITE'''
    if old_console not in lib:
        raise SystemExit("tinyemu serial console patch point missing")
    lib = lib.replace(old_console, new_console)
lib = lib.replace(
    'terminal_write(str); // OOONANA_SERIAL_CONSOLE_WRITE',
    'terminal_write(str, true); // OOONANA_SERIAL_CONSOLE_WRITE',
)
tinyemu.write_text(lib)
PY
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'would build Ooonana OS PDF\n'
  printf 'repo: %s\n' "$LINUXPDF_REPO"
  printf 'work: %s\n' "$SRC"
  printf 'out: %s\n' "$OUT"
fi

if [[ ! -d "$SRC/.git" ]]; then
  run mkdir -p "$WORK_DIR"
  run git clone --depth 1 --branch "$LINUXPDF_REF" "$LINUXPDF_REPO" "$SRC"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '+ patch linuxpdf build for Ooonana payload\n'
else
  patch_linuxpdf
fi

if [[ "$FORCE" -eq 1 ]]; then
  run sudo rm -rf "$SRC/build/root" "$SRC/build/files" "$SRC/out/linux.pdf"
fi

if [[ "$PREPARE_ONLY" -eq 1 ]]; then
  printf 'prepared Ooonana PDF source: %s\n' "$SRC"
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '+ python3 -m venv %q\n' "$SRC/.venv"
  printf '+ pip install -r %q\n' "$SRC/requirements.txt"
  printf '+ OOONANA_SOURCE_ROOT=%q OOONANA_PDF_BITS=%q ./build.sh\n' "$ROOT" "$BITS"
  printf '+ cp -f %q %q\n' "$SRC/out/linux.pdf" "$OUT"
  exit 0
fi

python3 -m venv "$SRC/.venv"
"$SRC/.venv/bin/pip" install -r "$SRC/requirements.txt"
(
  cd "$SRC"
  OOONANA_SOURCE_ROOT="$ROOT" OOONANA_PDF_BITS="$BITS" ./build.sh
)
mkdir -p "$(dirname "$OUT")"
cp -f "$SRC/out/linux.pdf" "$OUT"
chmod 0644 "$OUT" 2>/dev/null || true
printf 'Ooonana OS PDF ready: %s\n' "$OUT"
