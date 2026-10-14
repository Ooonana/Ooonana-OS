# Computer junk and RAM review - 2026-10-14

## Scan coverage

Read-only file metadata walk; no personal file contents uploaded or cloud
placeholders hydrated. Reparse points and inaccessible paths skipped.

| Volume | Files | Directories | Reparse skipped | Access gaps |
| --- | ---: | ---: | ---: | ---: |
| C: | 1,131,773 | 221,005 | 6,388 | 172 |
| F: | 528,694 | 70,028 | 163 | 3 |

Local-only detailed evidence:
`C:\Users\7ryan\AppData\Local\Temp\ooonana-computer-audit-b9b04dc1cad3437cb5b67415dd6ada9c\`.
Contains volume summary, candidate-directory paths, large-file metadata and
access gaps. These private inventories are not committed to Git.

Ubuntu/Ooonana native roots reviewed with mount-bounded disk inventories,
scratch/model filename checks and active-process/mount inspection. Ubuntu root
uses ~41.2 GiB; imported Ooonana root ~13.8 GiB (logical guest usage, not host VHD
allocation). Ubuntu Codex history (~7.7 GiB), caches needed by remaining tests,
kernel sources, signed repositories and small CPU QA model preserved. No model
weights found in the inspected Ooonana home/root/opt/native temporary paths;
this does not certify every possible filename or external Windows model store.

## Confirmed junk, removal blocked

Execution policy rejected the cleanup command before it ran. No payload was
removed in this pass; no alternate deletion, parent deletion or policy bypass.

- Inactive generated initramfs expansion:
  `/var/tmp/ooonana-recheck.zK9MDI/patched-live-tree` (~448 MiB).
- Its old QA kernel/initramfs copies under `boot/` (~204 MiB).
  Parent source/.git, logs and test history were to remain.
- Duplicate 229,347-byte C: QA `openvino-chat-0.2.1.tar.gz`, SHA256
  `63bfb0d40345360101b665c71811068d6e36ffa89e2396e1e48f09d3252d6d4d`.
  Matching second QA archive verified before attempted removal; both remain.

Existing policy-blocked targets from prior passes remain excluded. Personal
downloads/models, game/VM disks, valid releases, signing keys, current F-backed
staging and unknown-owner/current OpenVINO QA directories preserved. F: storage
probes contain retained logs rather than disposable image payloads; no confirmed
safe F: payload deletion selected. Do not equate disk cleanup with available RAM.

## RAM verification accounting

Reproduced the user's disk-verification refusal with Windows free physical RAM
below 3.5 GiB despite ~7 GiB Linux `MemAvailable`. Idle-only WSL shutdown and
one debugging clean-cache reclaim were attempted without killing user apps,
moving VHDs, changing `.wslconfig` or lowering reserves. Cold resume still
refused, so operational advice alone was insufficient.

Guard now estimates reusable memory already resident in the WSL VM, rather than
counting the whole guest allocation as additional Windows physical allocation:

`credit = min(Linux available, max(0, resident WSL - (Linux total - available) - 512 MiB))`.

Only one observable `vmmemWSL` process can supply credit; missing/ambiguous or
oversized VM readings credit zero. Virtual VM maximum alone never supplies credit. Sampling
uses lower Windows/resident readings across two samples and refreshes Linux
availability afterward. Invalid data refuses. Existing Linux and effective-host
ISO/guest/2-GiB reserve guards remain. Extra 512 MiB VM overhead excluded.
Windows must independently retain at least 1 GiB immediately free physical RAM.
This is conservative accounting, not a promise against unrelated future app
allocations or a general recommendation to drop Linux caches.

Unit/source/ShellCheck checks passed. Live disk budget passed with Windows
free 3,054,768 KiB plus 700,696 KiB resident credit, total 3,755,464 KiB,
versus 3,670,017 KiB required. Full existing-ISO resume completed: static/Rufus,
service, BIOS and UEFI gates passed, checksum/promotion completed, and the
temporary C: ISO copy was removed. No fresh ISO construction or WSL migration.

Published candidate: `F:\Ooonana\ooonana-os\release-current\ooonana-full-i3.iso`,
2,895,407,104 bytes. Independent Windows SHA256 matched its sidecar:
`96dc45a2f27f0cd6e0e2e4e76b78af0604b3cbe79231c3eddadd1fc85c94c86d`.

The full-resume service log exposed legacy virtual `e1000` Tx-hang warnings.
Host-only smoke harness now uses q35's PCIe `e1000e`; health checks reject
Tx-hang/watchdog errors even with success markers. Actual published-ISO retest
passed service/fault/clean-shutdown gates without those errors. Evidence:
`F:\Ooonana\ooonana-os\build-diagnostics-20261014\service.va5T6eo1.log`.
This does not certify physical Wi-Fi, which was explicitly skipped.

Latest post-publication storage snapshot: C: ~5.1 GiB, F: ~17.1 GiB free.
Future full-workspace setup refused its full-capacity-plus-8-GiB reserve check;
guard was not bypassed. The extra published-ISO probe used ~0.7 GiB native QA
scratch with its own 3-GiB C: headroom check and cleaned that scratch afterward.
Completed candidate needs no rebuild for these host-only repairs; future fresh
builds still need enough F: capacity. No manual junk removal was executed.

Supporting API semantics: [Microsoft WorkingSet64](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.workingset64)
describes physically resident process pages, including shared/private pages;
the accounting above additionally excludes guest-used memory and VM overhead.
[Kernel cache documentation](https://docs.kernel.org/admin-guide/sysctl/vm.html#drop-caches)
limits cache reclaim to clean/reclaimable objects and warns about performance.
