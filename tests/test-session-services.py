#!/usr/bin/env python3
"""Custom-init service ordering and refusal paths; never activates host services."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/ooonana/usr/lib/ooonana'))
import session_services as services

audit_spec = importlib.util.spec_from_file_location('runtime_audit', ROOT / 'tests/audit-full-i3-runtime.py')
runtime_audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(runtime_audit)


class ProviderStartup(unittest.TestCase):
    def setUp(self):
        self.events, self.owners = [], {}

    def command(self, command):
        self.events.append(command)
        if 'org.freedesktop.DBus.GetNameOwner' in command:
            name = command[-1]
            if name not in self.owners:
                raise OSError('No owner')
            return f"('{self.owners[name]}',)"
        if 'org.freedesktop.DBus.StartServiceByName' in command:
            self.owners[command[-2]] = f':1.{len(self.owners) + 1}'
            return '(uint32 1,)'
        return '()'

    def test_wsl_and_unprivileged_start_cannot_activate_services(self):
        with patch.object(services.os, 'geteuid', return_value=1000):
            with self.assertRaises(PermissionError): services.start(self.command)
        with patch.object(services.os, 'geteuid', return_value=0), \
             patch.object(services, 'is_wsl', return_value=True):
            self.assertEqual(services.start(self.command)['state'], 'unsupported-wsl')
        self.assertEqual(self.events, [])

    def test_real_start_contract_never_submits_power_or_changes_pam(self):
        with patch.object(services.os, 'geteuid', return_value=0), \
             patch.object(services, 'is_wsl', return_value=False), \
             patch.object(services, 'prepare_cgroups') as cgroups, \
             patch.object(services, 'prepare_polkit_account') as account:
            self.assertEqual(services.start(self.command)['state'], 'ready')
            cgroups.assert_called_once_with(self.command)
            account.assert_called_once_with(self.command)
        self.assertEqual([c[-2] for c in self.events if 'org.freedesktop.DBus.StartServiceByName' in c],
                         ['org.freedesktop.login1', 'org.freedesktop.PolicyKit1'])
        self.assertFalse(any(part in ('Suspend', 'Reboot', 'PowerOff') for c in self.events for part in c))

    def test_existing_services_are_probed_without_reactivation(self):
        self.owners['org.freedesktop.login1'] = ':1.3'
        services.activate('org.freedesktop.login1', self.command)
        self.assertFalse(any('org.freedesktop.DBus.StartServiceByName' in c for c in self.events))
        self.assertTrue(any('--dest' in c and ':1.3' in c for c in self.events))

    def test_existing_policy_provider_preserves_custom_service_identity(self):
        self.owners.update({'org.freedesktop.login1':':1.3','org.freedesktop.PolicyKit1':':1.4'})
        with patch.object(services.os,'geteuid',return_value=0), \
             patch.object(services,'is_wsl',return_value=False), \
             patch.object(services,'prepare_cgroups'), \
             patch.object(services,'prepare_polkit_account') as account:
            self.assertEqual(services.start(self.command)['state'],'ready')
            account.assert_not_called()
        self.assertFalse(any('org.freedesktop.DBus.StartServiceByName' in c for c in self.events))

    def test_frozen_or_replaced_service_is_not_ready(self):
        self.owners['org.freedesktop.login1'] = ':1.3'
        def replaced(command):
            result = self.command(command)
            if command[-1] == 'org.freedesktop.DBus.Peer.Ping':
                self.owners['org.freedesktop.login1'] = ':1.4'
            return result
        with self.assertRaisesRegex(OSError, 'changed'):
            services.activate('org.freedesktop.login1', replaced)
        def frozen(command):
            if command[-1] == 'org.freedesktop.DBus.Peer.Ping': raise OSError('Timeout')
            return self.command(command)
        with self.assertRaises(OSError): services.activate('org.freedesktop.login1', frozen)

    def test_polkit_root_identity_or_group_refused_before_mutation(self):
        with patch.object(services.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=0,pw_gid=27)):
            with self.assertRaises(OSError): services.prepare_polkit_account(self.command)
        with patch.object(services.pwd, 'getpwnam', side_effect=KeyError), \
             patch.object(services.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=0)):
            with self.assertRaises(OSError): services.prepare_polkit_account(self.command)
        self.assertEqual(self.events, [])

    def test_legacy_or_symlinked_cgroup_mount_never_replaced(self):
        with patch.object(services.Path, 'is_symlink', return_value=True):
            with self.assertRaises(OSError): services.prepare_cgroups(self.command)
        with patch.object(services.Path, 'is_symlink', return_value=False), \
             patch.object(services.Path, 'is_dir', return_value=True), \
             patch.object(services.Path, 'read_text', return_value='1 0 0:1 / /sys/fs/cgroup rw - cgroup cgroup rw'):
            with self.assertRaisesRegex(OSError, 'not unified'):
                services.prepare_cgroups(lambda c: 'cgroupfs')
        self.assertFalse(any('mount' == part for c in self.events for part in c))

    def test_imported_policy_group_repaired_but_custom_permissions_preserved(self):
        account = SimpleNamespace(pw_uid=991,pw_gid=991)
        with patch.object(services.Path,'is_symlink',return_value=False), \
             patch.object(services.Path,'is_dir',return_value=True), \
             patch.object(services.Path,'stat',return_value=SimpleNamespace(st_uid=0,st_gid=0,st_mode=0o40750)), \
             patch.object(services.os,'chown') as chown:
            services.prepare_polkit_rules(account)
            chown.assert_called_once_with(Path('/etc/polkit-1/rules.d'),0,991)
        with patch.object(services.Path,'is_symlink',return_value=False), \
             patch.object(services.Path,'is_dir',return_value=True), \
             patch.object(services.Path,'stat',return_value=SimpleNamespace(st_uid=0,st_gid=0,st_mode=0o40700)), \
             patch.object(services.os,'chown') as chown:
            with self.assertRaisesRegex(OSError,'policy preserved'):
                services.prepare_polkit_rules(account)
            chown.assert_not_called()

    def test_factory_provisions_polkit_identity_before_dbus(self):
        builder = ROOT / 'scripts/build-full-i3-rootfs.sh'
        source = builder.read_text()
        groups = source.split('\nwrite_full_groups() {\n', 1)[1].split('\nwrite_tarball()', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)
            etc = image / 'etc'
            (etc / 'ooonana').mkdir(parents=True)
            subprocess.run(['bash', '-e', '-c', 'write_full_groups() {\n' + groups +
                            '\nROOTFS=$1\nOS_VERSION=0.10.0\n'
                            'ooonana_alpine_branch() { echo v3.24; }\n'
                            'write_full_groups\nwrite_full_groups', 'fixture', str(image)], check=True)

            def account_file(name):
                return [line.split(':') for line in (etc / name).read_text().splitlines()
                        if line.startswith('polkitd:')]

            self.assertEqual(len(account_file('passwd')), 1, 'D-Bus needs polkitd in the live rootfs')
            account, = account_file('passwd')
            group, = account_file('group')
            shadow, = account_file('shadow')
            self.assertTrue(0 < int(account[2]) < 1000)
            self.assertTrue(0 < int(account[3]) < 1000)
            self.assertEqual(account[3], group[2])
            self.assertEqual(account[5:], ['/var/empty', '/bin/false'])
            self.assertTrue(shadow[1].startswith('!'))

    def test_rootfs_audit_reports_missing_dbus_policy_and_activation_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bus = root / 'usr/share/dbus-1'
            (bus / 'system.d').mkdir(parents=True)
            (bus / 'system-services').mkdir()
            (bus / 'system.conf').write_text('<busconfig><user>messagebus</user></busconfig>')
            (bus / 'system.d/polkit.conf').write_text(
                '<busconfig><policy user="polkitd"/><policy group="82"/>'
                '<policy context="default"><allow user="*"/></policy></busconfig>')
            (bus / 'system-services/helper.service').write_text(
                '[D-BUS Service]\nName=org.example.Helper\nUser=helper\n')
            (bus / 'session.conf').write_text('<busconfig><user>session-only</user></busconfig>')
            self.assertEqual(runtime_audit.dbus_identity_errors(root, {'messagebus'}, set()), [
                'D-Bus policy usr/share/dbus-1/system.d/polkit.conf references missing user: polkitd',
                'D-Bus policy usr/share/dbus-1/system.d/polkit.conf references missing group: 82',
                'D-Bus activation usr/share/dbus-1/system-services/helper.service references missing user: helper',
            ])
            self.assertEqual(runtime_audit.dbus_identity_errors(
                root, {'messagebus', 'polkitd', 'helper'}, {'polkitd', '82'}), [])

    def test_boot_and_policy_preserve_authentication_and_lock_contract(self):
        source = (ROOT/'scripts/build-full-i3-rootfs.sh').read_text()
        boot = source.index('ooonana-session-services start')
        self.assertGreater(boot, source.index('start_system_services || true'))
        graphical_login = source.index('/usr/bin/ooonana-graphical-login </dev/null')
        self.assertLess(boot, graphical_login)
        self.assertLess(source.index('start_installed_mounts || exit 1'), graphical_login)
        policy = (ROOT/'packages/ooonana/etc/elogind/logind.conf.d/90-ooonana.conf').read_text()
        for key in ('HandlePowerKey','HandleSuspendKey','HandleHibernateKey','HandleLidSwitch','IdleAction'):
            self.assertIn(key+'=ignore', policy)
        for name in ('full-i3','both'):
            packages = (ROOT/f'configs/packages/{name}.list').read_text().splitlines()
            self.assertIn('elogind', packages); self.assertIn('polkit-elogind', packages)
            self.assertIn('lightdm', packages)
            self.assertIn('lightdm-gtk-greeter', packages)


if __name__ == '__main__': unittest.main()
