# Both-distro cleanup and disk optimization — November 2, 2026

Ubuntu and Ooonana were inspected separately with mount-bounded native disk
inventories, cache classification, process/open-reference checks and receipts.
This follow-up includes installed Ooonana; the earlier C:/F: scan did not start it.

## Removed

| Distro | Confirmed regenerable junk | Result |
| --- | --- | --- |
| Ubuntu | Additional private Firefox QA caches, root pip HTTP/npm download caches, APT binary caches/downloads | About 619 MiB reclaimed inside Linux in this pass |
| Ooonana | Three Chromium code/GPU/cache directories | 36 KiB reclaimed; no substantial additional disposable cache found |

Ubuntu's earlier 263.8 MiB browser-cache cleanup is separate: approximately
883 MiB reclaimed there across today's two cleanup passes. Cached downloads
were removed, not installed Python/npm/APT packages. History, profiles,
credentials, models, signing keys, release/package generations, source,
toolchains and test checkpoints remain.

An old extracted rootfs was compared against its retained archive: 23,913
entries checked, archive SHA256
`3a74a4138629cd3f9488a2d13ecd625963b759d9c24fb12568aaefe1b9c31d1c`.
The metadata was not identical, so neither copy was deleted. Ubuntu still has
roughly 23 GiB of native temporary build/test inputs and retained checkpoints;
that total is not classified as disposable junk.

## Optimization

- Trimmed unused blocks in both mounted Linux filesystems. Large TRIM output
  describes virtual ranges submitted, not Windows space actually recovered.
- Waited for both distributions to idle/stop normally. No user session was
  forcibly terminated and no global WSL shutdown was issued.
- Ran the installed built-in `wsl --manage DISTRO --compact` sequentially for
  Ubuntu and Ooonana. Both reported successful completion. Disk locations
  stayed unchanged.
- Ubuntu VHD: 52,007,272,448 bytes before compaction; 50,780,438,528 bytes after
  subsequent boot checks: about **1.14 GiB smaller**, 48.44 to 47.29 GiB.
- Ooonana's small sparse VHD compacted successfully; subsequent boot metadata
  growth consumed the small initial reduction. No material lasting F: saving
  is claimed for it.
- Final free-space snapshot: **C: 2.80 GiB; F: 19.18 GiB**. Host usage fluctuates.

Installed WSL release packages, memory/CPU limits, models, private keys,
production repository, remote Git and ISO were not updated or relocated.
Production CURRENT remains
`4bf64022f11e74d5b8d24ada04d2eebc703d8f1431045e7683343bdf5f243a2e`.

## Verification and limits

Both distros passed a private 64 KiB write/fsync/cache-discard/readback probe;
the probe file was removed and its parent directory synced afterward.
Ubuntu `dpkg --audit` passed. Ooonana core/core-runtime/i3wm/linux-pam integrity
checks passed. All selected cleanup targets were absent at verification.

The first post-compaction probe detected a buffer-I/O warning in the previous
shared WSL kernel log for device `sdd`. Both distro probes saw that same shared
entry; it was not evidence of two independently failed disks. Exact timing and
cause were not established, and the failure receipts were preserved. A later
cold WSL boot had no storage-error recurrence in the sampled log. Ubuntu's
ext4 header reported clean and its error counters were zero; both read/write
and package checks subsequently passed. This is not a full offline filesystem
check or physical-disk certification. No filesystem repair was attempted.

Private receipts, initial failed checks and final passing checks:
`C:\Users\7ryan\AppData\Local\Temp\ooonana-cleanup-20261102\`.
No audible testing or model download occurred.
