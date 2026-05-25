# Ooonana OS

AI-built Linux experiment.

## Direction

Ooonana OS is moving toward a scratch-built, lightweight Linux:

- Linux kernel
- BusyBox/musl-style minimal userland target
- Ooonana-owned package/bundle manager
- Optional GUI, AI, developer, and security-lab bundles

The current Debian-based rootfs is a bootable test shell for QEMU while the Ooonana tooling and installer grow.

## Ooonana Command

```bash
ooonana update
ooonana list
ooonana info gui
ooonana get gui --dry-run
ooonana get ai
ooonana list --installed
ooonana remove ai
```

## Ooonana AI

```bash
ooonana ai setup
ooonana ai doctor
ooonana ai models
ooonana ai ask "what system am I in?"
ooonana-ai chat
```

AI uses NVIDIA NIM through an OpenAI-compatible chat API. Config lives in:

```text
~/.config/ooonana/ai.env
```

Package metadata lives in:

```text
/usr/lib/ooonana/repo/*.pkg
/usr/lib/ooonana/repo/hooks/*.install
/usr/lib/ooonana/repo/hooks/*.remove
```

Archive packages can add:

```text
OOONANA_PKG_ARCHIVE="hello.tar.gz"
OOONANA_PKG_SHA256="..."
```

Installed package state lives in:

```text
/var/lib/ooonana/packages/installed
/var/cache/ooonana/index.tsv
```

## WSL Rootfs Boot

```bash
bash scripts/install-wsl-deps.sh
bash scripts/build-rootfs.sh
bash scripts/run-qemu.sh --smoke
bash scripts/build-iso.sh --smoke
bash scripts/run-qemu.sh --iso /var/tmp/ooonana-os/build/ooonana.iso --smoke
truncate -s 4G /var/tmp/ooonana-os/build/install.ext4
bash scripts/build-iso.sh --install --force
bash scripts/run-qemu.sh --install --iso /var/tmp/ooonana-os/build/ooonana.iso --disk /var/tmp/ooonana-os/build/install.ext4 --smoke
bash scripts/run-qemu.sh
```

Windows root command:

```powershell
wsl.exe -u root bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash scripts/build-rootfs.sh'
```

Build output:

```text
/var/tmp/ooonana-os/build/rootfs
/var/tmp/ooonana-os/build/ooonana-rootfs.ext4
/var/tmp/ooonana-os/build/ooonana.iso
```

## Scratch Rootfs

```bash
bash scripts/install-wsl-deps.sh
bash scripts/build-scratch-rootfs.sh --force
bash scripts/run-qemu.sh \
  --rootfs /var/tmp/ooonana-os/build/rootfs \
  --image /var/tmp/ooonana-os/build/ooonana-scratch.ext4 \
  --smoke
bash scripts/build-scratch-initramfs.sh --force
bash scripts/run-qemu.sh \
  --initramfs-boot \
  --rootfs /var/tmp/ooonana-os/build/rootfs \
  --smoke
bash scripts/build-scratch-iso.sh --smoke --force
bash scripts/run-qemu.sh \
  --iso /var/tmp/ooonana-os/build/ooonana-scratch.iso \
  --smoke
```

Scratch output:

```text
/var/tmp/ooonana-os/build/scratch-rootfs
/var/tmp/ooonana-os/build/ooonana-scratch.ext4
/var/tmp/ooonana-os/build/ooonana-scratch-initramfs.cpio.gz
/var/tmp/ooonana-os/build/ooonana-scratch.iso
```
