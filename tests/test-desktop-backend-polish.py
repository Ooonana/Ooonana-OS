#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
assert "packages/ooonana/etc/environment text eol=lf" in (root / ".gitattributes").read_text()
assert b"\r" not in (root / "packages/ooonana/etc/environment").read_bytes(), "PAM retains CR in Python UTF8 setting"
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana"))
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from service_status import check_services
from memory_status import available_ram, memory_caption

calls = []
def probe(command):
    calls.append(command)
    if command[0] == "pactl":
        return 0, "Server Name: PipeWire"
    if command[-1] == "org.freedesktop.DBus.Peer.Ping":
        return 0, "method return"
    if "org.bluez" in command[-1]:
        return 1, ""
    return (0, 'string ":1.42"') if command[-2] == "org.freedesktop.DBus.GetNameOwner" else (0, "boolean true")
state = check_services(probe, lambda _: True, lambda: True)
assert state["dbus"]["state"] == state["network"]["state"] == state["audio"]["state"] == "ready"
assert state["bluetooth"]["state"] == "not-ready"
assert all("play" not in part for command in calls for part in command)
assert check_services(probe, lambda _: False, lambda: False)["network"]["state"] == "waiting-for-dbus"

loader = importlib.util.spec_from_file_location("manifest", root / "scripts/record-release-manifest.py")
manifest = importlib.util.module_from_spec(loader)
loader.loader.exec_module(manifest)
with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    source = work / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts/example.py").write_text("print(1)\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
    original = manifest.source_state(source)
    (source / "public").mkdir()
    (source / "public/large.pkg").write_text("Build output")
    (source / "scripts/__pycache__").mkdir()
    (source / "scripts/__pycache__/example.pyc").write_bytes(b"Bytecode")
    assert manifest.source_state(source) == original
    (source / "scripts/example.py").write_text("print(2)\n")
    changed = manifest.source_state(source)
    assert changed[0] != original[0] and changed[2]
    proc = work / "meminfo"
    proc.write_text("MemTotal: 8388608 kB\nMemAvailable: 4194304 kB\nSwapTotal: 67108864 kB\n")
    cgroup = work / "cgroup"
    cgroup.mkdir()
    (cgroup / "memory.max").write_text(str(2 * 1024**3))
    (cgroup / "memory.current").write_text(str(1536 * 1024**2))
    info = available_ram(proc, cgroup)
    assert info["available"] == 512 * 1024**2 and info["total"] == 2 * 1024**3
    assert "RAM available" in memory_caption(info) and "swap" not in memory_caption(info).lower()
    cli = (root / "packages/ooonana/usr/bin/ooonana").read_text()
    selector = re.search(r"^select_best_index_entries\(\) \{\n.*?^\}", cli, re.M | re.S)[0]
    input_file, output_file = work / "index", work / "chosen"
    rows = ["first\tfixture\t1.0\tbundle\tFirst", "second\tfixture\t1.0\tbundle\tSecond",
            "old\trelease\t1.9\tbundle\tOld", "new\trelease\t1.10\tbundle\tNew"]
    rows += [f"repo\tp{index:05d}\t1.0\tbundle\tFixture" for index in range(10000)]
    input_file.write_text("\n".join(rows) + "\n")
    started = time.monotonic()
    subprocess.run(["sh", "-eu", "-c", selector + '\nselect_best_index_entries "$1" "$2"', "test", str(input_file), str(output_file)], check=True, timeout=20)
    result = output_file.read_text().splitlines()
    assert len(result) == 10002 and rows[0] in result and rows[1] not in result and rows[3] in result
    print(f"INDEX_MERGE_OK 10004 rows -> 10002 packages ({time.monotonic() - started:.3f}s)")
print("ok source-only manifest, endpoint readiness, cgroup-aware RAM")
