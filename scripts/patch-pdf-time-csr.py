#!/usr/bin/env python3
"""Add architectural time/timeh reads backed by TinyEMU's existing CLINT clock."""
from pathlib import Path
import sys


def replace_once(text, old, new, marker):
    if marker in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"TinyEMU time CSR patch point missing/ambiguous: {marker}")
    return text.replace(old, new, 1)


def patch(root):
    header, cpu, machine = (root / name for name in ("riscv_cpu.h", "riscv_cpu.c", "riscv_machine.c"))
    original = {path: path.read_text() for path in (header, cpu, machine)}
    edited = dict(original)
    edited[header] = replace_once(edited[header],
        "    const RISCVCPUClass *class_ptr;\n} RISCVCPUCommonState;",
        """    const RISCVCPUClass *class_ptr;
    /* OOONANA_TIME_SOURCE: same units/source as CLINT mtime. */
    uint64_t (*time_source)(void *opaque);
    void *time_opaque;
} RISCVCPUCommonState;""", "OOONANA_TIME_SOURCE")
    edited[header] = replace_once(edited[header],
        "static inline void riscv_cpu_end(RISCVCPUState *s)",
        """/* OOONANA_TIME_SETTER */
static inline void riscv_cpu_set_time_source(RISCVCPUState *s,
                                            uint64_t (*source)(void *),
                                            void *opaque)
{
    RISCVCPUCommonState *common = (RISCVCPUCommonState *)s;
    common->time_source = source;
    common->time_opaque = opaque;
}

static inline void riscv_cpu_end(RISCVCPUState *s)""", "OOONANA_TIME_SETTER")
    edited[cpu] = replace_once(edited[cpu],
        "#define COUNTEREN_MASK ((1 << 0) | (1 << 2))",
        "#define COUNTEREN_MASK ((1 << 0) | (1 << 1) | (1 << 2)) /* OOONANA_TIME_ENABLE */",
        "OOONANA_TIME_ENABLE")
    edited[cpu] = replace_once(edited[cpu], "    case 0xc00: /* ucycle */",
        """    /* OOONANA_TIME_CSR: Linux vDSO/libc can issue rdtime in userspace. */
    case 0xc01: /* time */
    case 0xc81: /* timeh, RV32 only */
        if (csr == 0xc81 && s->cur_xlen != 32)
            goto invalid_csr;
        if (!s->common.time_source ||
            (s->priv < PRV_M && !(s->mcounteren & (1 << 1))) ||
            (s->priv < PRV_S && !(s->scounteren & (1 << 1))))
            goto invalid_csr;
        val = s->common.time_source(s->common.time_opaque);
        if (csr == 0xc81)
            val = (uint64_t)val >> 32;
        break;
    case 0xc00: /* ucycle */""", "OOONANA_TIME_CSR")
    edited[machine] = replace_once(edited[machine], "static uint32_t htif_read(void *opaque,",
        """/* OOONANA_TIME_CALLBACK: never substitute instruction count for mtime. */
static uint64_t csr_time_source(void *opaque)
{
    return rtc_get_time((RISCVMachine *)opaque);
}

static uint32_t htif_read(void *opaque,""", "OOONANA_TIME_CALLBACK")
    edited[machine] = replace_once(edited[machine], "    /* RAM */\n    ram_flags = 0;",
        """    /* OOONANA_TIME_CONNECT */
    riscv_cpu_set_time_source(s->cpu_state, csr_time_source, s);
    /* RAM */
    ram_flags = 0;""", "OOONANA_TIME_CONNECT")
    # Validate every source before changing any. Do not force rebuilds when
    # already patched: mtimes of unchanged files remain stable.
    for path, text in edited.items():
        if text != original[path]:
            path.write_text(text)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch-pdf-time-csr.py TINYEMU_DIR")
    patch(Path(sys.argv[1]))
