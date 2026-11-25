#!/usr/bin/env python3
"""Exercise the live and desktop wizard on a private display with inert drives."""

import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

assert os.getuid() != 0 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
import installer_app
from installer_app import Gdk, Gtk, InstallerWindow, apply_theme
from installer_backend import Device, InstallBackend, TOKEN_PREFIX, storage_inventory


TARGET = Device("/dev/fixture-ssd", "Internal SSD", 512_000_000_000, "disk", "/dev/fixture-ssd", (1,))
USB = Device("/dev/fixture-usb", "Boot USB", 32_000_000_000, "disk", "/dev/fixture-usb", (2,), "Boot media is protected")
ROOT_PART = Device("/dev/fixture-ssd1", "Partition", 511_000_000_000, "part", TARGET.path, (3,))
EFI = Device("/dev/fixture-ssd2", "Partition", 512_000_000, "part", TARGET.path, (4,))
TOKEN = "a" * 64


class Fixture:
    def __init__(self, install_result=0):
        self.install_result = install_result
        self.previews = []
        self.installs = []

    def inventory(self):
        return 0, {device.path: device for device in (TARGET, USB, ROOT_PART, EFI)}

    def preview(self, argv, password, devices):
        assert password == " example password "
        assert devices[0] in (TARGET, ROOT_PART)
        assert "--yes" not in argv and "--target-token" not in argv
        self.previews.append(tuple(argv))
        return 0, (TOKEN, f"Target: {devices[0].path}\nFixture installation plan")

    def install(self, argv, password, token, log_path):
        assert password == " example password " and token == TOKEN
        assert tuple(argv) == self.previews[-1]
        self.installs.append(tuple(argv))
        log = "Fixture install failure" if self.install_result else "OOONANA_INSTALL_OK"
        log_path.write_text(log + "\n", encoding="utf-8")
        return self.install_result, ""


def wait_until(predicate):
    limit = time.monotonic() + 5
    while not predicate():
        assert time.monotonic() < limit, "Timed out waiting for installer state"
        drain(.025)


def drain(seconds=.20):
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def capture(window, name):
    if output is None:
        return
    wait_until(lambda: not window.stack.get_transition_running())
    drain(.35)
    native = window.get_window()
    rectangle = native.get_frame_extents()
    root = Gdk.get_default_root_window()
    assert rectangle.width <= root.get_width() and rectangle.height <= root.get_height(), rectangle
    if not window.boot and root.get_width() >= 1000:
        assert rectangle.width <= 900, "Desktop installer did not float"
    screenshot = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
    screenshot.savev(str(output / (name + ".png")), "png", [], [])


def select_target(window):
    wait_until(lambda: not window.pending)
    assert window.selected is None and not window.next.get_sensitive()
    rows = {row.device.path: row for row in window.disks.get_children()}
    assert not rows[USB.path].get_selectable()
    window.disks.select_row(rows[TARGET.path])
    assert window.selected == TARGET and window.next.get_sensitive()


def enter_account(window):
    window.next.clicked()
    assert window.page == 1
    window.next.clicked()
    assert window.page == 1 and "password" in window.status.get_text().lower()
    assert not window.password.get_visibility()
    window.password.set_text(" example password ")
    window.confirm.set_text(" example password ")
    window.next.clicked()
    assert window.page == 2


output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if output is not None:
    output.mkdir(parents=True, exist_ok=True)
assert Gtk.init_check(None)[0]
installer_app.BOOT_MARK = ROOT / "branding/boot-mark.png"
apply_theme()

boot = InstallerWindow(boot=True, backend=Fixture())
select_target(boot)
capture(boot, "boot-installer")
boot.destroy()
drain()

fixture = Fixture()
desktop = InstallerWindow(backend=fixture)
select_target(desktop)
enter_account(desktop)
desktop.swap.set_value(4096)
desktop.next.clicked()
wait_until(lambda: desktop.page == 3)
assert "--swap-size-mib" in fixture.previews[-1] and "4096" in fixture.previews[-1]
assert desktop.prepared == TOKEN and not fixture.installs
assert desktop.review_warning.get_visible() and "erased" in desktop.review_warning_text.get_text()
capture(desktop, "installer-review")
desktop.back.clicked()
assert desktop.page == 2 and desktop.prepared is None and not fixture.installs
desktop.next.clicked()
wait_until(lambda: desktop.page == 3)
desktop.next.clicked()
wait_until(lambda: desktop.page == 4 and not desktop.pending)
assert fixture.installs == [fixture.previews[-1]]
assert not desktop.password.get_text() and "complete" in desktop.result_heading.get_text()
desktop.destroy()
drain()

custom = InstallerWindow(backend=Fixture(install_result=1))
wait_until(lambda: not custom.pending)
custom.custom.set_active(True)
assert not custom.next.get_sensitive()
custom.partitions["root"][0].set_active_id(ROOT_PART.path)
custom.partitions["efi"][0].set_active_id(EFI.path)
assert custom.next.get_sensitive()
enter_account(custom)
custom.next.clicked()
wait_until(lambda: custom.page == 3)
argv = custom.backend.previews[-1]
assert argv[argv.index("--target-mode")+1] == "partition"
assert "--keep-efi" in argv and "--swap-size-mib" not in argv
assert not custom.backend.installs
custom.next.clicked()
wait_until(lambda: custom.page == 4 and not custom.pending)
assert custom.result_heading.get_text() == "Installation failed"
start, end = custom.log_buffer.get_bounds()
assert "Fixture install failure" in custom.log_buffer.get_text(start, end, False)
custom.destroy()

backend = InstallBackend()
with patch("installer_backend.storage_inventory", return_value={TARGET.path: TARGET}), \
     patch("installer_backend.run", return_value=(0, f"{TOKEN_PREFIX}{TOKEN}\nTarget: {TARGET.path}")) as run:
    assert backend.preview(["test"], " example password ", (TARGET,)) == (0, (TOKEN, f"Target: {TARGET.path}"))
    assert run.call_args.args[0] == ["test", "--dry-run", "--yes"]
    assert run.call_args.kwargs["input_text"] == " example password \n"
    run.return_value = 0, "plan missing token"
    assert backend.preview(["test"], "password", (TARGET,))[0] != 0
with patch("installer_backend.storage_inventory", return_value={}), patch("installer_backend.run") as run:
    try:
        backend.preview(["test"], "password", (TARGET,))
    except ValueError:
        run.assert_not_called()
    else:
        raise AssertionError("Missing drive accepted")

def fixture_disk(path, mounts):
    return {"path": path, "type": "disk", "kname": Path(path).name, "size": 512_000_000_000,
            "ro": False, "mountpoints": mounts}


devices = {"blockdevices": [fixture_disk("/dev/fixture-root", ["/"]),
                            fixture_disk(USB.path, ["/mnt/ooonana-live/iso"]),
                            fixture_disk(TARGET.path, [None])]}
with patch("installer_backend.run", return_value=(0, json.dumps(devices))):
    inventory = storage_inventory()
assert inventory[USB.path].unavailable and inventory["/dev/fixture-root"].unavailable
assert not inventory[TARGET.path].unavailable
print("NATIVE_INSTALLER_UI_OK boot, review, token, back, success, failure log and custom partitions")
