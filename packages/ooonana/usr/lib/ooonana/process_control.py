"""Identity-bound process termination. No numeric-PID signal fallback."""
import os
from pathlib import Path
import signal


class ProcessChanged(ValueError):
    pass


def parse_process_stat(text):
    end = text.rfind(")")
    if end < 0:
        return None
    fields = text[end + 1:].split()
    if len(fields) < 20:
        return None
    try:
        ticks, starttime = int(fields[11]) + int(fields[12]), int(fields[19])
        return (fields[0], ticks, starttime) if ticks >= 0 and starttime >= 0 else None
    except ValueError:
        return None


def terminate_owned_process(pid, starttime, owner, proc=Path("/proc")):
    uid = os.getuid()
    if (any(type(value) is not int for value in (pid, starttime, owner)) or
            uid == 0 or owner != uid or pid <= 1 or pid == os.getpid() or starttime < 0):
        raise PermissionError("Only your own tasks can be stopped")
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("Identity-safe termination unavailable on this runtime")
    try:
        descriptor = os.pidfd_open(pid, 0)
    except ProcessLookupError as error:
        raise ProcessChanged("Process exited or PID was reused") from error
    try:
        try:
            with (proc / str(pid) / "stat").open(encoding="utf-8", errors="replace") as stream:
                current = parse_process_stat(stream.read(65536))
            with (proc / str(pid) / "status").open(encoding="utf-8", errors="replace") as stream:
                status = stream.read(65536)
            current_owner = next((line.split()[1] for line in status.splitlines()
                                  if line.startswith("Uid:")), "")
        except (OSError, IndexError, ValueError) as error:
            raise ProcessChanged("Process identity unreadable") from error
        if current is None or current[2] != starttime or current_owner != str(owner):
            raise ProcessChanged("Process exited or PID was reused")
        try:
            # Descriptor remains bound to original process across exit/PID reuse.
            signal.pidfd_send_signal(descriptor, signal.SIGTERM, None, 0)
        except ProcessLookupError as error:
            raise ProcessChanged("Process exited before termination") from error
    finally:
        os.close(descriptor)
