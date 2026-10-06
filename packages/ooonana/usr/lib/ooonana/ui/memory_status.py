"""Available physical/cgroup memory for UI hints; swap is never extra RAM."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cgroup_memory import constrain_memory


def available_ram(proc=Path("/proc/meminfo"), cgroup=None, *,
                  membership=Path("/proc/self/cgroup"), mountinfo=Path("/proc/self/mountinfo")):
    try:
        fields = dict((line.split(":", 1)[0], int(line.split(":", 1)[1].split()[0]) * 1024)
                      for line in proc.read_text().splitlines() if ":" in line)
        total = max(0, fields["MemTotal"])
        available = min(total, max(0, fields["MemAvailable"]))
    except (OSError, KeyError, ValueError):
        return None
    total, available = constrain_memory(total, available, membership, mountinfo, cgroup)
    return {"available": available, "total": total, "low": available < max(512 * 1024**2, total // 10)}


def memory_caption(info):
    if info is None:
        return "RAM unavailable"
    return f"{info['available'] / 1024**3:.1f} GiB RAM available" + (" · low" if info["low"] else "")
