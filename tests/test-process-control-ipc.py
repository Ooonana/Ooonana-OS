#!/usr/bin/env python3
"""Private proc/IPC fixtures; signals mocked, no host processes targeted."""
import errno
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana"))
import i3_events as ipc
import process_control as control

with tempfile.TemporaryDirectory(prefix="ooonana-process-ipc-") as temporary:
    proc = Path(temporary)
    task = proc / "1234"
    task.mkdir()
    started = 2**40

    def identity(start=started, uid=1000):
        fields = ["S"] + ["0"] * 19
        fields[19] = str(start)
        (task / "stat").write_text("1234 (qa) " + " ".join(fields))
        (task / "status").write_text(f"Name:\tqa\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")

    identity()
    with patch.object(control.os, "getuid", return_value=1000), \
            patch.object(control.os, "getpid", return_value=999), \
            patch.object(control.os, "pidfd_open", return_value=91, create=True) as opened, \
            patch.object(control.os, "close") as closed, \
            patch.object(control.os, "kill") as numeric_signal, \
            patch.object(control.signal, "pidfd_send_signal", create=True) as sent:
        control.terminate_owned_process(1234, started, 1000, proc)
        opened.assert_called_once_with(1234, 0)
        sent.assert_called_once_with(91, control.signal.SIGTERM, None, 0)
        closed.assert_called_once_with(91)
        for start, uid in ((started + 1, 1000), (started, 1001)):
            identity(start, uid)
            sent.reset_mock()
            closed.reset_mock()
            try:
                control.terminate_owned_process(1234, started, 1000, proc)
            except control.ProcessChanged:
                pass
            else:
                raise AssertionError("changed identity signaled")
            sent.assert_not_called()
            closed.assert_called_once_with(91)
        identity()
        for pid, owner in ((1, 1000), (999, 1000), (1234, 1001), (True, 1000)):
            opened.reset_mock()
            try:
                control.terminate_owned_process(pid, started, owner, proc)
            except PermissionError:
                pass
            else:
                raise AssertionError("unsafe task accepted")
            opened.assert_not_called()
        with patch.object(control.os, "getuid", return_value=0):
            try:
                control.terminate_owned_process(1234, started, 0, proc)
            except PermissionError:
                pass
            else:
                raise AssertionError("root task termination accepted")
        # Exit/reuse after identity check: only bound handle is signaled.
        sent.side_effect = ProcessLookupError(errno.ESRCH, "fixture exited")
        closed.reset_mock()
        try:
            control.terminate_owned_process(1234, started, 1000, proc)
        except control.ProcessChanged:
            pass
        else:
            raise AssertionError("exited descriptor reported success")
        closed.assert_called_once_with(91)
        numeric_signal.assert_not_called()
    quick_kill = (root / "packages/ooonana/usr/bin/ooonana-process-kill").read_text()
    assert "task_manager_app.py" in quick_kill and "kill -" not in quick_kill and "rofi" not in quick_kill

def frame(kind, value):
    data = json.dumps(value).encode()
    return ipc.HEADER.pack(ipc.MAGIC, len(data), kind) + data

def receive(data):
    left, right = socket.socketpair()
    try:
        right.sendall(data)
        right.shutdown(socket.SHUT_WR)
        return ipc.receive(left)
    finally:
        left.close()
        right.close()

assert receive(frame(4, {"nodes": []})) == (4, {"nodes": []})
with patch.object(ipc.json, "loads", side_effect=RecursionError("fixture nesting")):
    try:
        receive(frame(4, {}))
    except ValueError:
        pass
    else:
        raise AssertionError("parser recursion killed watcher instead of recoverable error")
for data in (b"short", ipc.HEADER.pack(b"broken", 0, 4),
             ipc.HEADER.pack(ipc.MAGIC, ipc.MAX_MESSAGE + 1, 4)):
    try:
        receive(data)
    except (ValueError, EOFError):
        pass
    else:
        raise AssertionError("invalid frame accepted")
with patch.object(ipc.socket, "socket") as constructor, patch.object(ipc, "send"):
    for kind, payload in ((4, []), (4, None), (1, {}), (1, [None])):
        with patch.object(ipc, "receive", return_value=(kind, payload)):
            try:
                ipc.request("fixture", kind)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid response schema accepted")
    with patch.object(ipc, "socket_path", return_value="fixture"), \
            patch.object(ipc, "receive", return_value=(2, [])):
        try:
            next(ipc.trees())
        except ValueError:
            pass
        else:
            raise AssertionError("invalid subscription schema accepted")
print("ok identity-bound termination, long-uptime stat, fail-closed quick-kill, recoverable IPC failures")
