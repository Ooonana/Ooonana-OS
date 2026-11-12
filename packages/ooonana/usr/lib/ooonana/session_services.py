"""Boot-time login1/polkit activation for Ooonana's custom init.

PAM's existing optional pam_elogind entry registers authenticated sessions.
This helper never submits a power operation or changes authentication policy.
"""
import grp
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys


BUS = ["gdbus", "call", "--system", "--dest", "org.freedesktop.DBus",
       "--object-path", "/org/freedesktop/DBus", "--method"]


def execute(command):
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=8, check=False)
    if result.returncode:
        raise OSError("Command failed: " + command[0])
    return result.stdout.strip()


def owner(name, run=execute):
    try:
        value = run(BUS + ["org.freedesktop.DBus.GetNameOwner", name])
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.fullmatch(r"\('(:[0-9]+\.[0-9]+)',\)", value)
    return match.group(1) if match else None


def activate(name, run=execute):
    current = owner(name, run)
    if current is None:
        run(BUS + ["org.freedesktop.DBus.StartServiceByName", name, "0"])
        current = owner(name, run)
    if current is None:
        raise OSError("Service did not acquire its name: " + name)
    run(["gdbus", "call", "--system", "--dest", current,
         "--object-path", "/org/freedesktop/login1" if name.endswith("login1") else
         "/org/freedesktop/PolicyKit1/Authority", "--method", "org.freedesktop.DBus.Peer.Ping"])
    # Do not accept a response from a service replaced during the probe.
    if owner(name, run) != current:
        raise OSError("Service changed during readiness check: " + name)


def is_wsl():
    return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()


def prepare_cgroups(run=execute):
    path = Path("/sys/fs/cgroup")
    if path.is_symlink() or not path.is_dir():
        raise OSError("Canonical cgroup directory unavailable")
    kind = run(["stat", "-f", "-c", "%T", str(path)])
    if kind == "cgroup2fs":
        return
    # Never replace an existing administrator/legacy cgroup mount.
    mounts = Path("/proc/self/mountinfo").read_text().splitlines()
    if any(line.split()[4] == str(path) for line in mounts):
        raise OSError("Existing cgroup mount is not unified")
    run(["mount", "-t", "cgroup2", "-o", "nosuid,nodev,noexec", "cgroup2", str(path)])
    if run(["stat", "-f", "-c", "%T", str(path)]) != "cgroup2fs":
        raise OSError("Unified cgroup mount not ready")


def prepare_polkit_account(run=execute):
    try:
        account = pwd.getpwnam("polkitd")
    except KeyError:
        try:
            if grp.getgrnam("polkitd").gr_gid == 0:
                raise OSError("Refusing privileged polkit service group")
        except KeyError:
            run(["/bin/busybox", "addgroup", "-S", "polkitd"])
        run(["/bin/busybox", "adduser", "-S", "-D", "-H", "-h", "/var/empty",
             "-s", "/bin/false", "-G", "polkitd", "polkitd"])
        account = pwd.getpwnam("polkitd")
    if account.pw_uid == 0 or account.pw_gid == 0:
        raise OSError("Refusing privileged polkit service identity")
    prepare_polkit_rules(account)


def prepare_polkit_rules(account):
    path = Path('/etc/polkit-1/rules.d')
    if path.is_symlink() or not path.is_dir():
        raise OSError('Polkit policy directory unavailable')
    info = path.stat()
    mode = stat.S_IMODE(info.st_mode)
    if (info.st_uid, info.st_gid, mode) == (0, 0, 0o750):
        # APK import normalizes group ownership. Repair only its known layout;
        # root retains ownership/write permission for authorization rules.
        os.chown(path, 0, account.pw_gid)
        return
    if info.st_uid != 0 or not ((info.st_gid == account.pw_gid and mode & 0o050 == 0o050)
                                or mode & 0o005 == 0o005):
        raise OSError('Custom polkit directory cannot be read safely; policy preserved')


def start(run=execute):
    if os.geteuid() != 0:
        raise PermissionError("Session-service startup requires root")
    if is_wsl():
        return {"state": "unsupported-wsl", "power_requests": False}
    prepare_cgroups(run)
    if owner("org.freedesktop.PolicyKit1", run) is None:
        prepare_polkit_account(run)
    activate("org.freedesktop.login1", run)
    activate("org.freedesktop.PolicyKit1", run)
    return {"state": "ready", "provider": "login1", "power_requests": False}


def main():
    if sys.argv[1:] != ["start"]:
        print("usage: ooonana-session-services start", file=sys.stderr)
        return 2
    try:
        print(json.dumps(start(), sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Session services unavailable: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
