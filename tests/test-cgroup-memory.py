#!/usr/bin/env python3
"""Fixture-only RAM limits: both standalone payloads, no host cgroup writes."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'packages/ooonana/usr/lib/ooonana'
AI = ROOT / 'packages/openvino-chat/source/src'
sys.path[:0] = [str(CORE), str(CORE / 'ui'), str(AI)]
import cgroup_memory
from memory_status import available_ram
from openvino_chat import cgroup_memory as ai_limits, memory_guard

assert (CORE / 'cgroup_memory.py').read_bytes() == (AI / 'openvino_chat/cgroup_memory.py').read_bytes()
MIB = 1024**2
GIB = 1024**3
cases = 0

with tempfile.TemporaryDirectory(prefix='ooonana-cgroup-test-') as temporary:
    work = Path(temporary)
    proc = work / 'meminfo'
    membership = work / 'membership'
    mountinfo = work / 'mountinfo'
    mount = work / 'mount with space'
    mount.mkdir()
    proc.write_text('MemTotal: 8388608 kB\nMemAvailable: 6291456 kB\nSwapFree: 67108864 kB\n')
    fake_psutil = SimpleNamespace(virtual_memory=lambda: SimpleNamespace(total=8*GIB, available=6*GIB),
                                  swap_memory=lambda: SimpleNamespace(free=64*GIB))

    def layout(kind='v2', member='/user.slice/app.scope', root='/'):
        membership.write_text('0::' + member + '\n' if kind == 'v2' else '7:cpu,memory:' + member + '\n')
        escaped = str(mount).replace('\\', '\\134').replace(' ', '\\040')
        mountinfo.write_text(f'29 20 0:28 {root} {escaped} rw,nosuid shared:9 - '
                            + ('cgroup2 cgroup rw\n' if kind == 'v2' else 'cgroup cgroup rw,cpu,memory\n'))

    def limits(path, maximum, used, kind='v2'):
        path.mkdir(parents=True, exist_ok=True)
        names = ('memory.max', 'memory.current') if kind == 'v2' else ('memory.limit_in_bytes', 'memory.usage_in_bytes')
        (path / names[0]).write_text(str(maximum))
        usage = path / names[1]
        if used is None:
            usage.unlink(missing_ok=True)
        else:
            usage.write_text(str(used))

    def check(expected, *, override=None):
        global cases
        kwargs = dict(membership=membership, mountinfo=mountinfo, cgroup_root=override)
        for module in (cgroup_memory, ai_limits):
            assert module.constrain_memory(8*GIB, 6*GIB, **kwargs) == expected
        info = available_ram(proc, override, membership=membership, mountinfo=mountinfo)
        assert (info['total'], info['available']) == expected, info
        with patch.dict(sys.modules, {'psutil': fake_psutil}):
            assert memory_guard.memory_snapshot(**kwargs) == (*expected, 64*GIB)
        cases += 1

    layout()
    parent, leaf = mount / 'user.slice', mount / 'user.slice/app.scope'
    limits(mount, 'max', 2*GIB)
    limits(leaf, GIB, 768*MIB)
    check((GIB, 256*MIB))  # Original regression: root-only reported 6 GiB.
    limits(parent, 2*GIB, 1920*MIB)
    check((GIB, 128*MIB))  # Parent siblings can exhaust shared allowance.
    limits(leaf, 'max', 768*MIB)
    check((2*GIB, 128*MIB))
    limits(parent, 2*GIB, 3*GIB)
    check((2*GIB, 0))
    limits(parent, 0, 0)
    check((0, 0))
    limits(parent, 'max', 0)
    for used in (None, 'broken', -1):
        limits(leaf, GIB, used)
        check((GIB, 0))
    limits(leaf, 'broken', 0)
    check((8*GIB, 6*GIB))
    limits(leaf, 1 << 63, 0)
    check((8*GIB, 6*GIB))
    limits(leaf, 4*GIB, GIB)
    limits(mount, 2*GIB, GIB)
    check((2*GIB, GIB))
    limits(mount, 'max', 0)
    layout(root='/user.slice')
    limits(mount / 'app.scope', GIB, 768*MIB)
    check((GIB, 256*MIB))  # Subtree bind mount strips actual mount root.
    layout(member='/', root='/')
    limits(mount, GIB, 768*MIB)
    check((GIB, 256*MIB))  # Namespaced root; ancestors outside mount unavailable.
    limits(mount, 'max', 0)
    for member in ('/../user.slice/app.scope', '/user.slice/./app.scope', 'relative/path', '/user.slice/app.scope (deleted)'):
        layout(member=member)
        check((8*GIB, 6*GIB))
    layout(member='/user.slice-extra/app.scope', root='/user.slice')
    limits(mount, 128*MIB, 64*MIB)
    check((8*GIB, 6*GIB))  # Prefix collision cannot select unrelated scope.
    layout()
    limits(mount, 'max', 0)
    other = work / 'unrelated'
    limits(other, 128*MIB, 64*MIB)
    mountinfo.write_text(mountinfo.read_text() + f'30 20 0:28 /other {other} rw - cgroup2 cgroup rw\n')
    limits(leaf, GIB, 768*MIB)
    check((GIB, 256*MIB))  # Ignore mounted scopes containing different processes.
    layout(kind='v1')
    limits(mount, 1 << 63, 0, 'v1')
    limits(parent, 2*GIB, 1920*MIB, 'v1')
    limits(leaf, GIB, 768*MIB, 'v1')
    check((GIB, 128*MIB))
    membership.write_text('0::/different\n7:cpu,memory:/user.slice/app.scope\n')
    check((GIB, 128*MIB))  # Hybrid membership selects memory hierarchy.
    mountinfo.write_text(mountinfo.read_text().replace('rw,cpu,memory', 'rw,cpu'))
    check((8*GIB, 6*GIB))
    membership.write_text('malformed\n0::/not-visible\n')
    mountinfo.write_text('malformed\n')
    check((8*GIB, 6*GIB))
    limits(mount, GIB, 768*MIB)
    check((GIB, 256*MIB), override=mount)
    limits(mount / 'memory', 512*MIB, 400*MIB, 'v1')
    membership.write_text('7:memory:/\n')
    check((512*MIB, 112*MIB), override=mount)
    membership.unlink()
    mountinfo.unlink()
    check((8*GIB, 6*GIB))

    # Real build helper repairs stale cached app files and refreshes its manifest.
    image = work / 'rootfs'
    app = image / 'usr/lib/ooonana/openvino-chat'
    (app / 'src/openvino_chat').mkdir(parents=True)
    (app / 'scripts').mkdir()
    (app / 'src/openvino_chat/memory_guard.py').write_text('stale cached code')
    for name in ('APP-MANIFEST.sha256', 'pyproject.toml', 'requirements-linux-runtime.lock',
                 'requirements-linux-full.lock', 'runtime-linux.env'):
        (app / name).write_text('fixture')
    builder = (ROOT / 'scripts/build-full-i3-rootfs.sh').read_text()
    function = re.search(r'^install_current_backend_checks\(\) \{\n.*?^\}', builder, re.M | re.S)[0]
    subprocess.run(['bash', '-eu', '-c', function + '\nROOT="$1"\nROOTFS="$2"\ninstall_current_backend_checks',
                    'test', str(ROOT), str(image)], check=True)
    for name in ('api.py', 'benchmarks.py', 'cgroup_memory.py', 'knowledge.py', 'memory_guard.py', 'perf.py', 'sessions.py', 'state_io.py'):
        assert (app / 'src/openvino_chat' / name).read_bytes() == (AI / 'openvino_chat' / name).read_bytes()
    assert (image / 'usr/lib/ooonana/cgroup_memory.py').read_bytes() == (CORE / 'cgroup_memory.py').read_bytes()
    subprocess.run(['sha256sum', '-c', 'APP-MANIFEST.sha256'], cwd=app, check=True, capture_output=True)
    assert 'src/openvino_chat/cgroup_memory.py' in (app / 'APP-MANIFEST.sha256').read_text()
    # No OpenVINO install: core UI still receives its self-contained probe.
    core_only = work / 'core-only'
    subprocess.run(['bash', '-eu', '-c', function + '\nROOT="$1"\nROOTFS="$2"\ninstall_current_backend_checks',
                    'test', str(ROOT), str(core_only)], check=True)
    assert (core_only / 'usr/lib/ooonana/ui/memory_status.py').exists()
    assert (core_only / 'usr/lib/ooonana/ui/task_manager_app.py').read_bytes() == (CORE / 'ui/task_manager_app.py').read_bytes()
    for name in ('chat_store.py', 'common.py', 'notification_utils.py', 'ui_preferences.py', 'window_controls.py'):
        assert (core_only / 'usr/lib/ooonana/ui' / name).read_bytes() == (CORE / 'ui' / name).read_bytes()
    assert (core_only / 'usr/bin/ooonana').read_bytes() == (CORE.parent.parent / 'bin/ooonana').read_bytes()
    assert (core_only / 'usr/lib/ooonana/storage_health.py').read_bytes() == (CORE / 'storage_health.py').read_bytes()
    assert (core_only / 'usr/lib/ooonana/panel_session.py').read_bytes() == (CORE / 'panel_session.py').read_bytes()
    for name in ('ooonana-panel-start', 'ooonana-window-list', 'ooonana-media-status'):
        assert (core_only / 'usr/bin' / name).read_bytes() == (CORE.parent.parent / 'bin' / name).read_bytes()
    assert not (core_only / 'usr/lib/ooonana/openvino-chat').exists()

    # Strict model preflight consumes scoped snapshot, never swap capacity.
    layout()
    limits(mount, 'max', 0)
    limits(parent, 'max', 0)
    limits(leaf, GIB, 768*MIB)
    model = work / 'model'
    model.mkdir()
    with (model / 'openvino_model.bin').open('wb') as stream:
        stream.truncate(64*MIB)
    with patch.dict(sys.modules, {'psutil': fake_psutil}), patch.dict('os.environ', {'OPENVINO_MEMORY_POLICY': 'strict'}), \
            patch.object(memory_guard, 'constrain_memory', lambda total, available, *_args: ai_limits.constrain_memory(total, available, membership, mountinfo)):
        try:
            memory_guard.preflight_model(model)
        except MemoryError:
            pass
        else:
            raise AssertionError('strict policy ignored nested memory allowance')

print(f'ok cgroup-memory: {cases} layouts, both payloads/UI/model parity; strict/no-swap-as-RAM')
