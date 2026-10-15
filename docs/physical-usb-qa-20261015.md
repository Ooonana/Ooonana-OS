# Physical USB and remaining GUI gates - 2026-10-15

## Completed from Windows

Confirmed local target: Disk 2, G:, VendorCo ProductCode, 31.5 GB,
FAT32 `OOONANAUSB`. User explicitly confirms disposable fault-test data.
Internal C: NVMe and separate F: storage are not test targets. No formatting,
partitioning, writable raw-device access or fault injection performed.

All four flashed payload SHA256 values match the published verified ISO:

| Payload | SHA256 |
| --- | --- |
| boot/vmlinuz | bc30e38e0ff539ac3b573a03a15c763ee49c072224e2d4620ba2e2be910065a3 |
| boot/live-initramfs.cpio.gz | d3cb4cc6a3edf7a05739d324df9d5bb1d77eee6499c69a99b913abaaaee1aeef |
| images/ooonana-full-i3-live-rootfs.ext4 | ce514c1217a83445234a9f278805212d7a0772db90d422a6169fcde21fb1c494 |
| efi/boot/bootx64.efi | a1aa30ae9100ab2aea6d571ab2bf60ca02562ac1ef8a65955474d138c4ea5dd3 |

EFI loader and persistent GRUB entry present; boot UUID comes from GRUB probe.
No persistence file exists yet. Windows volume health reports Healthy; that
does not certify Linux FAT dirty-state handling or power-loss recovery.

Installed Firefox launcher 1.0.1 and QTerminal 2.4.0 plus declared Qt6 dependencies
using the current native Ooonana signed-snapshot source as UID1000. Package
verification and offscreen QTerminal version check passed. Browser Flatpak
runtime has not been downloaded; GUI first-run/pickers are not certified.
WSLg X11/Wayland sockets exist, not proof of interactive input/session behavior.

## Current blockers

Computer Use initialization and reset/retry fail before any UI action:
`failed to write kernel assets: The system cannot find the path specified.`
Browser tool initialization fails identically. No alternate native automation,
helper protocol, local-PDF navigation bypass or security-setting change used.
Real PDF viewer/input/latency and Windows-to-WSLg input remain untested.
Restart/repair Codex UI helper and manually open the existing bootable PDF first.

USB can boot only this same PC; user chose manual boot/test steps. Windows
connection alone cannot certify Linux persistence, true power loss or recovery.
Signing enrollment/stable promotion scope answer is still pending; private key
stays local, no signing/publishing action taken. Existing WSL public PEM matches
documented SHA256 `951dabde44988d9db87ed146f483322a5830c8ceaaad07dde4e75aeca42ae34d`;
key presence is not enforced client enrollment.

## Manual stage 1: baseline and clean persistence

1. Keep source ISO available. Boot USB; choose
   `Ooonana OS Full i3 Live (persistent USB)`, not any installer entry.
2. At first storage prompt choose `1024` MiB and exact `CREATE`. This creates
   persistence on the verified boot USB, not C:/F: disks. Stop if an unexpected
   device or recovery error appears; do not guess, format or repair.
3. In Ooonana terminal run these read-only checks and return output/photos:

```sh
cat /proc/cmdline
uname -a
ooonana --version
ooonana-health --json
ooonana-service-status
ooonana-persistence status
lsblk -o NAME,TRAN,FSTYPE,LABEL,MOUNTPOINTS,RO
free -h
```

4. Only after output confirms persistent USB (not RAM or an installed system),
   create one disposable marker in the desktop user's home, without overwriting:

```sh
if grep -Eq '(^|[[:space:]])ooonana.persistence=1([[:space:]]|$)' /proc/cmdline; then
  mkdir -p "$HOME/ooonana-usb-qa"
  if [ ! -e "$HOME/ooonana-usb-qa/marker.txt" ]; then
    printf 'Ooonana disposable persistence marker\n' >"$HOME/ooonana-usb-qa/marker.txt"
  fi
  cat "$HOME/ooonana-usb-qa/marker.txt"
  sync
fi
```

5. Use normal shutdown/reboot. Boot the same persistent entry again and check
   marker returns, storage prompt does not recur, services and persistence remain
   healthy. Then return to Windows and share evidence. No sound test required.

Stop here before filling storage or disconnecting power. Later bounded full-
storage, verified offline backup/recovery and interrupted fixture-package upgrade
tests require this baseline and explicit matching boot-storage evidence. Real
power loss can damage outer FAT32 even when inner ext4 is journaled; dirty FAT
must refuse writable boot until explicit offline repair or reflash. Do not run
faults against kernel/core/system-library upgrades or mount internal disks.

No runtime/kernel source edit or ISO remake required for this preparation.
