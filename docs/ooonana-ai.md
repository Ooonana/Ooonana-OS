# Ooonana AI CLI

Ooonana AI is the terminal assistant for Ooonana. It is currently a standalone Ooonana CLI, not a literal checked-in fork of Gemini CLI source. It borrows the useful product shape from Gemini CLI and free-claude-code: terminal chat, provider separation, streaming chat completions, config files, model aliases, and an explicit system prompt.

## What It Does

- Runs as `ooonana ai ...` or `ooonana-ai ...`
- Uses NVIDIA NIM's OpenAI-compatible chat completions API
- Reads `NVIDIA_API_KEY` or `NVIDIA_NIM_API_KEY`
- Sends a system prompt that says the assistant's name is `Ooonana`
- Sends a Linux/WSL environment snapshot with each request
- Supports one-shot ask, code prompt alias, interactive chat, status, model listing, and config inspection

## Quick Start

```bash
cd "/mnt/c/Users/7ryan/.codex/worktrees/e5f2/Ooonana OS"
bash scripts/install-ooonana-ai-wsl.sh
ooonana-ai setup
nano ~/.config/ooonana/ai.env
ooonana-ai doctor
ooonana-ai ping
ooonana-ai ask --model code "who are you?"
ooonana-ai chat
```

Use mock mode before adding an API key:

```bash
OOONANA_AI_MOCK=1 ooonana-ai ask --no-stream "who are you?"
```

## Install In WSL

From this repo inside WSL:

```bash
cd "/mnt/c/Users/7ryan/.codex/worktrees/e5f2/Ooonana OS"
bash scripts/install-ooonana-ai-wsl.sh
```

This creates symlinks in `~/.local/bin`:

```text
~/.local/bin/ooonana
~/.local/bin/ooonana-ai
```

If `~/.local/bin` is not in `PATH`, add this to `~/.profile` or `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Configure NVIDIA NIM

Create the config:

```bash
ooonana ai setup
```

Edit it:

```bash
nano ~/.config/ooonana/ai.env
```

Or copy the checked-in example:

```bash
mkdir -p ~/.config/ooonana
cp docs/ooonana-ai.env.example ~/.config/ooonana/ai.env
nano ~/.config/ooonana/ai.env
chmod 600 ~/.config/ooonana/ai.env
```

Minimum config:

```text
NVIDIA_API_KEY=nvapi-your-key
OOONANA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
OOONANA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
OOONANA_MODEL_FAST=qwen/qwen3-next-80b-a3b-instruct
OOONANA_MODEL_DEEP=nvidia/nemotron-3-super-120b-a12b
OOONANA_AI_STREAM=1
```

### API Settings

Ooonana AI talks to NVIDIA NIM using the OpenAI-compatible chat completions shape.

| Setting | Default | Purpose |
| --- | --- | --- |
| `NVIDIA_API_KEY` | empty | NVIDIA NIM API key. Used as `Authorization: Bearer ...`. |
| `NVIDIA_NIM_API_KEY` | empty | Alternative key name. Takes precedence if both are set. |
| `OOONANA_NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | API base URL. Ooonana appends `/chat/completions` when needed. |
| `OOONANA_NIM_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Default chat model. |
| `OOONANA_MODEL_CODE` | `qwen/qwen3-coder-480b-a35b-instruct` | Model alias for coding prompts. |
| `OOONANA_MODEL_FAST` | `qwen/qwen3-next-80b-a3b-instruct` | Model alias for quick answers. |
| `OOONANA_MODEL_DEEP` | `nvidia/nemotron-3-super-120b-a12b` | Model alias for deeper reasoning. |
| `OOONANA_AI_MAX_TOKENS` | `1024` | Maximum generated tokens. |
| `OOONANA_AI_TEMPERATURE` | `0.2` | Sampling temperature. |
| `OOONANA_AI_STREAM` | `1` | Stream responses when possible. Set `0` to disable. |
| `OOONANA_AI_TIMEOUT` | `120` | HTTP timeout in seconds. |
| `OOONANA_ENV_CONTEXT_BYTES` | `12000` | Max size for injected Linux context. |
| `OOONANA_AI_CONFIG` | `~/.config/ooonana/ai.env` | Override config path. |
| `OOONANA_AI_MOCK` | unset | Set to `1` for offline/mock responses. |

Check it:

```bash
ooonana ai doctor
ooonana ai config
ooonana ai ping
```

`ooonana ai config` redacts API keys.
`ooonana ai ping` makes a tiny live NVIDIA NIM request, so it requires a real API key.

The live request is intentionally small:

```bash
ooonana-ai ping
```

Expected shape:

```text
Ooonana online
```

## Use It

One-shot prompt:

```bash
ooonana ai ask "who are you?"
```

Coding model alias:

```bash
ooonana ai ask --model code "write a bash script that lists mounted filesystems"
```

Interactive chat:

```bash
ooonana ai chat
```

Useful chat commands:

```text
/help
/status
/env
/model code
/save transcript.json
/clear
/exit
```

Direct alias:

```bash
ooonana-ai ask --model code "explain this repo"
ooonana-ai chat
ooonana-ai ping
```

Show the Linux/WSL context Ooonana will send:

```bash
ooonana-ai env
```

Inspect the provider payload without making an API request:

```bash
ooonana-ai ask --dry-run --model code "what environment am I in?"
```

## Verify Without Spending API Calls

Use mock mode:

```bash
OOONANA_AI_MOCK=1 ooonana ai ask --no-stream "who are you?"
```

Inspect the exact payload without calling NVIDIA NIM:

```bash
ooonana ai ask --dry-run --model code "what environment am I in?"
```

## System Prompt

Ooonana's built-in system prompt is intentionally explicit:

- The assistant's name is `Ooonana`.
- It must not claim to be Gemini, Claude, ChatGPT, or NVIDIA NIM.
- NVIDIA NIM is described only as the model/API provider.
- It should treat the provided Linux environment snapshot as authoritative context.
- It should notice hostname, OS release, current directory, available commands, workspace files, and package state.
- It should give concrete commands, paths, config keys, and exact next steps.
- It should not pretend it executed commands or saw files outside the supplied context.
- It should redact secrets and avoid exposing API keys.
- It should help make Ooonana feel like its own AI CLI, not a thin rebrand.

The source prompt lives in:

```text
packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py
```

## WSL Verification

Run the local checks:

```bash
bash tests/test-ooonana-ai.sh
bash tests/smoke-cli.sh
bash tests/test-ooonana-pkg.sh
```

The broader OS helper checks also still pass:

```bash
bash tests/test-rootfs-qemu.sh
bash tests/test-iso.sh
bash tests/test-installer.sh
bash tests/test-scratch-rootfs.sh
```

## Current Gap

This is not yet a full Gemini CLI source fork. To become a literal Gemini fork, the next step is to import Gemini CLI source or add it as an upstream subtree, then replace its Gemini provider with the Ooonana NVIDIA NIM provider and port this Ooonana prompt/UI layer into that codebase.
