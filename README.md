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

## Ooonana AI CLI

Ooonana includes a terminal AI app inspired by the provider-gateway shape of tools like Gemini CLI and free-claude-code, but it is branded as Ooonana and talks directly to NVIDIA NIM.

```bash
ooonana ai setup
${EDITOR:-vi} ~/.config/ooonana/ai.env
ooonana ai doctor
ooonana ai config
ooonana ai ask --model code "explain this Linux environment"
ooonana ai chat
ooonana ai env
ooonana ai models
```

The config file expects an NVIDIA NIM key:

```text
NVIDIA_API_KEY=nvapi-...
OOONANA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
OOONANA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
```

Every request includes an Ooonana identity prompt and a compact Linux environment snapshot so the assistant knows it is Ooonana running inside the current OS.

Package metadata lives in:

```text
/usr/lib/ooonana/repo/*.pkg
/usr/lib/ooonana/repo/hooks/*.install
/usr/lib/ooonana/repo/hooks/*.remove
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
```

Scratch output:

```text
/var/tmp/ooonana-os/build/scratch-rootfs
/var/tmp/ooonana-os/build/ooonana-scratch.ext4
```
