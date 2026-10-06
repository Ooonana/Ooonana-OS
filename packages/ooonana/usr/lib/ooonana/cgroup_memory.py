"""Read-only process cgroup limits. Kept identical in both standalone payloads."""
from pathlib import Path, PurePosixPath
import re


def _read(path):
    try:
        return Path(path).read_text()
    except (OSError, UnicodeError):
        return ""


def _absolute(value):
    # Do not follow namespace-relative ".." paths outside visible mounts.
    if not value.startswith("/") or any(part in (".", "..") for part in value.split("/")):
        return None
    return PurePosixPath(value)


def _unescape(value):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def constrain_memory(total, available, membership=Path("/proc/self/cgroup"),
                     mountinfo=Path("/proc/self/mountinfo"), cgroup_root=None):
    """Clamp RAM against current scope and every visible limiting ancestor."""
    total = max(0, total)
    available = min(total, max(0, available))
    members = {}
    for line in _read(membership).splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3:
            continue
        hierarchy, controllers, name = fields
        path = _absolute(name)
        if path is None:
            continue
        if hierarchy == "0" and not controllers:
            members["v2"] = path
        elif "memory" in controllers.split(","):
            members["v1"] = path
    mounts = []
    if cgroup_root is not None:
        # Explicit fixture/legacy mount override; never consult host mounts.
        mounts = [("v2", PurePosixPath("/"), Path(cgroup_root)),
                  ("v1", PurePosixPath("/"), Path(cgroup_root) / "memory")]
    else:
        for line in _read(mountinfo).splitlines():
            before, separator, after = line.partition(" - ")
            left, right = before.split(), after.split()
            if not separator or len(left) < 5 or len(right) < 3:
                continue
            kind = "v2" if right[0] == "cgroup2" else "v1" if (
                right[0] == "cgroup" and "memory" in right[2].split(",")) else None
            root, point = _absolute(_unescape(left[3])), _absolute(_unescape(left[4]))
            if kind and root is not None and point is not None:
                mounts.append((kind, root, Path(str(point))))
    seen = set()
    for kind, root, point in mounts:
        member = members.get(kind)
        if members and member is None:
            continue
        directories = [point]
        if member is not None:
            try:
                relative = member.relative_to(root)
            except ValueError:
                continue  # Unrelated bind mount is not this process's budget.
            current = point.joinpath(*relative.parts)
            while current != point:
                directories.append(current)
                current = current.parent
        for directory in directories:
            key = kind, directory
            if key in seen:
                continue
            seen.add(key)
            limit_name, used_name = (("memory.max", "memory.current") if kind == "v2"
                                     else ("memory.limit_in_bytes", "memory.usage_in_bytes"))
            try:
                limit = int(_read(directory / limit_name).strip())
            except ValueError:
                continue  # "max", missing controller or malformed/unreadable limit.
            if not 0 <= limit < 1 << 60:
                continue  # v1 unlimited sentinel.
            total = min(total, limit)
            try:
                used = int(_read(directory / used_name).strip())
                if used < 0:
                    raise ValueError("negative usage")
            except ValueError:
                available = 0  # Known finite limit; unknown usage cannot prove room.
                continue
            available = min(available, max(0, limit - used))
    return total, min(total, available)
