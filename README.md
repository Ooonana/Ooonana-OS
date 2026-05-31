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

Ooonana includes a terminal AI app inspired by the provider-gateway shape of tools like Gemini CLI, free-claude-code, and Jarvis-style desktop agents, but it is branded as Ooonana. It supports NVIDIA NIM and Google Gemini. Full usage notes live in [docs/ooonana-ai.md](docs/ooonana-ai.md), with Jarvis notes in [docs/jarvis-agi-research.md](docs/jarvis-agi-research.md).

Install the dev command in WSL:

```bash
bash scripts/install-ooonana-ai-wsl.sh
```

This creates:

```text
~/.local/bin/ooonana
~/.local/bin/ooonana-ai
```

Quick start:

```bash
ooonana ai setup
${EDITOR:-vi} ~/.config/ooonana/ai.env
ooonana ai doctor
ooonana ai status
ooonana ai provider
ooonana ai provider set gemini
ooonana ai model
ooonana ai model set code
ooonana ai config
ooonana ai ping
ooonana ai ask --model code "explain this Linux environment"
ooonana ai chat
ooonana ai env
ooonana ai models
ooonana ai history
ooonana ai sessions
ooonana ai agents
ooonana ai agent activity
ooonana-ai help
ooonana-ai model list
ooonana-ai model alias tiny meta/llama-3.3-70b-instruct
ooonana-ai
ooonana-ai "who are you?"
ooonana-ai --model code "write a bash script"
```

The config file expects at least one provider key:

```text
OOONANA_AI_PROVIDER=nim
NVIDIA_API_KEY=nvapi-...
GEMINI_API_KEY=...
OOONANA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
OOONANA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
OOONANA_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
OOONANA_GEMINI_MODEL=gemini-2.5-flash
OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
OOONANA_MODEL_FAST=qwen/qwen3-next-80b-a3b-instruct
OOONANA_MODEL_DEEP=nvidia/nemotron-3-super-120b-a12b
OOONANA_MODEL_TINY=meta/llama-3.3-70b-instruct
OOONANA_AI_STREAM=1
```

A copyable example lives at:

```text
docs/ooonana-ai.env.example
```

Useful API/config variables:

```text
NVIDIA_NIM_API_KEY        optional alternate key name
GEMINI_API_KEY            Gemini API key
GOOGLE_API_KEY            alternate Gemini API key, takes precedence
OOONANA_AI_PROVIDER       nim, gemini, or auto
OOONANA_AI_MAX_TOKENS     default 1024
OOONANA_AI_TEMPERATURE    default 0.2
OOONANA_AI_TIMEOUT        default 120
OOONANA_ENV_CONTEXT_BYTES default 12000
OOONANA_AI_STATE_DIR      default ~/.local/state/ooonana/ai
OOONANA_AI_MOCK=1         offline/mock mode
```

Switch providers:

```bash
ooonana-ai provider
ooonana-ai provider set gemini
ooonana-ai model list
ooonana-ai model set deep
ooonana-ai --provider gemini "who are you?"
ooonana-ai provider set nim
```

Change models without editing config:

```bash
ooonana-ai model              # show active model and aliases
ooonana-ai model list         # aliases plus useful active-provider model ids
ooonana-ai model set code     # make code alias the default
ooonana-ai model set nvidia/nemotron-3-super-120b-a12b
ooonana-ai model alias tiny meta/llama-3.3-70b-instruct
ooonana-ai --model tiny "quick answer"
```

Every request includes a detailed Ooonana identity prompt and a compact Linux/WSL/workspace snapshot so the assistant knows it is Ooonana running inside the current OS. One-shot asks include the local `activity` agent by default, which adds recent shell and Ooonana AI history with secrets redacted. The direct `ooonana-ai ping` command makes a tiny live provider request once a real key is configured.

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
