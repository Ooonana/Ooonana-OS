# Persistent live USB safety

Priority: reliability and data safety. No automatic partitioning, device
formatting, fsck repair, or deletion of saved overlays. First persistent boot
may create/format a new storage file after explicit size + `CREATE` confirmation.

## Boot policy

- GRUB probes its root filesystem UUID and passes `ooonana.live.boot_uuid`.
  Writable storage requires matching removable/USB boot media. Cloned UUIDs
  visible on different parent disks are ambiguous and stop boot before writing.
  ISO9660 UUIDs need a read-only fallback because release BusyBox reports only
  ISO label/type. At most 16 descriptors are inspected; valid primary descriptor
  modification digits form GRUB's UUID. Invalid/truncated descriptors refuse.
  Native FAT/ext4 UUIDs take precedence; label-only matching is never allowed.
- Exactly one storage backend: ext4 `OOONANA_PERSIST` partition on that boot
  parent, or `ooonana-persistence.ext4` directly on its writable boot filesystem.
  Both present refuses to guess. Same-label internal disks and unrelated USB/SD
  devices cannot satisfy selection. File path rejects symlinks, nonregular files,
  hardlinks, unexpected ext4 label/type and undersized images; no recursive search.
- MX-style static file setup runs only in requested persistent mode on verified
  FAT32/ext4 boot media without existing storage. Size range starts at 256 MiB,
  reserves 256 MiB outer space, caps FAT32 at 4095 MiB. Prompts use physical tty1
  or serial-only console, require exact `CREATE`, and time out after 120 seconds.
  Identity and free space rechecked after confirmation, before writable remount.
  DD/ISO9660 cannot create files; separate prepared persistence partition needed.
- Setup fully allocates a newly owned temporary file, formats it using bundled
  e2fsprogs, verifies ext4 identity, syncs, then publishes by no-clobber rename.
  Existing storage files never overwritten. Cancellation/invalid size never
  remounts boot storage writable. Interrupted power loss may leave an unpromoted
  temporary file; it is never auto-adopted/deleted. FAT32 is not journaled; ext4
  inner journaling does not guarantee outer filesystem power-loss protection.
  File-backed storage uses loop1, records `persistence-file` in live metadata,
  retains outer filesystem mount, and uses existing shutdown/storage monitoring.
