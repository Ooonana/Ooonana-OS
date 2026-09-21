#!/usr/bin/env python3
import ast
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'scripts/build-full-i3-rootfs.sh').read_text()
functions = re.findall(r'^unblock_rfkill\(\) \{\n.*?^\}', source, re.M | re.S)
assert len(functions) == 2
with tempfile.TemporaryDirectory(prefix='ooonana-radio-test-') as temporary:
    root = Path(temporary)
    for index, kind in enumerate(['wlan', 'bluetooth', 'wwan']):
        radio = root/f'rfkill{index}'
        radio.mkdir()
        (radio/'type').write_text(kind)
        (radio/'soft').write_text('1')
    for function in functions:
        for mode, expected in [('wifi', [0]), ('bluetooth', [1]), ('all', [0, 1, 2])]:
            for index in range(3):
                (root/f'rfkill{index}/soft').write_text('1')
            code = function.replace('/sys/class/rfkill', str(root))
            code += '\nLOG=/dev/null\nrfkill() { :; }\nunblock_rfkill "$1"\n'
            subprocess.run(['sh', '-eu', '-c', code, 'probe', mode], check=True)
            changed = [i for i in range(3) if (root/f'rfkill{i}/soft').read_text() == '0']
            assert changed == expected, (mode, changed)

    audio = (ROOT/'packages/ooonana/usr/bin/ooonana-audio-start').read_text()
    functions = '\n'.join(re.search(r'^' + name + r'\(\) \{\n.*?^\}', audio, re.M | re.S).group()
                          for name in ['owned_pids', 'running', 'stop_owned'])
    for pid, owner in [(101, 1000), (102, 1001)]:
        (root/str(pid)).mkdir()
        (root/str(pid)/'status').write_text(f'Uid:\t{owner}\t{owner}\t{owner}\t{owner}\n')
    code = functions.replace('/bin/busybox pidof', 'fixture_pidof').replace('/proc/', str(root)+'/')
    code += '\nuid=1000\nfixture_pidof() { echo 101 102; }\nkill() { echo "$1"; }\nstop_owned pipewire\n'
    result = subprocess.run(['sh', '-c', code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == '101', result.stdout

setup = ast.parse((ROOT/'packages/ooonana/usr/lib/ooonana/ui/setup_app.py').read_text())
method = next(node for node in ast.walk(setup) if isinstance(node, ast.FunctionDef) and node.name == 'apply')
for password_rc in [0, 1]:
    commands = []
    completion = []
    def run(command, **kwargs):
        commands.append(command)
        return 0, 'saved'
    def thread(target, **kwargs):
        return SimpleNamespace(start=target)
    namespace = dict(run=run, command_exists=lambda _: True, admin_command=lambda x: x,
                     subprocess=SimpleNamespace(run=lambda *a, **k: SimpleNamespace(returncode=password_rc, stdout=''),
                                                PIPE=-1, STDOUT=-2, TimeoutExpired=subprocess.TimeoutExpired),
                     threading=SimpleNamespace(Thread=thread),
                     GLib=SimpleNamespace(idle_add=lambda callback, *args: completion.append(args)))
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'setup-test', 'exec'), namespace)
    values = dict(user='test', password='secret', mode='dhcp', theme='dark', repo='file:///repo')
    target = SimpleNamespace(validate=lambda: (values, ''), spinner=SimpleNamespace(start=lambda: None),
                             status=SimpleNamespace(set_text=lambda _: None), finished=lambda *args: None)
    namespace['apply'](target, SimpleNamespace(set_sensitive=lambda _: None))
    assert '--done' not in commands[0]
    assert any('--done' in command for command in commands) == (password_rc == 0)
    assert completion[0][1] == password_rc
print('ok radio scope, audio owner, setup failure ordering')
