# Installed candidate integrity — November 2, 2026

Core 0.10.0 candidate; stable is not promoted. This continues items10–15.
Installed Ooonana WSL release sync, remote push/CI, production publication,
signing enrollment and ISO creation remain held. No sound or models are used.

## Repairs

- Real installs write directly probed filesystem UUIDs for root, home, EFI and
  swap, including retained partitions. Cached identities and installer-specific
  `/dev/vdb*` names cannot become the installed fstab. Missing, empty or malformed
  UUIDs refuse publication; a same-directory atomic replacement preserves the
  previous file on generation, chmod or rename failure. The success marker
  follows fstab publication.
- Installed root is explicitly shadowed and locked, including sources with a
  missing root shadow record or an inline empty passwd field. Duplicate root
  records refuse installation. Installer identity options are checked before
  target mutation; root aliases and system accounts cannot become the selected
  desktop user. Follow-up checks cap usernames at32 characters and single-label
  hostnames at63, with no trailing hostname hyphen. Invalid values refuse before
  target mutation; valid boundary lengths pass. PAM rules and the user's normal
  authentication remain intact.
- Retained-root copying uses rsync content checksums. Reproducible timestamps
  and equal file sizes do not prove that a prior interrupted copy is complete.
  Unrelated retained files remain in place.

## Reproduced failures and evidence boundary

A full private install completed EFI and BIOS GRUB installation and UUID fstab
generation. Standalone BIOS boot renamed its target from `/dev/vdb` to
`/dev/vda`, mounted EFI and enabled configured disk swap alongside zram.
Normal user authentication then failed before any password prompt.

Actual PAM diagnostics found zero-filled vendor login policies in the retained
target. The PAM library matched its signed archive. The source image's policies
matched the signed vendor archive both before and after its native PAM upgrade.
This isolates the bad bytes to the retained target; it does not establish the
original cause of those bytes. A normal size/mtime rsync comparison had skipped
them. No authentication-policy weakening or replacement rule was used.

The eight temporary policy copies created during diagnosis were removed only
after confirming that each was an owned, zero-filled copy identical to its
target vendor file. Existing i3lock and su-l policies were retained.

Source regression tests and ShellCheck pass, including UUID failure injection,
root-record policy and an actual same-size/same-timestamp rsync repair fixture.
The real checksum reinstall passes. Every vendor PAM policy matches its source
bytes afterwards, including the previously zero-filled login policy. Actual
EFI and BIOS GRUB installation both complete successfully.

Standalone BIOS and UEFI boots now both pass without direct kernel/initramfs
injection: locked-root and wrong-password rejection, correct nonroot login,
password-authenticated sudo, EFI UUID mounting, disk swap plus zram and clean
shutdown. Their target changes from installer `/dev/vdb` to standalone
`/dev/vda`; the UUID fstab remains correct. The unrelated canary stays unchanged.

Receipts under `F:\Ooonana\ooonana-os\build\native-vm-20261101\receipts`:

- `install-e1000e-whpx-multi-icount0-1793624817015499700.log`
- `bios-e1000e-whpx-multi-icount0-1793625591196531600.log`
- `uefi-e1000e-whpx-multi-icount0-1793625655711308600.log`

The private core archive contains installer SHA256
`e0db9b3acac4b271deb06e95bbd77c1e3acb6d8c3c9e44017fbb4f8c2b41f6e8`.
Its QA-signed catalog passes closure/native-control verification at711 packages
and630 dependency nodes. This is a private test generation, not publication of
the final candidate or a source-freeze claim.

## Private infrastructure and remaining work

### November 3 console follow-up

The real installed console exposed a separate logo defect: BusyBox getty treats
backslashes/percent characters in `/etc/issue` as escapes. The canonical plain
logo remains unchanged for MOTD/other surfaces; the shipped issue asset now
escapes those characters, and scratch generation retains it. Fresh core
packaging contains the exact current installer and issue bytes. Logo, scratch
rootfs, reproducible tarball and ShellCheck tests pass.

Actual candidate BusyBox getty renders the complete mascot correctly in80- and
40-column disposable VM PTYs. The rendered text was reviewed using Impeccable's
polish/craft guidance; its shape and scale are preserved. Receipt:
`fault-e1000e-whpx-multi-icount0-1793664340961602200.log`, marker
`OO_NATIVE_GETTY_LOGO_RENDER_PASS`. Existing untracked/custom issue configuration
uses normal package preservation and may receive a pending `.ooonana-new`
default; no installed WSL configuration was changed.

Upstream escape handling: [BusyBox login issue renderer](https://raw.githubusercontent.com/mirror/busybox/master/libbb/login.c).

Initial installed update-fault QA attempts remain failed evidence. The first metadata rejection came from
Windows-generated CRLF fixture metadata/hooks; the fixture was normalized and
QA-signed again. A later run stopped when C: crossed the reserve. A512MiB
attempt reached no firmware output before its bound. A768MiB run subsequently
passes actual login/sudo and the getty render check. None of the earlier
attempts is counted as an update/recovery pass. Images and receipts remain.

### November 3 installed update/fault acceptance

Read-only virtual FAT media replaces the native HTTP forwarder for these tests;
both transport attempts retain their own boundaries. Signature requirements and
the ephemeral QA public key remain enforced. No physical device is attached,
no private key is exposed, and host media is never writable by the guest.

The installed system now passes actual signed-fixture package installation,
failed-health rollback and a successful upgrade preserving local configuration
with a separate new factory default. The host forcibly stops QEMU only after
the next update has synced its prepared checkpoint and entered its health hook.
After reboot and real nonroot PAM/sudo login, new package writes refuse the
pending checkpoint. Explicit recovery restores the prior version, payload,
custom configuration and previous pending default. A second recovery reports
no interrupted checkpoints; normal shutdown succeeds; the canary stays intact.

A separate32MiB ext4 target in the same disposable VM receives a signed40MiB
payload. Real `ENOSPC` during unpack triggers rollback. Prior payload, metadata
and custom config remain correct; the partial large file is removed; no pending
checkpoint remains. Offline `e2fsck -fn` passes all five phases afterwards.
The main installed package state and canary remain unchanged.

Receipts:

- `fault-e1000e-whpx-multi-icount0-1793664951411675000.log`
- `recover-e1000e-whpx-multi-icount0-1793665142980879300.log`
- `fullstorage-e1000e-whpx-multi-icount0-1793665290505805200.log`

These close the bounded installed package-checkpoint failure cases. They do not
certify arbitrary power-loss timings, kernel/bootloader replacement, an entirely
full system root or physical USB media. Those remain release/manual gates.

Native Windows QEMU avoids the earlier WSL/F: image-transfer bottleneck. Its
existing WHPX accelerator boots this kernel without changing host features or
kernel/APIC policy. TCG attempts had intermittent pre-userspace timer failures;
their logs remain evidence, not a certified diagnosis of a kernel defect.

Only owned regular image files are attached. The source image is read-only;
the target is disposable; an unrelated canary is checked. Networking is
restricted to the local private QA HTTP repository, with an ephemeral QA key.
Production trust and the published repository generation remain unchanged.
Disk/RAM reserves are checked before and during runs; no physical disks are
passed through.

Still required: broader system/kernel upgrade and physical fault acceptance;
login1/seat/inhibitor/lock-before-sleep integration;
physical controls and persistence tests. Real cloud AI needs fresh credential
authorization. PDF is item16, outside this pass. Earlier bounded UI/PAM/input
passes remain valid within their documented limits.
