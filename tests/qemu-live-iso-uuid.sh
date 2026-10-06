#!/usr/bin/env bash
# Boot current live init against a read-only existing ISO. No release rebuild.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO="${1:?usage: qemu-live-iso-uuid.sh ISO KERNEL SEED_INITRAMFS}"
KERNEL="${2:?kernel required}"
SEED="${3:?live initramfs required}"
[[ -f "$ISO" && -f "$KERNEL" && -f "$SEED" ]] || exit 2
for tool in grub-mkrescue qemu-system-x86_64 blkid cpio gzip od dd; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 2; }
done
ACCEL="${OOONANA_QEMU_ACCEL:-tcg}"
case "$ACCEL" in kvm|tcg) ;; *) exit 2 ;; esac
iso_uuid="$(blkid -p -s UUID -o value "$ISO")"
[[ "$iso_uuid" =~ ^[0-9]{4}(-[0-9]{2}){6}$ ]] || exit 2
work="$(mktemp -d /var/tmp/ooonana-iso-uuid.XXXXXXXX)"
qpid=""
cleanup() {
  local result=$?
  if [[ -n "$qpid" ]]; then kill "$qpid" 2>/dev/null || true; wait "$qpid" 2>/dev/null || true; fi
  if [[ "$result" = 0 ]]; then
    case "$(realpath "$work")" in /var/tmp/ooonana-iso-uuid.????????) rm -rf -- "$work" ;; esac
  else
    printf 'Failed UUID fixture/logs retained: %s\n' "$work" >&2
  fi
}
trap cleanup EXIT
mkdir -p "$work/tree" "$work/cd/boot/grub"
(cd "$work/tree"; gzip -dc "$SEED" | cpio -id --quiet --no-absolute-filenames)
install -m 0644 "$ROOT/scripts/lib/live-boot-storage.sh" "$work/tree/lib/ooonana-live-storage.sh"
install -m 0644 "$ROOT/scripts/lib/live-persistence-file.sh" "$work/tree/lib/ooonana-live-persistence-file.sh"
awk -v marker='cat > "$LIVE_INIT_TREE/init"' '
  index($0, marker) { capture=1; next }
  capture && $0 == "EOF" { exit }
  capture { print }
' "$ROOT/scripts/build-full-i3-live-initramfs.sh" > "$work/tree/init"
[[ -s "$work/tree/init" ]] || exit 1
chmod 0755 "$work/tree/init"
for applet in dd od stat ln chroot; do ln -sf busybox "$work/tree/bin/$applet"; done
(cd "$work/tree"; find . -print0 | cpio --null -o --format=newc --quiet | gzip -1 > "$work/cd/boot/live.cpio.gz")
cp "$KERNEL" "$work/cd/boot/vmlinuz"
# GRUB discovers/probes the real runtime USB, not the disposable bootstrap CD.
cat > "$work/cd/boot/grub/grub.cfg" <<EOF
serial --unit=0 --speed=115200
terminal_input serial
terminal_output serial
insmod probe
search --no-floppy --fs-uuid --set=runtime $iso_uuid
probe --set=ooonana_boot_uuid --fs-uuid (\$runtime)
linux /boot/vmlinuz console=ttyS0 loglevel=6 panic=1 rdinit=/init ooonana.live=1 ooonana.edition=full-i3 ooonana.live.boot_uuid=\$ooonana_boot_uuid
initrd /boot/live.cpio.gz
boot
EOF
grub-mkrescue -o "$work/bootstrap.iso" "$work/cd" > "$work/grub.log" 2>&1
for mode in bios uefi; do
  firmware=()
  if [[ "$mode" = uefi ]]; then
    if [[ -f /usr/share/OVMF/OVMF_CODE_4M.fd && -f /usr/share/OVMF/OVMF_VARS_4M.fd ]]; then
      cp /usr/share/OVMF/OVMF_VARS_4M.fd "$work/vars.fd"
      firmware=(-drive "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd" -drive "if=pflash,format=raw,unit=1,file=$work/vars.fd")
    elif [[ -f /usr/share/ovmf/OVMF.fd ]]; then
      firmware=(-bios /usr/share/ovmf/OVMF.fd)
    else
      echo 'OVMF missing; UEFI not verified' >&2; exit 2
    fi
  fi
  log="$work/$mode.log"
  : > "$log"
  qemu-system-x86_64 -accel "$ACCEL" -machine q35 -m 2048 -smp 2 \
    -display none -serial "file:$log" -monitor none -no-reboot -nic none \
    -boot d -cdrom "$work/bootstrap.iso" "${firmware[@]}" \
    -device qemu-xhci,id=usb -drive "if=none,id=runtime,format=raw,readonly=on,file=$ISO" \
    -device usb-storage,bus=usb.0,drive=runtime > "$work/$mode.stderr" 2>&1 &
  qpid=$!
  for ((attempt=0; attempt<180; attempt++)); do
    grep -q 'Ooonana full i3 rootfs' "$log" && break
    grep -qE 'Ooonana live init failed:|Kernel panic' "$log" && break
    kill -0 "$qpid" 2>/dev/null || break
    sleep 1
  done
  kill "$qpid" 2>/dev/null || true; wait "$qpid" 2>/dev/null || true; qpid=""
  if ! grep -q 'Ooonana full i3 rootfs' "$log" || ! grep -q "Kernel command line:.*ooonana.live.boot_uuid=$iso_uuid" "$log"; then
    tail -n 40 "$log" >&2; cat "$work/$mode.stderr" >&2; exit 1
  fi
  printf 'ok live-iso-uuid-%s: GRUB UUID -> BusyBox -> full rootfs\n' "$mode"
done
