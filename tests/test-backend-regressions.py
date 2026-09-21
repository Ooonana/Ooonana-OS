import contextlib
import ast
import difflib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'packages/ooonana/usr/bin/ooonana'

def command(args, env=None, input=None):
    return subprocess.run(args, env=env, input=input, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=45)

def fixture(base):
    env = os.environ.copy()
    for key, name in [('OOONANA_REPO_DIR', 'repo'), ('OOONANA_STATE_DIR', 'state'),
                      ('OOONANA_CACHE_DIR', 'cache'), ('OOONANA_ROOT', 'root')]:
        env[key] = str(base / name)
        (base / name).mkdir()
    return env

def pkg(base, name, version='1', deps='', conflicts='', archive='', sha=''):
    fields = dict(ID=name, VERSION=version, KIND='archive', SUMMARY='Audit fixture',
                  DEPS=deps, CONFLICTS=conflicts, ARCHIVE=archive, SHA256=sha)
    (base / 'repo' / (name + '.pkg')).write_text(''.join(
        f'OOONANA_PKG_{key}="{value}"\n' for key, value in fields.items()))

with tempfile.TemporaryDirectory(prefix='ooonana-audit-') as temporary:
    work = Path(temporary)
    for scenario in ['dependents', 'upgrade-conflict', 'reinstall']:
        base = work / scenario
        base.mkdir()
        env = fixture(base)
        if scenario == 'dependents':
            pkg(base, 'shared')
            pkg(base, 'alpha', deps='shared')
            pkg(base, 'beta', deps='shared')
            assert command([str(CLI), 'install', 'alpha', 'beta'], env).returncode == 0
            result = command([str(CLI), 'remove', 'shared', 'alpha'], env)
            assert result.returncode != 0 and (base/'state/installed/shared.pkg').exists()
            print('DEPENDENTS', 'rc=', result.returncode,
                  'shared_exists=', (base/'state/installed/shared.pkg').exists(),
                  'beta_exists=', (base/'state/installed/beta.pkg').exists())
        elif scenario == 'upgrade-conflict':
            pkg(base, 'left')
            pkg(base, 'right')
            assert command([str(CLI), 'install', 'left', 'right'], env).returncode == 0
            pkg(base, 'left', version='2', conflicts='right')
            result = command([str(CLI), 'upgrade', 'left'], env)
            assert result.returncode != 0 and 'VERSION="1"' in (base/'state/installed/left.pkg').read_text()
            print('UPGRADE_CONFLICT', 'rc=', result.returncode,
                  'upgraded=', 'VERSION="2"' in (base/'state/installed/left.pkg').read_text())
        else:
            payload = base / 'healthy'
            payload.write_text('working')
            archive = base / 'repo/healthy.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                tar.add(payload, arcname='usr/share/audit/healthy')
            pkg(base, 'healthy', archive='healthy.tar.gz', sha=hashlib.sha256(archive.read_bytes()).hexdigest())
            assert command([str(CLI), 'install', 'healthy'], env).returncode == 0
            archive.write_bytes(b'corrupt')
            result = command([str(CLI), 'reinstall', 'healthy'], env)
            assert result.returncode != 0 and (base/'root/usr/share/audit/healthy').read_text() == 'working'
            assert (base/'state/installed/healthy.pkg').exists()
            print('REINSTALL', 'rc=', result.returncode,
                  'working_file_exists=', (base/'root/usr/share/audit/healthy').exists(),
                  'metadata_exists=', (base/'state/installed/healthy.pkg').exists())

    for operation in ['reinstall', 'upgrade']:
        base = work / ('rollback-' + operation)
        base.mkdir()
        env = fixture(base)
        payload = base/'payload'
        payload.write_text('working')
        archive = base/'repo/package.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(payload, arcname='usr/share/audit/healthy')
        pkg(base, 'healthy', archive='package.tar.gz', sha=hashlib.sha256(archive.read_bytes()).hexdigest())
        assert command([str(CLI), 'install', 'healthy'], env).returncode == 0
        payload.write_text('replacement')
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(payload, arcname='usr/share/audit/healthy')
            tar.add(payload, arcname='usr/share/audit/new-file')
        pkg(base, 'healthy', version='2', archive='package.tar.gz', sha=hashlib.sha256(archive.read_bytes()).hexdigest())
        (base/'repo/hooks').mkdir()
        hook = base/'repo/hooks/healthy.install'
        hook.write_text('#!/bin/sh\nexit 7\n')
        hook.chmod(0o755)
        result = command([str(CLI), operation, 'healthy'], env)
        assert result.returncode != 0, result.stdout
        assert (base/'root/usr/share/audit/healthy').read_text() == 'working', result.stdout
        assert not (base/'root/usr/share/audit/new-file').exists(), result.stdout
        assert 'VERSION="1"' in (base/'state/installed/healthy.pkg').read_text(), result.stdout
        assert not list((base/'state').glob('.replace-*')), result.stdout
        print('ROLLBACK_OK', operation)

    base = work/'metadata-only'
    base.mkdir()
    env = fixture(base)
    busybox = shutil.which('busybox')
    if busybox:
        (base/'bin').mkdir()
        wrapper = base/'bin/tar'
        wrapper.write_text(f'#!/bin/sh\nexec "{busybox}" tar "$@"\n')
        wrapper.chmod(0o755)
        env['PATH'] = str(base/'bin') + ':' + env['PATH']
    pkg(base, 'meta')
    assert command([str(CLI), 'install', 'meta'], env).returncode == 0
    pkg(base, 'meta', version='2')
    result = command([str(CLI), 'upgrade', 'meta'], env)
    assert result.returncode == 0, result.stdout
    result = command([str(CLI), 'reinstall', 'meta'], env)
    assert result.returncode == 0, result.stdout
    print('METADATA_ONLY_OK', 'BusyBox tar' if busybox else 'system tar')

    kernel = work / 'kernel'
    (kernel/'source').mkdir(parents=True)
    (kernel/'source/arch/x86').mkdir(parents=True)
    (kernel/'source/Makefile').write_text('VERSION = 6\n')
    (kernel/'source/Kconfig').write_text('mainmenu "Audit"\n')
    (kernel/'build').mkdir()
    (kernel/'out').mkdir()
    sentinel = kernel/'build/sentinel'
    sentinel.write_text('preserve')
    image = kernel/'out/vmlinuz-ooonana'
    image.write_text('preserve')
    result = command(['bash', str(ROOT/'scripts/build-kernel.sh'), '--source', str(kernel/'source'),
                      '--build-dir', str(kernel/'build'), '--out-dir', str(kernel/'out'), '--dry-run', '--force'])
    assert result.returncode == 0 and sentinel.exists() and image.exists()
    print('KERNEL_DRY_RUN', 'rc=', result.returncode, 'build_preserved=', sentinel.exists(),
          'image_preserved=', image.exists())
    if result.returncode: print(result.stdout)

    release = (ROOT/'scripts/rebuild-full-i3-release.sh').read_text()
    predicate = re.search(r'^kernel_cache_matches_fragment\(\) \{\n.*?^\}', release, re.M | re.S).group()
    (kernel/'out/vmlinuz').write_text('fixture kernel')
    (kernel/'out/config').write_text('CONFIG_EXT4_FS=y\n')
    (kernel/'out/kernel.env').write_text('OOONANA_KERNEL_VERSION=1.0.0\n')
    code = predicate + '\nKERNEL="$1/vmlinuz"; KERNEL_CONFIG="$1/config"; KERNEL_FRAGMENT="$1/config"; KERNEL_SOURCE_VERSION=6.18.37; kernel_cache_matches_fragment\n'
    result = command(['bash', '-c', code, 'probe', str(kernel/'out')])
    assert result.returncode != 0
    print('KERNEL_WRONG_VERSION_ACCEPTED=', result.returncode == 0)
    (kernel/'out/kernel.env').write_text('OOONANA_KERNEL_VERSION=6.18.37\n')
    assert command(['bash', '-c', code, 'probe', str(kernel/'out')]).returncode == 0
    (kernel/'out/kernel.env').write_text('OOONANA_KERNEL_VERSION=6.18.37\nOOONANA_KERNEL_VERSION=6.18.37\n')
    assert command(['bash', '-c', code, 'probe', str(kernel/'out')]).returncode != 0

