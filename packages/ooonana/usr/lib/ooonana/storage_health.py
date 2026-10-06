"""Read-only live storage health. No mounts, repairs, swaps or disk selection."""
import os
from pathlib import Path

MIB = 1024 ** 2


def storage_health(metadata=Path("/mnt/ooonana-live"), filesystem=Path("/"), statvfs=os.statvfs):
    try:
        with (metadata / "persistence-mode").open("r", encoding="utf-8") as stream:
            text = stream.read(65)
        if len(text) > 64:
            raise ValueError("live storage mode exceeds limit")
        mode = text.strip()
    except FileNotFoundError:
        return {"mode": "installed", "level": "none", "caption": "Installed storage"}
    except (OSError, ValueError):
        return {"mode": "unknown", "level": "critical", "caption": "Live storage state unreadable; save work elsewhere"}
    if mode not in ("ram", "usb", "usb-temporary"):
        return {"mode": mode, "level": "critical", "caption": "Live storage state invalid"}
    try:
        stats = statvfs(filesystem)
        free = stats.f_bavail * stats.f_frsize
        total = stats.f_blocks * stats.f_frsize
        inode_low = stats.f_files > 0 and stats.f_favail < max(64, stats.f_files // 100)
        readonly = bool(stats.f_flag & os.ST_RDONLY)
        level = "critical" if readonly or free < 64 * MIB or (stats.f_files > 0 and stats.f_favail < 16) else "low" if free < max(512 * MIB, total // 20) or inode_low else "ok"
        name = {"ram": "Temporary RAM", "usb": "Persistent USB", "usb-temporary": "Temporary USB"}[mode]
        caption = f"{name} · {free / 1024**3:.1f} GiB free"
        if readonly:
            caption += " · read-only"
        elif level != "ok":
            caption += " · " + ("critically low space" if level == "critical" else "low space")
        return {"mode": mode, "level": level, "caption": caption, "free": free,
                "readonly": readonly, "inode_low": inode_low}
    except OSError:
        return {"mode": mode, "level": "critical", "caption": "Live storage unavailable; save work elsewhere"}
