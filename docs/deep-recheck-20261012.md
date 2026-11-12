# Deep software recheck - 2026-10-12

Core 0.10.0 candidate, branch `codex/supported-base-0-10`. This is source,
fixture and isolated actual-userspace validation, not a zero-bug guarantee.
Installed Ooonana WSL/stable 0.9.9 remain untouched. No ISO or sound tests.

## Confirmed bugs repaired

- Task Manager stored kernel start ticks in signed 32-bit GTK columns: long
  uptime could overflow and interrupt refresh. Start ticks now use unsigned
  64-bit storage; Linux unsigned 32-bit UIDs also no longer overflow.
- Own-task termination checked `/proc`, then signaled a numeric PID. Exit/PID
  reuse could target another task. Shared helper binds a pidfd before identity
  checks, validates owner/start ticks, signals only that descriptor and closes
  it on every path. Missing support refuses; no unsafe fallback.
- Old rofi quick-kill generator bypassed native safeguards. Source-owned
  launcher now opens Task Manager, with one ownership/confirmation policy.
  Builder/core archive both install that launcher; no raw TERM/KILL fallback.
- Task Manager read all command-line bytes before truncating. Read is now
  bounded at the file operation, not after allocation.
- Preferences/notification-state replacement lacked a file flush: delayed
  ENOSPC/EIO could promote failed contents. Flush/fsync now precede replacement;
  injected failure preserves previous state and removes only owned temporary.
- Malformed/deep i3 replies could crash dock/control watchers. Recursion becomes
  a recoverable error; tree/workspace/subscription schemas are checked.
- Linux AI API stop had the numeric-PID race too. It now binds a pidfd, rechecks
  unique server instance, signals the bound process and retains replacement
  state. PID1/self/unsupported runtime refuse. Windows taskkill unchanged.
- Repository promotion flushed CURRENT, but not generation contents/directories.
  Generation files flush before promotion; POSIX directory entries flush before
  and after pointer publication. Windows flushes files, but Python has no portable
  directory-flush primitive there. This is not physical power-loss certification.
- AI QA installer ran before granting traversal of its owned empty mktemp tree.
  Harness fixes that ordering; preserved runtime/model stores remain read-only.
- AI source archive inherited 0777 Windows/DrvFS modes. Builder now normalizes
  directories to 0755, data/source to 0644 and launcher/shell scripts to 0755.
  Regression starts with writable input and umask 077; every archive entry's
  mode and root ownership is checked before signing.
- Follow-up archive audit found the same writable-directory issue in Firefox,
  Wine and Windows-chat wrappers. Those builders and native BunanaChat now
  normalize payload modes too; executable launchers/binaries remain executable.
  Private 0777-source/umask-077 fixtures cover all four, with no real installer
  executed. DeviceChat's 0777 symlinks are normal, not writable regular files.

## Evidence

- Full root workflow suite: `/var/tmp/ooonana-deep-bugs-20261012.pf7TSzPZ/final-root.log`.
- Full UID1000 workflow suite with private HOME/XDG state: same directory,
  `final-nonroot.log`. Both passed; no host service/account changes.
- Focused termination, state-I/O and IPC faults plus native source checks:
  `/var/tmp/ooonana-deep-bugs-20261012.pf7TSzPZ/focused.log`.
- Generation ENOSPC/promotion ordering: same directory, `publication.log`.
- Final package permission checks passed as root and UID1000: same directory,
  `package-modes-{root,nonroot}.log` and `wrapper-modes-{root,nonroot}.log`.
  These run after the full suites; final remote CI also includes the new fixtures.
- Thirteen actual candidate GUI gates, including owned-child termination:
  `/var/tmp/ooonana-deep-gui-20261012.5GxoogpS/run.log`.
- Latest actual GTK long-starttime/unsigned-UID regression:
  `/var/tmp/ooonana-deep-uid-20261012.56AC6EIG/run.log`.
- Current offline-installed app/pinned runtime, private nonroot bubblewrap,
  read-only small QA model, 1280 MiB cgroup/no swap: CPU inference, JSON/SSE
  memory refusal, native GTK streaming/cancel/reuse and loaded-engine restart:
  `/var/tmp/ooonana-deep-ai-20261012.5l90VrgX/run.log`.
  CPU load/inference 8.695 s under parallel checks; not a hardware benchmark.
- Scan covered boot/persistence/shutdown guards, package/configuration recovery,
  service readiness/watchdog, kernel policy, cgroup/memory metrics, API/state,
  generation publication and desktop IPC/task controls. Physical gates stay open.

## Cleanup

Removed 229896 KiB (~224.5 MiB) allocated duplicate scratch payloads: three
completed BusyBox mode-test extractions and two completed GUI overlay trees.
Exact paths were resolved, checked for mounts/open files, then removed. Their
logs/screenshots remain; payloads can be regenerated, deletion has no undo.
Latest GUI proof, candidate/rootfs/runtime caches, releases, keys and all user
history/models/configuration remain. C/F scan did not justify removing archives
or other old unknown-provenance files.

Bytecode cleanup was rejected by tool policy before execution. Previously
blocked 6 GiB F: scratch image, synthetic persistence images, QA source copies
and temporary metadata stay untouched; no alternate deletion attempted.
WSL cleanup does not automatically shrink its VHD or return Windows free space.
C: approximately 4.2 GiB, F: 10.8 GiB; ISO staging still needs C: 20 GiB/F: 8 GiB.

## Assistant-owned remaining work

1. Firefox sandboxed picker/first-run journey after Terms decision; consent
   remains deferred. Installation/update, Documents/FUSE and controls passed.
2. Actual Chromium PDF viewer boot/input/Backspace and latency, when local-viewer
   policy allows. Embedded VM/input regressions are not that viewer proof.
3. New-base Qt file-picker/theme/dialog journeys beyond QTerminal close dialog.
4. Interactive new-base desktop/WSLg input: IME, keyboard/clipboard/text scaling,
   settings persistence, notifications, session lock/logout/suspend/resume.
5. Final-image kernel/BIOS/UEFI/service/GUI boot matrix after user creates image;
   inspect failures and patch only confirmed defects. No old-stage resume.
6. Installed Ooonana WSL migration only after resumed approval and verified full
   backup with safe disk headroom; accounts/history/models must survive.
7. Physical USB persistence/upgrade faults, unrelated-drive safety, wallpaper/
   cursor/DPI/multimonitor/hotplug and Wi-Fi/Bluetooth/silent audio/GPU/thermals/
   Task Manager counters when disposable hardware is available. User skipped now.
8. Real GPU/heavy-model inference, cancellation and memory handling on hardware.
9. Client signing enrollment/CI signing only if user resumes it. Private key local.

These are conditional validation/migration gates, not claims of unfinished known
feature fixes. Any subsequent shipped runtime/kernel/package fix requires a fresh
ISO; documentation/test-only changes do not. User performs ISO build.

Current launcher uses F-backed native scratch, not the historical C: 20 GiB
staging requirement above. See [current build instructions](../README.md#build-from-source).
Do not rerun this command while the user's October 14 build is active.

PowerShell, using the separate signed candidate:

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1' --repo '/mnt/winf/Ooonana/ooonana-os/build/full-i3-repo-0.10'
```
