#!/usr/bin/env python3
"""Actual private package transactions: GSettings install/upgrade/rollback/remove."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'packages/ooonana/usr/bin/ooonana'
if not shutil.which('glib-compile-schemas') or not shutil.which('gsettings'):
    raise SystemExit('GSettings tools required for desktop cache regression')

with tempfile.TemporaryDirectory(prefix='ooonana-schema-transactions-') as temporary:
    work = Path(temporary)
    repo = work / 'repo'
    (repo / 'hooks').mkdir(parents=True)
    target = work / 'root'
    env = dict(os.environ, OOONANA_ROOT=str(target), OOONANA_REPO_DIR=str(repo),
               OOONANA_STATE_DIR=str(work / 'state'), OOONANA_CACHE_DIR=str(work / 'cache'),
               OOONANA_SOURCES_DIR=str(work / 'sources'), GSETTINGS_BACKEND='memory')

    def cli(*args, ok=True):
        result = subprocess.run(['sh', str(CLI), *args], env=env, capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == ok, result.stdout + result.stderr

    schema = 'usr/share/glib-2.0/schemas/org.ooonana.CacheQa.gschema.xml'
    override = 'usr/share/glib-2.0/schemas/20_cacheqa.gschema.override'

    def package(version, value=None):
        payload = {schema: '<schemalist><schema id="org.ooonana.CacheQa" path="/org/ooonana/cacheqa/">'
                   '<key name="enabled" type="b"><default>true</default></key></schema></schemalist>'}
        if value is not None:
            payload[override] = '[org.ooonana.CacheQa]\nenabled=' + value + '\n'
        archive = repo / 'cacheqa.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            for name, text in payload.items():
                data = text.encode()
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o644
                bundle.addfile(member, io.BytesIO(data))
        fields = dict(ID='cacheqa', VERSION=version, KIND='archive', SUMMARY='Private schema fixture',
                      DEPS='', ARCHIVE=archive.name, SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())
        (repo / 'cacheqa.pkg').write_text(''.join(f'OOONANA_PKG_{k}="{v}"\n' for k, v in fields.items()))
        cli('repo', 'index', str(repo))

    def value():
        return subprocess.check_output(['gsettings', '--schemadir', str(target / Path(schema).parent),
            'get', 'org.ooonana.CacheQa', 'enabled'], env=env, text=True).strip()

    package('1')
    cli('get', 'cacheqa')
    assert value() == 'true'
    package('2', 'false')
    cli('upgrade', 'cacheqa')
    assert value() == 'false', 'New override did not activate without reboot'
    package('3', 'true')
    hook = repo / 'hooks/cacheqa.healthcheck'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o755)
    cli('repo', 'index', str(repo))
    cli('upgrade', 'cacheqa', ok=False)
    assert value() == 'false', 'Rollback left cache from failed update'
    package('4', 'true')
    hook.write_text('#!/bin/sh\nprintf ready > "$OOONANA_ROOT/ready"\nwhile :; do sleep 1; done\n')
    cli('repo', 'index', str(repo))
    with (work / 'killed-update.log').open('w') as log:
        process = subprocess.Popen(['sh', str(CLI), 'upgrade', 'cacheqa'], env=env,
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            while not (target / 'ready').exists():
                assert process.poll() is None, 'Upgrade exited before interruption'
                assert time.monotonic() < deadline, 'Upgrade did not reach health hook'
                time.sleep(.03)
            assert value() == 'true'
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    cli('recover')
    assert value() == 'false', 'Explicit recovery left cache from killed update'
    cli('remove', 'cacheqa')
    assert not (target / Path(schema).parent / 'gschemas.compiled').exists()

print('DESKTOP_PACKAGE_CACHE_TRANSACTIONS_OK')
