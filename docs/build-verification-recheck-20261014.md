# Build verification and cleanup - 2026-10-14

## Follow-up: disk verification instead of RAM mirroring

Repeated RAM refusal is a host-resource limitation, not another ISO build
failure. Added explicit `--verify-on-disk PATH`; RAM guard remains unchanged.
On WSL this path must be C: DrvFS, so no VHD expansion or another slow F: mirror.
The existing ISO is copied to a private temporary directory, compared byte for
byte, and used directly by QEMU rather than recopied into F-backed scratch.
Only its one copied ISO and empty directory are removed afterward; unexpected
files, symlinks or a changed mount refuse cleanup. No recursive disk-cache delete.

Destination and Windows C: must retain ISO-size-plus-2-GiB disk headroom.
Windows/Linux RAM must cover guest plus the unchanged 2 GiB reserve, not pinned
ISO media. Disk-backed service and simple BIOS/UEFI startup probes use the
already-used 1536 MiB service VM size by default (~3.5 GiB available RAM), or
the explicit `OOONANA_QEMU_MEMORY` value. This is verification VM sizing, not a
physical Ooonana RAM limit. Source/fixture/ShellCheck checks pass. Actual full
ISO copy/comparison, Rufus/static checks, service smoke and BIOS/UEFI startup
probes all passed with no guest I/O/OOM/panic errors. Temporary 2.90 GB C: copy
was removed; normal F-workspace unmount passed. Fresh helper copy/cleanup also
passed after ownership guards were added. No rebuild, promotion or installed
WSL change. Slow F: copy/comparison can take several minutes.

Evidence under `F:\Ooonana\ooonana-os\build-diagnostics-20261014\`:
`service.jQ5tj5Ro.log`, `disk-bios-ooonana-disk-verify.knCZ13cJ.log`,
`disk-uefi-ooonana-disk-verify.knCZ13cJ.log`.

## Original failure and retained evidence

User built the ISO; assistant did not rebuild or promote it. Full-rootfs audit
passed 174 scripts / 524 ELF files with zero errors. Staged ISO is
2,895,407,104 bytes; static hybrid, GRUB menu, kernel and payload checks passed.
First QEMU service run failed on NetworkManager and BlueZ readiness.

Actual repeat with the same staged ISO reached Wi-Fi profile, watchdog,
frozen-BlueZ recovery, silent audio routing, Chromium, desktop, privilege and
clean shutdown markers. However, serial also recorded an ATA/CD-ROM timeout and
`I/O error, dev sr0`. The former test accepted success despite that error.
This is not a clean verification pass. Slow/backing-media I/O was observed;
the exact first-run cause or physical USB reliability is not proven.

Retained serial:
`F:\Ooonana\ooonana-os\build-diagnostics-20261014\service.hr1bqqrq.log`.

## Host fixes and checks

- Service and BIOS/UEFI probes reject storage/filesystem errors, kernel panic
  and OOM regardless of success markers. Log read failures also refuse.
- Service failure diagnostics include processes, memory and kernel output;
  cold-start retries are bounded and preserve endpoint/fault assertions.
- Service serial evidence survives fixture cleanup; interruption exits safely.
- ISO resume checks requested kernel configuration/version, completed build
  markers, original input fingerprint and signed repository closure.
- Resume and final promotion refuse mounted children. Workspace cleanup checks
  loop ownership and retries ordinary unmount at most five times; busy/foreign
  mounts stay, with diagnostics. No forced unmount or unrelated process killing.
- F-backed builds require 1 GiB minimum C: headroom, independent of the F: budget.
- Optional `--verify-in-ram` mirrors existing ISO into nonswappable tmpfs only
  when Windows and Linux free RAM cover media, largest guest and 2 GiB reserve.
  Larger service-memory overrides count toward the budget.

Actual current staged provenance/fingerprint passed. These changes affect host
tools/tests/docs, not packaged runtime, firmware, cursor or kernel payloads.
No fresh ISO payload build is required for this pass. Original signed candidate
generation remains pinned rather than relabelling existing packages:
`5f8074ffabc6ed5848360cd1666d0c7f74ae9f2961656b6ade612efc192dbe8f`,
654 packages / 612 dependency nodes, clean runtime source revision
`2c7a925e1d9e6d0e7b4e8723350b036885a4a795`, core 0.10.0.

Passed source/fixture checks: launcher/F storage, RAM budget/ownership/log
predicates, release resume/repository closure, service smoke source, ShellCheck,
backend policy/regressions, readiness/watchdog, process-control IPC, state
recovery, interrupted updates, live storage/persistence/maintenance and kernel
source/build fixtures. Kernel was not recompiled during this pass.

Actual RAM preparation correctly refused with ~1.7 GiB Windows free RAM while
WSL was running; latest snapshot was ~2 GiB. The 2.90 GB ISO with 2 GiB guest needs ~6.7 GiB available on both
sides. Actual RAM-mirror integration and clean guest verification remain pending;
unit-test success does not certify them.

## Cleanup and storage

Deleted only redundant, inactive QA libraries:
`/var/tmp/ooonana-runtime-lock-verify/lib`, 467,228 KiB (~456 MiB).
Confirmed matching retained QA library tree before deletion; installation
metadata, configuration and file history remain under
`/var/tmp/ooonana-junk-review-20261014.lU0eUco4/`.
Guest logical space reclaimed does not guarantee equal host disk space.

Preserved F-backed workspace/staged ISO, signed generations, kernel/source
caches, releases, personal models, small CPU QA model, signing keys and history.
Previously policy-blocked targets were not retried or bypassed. No other
confirmed safe junk was removed. User compacted Ubuntu VHD; latest observed
C: ~9.8 GiB / F: ~17.5 GiB free. WSL distro locations unchanged.
No downloads, sound playback or private-key upload during this pass.

## Remaining work

1. User-run final checksum/promotion using the disk-backed resume command below.
   Actual service and BIOS/UEFI checks now passed; command repeats them before
   promoting. Existing October 6 release remains unchanged until then.
2. RAM-mirror integration is optional and still untested; disk verification
   removes this prerequisite. Do not disable either mode's resource guard.
3. Actual Chromium PDF-viewer boot/input/Backspace/latency; earlier tool-policy
   restriction remains, not bypassed.
4. Real session coverage still pending: WSLg input, Korean IME, clipboard,
   lock/logout/suspend/resume, physical DPI/multi-monitor/hotplug and GPU.
5. Heavyweight/GPU OpenVINO inference and physical hardware/persistence/upgrade
   fault tests remain separate. Hardware checks were explicitly skipped.
6. Installed Ooonana WSL migration remains deferred until a verified backup and
   sufficient storage; stable channel/installed WSL/October 6 ISO stay 0.9.9.
7. Repository signing enrollment stays deferred; private key remains local.

## Resume existing staged ISO using temporary C: disk copy

Run in PowerShell with at least ~3.5 GiB free RAM and ~4.7 GiB free C: disk
space (for this ISO). No `--verify-in-ram`:

```powershell
$repo = '/mnt/winf/Ooonana/ooonana-os/build/full-i3-repo-0.10/generations/5f8074ffabc6ed5848360cd1666d0c7f74ae9f2961656b6ade612efc192dbe8f'
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1' --repo $repo --resume-after-iso --verify-on-disk '/mnt/c/Users/7ryan/AppData/Local/Temp'
```

This skips ISO construction, verifies existing media and promotes only after
all enabled gates pass. No `--skip-boot-matrix`. Any subsequent packaged-input
change correctly refuses resume and needs a fresh normal build. Retain staged
media and the original generation until verification completes.
