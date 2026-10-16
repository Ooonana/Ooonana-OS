#!/usr/bin/env python3
"""Owned XTerms/native window, real i3 keys/pointer and private compositor."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme, header
from window_controls import Manager, decoration_targets

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
findings = []


def check(condition, detail):
    if not condition:
        findings.append(detail)
        print("WORKSPACE_FINDING: " + detail, flush=True)


def request(kind):
    return json.loads(subprocess.check_output(["i3-msg", "-t", kind], text=True))


def command(text):
    result = json.loads(subprocess.check_output(["i3-msg", text], text=True))
    assert all(item.get("success") for item in result), (text, result)


def settle():
    deadline = time.monotonic() + .15
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def wait(predicate, detail):
    deadline = time.monotonic() + 4
    while not predicate():
        settle()
        assert time.monotonic() < deadline, detail
    settle()


def state():
    result = {}
    def visit(node, workspace=None, parent=None):
        if node.get("type") == "workspace":
            workspace = node["name"]
        if node.get("window"):
            result[node["id"]] = (node, workspace, parent)
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                visit(child, workspace, node)
    visit(request("get_tree"))
    return result


def current():
    return next(item["name"] for item in request("get_workspaces") if item["focused"])


def focus(identifier):
    command(f"[con_id={identifier}] focus")
    wait(lambda: state()[identifier][0]["focused"], "Owned window focus did not settle")


def keys(chord):
    subprocess.run(["xdotool", "key", "--clearmodifiers", chord], check=True)
    settle()


def window_action(identifier, action):
    subprocess.run([sys.executable, str(ROOT / "packages/ooonana/usr/bin/ooonana-window-list"),
                    "--window-action", action, str(identifier)], check=True, stdout=subprocess.DEVNULL)
    settle()


def capture(name):
    settle()
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output / (name + ".png")), "png", [], [])


def targets(manager):
    manager.refresh()
    settle()
    visible = {item["name"] for item in request("get_workspaces") if item["visible"]}
    expected = decoration_targets(request("get_tree"), visible)
    check(set(manager.controls) == set(expected), "Overlay targets disagree with visible clients")
    for identifier, rect in expected.items():
        check(manager.controls[identifier].last_position == rect, "Overlay position lags final client geometry")
    return set(manager.controls)


apply_theme()
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
with tempfile.TemporaryDirectory(prefix="ooonana-workspaces-") as temporary:
    temporary = Path(temporary)
    config = temporary / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
    compositor_config = temporary / "picom.conf"
    policy = builder.split('"$ROOTFS/etc/ooonana/picom.conf" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
    compositor_config.write_text(policy.replace("use-damage = true;", "use-damage = false;").replace("unredir-if-possible = true;", "unredir-if-possible = false;"))
    processes, manager, native = [], None, None
    with (output / "session.log").open("w") as log:
        wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
        processes.append(wm)
        try:
            deadline = time.monotonic() + 8
            while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
                assert time.monotonic() < deadline
                time.sleep(.03)
            compositor = subprocess.Popen(["picom", "--backend", "xrender", "--no-use-damage", "--config", str(compositor_config)], stdout=log, stderr=log)
            processes.append(compositor)
            for title in ("Ooonana QA Term A", "Ooonana QA Term B"):
                processes.append(subprocess.Popen(["xterm", "-title", title, "-geometry", "45x10", "-e", "sleep", "120"], stdout=log, stderr=log))
            wait(lambda: len([node for node, _workspace, _parent in state().values() if node.get("name", "").startswith("Ooonana QA Term")]) == 2, "Owned XTerms missing")
            by_title = {node["name"]: identifier for identifier, (node, _workspace, _parent) in state().items()}
            a, b = by_title["Ooonana QA Term A"], by_title["Ooonana QA Term B"]
            native = Gtk.Window(title="Ooonana QA native workspace")
            native.set_default_size(420, 200)
            header(native, "Workspace fixture")
            native.add(Gtk.Entry(text="Owned keyboard/focus fixture"))
            native.show_all()
            wait(lambda: any(node.get("name") == native.get_title() for node, _, _ in state().values()), "Native fixture missing")
            n = next(identifier for identifier, (node, _, _) in state().items() if node.get("name") == native.get_title())
            manager = Manager()

            # Every number shortcut and move shortcut, with IPC fallback solely
            # to continue baseline diagnostics after a missing binding.
            for number in range(1, 11):
                focus(a)
                key = str(number % 10)
                keys("super+shift+" + key)
                moved = state()[a][1] == str(number)
                check(moved, "Super+Shift+" + key + " does not move to workspace " + str(number))
                if not moved:
                    command(f"[con_id={a}] move container to workspace number {number}")
                keys("super+" + key)
                switched = current() == str(number)
                check(switched, "Super+" + key + " does not select workspace " + str(number))
                if not switched:
                    command(f"workspace number {number}")
                targets(manager)
            command(f"[con_id={a}] move container to workspace number 1")
            command("workspace number 1")
            command(f"[con_id={b}] move container to workspace number 2")
            keys("super+ctrl+Right")
            check(current() == "2", "Next workspace keyboard shortcut missing")
            command("workspace number 2")
            keys("super+ctrl+Left")
            check(current() == "1", "Previous workspace keyboard shortcut missing")
            command(f"[con_id={b}] move container to workspace number 1")
            command("workspace number 1")

            command(f"[con_id={a}] resize set 420 px 220 px, move position 60 px 110 px")
            command(f"[con_id={b}] resize set 420 px 220 px, move position 690 px 110 px")
            command(f"[con_id={n}] move position 400 px 390 px")
            focus(n)
            rect = state()[a][0]["rect"]
            subprocess.run(["xdotool", "mousemove", "--sync", str(rect["x"] + 90), str(rect["y"] + 90)], check=True)
            settle()
            check(state()[n][0]["focused"], "Pointer hover steals native focus")
            targets(manager)
            capture("floating-focus")

            # Real modifier+pointer movement/resizing, not synthetic i3 geometry.
            for identifier in (a, n):
                focus(identifier)
                for button, dx, dy in ((1, 90, 55), (3, 70, 40)):
                    before = dict(state()[identifier][0]["rect"])
                    x = before["x"] + (60 if button == 1 else before["width"] - 25)
                    y = before["y"] + (80 if button == 1 else before["height"] - 25)
                    subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y), "keydown", "Super_L", "mousedown", str(button),
                                    "sleep", "0.1", "mousemove", "--sync", str(x + dx), str(y + dy), "sleep", "0.1",
                                    "mouseup", str(button), "keyup", "Super_L"], check=True)
                    settle()
                    after = state()[identifier][0]["rect"]
                    changed = (after["x"] != before["x"] or after["y"] != before["y"]) if button == 1 else (after["width"] > before["width"] or after["height"] > before["height"])
                    check(changed, ("Native" if identifier == n else "XTerm") + " modifier pointer " + ("drag" if button == 1 else "resize") + " did not change geometry")
                    targets(manager)
            capture("drag-resize")

            for identifier in (a, b):
                focus(identifier)
                keys("super+shift+space")
                check(state()[identifier][0]["floating"] in ("user_off", "auto_off"), "Floating toggle did not tile client")
            keys("super+w")
            check(state()[b][2]["layout"] == "tabbed", "Tabbed layout binding failed")
            visible_targets = targets(manager)
            check(b in visible_targets and a not in visible_targets, "Hidden tab exposes wrong controls")
            capture("tabbed-layout")
            keys("super+s")
            check(state()[b][2]["layout"] == "stacked", "Stacked layout binding failed")
            targets(manager)
            keys("super+e")
            check(state()[b][2]["layout"] not in ("stacked", "tabbed"), "Split layout did not restore")
            keys("super+r")
            check(request("get_binding_state")["name"] == "resize", "Keyboard resize mode missing")
            keys("Right")
            keys("Escape")
            check(request("get_binding_state")["name"] == "default", "Resize mode traps keyboard")
            keys("super+f")
            check(state()[b][0]["fullscreen_mode"] == 1, "Fullscreen binding failed")
            check(not targets(manager), "Fullscreen leaves detached titlebar controls")
            keys("super+f")
            check(state()[b][0]["fullscreen_mode"] == 0, "Fullscreen restore failed")
            targets(manager)

            clients = {identifier: state()[identifier][0]["window"] for identifier in (a, b)}
            for identifier in (a, b):
                window_action(identifier, "minimize")
            window_action(b, "show")
            check(state()[b][1] != "__i3_scratch" and state()[a][1] == "__i3_scratch", "Restore opened wrong minimized session")
            check(state()[b][0]["window"] == clients[b] and processes[3].poll() is None, "Restore replaced original client")
            window_action(a, "fullscreen")
            check(state()[a][1] != "__i3_scratch" and state()[a][0]["fullscreen_mode"] == 1, "Hidden fullscreen action did not restore intended session")
            window_action(a, "fullscreen")
            targets(manager)
            capture("restored-sessions")
            focus(n)
            targets(manager)
            manager.controls[a].activate("close")
            wait(lambda: a not in state(), "Unfocused overlay close did not target owned XTerm")
            check(b in state() and n in state(), "Closing unfocused client affected another window")
            focus(b)
            keys("alt+F4")
            wait(lambda: b not in state(), "Alt+F4 failed")
            check(compositor.poll() is None, "Private compositor stopped")
            log.flush()
            check("Your command:" not in (output / "session.log").read_text(), "i3 command error/nagbar during interaction")
        finally:
            if manager:
                manager.clear()
            if native:
                native.destroy()
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)

if findings:
    raise SystemExit(1)
print("WORKSPACE_UI_OK all number/move keys; pointer drag/resize; click focus; tile/tab/stack; fullscreen; targeted session restore; owned close")
