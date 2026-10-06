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
Writable ISO-mode USB: ooonana-persistence.ext4 (first-boot size + CREATE prompt)
DD-mode USB / partition alternative: OOONANA_PERSIST ext4 partition
```

On a writable FAT32/ext4 ISO-mode USB labeled `OOONANAUSB`, first persistent
boot asks for storage size in MiB, then exact `CREATE` confirmation. It creates
one ext4 filesystem inside `ooonana-persistence.ext4`; no manual partitioning.
Later boots reuse it automatically. FAT32 caps the file at 4095 MiB; 256 MiB
remains outside it. It is fully allocated, not sparse. Cancel/invalid input
does not change boot storage; missing storage stops in recovery, never fake
persistence in RAM. Prompts time out after two minutes without input.

DD mode leaves boot ISO9660 read-only. For this path, or larger partition-backed
AI storage, create a second ext4 partition labeled `OOONANA_PERSIST` in verified
unused space using Linux/GParted. Ooonana never repartitions automatically.
Do not keep both storage backends on one USB: ambiguous saved sessions refuse.

Both paths use a full writable live-root overlay: user files, settings, Wi-Fi,
Bluetooth pairings, installed packages and system changes survive reboot.
Writes go directly to USB, not a shutdown-only RAM snapshot. Save app work and
shut down normally before unplugging. UUID verification restricts writes to
boot USB; same-label internal/unrelated disks are ignored.

Disk-write safety:

- Live rootfs image remains read-only. File-backed storage requires boot filesystem writable; partition-backed storage leaves boot filesystem read-only.
- Normal live mode uses a separate temporary overlay inside existing verified persistence storage, cleared at next normal boot. No storage means RAM; normal mode never creates a storage file.
- Persistent live mode writes only to verified boot-USB persistence. File setup formats only its newly created temporary file, publishing it after verification; it never reformats existing files/devices.
- Neither live mode partitions, formats, or installs to internal disks. Saved overlays are not reset/repaired automatically.
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
