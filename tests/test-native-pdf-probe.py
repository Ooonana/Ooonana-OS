#!/usr/bin/env python3
"""Prompt readiness, split output, panic/timeout and owned-child cleanup."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temporary:
    fixture = Path(temporary)
    runtime, emulator = fixture / "runtime", fixture / "tree"
    (runtime / "rootfs").mkdir(parents=True)
    (runtime / "kernel-riscv64.bin").write_bytes(b"fixture")
    program = emulator / "tinyemu/temu"
    program.parent.mkdir(parents=True)
    for mode, expected in (("ready", 0), ("panic", 1), ("quiet", 1)):
        program.write_text("""#!/usr/bin/env python3
import os, time
from pathlib import Path
Path(os.environ['PROBE_PID_FILE']).write_text(str(os.getpid()))
mode = os.environ['PROBE_FIXTURE']
if mode == 'ready':
    print('OOONANA_PDF_BOOT_', end='', flush=True)
    time.sleep(.05)
    print('OK\\nooonana# ', end='', flush=True)
elif mode == 'panic':
    print('Kernel panic: fixture', flush=True)
while True: time.sleep(1)
""")
        program.chmod(0o755)
        pid_file = fixture / "pid"
        result = subprocess.run(["bash", str(root / "scripts/probe-native-pdf-kernel.sh"),
                                 str(runtime), str(emulator)],
            env={**os.environ, "OOONANA_PDF_PROBE_TIMEOUT": "1",
                 "PROBE_FIXTURE": mode, "PROBE_PID_FILE": str(pid_file)},
            capture_output=True, text=True, timeout=8)
        assert result.returncode == expected, (mode, result.stdout, result.stderr)
        if mode == "ready":
            assert "guest reached interactive prompt" in result.stdout
        assert not Path(f"/proc/{int(pid_file.read_text())}").exists(), "Probe child survived"
print("ok native-pdf-probe: split prompt, panic/timeout, child cleanup")
