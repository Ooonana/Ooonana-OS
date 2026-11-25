"""Read-only storage inventory and the existing installer's review protocol."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat
import subprocess

from common import admin_command, run


INSTALLER = "/usr/sbin/ooonana-install"
TOKEN_PREFIX = "OOONANA_INSTALL_TARGET_TOKEN="


@dataclass(frozen=True)
class Device:
    path: str
    model: str
    size: int
    kind: str
    disk: str
    identity: tuple
    unavailable: str = ""

    @property
    def capacity(self):
        unit, divisor = ("GB", 10**9) if self.size >= 10**9 else ("MB", 10**6)
        return f"{self.size / divisor:.1f}".removesuffix(".0") + f" {unit}"


def device_tree(node):
    yield node
    for child in node.get("children", []):
        yield from device_tree(child)


def storage_inventory():
    rc, output = run(["lsblk", "--json", "--bytes", "--tree", "-o",
                      "NAME,KNAME,PATH,TYPE,SIZE,MODEL,RO,MAJ:MIN,START,PARTUUID,MOUNTPOINTS"],
                     timeout=8, utf8=True)
    if rc:
        raise ValueError("Could not read the drive list.")
    marker = Path("/mnt/ooonana-live/boot-device")
    try:
        boot_device = str(Path(marker.read_text(encoding="utf-8").strip()).resolve())
    except OSError:
        boot_device = ""
    devices = {}
    for disk in json.loads(output)["blockdevices"]:
        if disk["type"] != "disk" or not (disk.get("path") or "").startswith("/dev/"):
            continue
        children = list(device_tree(disk))
        system_disk = any("/" in (child.get("mountpoints") or []) for child in children)
        boot_disk = any(child["path"] and (str(Path(child["path"]).resolve()) == boot_device
                        or "/mnt/ooonana-live/iso" in (child.get("mountpoints") or [])) for child in children)
        reason = "Protected system disk" if system_disk else "Boot media is protected" if boot_disk else ""
        try:
            seq = (Path("/sys/class/block") / Path(disk["kname"]).name / "diskseq").read_text().strip()
        except OSError:
            seq = ""
        for node in children:
            if node["type"] not in ("disk", "part") or not (node.get("path") or "").startswith("/dev/"):
                continue
            mounted = any(any(child.get("mountpoints") or []) for child in device_tree(node))
            unavailable = reason
            if not unavailable:
                unavailable = "Read-only" if node["ro"] else "Mounted" if mounted else ""
            identity = tuple(node.get(key) for key in ("kname", "maj:min", "size", "start", "partuuid")) + (seq,)
            devices[node["path"]] = Device(
                node["path"], (node.get("model") or "").strip() or ("Disk" if node["type"] == "disk" else "Partition"),
                int(node["size"]), node["type"], disk["path"], identity, unavailable)
    return devices


def image_device(path):
    target = Path(path)
    if not target.is_absolute() or str(target).startswith("/dev/"):
        raise ValueError("Choose an existing disk image by its full path.")
    try:
        info = target.stat()
    except OSError as exc:
        raise ValueError("Could not read the disk image.") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Choose an existing disk image file.")
    identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return Device(path, target.name, info.st_size, "image", path, identity)


def command_for(mode, target, user, hostname, theme, repo, source, swap_size, partitions):
    argv = [INSTALLER, "--target", target, "--target-mode", mode, "--source", source,
            "--hostname", hostname, "--user", user, "--theme", theme, "--password-stdin"]
    if repo:
        argv.extend(("--cloud-repo", repo))
    if mode == "disk":
        argv.extend(("--swap-size-mib", str(swap_size)))
    else:
        argv.extend(("--bootloader", "grub"))
        for role, (path, should_format) in partitions.items():
            if path and role != "root":
                argv.extend((f"--{role}-part", path))
            if path and not should_format:
                argv.append(f"--keep-{role}")
            if role == "efi" and should_format:
                argv.append("--format-efi")
    return argv


class InstallBackend:
    def inventory(self):
        return 0, storage_inventory()

    def preview(self, argv, password, selected):
        def verify_selection():
            inventory = storage_inventory() if any(d.kind != "image" for d in selected) else {}
            for previous in selected:
                current = image_device(previous.path) if previous.kind == "image" else inventory.get(previous.path)
                if current is None or current.identity != previous.identity or current.unavailable:
                    raise ValueError("Selected storage changed. Return to Destination and select it again.")

        verify_selection()
        rc, output = run([*argv, "--dry-run", "--yes"], admin=True, timeout=180, input_text=password + "\n")
        lines = output.splitlines()
        tokens = [line.removeprefix(TOKEN_PREFIX) for line in lines if line.startswith(TOKEN_PREFIX)]
        detail = "\n".join(line for line in lines if not line.startswith(TOKEN_PREFIX))
        if rc:
            return rc, detail
        if len(tokens) != 1 or not re.fullmatch(r"[a-f0-9]{64}", tokens[0]):
            return 1, "Installer could not verify the target."
        verify_selection()
        return 0, (tokens[0], detail)

    def install(self, argv, password, token, log_path):
        command = admin_command([*argv, "--target-token", token, "--yes"])
        with log_path.open("wb") as log:
            result = subprocess.run(command, input=password.encode("utf-8") + b"\n",
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True, check=False)
        return result.returncode, ""
