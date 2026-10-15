#!/usr/bin/env python3
"""Summary is presentation, not permission to manufacture healthy status."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana/ui"))
from health_summary import format_snapshot, size_text

for value in (None, True, "1024", -1, float("nan"), float("inf"), 10**500):
    assert size_text(value) == "Not reported", value
assert size_text(0) == "0 B" and size_text(3 * 1024**3) == "3.0 GiB"
for value in ("", "not json", "[]", "null", '{"kernel":"x"}', '{"kernel":"","services":{},"memory_bytes":{}}'):
    assert format_snapshot(value) is None, value
report = dict(kernel="test", architecture="x86_64", mode="fixture", memory_bytes={},
    services=dict(audio=dict(state="not-ready", probe="no playback")),
    zram=[None, dict(device="zram0", logical_capacity=4*1024**3, original_data=300*1024**2,
                     compressed_data=100*1024**2, physical_consumption=110*1024**2)],
    reboot_required=True, audio_playback_tested=False, hardware_functionality_tested=False)
formatted, attention = format_snapshot(json.dumps(report))
assert "Physical consumption: 110.0 MiB" in formatted and "Logical capacity: 4.0 GiB" in formatted
assert "not extra physical RAM" in formatted and "Hardware functionality tested: No" in formatted
assert {"Memory information incomplete", "Restart required", "audio: not-ready"} <= set(attention)
report["services"] = {}
assert "No service checks reported" in format_snapshot(json.dumps(report))[1]
report.update(services=dict(audio=dict(state="ready", probe="no playback")), reboot_required=False,
              memory_bytes=dict(MemTotal=8*1024**3, MemAvailable=3*1024**3, SwapTotal=0, SwapFree=0))
assert not format_snapshot(json.dumps(report))[1]
print("HEALTH_SUMMARY_OK malformed values; honest attention; physical zram; no hardware claim")
