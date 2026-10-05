#!/usr/bin/env python3
"""Optional bounded CPU diagnostics for native-PDF compatibility debugging."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
cpu = root / "riscv_cpu.c"
text = cpu.read_text()
if "OOONANA_VM_DEBUG" not in text:
    definitions = '''
#ifdef EMSCRIPTEN
/* OOONANA_VM_DEBUG: diagnostic snapshots only, no host state exposed. */
uint32_t oo_vm_pc_low, oo_vm_pc_high, oo_vm_priv, oo_vm_cause;
#endif
'''
    needle = 'static void glue(riscv_cpu_interp, MAX_XLEN)(RISCVCPUState *s, int n_cycles)'
    text = text.replace(needle, definitions + '\n' + needle)
    needle = '    timeout = s->insn_counter + n_cycles;'
    text = text.replace(needle, '''#ifdef EMSCRIPTEN
    oo_vm_pc_low = (uint32_t)s->pc;
    oo_vm_pc_high = (uint32_t)((uint64_t)s->pc >> 32);
    oo_vm_priv = s->priv;
    oo_vm_cause = s->mcause;
#endif
''' + needle, 1)
    cpu.write_text(text)
text = cpu.read_text()
if "OOONANA_VM_RETURN_ADDRESS" not in text:
    text = text.replace("uint32_t oo_vm_pc_low, oo_vm_pc_high, oo_vm_priv, oo_vm_cause;",
                        "uint32_t oo_vm_pc_low, oo_vm_pc_high, oo_vm_priv, oo_vm_cause;\n"
                        "uint32_t oo_vm_ra_low, oo_vm_ra_high; /* OOONANA_VM_RETURN_ADDRESS */")
    text = text.replace("    oo_vm_cause = s->mcause;",
                        "    oo_vm_cause = s->mcause;\n"
                        "    oo_vm_ra_low = (uint32_t)s->reg[1];\n"
                        "    oo_vm_ra_high = (uint32_t)((uint64_t)s->reg[1] >> 32);")
    cpu.write_text(text)
js = root / "jsemu.c"
text = js.read_text()
if "OOONANA_VM_DEBUG" not in text:
    text += '''
/* OOONANA_VM_DEBUG */
extern uint32_t oo_vm_pc_low, oo_vm_pc_high, oo_vm_priv, oo_vm_cause;
int oo_vm_debug(int field) {
    switch(field) {
    case 0: return oo_vm_pc_low;
    case 1: return oo_vm_pc_high;
    case 2: return oo_vm_priv;
    default: return oo_vm_cause;
    }
}
'''
    js.write_text(text)
text = js.read_text()
if "OOONANA_VM_RETURN_ADDRESS" not in text:
    text = text.replace("int oo_vm_debug(int field) {",
                        "extern uint32_t oo_vm_ra_low, oo_vm_ra_high; /* OOONANA_VM_RETURN_ADDRESS */\n"
                        "int oo_vm_debug(int field) {")
    text = text.replace("    default: return oo_vm_cause;",
                        "    case 3: return oo_vm_cause;\n"
                        "    case 4: return oo_vm_ra_low;\n"
                        "    case 5: return oo_vm_ra_high;\n"
                        "    default: return 0;")
    js.write_text(text)
makefile = root / "Makefile.pdfjs"
text = makefile.read_text()
if "_oo_vm_debug" not in text:
    text = text.replace("'_virt_machine_run']", "'_virt_machine_run','_oo_vm_debug']")
    makefile.write_text(text)
