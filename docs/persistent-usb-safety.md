# Persistent live USB safety

Priority: reliability and data safety. No automatic partitioning, formatting,
fsck repair, or deletion of saved overlays.

## Boot policy

- GRUB probes its root filesystem UUID and passes `ooonana.live.boot_uuid`.
  Writable storage requires matching removable/USB boot media. Cloned UUIDs
  visible on different parent disks are ambiguous and stop boot before writing.
- Exactly one ext4 `OOONANA_PERSIST` partition must exist on that boot parent.
  Same-label internal disks and unrelated USB/SD devices cannot satisfy selection.
- `ooonana.persistence=1` is an exact kernel argument. Missing storage gets a
  bounded discovery wait, then recovery; it never becomes an apparently saved
  RAM session. Duplicate arguments for boot identity/root image are rejected.
- The base image is attached read-only; ext4 lower layers use `ro,noload`.
  Its resolved path must remain inside the mounted boot filesystem.
- Saved `overlay/upper` and `overlay/work` must be real directories, not
  symlinks/files. Directory creation and mount failures are explicit errors.
  Existing saved upper data is never reset.
- A disposable write probe checks storage readiness. At least 16 MiB must be
  available before persistent startup. This startup check is not ongoing disk-full
  protection. Normal ext4 journal replay can write the selected persistence
  partition during its read-write mount; no automatic fsck repair is run.
- Normal live clears only guarded `temporary-overlay` on verified boot media;
  saved `overlay` remains separate. With no matching partition it uses RAM.
  Unsafe/unmountable matching storage stops boot. Without a GRUB UUID, normal
  direct-kernel boots use RAM without mounting persistence writable.
- Critical bind/move failures stop live handoff. Saved symlinks cannot redirect
  handoff directories/status files. rcS emits `OOONANA_PERSISTENCE_OK` only after
  its bind succeeds; failure emits `OOONANA_PERSISTENCE_FAILED`.
- Release resume fingerprints include the storage helper, so storage-policy
  edits invalidate stale rootfs stages.

UUID checks protect against accidental selection, not malicious removable media.
The installer is separate and still requires confirmation of its target.
Reference: [GRUB probe command](https://www.gnu.org/software/grub/manual/grub/html_node/probe.html)
and [kernel OverlayFS requirements](https://docs.kernel.org/filesystems/overlayfs.html).

## Verification

`tests/test-live-boot-storage.sh` uses fake device metadata and temporary files.
It covers exact arguments, duplicate/cloned identities, wrong-parent selection,
filesystem checks, path rejection, low space, unwritable probes and rcS markers.
Release preflight and GitLab smoke include it.

`tests/qemu-live-persistence.sh` builds a tiny fixture initramfs using release
BusyBox plus the current live-init source. It attaches only newly created regular
file USB images, never host disks. It checks save/reboot, temporary reset, saved
data surviving normal boots, missing identity/storage and cloned boot UUIDs.
An unrelated same-label USB image must remain byte-identical across tests.
No production ISO is built. Example, with already available kernel/seed files:

```bash
bash tests/qemu-live-persistence.sh \
  --kernel /path/to/vmlinuz-ooonana \
  --seed-initramfs /path/to/live-initramfs.cpio.gz
```

## Remaining gates

- User builds a fresh ISO, then verifies Rufus ISO mode and DD mode on physical
  BIOS/UEFI hardware. Back up persistent data before reflashing; a writer may erase
  the whole selected USB, including its persistence partition.
- Confirm saved files, network settings and package changes across clean reboots;
  confirm unrelated SSD/USB/SD disks stay unchanged. Avoid power-cut tests with
  valuable data; controlled crash recovery needs disposable media.
- Replace forced shutdown with tested orderly service stop/unmount sequencing.
- Add disk-space warnings during sessions, backup/export and explicit migration
  for saved overlays when the base ISO changes. Old upper files can hide newer
  lower files; no migration/reset is claimed by this patch.
- Physical RAM/swap, USB disconnect and filesystem-error handling still need
  hardware regression checks. No kernel rebuild, swap-policy change, WSL upgrade,
  audio playback or signing enrollment occurs in this pass.
