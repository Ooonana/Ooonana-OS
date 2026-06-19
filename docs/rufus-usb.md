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
`OOONANA_PERSIST` using Linux, GParted, or another partition tool. Ooonana
bind-mounts persistent `/home`, `/etc/ooonana`, `/var/lib/ooonana`, and
`/var/cache/ooonana`.

Verify an ISO:

```bash
bash scripts/verify-rufus-iso.sh \
  --iso /var/tmp/ooonana-os/release/ooonana-full-i3.iso
```

Expected marker:

```text
OOONANA_RUFUS_ISO_OK
```
