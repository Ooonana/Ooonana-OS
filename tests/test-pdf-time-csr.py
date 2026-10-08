#!/usr/bin/env python3
"""TinyEMU time CSR uses CLINT units, privilege gates, RV32 high word; idempotent."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("time_patch", root / "scripts/patch-pdf-time-csr.py")
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

with tempfile.TemporaryDirectory(prefix="ooonana-time-csr-") as temporary:
    work = Path(temporary)
    originals = {
        "riscv_cpu.h": "    const RISCVCPUClass *class_ptr;\n} RISCVCPUCommonState;\nstatic inline void riscv_cpu_end(RISCVCPUState *s)\n",
        "riscv_cpu.c": "#define COUNTEREN_MASK ((1 << 0) | (1 << 2))\n    case 0xc00: /* ucycle */\n",
        "riscv_machine.c": "static uint32_t htif_read(void *opaque,\n    /* RAM */\n    ram_flags = 0;\n",
    }
    for name, text in originals.items():
        work.joinpath(name).write_text(text)
    patcher.patch(work)
    patched = {name: work.joinpath(name).read_text() for name in originals}
    mtimes = {name: work.joinpath(name).stat().st_mtime_ns for name in originals}
    patcher.patch(work)
    assert mtimes == {name: work.joinpath(name).stat().st_mtime_ns for name in originals}
    assert "(1 << 1)" in patched["riscv_cpu.c"].splitlines()[0]
    assert "return rtc_get_time((RISCVMachine *)opaque);" in patched["riscv_machine.c"]
    assert "riscv_cpu_set_time_source(s->cpu_state, csr_time_source, s)" in patched["riscv_machine.c"]
    body = patched["riscv_cpu.c"].split("    case 0xc01:", 1)[1].split("    case 0xc00:", 1)[0]
    body = "    case 0xc01:" + body
    assert "insn_counter" not in body
    cc = shutil.which("cc")
    if cc:
        source = work / "gate.c"
        source.write_text('''#include <stdint.h>
#include <assert.h>
#define PRV_M 3
#define PRV_S 1
static uint64_t ticks(void *opaque) { return *(uint64_t *)opaque; }
typedef struct { uint64_t (*time_source)(void *); void *time_opaque; } Common;
typedef struct { int priv, cur_xlen; unsigned mcounteren, scounteren; Common common; } State;
static int read_csr(State *s, unsigned csr, uint64_t *result) {
  uint64_t val;
  switch (csr) {
''' + body + '''
  default: goto invalid_csr;
  }
  *result = val;
  return 0;
invalid_csr: return -1;
}
int main(void) {
  uint64_t clock = UINT64_C(0x123456789), result = 0;
  for (int priv = 0; priv <= 3; ++priv)
    for (unsigned m = 0; m < 4; ++m)
      for (unsigned sup = 0; sup < 4; ++sup)
        for (int width = 32; width <= 64; width += 32) {
          State s = {priv, width, m, sup, {ticks, &clock}};
          int enabled = (priv == PRV_M || (m & 2)) && (priv >= PRV_S || (sup & 2));
          assert((read_csr(&s, 0xc01, &result) == 0) == !!enabled);
          if (enabled) assert(result == clock);
          assert((read_csr(&s, 0xc81, &result) == 0) == (enabled && width == 32));
          if (enabled && width == 32) assert(result == (clock >> 32));
          s.common.time_source = 0;
          assert(read_csr(&s, 0xc01, &result) == -1);
        }
  return 0;
}
''')
        binary = work / "gate"
        subprocess.run([cc, "-std=c99", "-Wall", "-Werror", str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    else:
        print("SKIP compiled time CSR matrix: C compiler unavailable; source/patch checks retained")
    # Unknown upstream shape must fail before even the recognized files change.
    for name, text in originals.items():
        work.joinpath(name).write_text(text)
    work.joinpath("riscv_machine.c").write_text("unsupported upstream")
    before = {name: work.joinpath(name).read_bytes() for name in originals}
    try:
        patcher.patch(work)
    except SystemExit:
        pass
    else:
        raise AssertionError("Unknown source shape accepted")
    assert before == {name: work.joinpath(name).read_bytes() for name in originals}

print("ok pdf-time-csr: CLINT callback, privilege gates, high-word/width, idempotence, unknown-source refusal")
