#!/usr/bin/env python3
"""Real signed fixture transactions through GTK/PAM; isolated target root only."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
from packages_app import PackagesWindow
from health_app import HealthWindow

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert os.environ.get("OOONANA_GUI_TEST_ADMIN_POLICY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode
# Match a normal desktop login; QA signing's restrictive key mask is unrelated.
os.umask(0o022)
output = Path(sys.argv[1])
assert output == Path("/qa/package-transactions")
output.mkdir()
repo, target, state, cache, sources = (output / name for name in ("repo", "root", "state", "cache", "sources"))
(repo / "hooks").mkdir(parents=True); sources.mkdir()
key = output / "qa-only.key"
subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
key.chmod(0o600)
os.environ.update({name: str(value) for name, value in dict(
    OOONANA_ROOT=target, OOONANA_REPO_DIR=repo, OOONANA_STATE_DIR=state, OOONANA_CACHE_DIR=cache,
    OOONANA_SOURCES_DIR=sources, OOONANA_REPO_VERIFY_KEY=repo / "repo.pub",
    OOONANA_REQUIRE_SIGNED_REPOS="1", OOONANA_KEEP_UPDATE_BACKUPS="all").items()})
assert subprocess.run(["sudo", "-n", "/usr/bin/ooonana", "get", "qa-ui-fixture"], capture_output=True).returncode


def package(version, health="ok"):
    archive = repo / ("fixture-" + version + ".tar.gz")
    with tarfile.open(archive, "w:gz") as bundle:
        for name in ("./", "etc/", "usr/", "usr/share/", "usr/share/qa-ui/"):
            directory = tarfile.TarInfo(name)
            directory.type, directory.mode = tarfile.DIRTYPE, 0o755
            bundle.addfile(directory)
        for name, value in (("etc/qa-ui.conf", "default=" + version), ("usr/share/qa-ui/version", version)):
            item = tarfile.TarInfo(name)
            data = value.encode()
            item.size, item.mode = len(data), 0o640 if name.startswith("etc/") else 0o644
            # This private sample config is user-owned so the test can make a
            # real local edit without adding any arbitrary sudo command.
            item.uid = item.gid = 1000 if name.startswith("etc/") else 0
            bundle.addfile(item, io.BytesIO(data))
    fields = dict(ID="qa-ui-fixture", VERSION=version, KIND="archive", SUMMARY="Private signed GUI fixture",
                  ARCHIVE=archive.name, SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), DEPS="")
    (repo / "qa-ui-fixture.pkg").write_text("".join(f'OOONANA_PKG_{name}="{value}"\n' for name, value in fields.items()))
    hook = repo / "hooks/qa-ui-fixture.healthcheck"
    action = "exit 0" if health == "ok" else "exit 7" if health == "fail" else 'kill -KILL "$PPID"\nexit 0'
    if version == "1":
        action = 'mkdir -p "$OOONANA_ROOT/etc/ooonana/packages/qa-ui-fixture"\nprintf retained=yes > "$OOONANA_ROOT/etc/ooonana/packages/qa-ui-fixture/local.conf"\n' + action
    hook.write_text('#!/bin/sh\nset -eu\n[ "$OOONANA_ROOT" = /qa/package-transactions/root ] || exit 88\n' + action + "\n")
    hook.chmod(0o755)
    subprocess.run(["python3", "-B", str(ROOT / "scripts/index-repo-fast.py"), "--repo", str(repo), "--sign-key", str(key)], check=True)


def settle():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    time.sleep(.01)


def text(window):
    buffer = window.output.get_buffer()
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)


def capture(name):
    for _ in range(12):
        settle()
    screen = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(output / (name + ".png")), "png", [], [])


def operate(window, name, action, *, fail=False, cancel_review=False, expect_review=False, cancel_confirm=False):
    deadline = time.monotonic() + 35
    prompts, reviews, errors = set(), [], []

    def interact():
        try:
            found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^Authorize( administration)?$"], capture_output=True, text=True)
            for identifier in found.stdout.splitlines() if found.returncode == 0 else []:
                # X11 may reuse an XID between preview and execution prompts.
                owner = subprocess.run(["xdotool", "getwindowpid", identifier], capture_output=True, text=True)
                if owner.returncode or not owner.stdout.strip():
                    continue  # Previous prompt can close between search/read.
                pid = owner.stdout.strip()
                identity = (identifier, pid)
                if identity not in prompts:
                    focused = subprocess.run(["xdotool", "windowfocus", identifier], capture_output=True)
                    if focused.returncode:
                        continue
                    subprocess.run(["xdotool", "type", "--clearmodifiers", "--file", "-"],
                                   input="Ooonana-private-admin-QA-20261026", text=True, check=True)
                    subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True)
                    prompts.add(identity)
            for dialog in Gtk.Window.list_toplevels():
                if not isinstance(dialog, Gtk.Dialog) or not dialog.get_visible():
                    continue
                assert dialog.get_transient_for() is window, name + ": unrelated dialog"
                if dialog.get_title() == "Review package changes":
                    assert dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
                    reviews.append(dialog)
                    dialog.response(Gtk.ResponseType.CANCEL if cancel_review else Gtk.ResponseType.OK)
                elif isinstance(dialog, Gtk.MessageDialog) or dialog.get_title() in (
                        "Recover interrupted package update?", "Refresh repository metadata?"):
                    menu = getattr(window, "more_button", None) or next(
                        item for item in window.action_buttons if isinstance(item, Gtk.MenuButton))
                    if menu.get_popover().get_visible():
                        # Native popdown can finish its short transition after
                        # the modal maps. Require it to finish before acting.
                        assert time.monotonic() < deadline, "Menu still overlays modal confirmation"
                        return True
                    assert dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
                    dialog.response(Gtk.ResponseType.CANCEL if cancel_confirm else Gtk.ResponseType.OK)
        except Exception as exc:
            errors.append(repr(exc))
            for dialog in Gtk.Window.list_toplevels():
                if isinstance(dialog, Gtk.Dialog) and dialog.get_visible():
                    dialog.response(Gtk.ResponseType.CANCEL)
            return False
        return time.monotonic() < deadline

    watcher = GLib.timeout_add(60, interact)
    try:
        action()
        while (getattr(window, "busy", False) or getattr(window, "pending", False) or getattr(window, "review_open", False)) and time.monotonic() < deadline:
            settle()
        assert not errors, errors
        assert time.monotonic() < deadline, name + ": operation stalled"
        assert prompts or cancel_confirm, name + ": real password prompt missing"
        assert not cancel_confirm or not prompts, name + ": cancelled confirmation requested privilege"
        assert bool(reviews) == expect_review, name + ": review mismatch"
        assert ("failed" in window.status.get_text().lower()) == fail, (name, window.status.get_text())
        capture(name)
        print("PACKAGE_TRANSACTION_PASS", name, flush=True)
    finally:
        if GLib.MainContext.default().find_source_by_id(watcher):
            GLib.source_remove(watcher)


config = output / "i3.conf"
config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
window = health = None


def menu_action(menu, name):
    menu.set_active(True)
    settle()
    control = next(item for item in menu.get_popover().get_child().get_children() if item.get_label() == name)
    control.clicked()


try:
    deadline = time.monotonic() + 8
    while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
        assert time.monotonic() < deadline
        time.sleep(.03)
    Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
    apply_theme()
    package("1")
    window = PackagesWindow(); window.show_all()
    operate(window, "metadata", window.update_repos)
    install = lambda: window.preview("Installing private fixture", ["ooonana", "get", "qa-ui-fixture"], "Install", 30)
    operate(window, "cancel-install-review", install, cancel_review=True, expect_review=True)
    version = target / "usr/share/qa-ui/version"
    assert not version.exists(), "Cancelled review installed payload"
    operate(window, "install", install, expect_review=True)
    assert version.read_text() == "1" and version.stat().st_uid == 0
    custom = target / "etc/qa-ui.conf"
    custom.write_text("custom=yes"); custom.chmod(0o640)
    upgrade = lambda: window.preview("Upgrading private fixture", ["ooonana", "upgrade", "qa-ui-fixture"], "Upgrade", 30)
    package("2")
    operate(window, "upgrade", upgrade, expect_review=True)
    assert version.read_text() == "2" and custom.read_text() == "custom=yes"
    assert custom.with_suffix(".conf.ooonana-new").read_text() == "default=2"
    previous = (state / "installed/qa-ui-fixture.pkg").read_bytes()
    package("3", "fail")
    operate(window, "health-failure-rollback", upgrade, fail=True, expect_review=True)
    assert version.read_text() == "2" and custom.read_text() == "custom=yes"
    assert (state / "installed/qa-ui-fixture.pkg").read_bytes() == previous
    package("3", "interrupt")
    operate(window, "interrupted-upgrade", upgrade, fail=True, expect_review=True)
    assert version.read_text() == "3" and list(state.glob(".replace-*")), "SIGKILL journal not retained"
    tools = next(item for item in window.action_buttons if isinstance(item, Gtk.MenuButton))
    recovery = lambda: menu_action(tools, "Recover interrupted update")
    operate(window, "cancel-recovery", recovery, cancel_confirm=True)
    assert version.read_text() == "3" and list(state.glob(".replace-*"))
    operate(window, "recovery", recovery)
    assert version.read_text() == "2" and not list(state.glob(".replace-*"))
    assert custom.read_text() == "custom=yes" and custom.stat().st_mode & 0o777 == 0o640
    assert (state / "installed/qa-ui-fixture.pkg").read_bytes() == previous
    package("3")
    operate(window, "upgrade-retry", upgrade, expect_review=True)
    assert version.read_text() == "3"
    window.destroy(); window = None
    health = HealthWindow(updates=True); health.show_all()
    deadline = time.monotonic() + 15
    while health.pending and time.monotonic() < deadline:
        settle()
    assert not health.pending and "complete" in health.status.get_text().lower(), health.raw_output
    operate(health, "health-refresh", lambda: menu_action(health.more_button, "Refresh repository"))
    health.check(False)
    deadline = time.monotonic() + 25
    while health.pending and time.monotonic() < deadline:
        settle()
    assert not health.pending and health.summary_output is not None, health.raw_output
    assert json.loads(health.raw_output)["audio_playback_tested"] is False
    assert health.copy_button.get_sensitive()
    capture("health-snapshot")
    health.destroy(); health = None
    window = PackagesWindow(); window.show_all()
    operate(window, "remove", lambda: window.preview("Removing private fixture",
        ["ooonana", "remove", "qa-ui-fixture"], "Remove", 30), expect_review=True)
    # Remove deletes archive-owned files. Ooonana-managed config directories
    # are retained; deleting those is the separate explicit purge operation.
    assert not version.exists() and not custom.exists()
    assert (target / "etc/ooonana/packages/qa-ui-fixture/local.conf").read_text() == "retained=yes"
    assert not (state / "installed/qa-ui-fixture.pkg").exists()
    print("PACKAGE_TRANSACTIONS_UI_OK real GTK review/PAM/signed install/remove, config preservation, rollback, SIGKILL/recover, retry, Health refresh/snapshot", flush=True)
finally:
    for item in (window, health):
        if item is not None:
            item.destroy()
    wm.terminate(); wm.wait(timeout=5)
