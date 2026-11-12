#!/usr/bin/env python3
"""BusyBox/POSIX console feedback, with no host console/storage interaction."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "packages/ooonana/usr/lib/ooonana/console-ui.sh").read_text()
assert "trap " not in source and " &\n" not in source
assert "mount " not in source and "kill " not in source
assert "\\033[?25" not in source  # Never leave the user's cursor hidden.

with tempfile.TemporaryDirectory(prefix="ooonana-console-test-") as temporary:
    work = Path(temporary)
    device = work / "console"
    device.touch()
    logo = ROOT / "packages/ooonana/usr/share/ooonana/boot-logo.txt"
    # Only private output file. Stubs prohibit touching a host VT or waiting.
    fixture = source.replace("ooonana_ui_device=/dev/tty1", f"ooonana_ui_device='{device}'")
    fixture = fixture.replace('[ -c "$ooonana_ui_device" ]', '[ -f "$ooonana_ui_device" ]')
    helper = work / "helper.sh"
    helper.write_text(fixture)
    shell_cases = [["sh"]]
    if shutil.which("busybox"):
        shell_cases.append(["busybox", "sh"])
    for shell in shell_cases:
        for mode, cmdline, geometry, animated in (
            ("on", "ooonana.live=1", "25 80", True),
            ("off", "ooonana.live=1", "25 80", False),
            ("on", "ooonana.motion=off", "25 80", False),
            ("on", "console=ttyS0,115200 ooonana.live=1", "25 80", False),
            ("on", "console=ttyS0,115200 console=tty0", "25 80", True),
            ("on", "console=tty0 console=ttyS0,115200", "25 80", False),
            ("on", "console=ttyS0 console=ttyS1 console=tty0", "25 80", False),
            ("on", "console=tty0 console=tty1", "25 80", False),
            ("on", "console=ttyUSB0", "25 80", False),
            ("on", "console=", "25 80", False),
            ("on", "ooonana.live=1 console=hvc0", "25 80", False),
            ("on", "console=ttyAMA0", "25 80", False),
            ("on", "ooonana.live=1", "0 0", False),
            ("on", "ooonana.live=1", "19 59", False),
            ("on", "ooonana.live=1", "broken", False),
        ):
            environment = dict(os.environ, OOONANA_CONSOLE_MOTION=mode,
                               FIXTURE_CMDLINE=cmdline, FIXTURE_GEOMETRY=geometry)
            script = f"""set -eu
. '{helper}'
cat() {{ printf '%s\\n' "$FIXTURE_CMDLINE"; }}
stty() {{ printf '%s\\n' "$FIXTURE_GEOMETRY"; }}
sleep() {{ printf 'WAIT:%s\\n' "$1"; }}
ooonana_console_begin '{logo}'
printf 'ANIMATED:%s\\n' "$ooonana_ui_animated"
ooonana_console_stage 'Finding boot media'
ooonana_console_wait 2
ooonana_console_end
printf 'ENDED:%s\\n' "$ooonana_ui_animated"
"""
            result = subprocess.run([*shell, "-c", script], text=True, capture_output=True,
                                    env=environment, timeout=5, check=True)
            assert f"ANIMATED:{int(animated)}" in result.stdout, result
            assert result.stdout.count("WAIT:1") == 2, result
            assert "ENDED:0" in result.stdout
            if not animated:
                assert "Ooonana: Finding boot media" in result.stdout
                assert "\x1b" not in result.stdout
        # Consecutive frames replace only status rows, never clear warnings.
        script = f"""set -eu
. '{helper}'
ooonana_ui_device='{device}'
ooonana_ui_animated=1; ooonana_ui_frame=0; ooonana_ui_cols=80
ooonana_ui_row=16; ooonana_ui_label='Saving changes'
ooonana_console_frame
"""
        frames = []
        for frame in range(3):
            subprocess.run([*shell, "-c", script.replace("ooonana_ui_frame=0", f"ooonana_ui_frame={frame}")],
                           check=True, timeout=5)
            frames.append(device.read_text())
        assert len(set(frames)) == 3
        assert all("\x1b[2J" not in frame and "Saving changes" in frame for frame in frames)
        assert all(frame.startswith("\x1b7") and frame.endswith("\x1b8") for frame in frames), \
            "Status redraw must restore diagnostic cursor, not rewind warning output"

    # A disappearing /dev must never turn drawing into regular-file writes.
    strict = work / "strict-helper.sh"
    strict.write_text(source.replace("ooonana_ui_device=/dev/tty1", f"ooonana_ui_device='{device}'"))
    for exists in (True, False):
        if exists:
            device.write_text("untouched")
        else:
            device.unlink()
        subprocess.run(["sh", "-c", f"""set -eu
. '{strict}'
ooonana_ui_device='{device}'
ooonana_ui_animated=1
ooonana_console_frame
ooonana_console_end
"""], check=True, timeout=5)
        assert device.exists() == exists
        if exists:
            assert device.read_text() == "untouched"

init = (ROOT / "scripts/build-full-i3-live-initramfs.sh").read_text()
assert init.index("ooonana_console_end\nmount --move /proc") < init.index("exec switch_root")
assert 'cp /lib/ooonana-console-ui.sh "$shutdown_root/console-ui.sh"' in init
shutdown = (ROOT / "scripts/lib/live-shutdown.sh").read_text()
assert shutdown.index('[ "${1:-}" = --from-init ]') < shutdown.index("ooonana_console_begin")
assert shutdown.index("kill -TERM -1") < shutdown.index("ooonana_console_wait 2") < shutdown.index("kill -KILL -1")
assert "umount /oldroot" in shutdown and "trap 'shutdown_failed" in shutdown
normal_shutdown = (ROOT / "packages/ooonana/usr/bin/ooonana-shutdown-cleanup").read_text()
assert normal_shutdown.index("&& ooonana_console_end") < normal_shutdown.index("umount -a -r")
print("CONSOLE_UI_OK POSIX/BusyBox; motion-off/serial/small-console; exact waits; no worker/trap; guarded RAM shutdown")
