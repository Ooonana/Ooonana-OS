#!/usr/bin/env python3
"""Whole installer GUI, real PAM, inert backend, no exposed block devices."""
import configparser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get('OOONANA_GUI_TEST_DISPLAY') == '1'
assert os.environ.get('OOONANA_GUI_TEST_ADMIN_POLICY') == '1'
assert Path('/run/ooonana-installer-lifecycle-fixture').is_file()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/ooonana/usr/lib/ooonana/ui'))
from common import Gdk, Gtk
from gi.repository import GdkX11

output = Path(sys.argv[1]); assert output == Path('/qa/installer-lifecycle')
output.mkdir()
source = (ROOT/'scripts/build-full-i3-rootfs.sh').read_text()
helper = source.split('"$ROOTFS/usr/bin/ooonana-installer-gui" <<\'EOF\'\n', 1)[1].split('\nEOF', 1)[0]
script = output/'installer'; script.write_text(helper)
theme = output/'theme'
theme.write_text(source.split('"$ROOTFS/usr/bin/ooonana-theme-env" <<\'EOF\'\n', 1)[1].split('\nEOF', 1)[0])
subprocess.run(['sh', str(theme), 'apply'], check=True, capture_output=True, timeout=15)
settings_path = Path.home()/'.config/gtk-3.0/settings.ini'
settings = configparser.RawConfigParser(); settings.read(settings_path)
settings['Settings']['gtk-font-name'] = 'Sans 10'
settings['Settings']['gtk-xft-dpi'] = '98304'
with settings_path.open('w') as stream: settings.write(stream, space_around_delimiters=False)
env = {**os.environ, 'GDK_DPI_SCALE': os.environ.get('OOONANA_GUI_TEXT_SCALE', '1')}
env.pop('GTK_THEME', None)  # Use the actual saved Ooonana theme, not QA's Adwaita pin.
root = Gdk.get_default_root_window()
prompts = set()


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=6)


def drain(seconds=.08):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(.005)


def key(*keys):
    run('xdotool', 'key', '--clearmodifiers', *keys); drain()


def auth():
    found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', '^Authorize( administration)?$'], capture_output=True, text=True)
    for xid in found.stdout.splitlines():
        pid = subprocess.run(['xdotool', 'getwindowpid', xid], capture_output=True, text=True)
        identity = xid, pid.stdout.strip()
        if not pid.returncode and identity not in prompts:
            if subprocess.run(['xdotool', 'windowfocus', xid], capture_output=True).returncode: continue
            run('xdotool', 'type', '--clearmodifiers', 'Ooonana-private-admin-QA-20261026')
            key('Return'); prompts.add(identity)


def wait(predicate, detail, timeout=20):
    until = time.monotonic()+timeout
    while not predicate():
        assert time.monotonic() < until, detail
        auth(); drain()


def find(title):
    result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', '^'+title+'$'], capture_output=True, text=True)
    return result.stdout.splitlines()[-1] if result.returncode == 0 else None


def window(title, name):
    wait(lambda: find(title), title+' missing')
    xid = find(title); run('xdotool', 'windowactivate', '--sync', xid); drain(.2)
    foreign = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(xid))
    bounds = foreign.get_frame_extents()
    assert 0 <= bounds.x and bounds.x+bounds.width <= root.get_width(), (name, 'horizontal overflow', bounds.width)
    assert 0 <= bounds.y and bounds.y+bounds.height <= root.get_height(), (name, 'vertical overflow', bounds.height)
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output/(name+'.png')), 'png', [], [])
    return xid


def fill():
    key('alt+m', 'Home', 'Tab')
    run('xdotool', 'type', '--clearmodifiers', '/dev/ooonana-qa-target')
    # Home, swap, EFI; four format controls; user; password.
    key(*(['Tab']*9))
    run('xdotool', 'type', '--clearmodifiers', ' private|target password ')
    # Hostname, theme, repository, source, swap-size; Cancel; Review.
    key(*(['Tab']*7), 'space')


def action_button(xid):
    # The review text view owns initial focus. Click the real bottom-right
    # action of this exact owned dialog; Enter inside text must not approve.
    geometry = dict(line.split('=', 1) for line in run('xdotool', 'getwindowgeometry', '--shell', xid).stdout.splitlines())
    run('xdotool', 'mousemove', '--window', xid, str(int(geometry['WIDTH'])-65), str(int(geometry['HEIGHT'])-24))
    run('xdotool', 'click', '1'); drain()


wm = process = None
receipts = {}
with tempfile.TemporaryDirectory(prefix='ooonana-installer-lifecycle-') as temporary:
    config = Path(temporary)/'i3.conf'
    config.write_text('\n'.join(line for line in (ROOT/'branding/i3/config').read_text().splitlines() if not line.startswith('exec'))+'\n')
    try:
        wm = subprocess.Popen(['i3', '-c', str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait(lambda: subprocess.run(['i3-msg','-t','get_tree'],capture_output=True).returncode == 0, 'Private i3 missing')
        for scenario in ('cancel', 'blocked', 'success', 'failure'):
            (output/'scenario').write_text(scenario)
            before = len(prompts)
            with (output/(scenario+'.log')).open('w') as log:
                process = subprocess.Popen(['sh', str(script)], stdout=log, stderr=log, env=env)
                window('Install Ooonana OS', scenario+'-form'); fill()
                if scenario == 'blocked':
                    xid = window('Ooonana Install Blocked', 'blocked'); action_button(xid)
                    assert process.wait(timeout=8) == 1
                else:
                    xid = window('Ooonana Install Preview', scenario+'-preview')
                    if scenario == 'cancel':
                        key('Return'); drain(.2)
                        assert not (output/(scenario+'.started')).exists(), 'Enter in preview approved install'
                        if process.poll() is None: key('Escape')
                        assert process.wait(timeout=8) == 0
                    else:
                        action_button(xid)
                        xid = window('Ooonana Install Log', scenario+'-log')
                        wait(lambda: (output/(scenario+'.started')).exists(), 'Backend never started')
                        action_button(xid)  # Hide log; worker must survive.
                        drain(.2); assert process.poll() is None, 'Closing log abandoned installation'
                        (output/(scenario+'.release')).touch()
                        window('Ooonana OS' if scenario == 'success' else 'Ooonana Install Failed', scenario+'-result')
                        key('Return')  # Failure default must refuse fallback shell.
                        assert process.wait(timeout=8) == (0 if scenario == 'success' else 7)
                records = [json.loads(line) for line in (output/(scenario+'.jsonl')).read_text().splitlines()]
                expected = 1 if scenario in ('cancel','blocked') else 2
                assert len(records) == expected and records[0]['preview']
                if expected == 2: assert not records[1]['preview']
                assert len(prompts)-before == expected, 'Preview/execution must each authenticate'
                receipts[scenario] = dict(backend_calls=expected, real_auth_prompts=expected, password_via_stdin=True)
                process = None
        for path in output.iterdir():
            if path.is_file() and path.suffix in ('.jsonl','.log'):
                assert ' private|target password ' not in path.read_text(), 'Target password leaked'
        (output/'receipt.json').write_text(json.dumps(dict(scenarios=receipts, fake_backend=True,
            physical_disks_exposed=False, log_close_preserves_worker=True), indent=2)+'\n')
        print('INSTALLER_LIFECYCLE_UI_OK real PAM; preview cancel/block; log hide; success/failure; no disks', flush=True)
    finally:
        if process is not None and process.poll() is None: process.terminate(); process.wait(timeout=5)
        if wm is not None: wm.terminate(); wm.wait(timeout=5)
