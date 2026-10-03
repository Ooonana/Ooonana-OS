"""Available physical/cgroup memory for UI hints; swap is never extra RAM."""
from pathlib import Path


def available_ram(proc=Path("/proc/meminfo"), cgroup=Path("/sys/fs/cgroup")):
    try:
        fields = dict((line.split(":", 1)[0], int(line.split(":", 1)[1].split()[0]) * 1024)
                      for line in proc.read_text().splitlines() if ":" in line)
        total = max(0, fields["MemTotal"])
        available = min(total, max(0, fields["MemAvailable"]))
    except (OSError, KeyError, ValueError):
        return None
    for limit_name, used_name in (("memory.max", "memory.current"),
                                  ("memory/memory.limit_in_bytes", "memory/memory.usage_in_bytes")):
        try:
            limit = int((cgroup / limit_name).read_text().strip())
            used = int((cgroup / used_name).read_text().strip())
            if 0 <= limit < 1 << 60:
                total = min(total, limit)
                available = min(available, max(0, limit - used))
        except (OSError, ValueError):
            continue
    return {"available": available, "total": total, "low": available < max(512 * 1024**2, total // 10)}


def memory_caption(info):
    if info is None:
        return "RAM unavailable"
    return f"{info['available'] / 1024**3:.1f} GiB RAM available" + (" · low" if info["low"] else "")
