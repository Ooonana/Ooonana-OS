# Ooonana Rufus USB

Use `ooonana-full-i3.iso` for normal USB boot.

Rufus settings:

```text
Boot selection: ooonana-full-i3.iso
Image mode: Write in ISO Image mode (Recommended)
Secure Boot: off
Target system: BIOS or UEFI
```

If Rufus shows `ISOHybrid image detected`, choose `Write in ISO Image mode (Recommended)`.
Use DD Image mode only as fallback if ISO mode fails on a specific machine.

Ooonana ISO layout:

```text
BIOS boot: GRUB MBR path
UEFI boot: /efi.img path from grub-mkrescue
GRUB menu: live, persistent live, installer, safe graphics installer
Volume label: OOONANAUSB
Payload limit: every copied file stays below the FAT32 4GiB limit
```

Persistence:

```text
GRUB entry: Ooonana OS Full i3 Live (persistent USB)
Partition label: OOONANA_PERSIST
Filesystem: ext4
```

After flashing with Rufus, create a second ext4 partition labeled
`OOONANA_PERSIST` using Linux, GParted, or another partition tool. Ooonana uses
it as the writable overlay for the live root, so user files, settings, Wi-Fi,
Bluetooth pairings, installed packages, and system changes survive reboot.
Persistence is accepted only when this partition belongs
to the same physical USB device as the read-only Ooonana boot media. An
internal disk with the same label is ignored.

Disk-write safety:

- Normal live mode mounts ISO and live rootfs read-only. Session writes use RAM.
- Persistent live mode writes only to `OOONANA_PERSIST` on boot USB.
- Neither live mode partitions, formats, or installs to internal disks.
- Installer entries can write selected target only after installer confirmation.

Verify an ISO:

```bash
bash scripts/verify-rufus-iso.sh \
  --iso /var/tmp/ooonana-os/release/ooonana-full-i3.iso
```

Expected marker:

```text
OOONANA_RUFUS_ISO_OK
```
