# Ooonana OS

```
Ooonana OS
      _____________________
     |     __       __     |
     |   /    \   /    \   |
   / |                     |\
 /   |      \______/       |  \
     |_____________________|
          |            |
```

Lightweight scratch-built Linux for QEMU, WSL, installer experiments, and AI-first terminal work.

## Quick Links

- [Download / Release Files](#download--release-files)
- [What Ooonana Is](#what-ooonana-is)
- [Current Status](#current-status)
- [Install And Test](#install-and-test)
- [Ooonana Command](#ooonana-command)
- [Ooonana AI](#ooonana-ai)
- [Build From Source](#build-from-source)
- [Project Files](#project-files)

## Download / Release Files

Current release artifacts live in:

```text
/var/tmp/ooonana-os/release
```

Main installer ISO:

```text
/var/tmp/ooonana-os/release/ooonana-scratch.iso
```

Release files:

```text
ooonana-scratch.iso          bootable GRUB installer ISO
ooonana-scratch-disk.raw     bootable installed raw disk image
ooonana-rootfs.tar.gz        generic chroot/container rootfs tarball
ooonana-wsl-rootfs.tar.gz    WSL import rootfs
vmlinuz-ooonana              Ooonana Linux kernel
SHA256SUMS                   checksums for release artifacts
qemu-rootfs-boot.log         direct rootfs QEMU boot proof
qemu-disk-boot.log           GRUB disk QEMU boot proof
qemu-installer.log           installer ISO QEMU proof
qemu-installed-boot.log      installed disk QEMU proof
```

Verify files:

```bash
cd /var/tmp/ooonana-os/release
sha256sum -c SHA256SUMS
```

## What Ooonana Is

Ooonana OS is a small scratch-built Linux project. Target system is not Debian or Alpine. Debian/Ubuntu packages are only host build tools used from WSL while Ooonana grows its own userspace and package manager.

Core pieces:

- Linux kernel
- BusyBox-style minimal userspace
- Custom `ooonana` package manager
- GRUB boot disk and installer ISO
- WSL rootfs export
- QEMU verification flow
- Optional AI CLI with provider routing

## Current Status

Working now:

- Scratch rootfs boots in QEMU
- GRUB raw disk boots in QEMU
- Installer ISO writes Ooonana to blank disk
- Installer has a serial-safe text UI with logo, target disk, and confirmation
- Installed disk boots in QEMU
- Generic `ooonana-rootfs.tar.gz` can be unpacked for chroot/container-style use
- WSL distro import works
- `ooonana` package manager has repo index, checksums, install, remove, upgrade, files, verify
- `ooonana-ai` supports NVIDIA NIM, Google Gemini, tools, tasks, audit, and shell fallback for scratch WSL

Next work:

- Graphical installer UI
- Real package repository publishing flow
- More first-party packages
- Users, networking, services, security defaults
- Optional GUI bundle

## Install And Test

Run QEMU installer from repo root:

```bash
truncate -s 512M /var/tmp/ooonana-os/install-target.raw
bash scripts/run-qemu.sh \
  --install \
  --iso /var/tmp/ooonana-os/release/ooonana-scratch.iso \
  --disk /var/tmp/ooonana-os/install-target.raw \
  --smoke
bash scripts/run-qemu.sh \
  --disk-boot \
  --image /var/tmp/ooonana-os/install-target.raw \
  --smoke
```

Boot release disk directly:

```bash
bash scripts/run-qemu.sh \
  --disk-boot \
  --image /var/tmp/ooonana-os/release/ooonana-scratch-disk.raw \
  --smoke
```

Use the generic rootfs tarball:

```bash
mkdir -p /tmp/ooonana-rootfs
sudo tar -xzf /var/tmp/ooonana-os/release/ooonana-rootfs.tar.gz -C /tmp/ooonana-rootfs
sudo mount -t proc proc /tmp/ooonana-rootfs/proc
sudo mount --rbind /sys /tmp/ooonana-rootfs/sys
sudo mount --rbind /dev /tmp/ooonana-rootfs/dev
sudo chroot /tmp/ooonana-rootfs /bin/sh
```

Import WSL rootfs:

```bash
bash scripts/install-wsl-distro.sh --distro Ooonana --force \
  --tarball /var/tmp/ooonana-os/release/ooonana-wsl-rootfs.tar.gz
wsl.exe -d Ooonana -- /usr/bin/ooonana me
wsl.exe -d Ooonana -- /usr/bin/ooonana ai tools
```

## Ooonana Command

```bash
ooonana me
ooonana version
ooonana wsl status
ooonana update
ooonana sources
ooonana list
ooonana list --installed
ooonana list --upgradeable
ooonana search gui
ooonana info ai
ooonana depends gui
ooonana get gui --dry-run
ooonana install ai
ooonana files ai
ooonana verify ai
ooonana upgrade --dry-run
ooonana remove ai
ooonana repo index /usr/lib/ooonana/repo
```

Package metadata lives inside Ooonana:

```text
/usr/lib/ooonana/repo/*.pkg
/usr/lib/ooonana/repo/index.tsv
/usr/lib/ooonana/repo/SHA256SUMS
/etc/ooonana/sources.d/*.repo
/var/lib/ooonana/packages/installed
/var/cache/ooonana/index.tsv
```

## Ooonana AI

Ooonana AI is CLI-first. It can run as `ooonana ai ...` or direct `ooonana-ai ...`.

```bash
ooonana ai setup
ooonana ai doctor
ooonana ai status
ooonana ai provider
ooonana ai provider set gemini
ooonana ai models
ooonana ai model
ooonana ai agents
ooonana ai tools
ooonana ai tool processes
ooonana ai task add "inspect system"
ooonana ai tasks
ooonana ai audit
ooonana ai ask "what system am I in?"
ooonana-ai --model code "write a shell script"
ooonana-ai chat
```

Config:

```text
~/.config/ooonana/ai.env
docs/ooonana-ai.env.example
```

Scratch WSL does not include `python3` yet. `provider`, `status`, and `tools` still work through shell fallback. Full chat and live provider calls need `python3`.

More:

```text
docs/ooonana-ai.md
docs/jarvis-agi-research.md
```

## Build From Source

Install host tools in WSL:

```bash
bash scripts/install-wsl-deps.sh
```

Build kernel:

```bash
bash scripts/fetch-kernel-source.sh --force
bash scripts/build-kernel.sh \
  --config-fragment configs/kernel/ooonana-minimal-x86_64.fragment \
  --force
```

Build scratch rootfs, WSL tarball, disk, and installer ISO:

```bash
bash scripts/build-scratch-rootfs.sh --force
bash scripts/build-scratch-initramfs.sh --force
bash scripts/build-rootfs-tarball.sh --force
bash scripts/build-wsl-rootfs.sh --force
bash scripts/build-scratch-disk.sh --smoke --force
bash scripts/build-scratch-grub-iso.sh \
  --install \
  --disk-image /var/tmp/ooonana-os/build/ooonana-scratch-disk.raw \
  --iso /var/tmp/ooonana-os/build/ooonana-scratch.iso \
  --force
```

Build output:

```text
/var/tmp/ooonana-os/build
```

Clean generated build files:

```bash
bash scripts/clean-build-artifacts.sh --yes
```

Keep kernel source/cache while cleaning images:

```bash
bash scripts/clean-build-artifacts.sh --keep-source --yes
```

## Verification

Fast tests:

```bash
bash tests/test-ooonana-pkg.sh
bash tests/test-ooonana-ai.sh
bash tests/test-scratch-rootfs.sh
bash tests/test-installer.sh
```

QEMU proof markers:

```text
OOONANA_CLI_OK
OOONANA_BOOT_OK
OOONANA_INSTALL_OK
```

## Project Files

Top-level files:

```text
README.md                         project homepage
.gitignore                        generated artifact ignores
.gitattributes                    repo text/binary rules
AGENTS.md                         local Codex instruction file
```

Kernel and package config:

```text
configs/kernel/ooonana-minimal-x86_64.fragment
configs/packages/core.list
```

Ooonana package:

```text
packages/ooonana/usr/bin/ooonana
packages/ooonana/usr/bin/ooonana-ai
packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py
packages/ooonana/usr/lib/ooonana/repo/*.pkg
packages/ooonana/usr/lib/ooonana/repo/index.tsv
packages/ooonana/usr/lib/ooonana/repo/SHA256SUMS
packages/ooonana/usr/sbin/ooonana-install
packages/ooonana/usr/share/ooonana/logo.txt
```

Build scripts:

```text
scripts/install-wsl-deps.sh
scripts/fetch-kernel-source.sh
scripts/build-kernel.sh
scripts/build-scratch-rootfs.sh
scripts/build-scratch-initramfs.sh
scripts/build-rootfs-tarball.sh
scripts/build-wsl-rootfs.sh
scripts/build-scratch-disk.sh
scripts/build-scratch-grub-iso.sh
scripts/install-wsl-distro.sh
scripts/run-qemu.sh
scripts/clean-build-artifacts.sh
scripts/lib/common.sh
```

Tests:

```text
tests/test-ooonana-pkg.sh
tests/test-ooonana-ai.sh
tests/test-logo-sync.sh
tests/test-rootfs-tarball.sh
tests/test-scratch-rootfs.sh
tests/test-scratch-initramfs.sh
tests/test-scratch-disk.sh
tests/test-scratch-grub-iso.sh
tests/test-wsl-distro.sh
tests/test-rootfs-qemu.sh
tests/test-iso.sh
tests/test-installer.sh
tests/smoke-cli.sh
```

Docs:

```text
docs/logo.txt
docs/ooonana-ai.md
docs/ooonana-ai.env.example
docs/jarvis-agi-research.md
docs/superpowers/plans/2026-05-21-rootfs-qemu.md
```