spec = importlib.util.spec_from_file_location('ooonana_ai', ROOT/'packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py')
ai = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ai
spec.loader.exec_module(ai)
for name, data in [('usage', b'data: {"choices":[],"usage":{}}\n\n'),
                   ('error', b'data: {"error":{"message":"generation failed"}}\n\n')]:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            output = ai.read_streaming_response(io.BytesIO(data))
        assert name == 'usage' and output == ''
        print('STREAM', name, 'returned=', repr(output))
    except Exception as exc:
        assert name == 'error' and isinstance(exc, ai.OoonanaError)
        print('STREAM', name, 'raised=', type(exc).__name__)

spec = importlib.util.spec_from_file_location('wireless_utils', ROOT/'packages/ooonana/usr/lib/ooonana/ui/wireless_utils.py')
wireless = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wireless)
networks = wireless.parse_nmcli_wifi(':AA\\:BB\\:CC\\:DD\\:EE\\:FF: Cafe :80:WPA2:wlan0')
assert networks[0]['ssid'] == ' Cafe '
print('SSID', 'input=', repr(' Cafe '), 'parsed=', repr(networks[0]['ssid']))

source = (ROOT/'scripts/build-full-i3-live-initramfs.sh').read_text()
startup = source.split('cat > "$LIVE_INIT_TREE/init" <<\'EOF\'\n', 1)[1].split('\nEOF', 1)[0]
startup = startup[:startup.index('mount -t sysfs')]
mock = '''proc_ready=0
mount() { proc_ready=1; }
cat() { [ "$proc_ready" = 1 ] || return 1; echo ooonana.live.rootfs=/images/custom.ext4; }
'''
result = command(['sh'], input=mock + startup + '\nprintf "%s\\n" "$LIVE_IMAGE"\n')
assert result.stdout.strip() == '/images/custom.ext4'
print('LIVE_ROOTFS_OVERRIDE', repr(result.stdout.strip()))
