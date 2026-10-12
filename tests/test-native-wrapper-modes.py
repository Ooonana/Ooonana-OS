#!/usr/bin/env python3
"""Private writable-source fixtures; no real installers, models or applications."""
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="ooonana-wrapper-modes-") as temporary:
    work = Path(temporary)
    source = work / "source"
    (source / "scripts").mkdir(parents=True)
    installer = work / "fixture.exe"
    installer.write_bytes(b"MZ private fixture; never distributed")
    binaries = work / "binaries"
    binaries.mkdir()
    for name in ("BunanaChat.Linux", "libSkiaSharp.so", "libHarfBuzzSharp.so"):
        (binaries / name).write_bytes(b"ELF private fixture; never executed")
    for package, builder, arguments in (
        ("firefox", "build-firefox-package.sh", []),
        ("wine-compat", "build-wine-compat-package.sh", []),
        ("ooonana-chat-windows", "build-ooonana-chat-windows-package.sh", ["--source", str(installer)]),
        ("bunanachat-linux", "build-bunanachat-linux-package.sh", ["--source-dir", str(binaries)]),
    ):
        payload = source / "packages" / package / "rootfs"
        shutil.copytree(root / "packages" / package / "rootfs", payload)
        for path in [payload, *payload.rglob("*")]:
            if not path.is_symlink():
                path.chmod(0o777)
        script = source / "scripts" / builder
        shutil.copyfile(root / "scripts" / builder, script)
        repo = work / package
        subprocess.run(["bash", str(script), "--out-dir", str(repo), *arguments],
                       check=True, capture_output=True, preexec_fn=lambda: os.umask(0o077))
        for archive in (repo / "archives").glob("*.tar.gz"):
            with tarfile.open(archive) as bundle:
                for item in bundle:
                    path = item.name.removeprefix("./")
                    assert item.uid == item.gid == 0, item.name
                    if item.isdir():
                        assert item.mode == 0o755, (package, item.name, item.mode)
                    elif item.isfile():
                        executable = path.startswith("usr/bin/") or path in {
                            "opt/bunanachat/BunanaChat.Linux", "opt/bunanachat/libSkiaSharp.so",
                            "opt/bunanachat/libHarfBuzzSharp.so"}
                        assert item.mode == (0o755 if executable else 0o644), (package, item.name, item.mode)
print("ok native wrapper modes: 0777 source, umask 077, safe directories/data/executables")
