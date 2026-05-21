# Rootfs QEMU Design

Goal: build Ooonana OS as a Debian rootfs in WSL, boot it with QEMU, then make ISO only after boot proof.

## Approach

Use WSL Linux tools, not Windows-native build paths. `debootstrap` creates `/var/tmp/ooonana-os/build/rootfs` unless `OOONANA_BUILD_DIR` overrides it. Ooonana files are copied into that tree. `mkfs.ext4 -d` turns the tree into `ooonana-rootfs.ext4` without loop mounts. QEMU boots that image with the kernel and initrd from the rootfs boot directory.

## Units

- `scripts/install-wsl-deps.sh`: installs WSL build dependencies.
- `scripts/build-rootfs.sh`: builds and configures rootfs plus ext4 image.
- `scripts/run-qemu.sh`: boots image normally or runs smoke boot.
- `scripts/lib/common.sh`: shared package-profile parsing and shell helpers.
- `packages/ooonana/usr/bin/ooonana`: early OS command.
- `configs/packages/core.list`: base package profile.
- `tests/*.sh`: smoke and static behavior checks.

## Boot Proof

Normal boot opens serial console with `-nographic`. Smoke boot uses `systemd.unit=ooonana-smoke.service`; service prints `OOONANA_BOOT_OK` to console and powers off. Test passes only when marker appears in QEMU log.

## Error Handling

Scripts fail fast, check Linux/WSL context, verify dependencies, and refuse silent sudo prompts. Root commands can run through `wsl.exe -u root` when needed.

## Testing

Before real VM boot:

- package-profile parser test
- CLI smoke test
- script help and dry-run test

After dependencies:

- build rootfs in WSL
- run QEMU smoke boot
- only then start ISO pipeline