- Before file-backed FAT gains a writable mount, its Linux extended-BPB dirty
  state is checked read-only. Dirty/unreadable state refuses both saved-file
  attachment and new-file creation, keeping the boot filesystem read-only.
  Back up the USB, then check/repair the unmounted filesystem offline with an
  explicitly selected target. Boot never clears the flag or repairs FAT itself.
  The flag is a limited safety gate, not a complete fsck or a guarantee against
  controller/cache power-loss faults. Implementation follows the kernel's
  [FAT mount-state handling](https://github.com/torvalds/linux/blob/v6.18/fs/fat/inode.c).
- `ooonana.persistence=1` is an exact kernel argument. Missing storage gets a
  bounded discovery wait, then eligible file setup or recovery; it never becomes an apparently saved
  RAM session. Duplicate arguments for boot identity/root image are rejected.
- The base image is attached read-only; ext4 lower layers use `ro,noload`.
  Its resolved path must remain inside the mounted boot filesystem.
- Saved `overlay/upper` and `overlay/work` must be real directories, not
  symlinks/files. Directory creation and mount failures are explicit errors.
  Existing saved upper data is never reset.
- Saved overlays record root-image filesystem UUID in `overlay/base-id`.
  Different ISO bases and legacy nonempty overlays without that marker stop
  before mounting the overlay. Empty first-use overlays receive the marker
  atomically. No old system files silently hide new boot services.
- A disposable write probe checks storage readiness. At least 16 MiB must be
  available before persistent startup. Session monitor checks free space,
  inodes and read-only state once per minute, with silent, rate-limited warnings;
  it never deletes files or guarantees protection from disk-full writes.
  Normal ext4 journal replay can write the selected persistence
  filesystem during its read-write mount; no automatic fsck repair is run.
- Normal live clears only guarded `temporary-overlay` inside verified storage;
  saved `overlay` remains separate. With no matching storage it uses RAM.
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
ISO UUID format follows [GRUB's ISO9660 implementation](https://github.com/rhboot/grub2/blob/master/grub-core/fs/iso9660.c).

## Verification

`tests/test-live-boot-storage.sh` uses fake device metadata and temporary files.
It covers exact arguments, duplicate/cloned identities, wrong-parent selection,
filesystem checks, path rejection, low space, unwritable probes and rcS markers.
Release preflight and GitLab smoke include it. `tests/test-live-persistence-file.sh`
covers size limits, reserved space, unsafe/hardlinked files, exact confirmation,
cancellation and integration; both CI providers run these file-policy checks.

`tests/test-iso-boot-uuid.py` checks bounded ISO UUID probing, malformed input,
native UUID precedence, mismatched identity and byte-identical source media.
It runs inside the full-i3 live-initramfs suite. `tests/qemu-live-iso-uuid.sh`
boots current live-init source/release BusyBox through BIOS and UEFI GRUB against
an existing ISO attached as read-only USB. Its disposable bootstrap CD contains
no production rootfs; original ISO is not rebuilt, patched or promoted. This
checks the corrected identity handoff, not the final user-rebuilt release ISO.

`tests/qemu-live-persistence.sh` builds a tiny fixture initramfs using release
BusyBox plus the current live-init source. It attaches only newly created regular
file USB images, never host disks. It checks save/reboot, temporary reset, saved
data surviving normal boots, missing identity/storage and cloned boot UUIDs.
An unrelated same-label USB image must remain byte-identical across tests.
Additional cases cut power to the disposable QEMU process after a committed
sentinel while another file is being written, then verify the sentinel returns.
ENOSPC fixtures fill only their disposable overlay, require low-space boot
refusal without RAM fallback, reclaim one known filler offline and reboot with
saved data intact. Partition and file backends are covered; file recovery checks
both inner ext4 and outer ext4/FAT before restoring the fixture. Use
`--file-space-only --format-rootfs DIR` for the file-backed ENOSPC subset.
Real guest package upgrade interruption/recovery is included;
`--upgrade-only` runs just that pair. These are VM crash simulations, not physical
USB/controller power-loss certification.
No production ISO is built. Example, with already available kernel/seed files:

```bash
bash tests/qemu-live-persistence.sh \
  --kernel /path/to/vmlinuz-ooonana \
  --seed-initramfs /path/to/live-initramfs.cpio.gz
```

Add `--format-rootfs /path/to/full-i3-rootfs` to include ten extra file-storage
cases using bundled musl e2fsprogs and its dependency closure: cancellation and
oversized input leave the boot image byte-identical, confirmed create/reboot,
temporary reset, saved data surviving temporary boots, and a real ext4 mount
failure with unsupported feature bits. That failure must leave the outer USB
read-only, loop detached and saved image byte-identical. Successful boots require
QEMU exit status zero, actual power-down, no cleanup/dirty-volume warnings, and
read-only inner/outer markers; offline filesystem checks inspect both layers.
Additional fault cases abort after all handoff mounts move, and inject an
ordinary shutdown-unmount failure. Three rescue-shell exits must keep PID1's
shutdown action alive with no power-down or false cleanup-success marker.
Run with both
`--boot-fs ext4` and `--boot-fs vfat`; only disposable file-backed USBs attach.
The file-backed crash case on FAT must refuse the dirty outer filesystem without
changing any USB bytes. Explicit offline fsck runs only on a copied regular-file
test image; subsequent boot must restore the committed sentinel. Ext4-backed
files exercise journal replay directly. No unsynced draft is promised to survive.

For hardware-accelerated fixtures, set `OOONANA_QEMU_ACCEL=kvm`; default is TCG.
Persistence guest deadline defaults to 180 seconds (positive override:
`OOONANA_QEMU_PERSIST_TIMEOUT`) to avoid false failures during emulated discovery.
Example ISO identity test with an existing artifact:

```bash
OOONANA_QEMU_ACCEL=kvm bash tests/qemu-live-iso-uuid.sh \
  /path/to/ooonana-full-i3.iso /path/to/vmlinuz /path/to/live-initramfs.cpio.gz
```

## Remaining gates

- User builds a fresh ISO, then verifies Rufus ISO mode and DD mode on physical
  BIOS/UEFI hardware. Back up persistent data before reflashing; a writer may erase
  the whole selected USB, including its persistence partition.
- Confirm saved files, network settings and package changes across clean reboots;
  confirm unrelated SSD/USB/SD disks stay unchanged. Avoid power-cut tests with
  valuable data; controlled crash recovery needs disposable media.
- Physical RAM/swap, USB disconnect and filesystem-error handling still need
  hardware regression checks. No audio playback or signing enrollment occurs.

## Orderly shutdown

Fresh full-i3 and minimal images run BusyBox init. `bunana --shutdown` and
`--restart` signal init normally; no forced fallback. Its guarded shutdown action
terminates writers, waits two seconds, kills remaining processes, syncs,
disables swap and unmounts/remounts filesystems read-only before final sync.
Direct host/WSL invocation of cleanup is refused. QEMU persistence fixtures
require the cleanup marker before successful save/reboot verification.
File-backed live boots retain a small private RAM shutdown root and run PID1
from its BusyBox/musl copy. Cleanup pivots there, releases the overlay, unmounts
inner ext4, detaches its writable loop, then remounts/unmounts the outer USB.
Original storage mounts are moved into the desktop instead of leaving hidden
writable mounts behind. Ordinary unmounts only: no forced/lazy unmount or global
emergency-remount workaround. An incomplete RAM cleanup stops for diagnosis;
the parent shutdown action stays alive while launching rescue children. Closing
or exiting a rescue shell returns to that hold, never to PID1's poweroff path.
It does not silently report a clean shutdown. Failed boot likewise releases its
own loop and restores read-only boot storage before entering recovery.
Unmount warnings remain visible; hardware write-cache/power-loss behavior needs
physical testing. Applications may lose unsaved in-memory work at shutdown.

Upgrade changes only the single exact known legacy shutdown action; other lines,
including installed getty/login entries, remain unchanged. Custom shutdown actions
are not rewritten. Review `.ooonana-new` without importing live root-shell lines.
Keep installed getty/login lines and replace only legacy
`::shutdown:/bin/umount -a -r` with:

```text
::shutdown:/usr/bin/ooonana-shutdown-cleanup --from-init
```

## Offline backup and data-only migration

Run from another Linux system, never the active persistent/temporary USB session.
Select and mount the intended ext4 partition yourself; tools never mount, format,
repair, enumerate/select writable disks, or delete saved data. Verify UUID first.
Backup needs a read-only `ro,noload` whole-filesystem mount and a new destination
directory on a different Linux filesystem supporting ownership, links and xattrs.
Use sanitized placeholders below, not guessed device paths:

```sh
sudo ooonana-persistence backup --mount /mnt/confirmed-persistence \
  --expect-uuid CONFIRMED-PERSISTENCE-UUID --output /safe/other-filesystem/usb-backup
```

Export verifies file hashes, modes, ownership, timestamps, symlinks, hardlinks,
special nodes and extended attributes. Incomplete exports remain private staging
directories, never promoted as verified backups. Sockets/unsupported metadata
fail clearly. Filesystem contents must remain offline; this is not a live snapshot.

For a new ISO, read its root-image UUID from normal live mode's
`/mnt/ooonana-live/base-id`, then shut down. Remount the confirmed persistence
filesystem read-write from another Linux system and run:

```sh
sudo ooonana-persistence migrate --mount /mnt/confirmed-persistence \
  --expect-uuid CONFIRMED-PERSISTENCE-UUID --base-id NEW-ROOT-IMAGE-UUID \
  --backup /safe/other-filesystem/usb-backup \
  --confirm-data-only CONFIRMED-PERSISTENCE-UUID
```

Migration requires an unchanged, metadata-verified backup and sufficient free
space. It copies only saved `home` data into a fresh upper layer, strips overlay
xattrs/whiteouts there, and atomically exchanges directories. Complete original
overlay/work/base identity remains at the printed `overlay.previous-*` path;
nothing is deleted, and failed exchange leaves the original active overlay.
Accounts, packages, network/system configuration are not imported automatically;
recreate previous account UIDs and selectively reapply configuration from backup.
This avoids stale system binaries masking the new ISO. Keep backups/previous
overlay until verified. Atomic rename does not replace physical crash testing.
