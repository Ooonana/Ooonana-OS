# Ooonana AI CLI

Ooonana AI is the terminal assistant for Ooonana. It is currently a standalone Ooonana CLI, not a literal checked-in fork of Gemini CLI source. It borrows the useful product shape from Gemini CLI and free-claude-code: terminal chat, provider separation, streaming chat completions, config files, model aliases, and an explicit system prompt.

## What It Does

- Runs as `ooonana ai ...` or `ooonana-ai ...`
- Opens as a full-i3 terminal dashboard through `ooonana-ai-app`
- Uses NVIDIA NIM's OpenAI-compatible chat completions API
- Uses Google Gemini's `generateContent` and `streamGenerateContent` REST API
- Reads `NVIDIA_API_KEY`, `NVIDIA_NIM_API_KEY`, `GEMINI_API_KEY`, or `GOOGLE_API_KEY`
- Sends a system prompt that says the assistant's name is `Ooonana`
- Sends a Linux/WSL environment snapshot with each request
- Supports one-shot ask, code prompt alias, interactive chat, status, model listing, config inspection, persistent history, rewind, and local context agents
- Provides a native app dashboard with quick actions for chat, ask, tools, tasks, sessions, setup, and shell fallback
- Keeps a BusyBox/scratch shell fallback for `provider`, `status`, `tools`, and basic inspection when `python3` is not present

## Quick Start

```bash
cd "/mnt/c/Users/<windows-user>/path/to/Ooonana OS"
bash scripts/install-ooonana-ai-wsl.sh
ooonana-ai setup
nano ~/.config/ooonana/ai.env
ooonana-ai doctor
ooonana-ai ping
ooonana-ai ask --model code "who are you?"
ooonana-ai chat
ooonana-ai history
ooonana-ai agents
ooonana-ai-app
```

Use mock mode before adding an API key:

```bash
OOONANA_AI_MOCK=1 ooonana-ai ask --no-stream "who are you?"
```

## Install In WSL

From this repo inside WSL:

```bash
cd "/mnt/c/Users/<windows-user>/path/to/Ooonana OS"
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

In scratch Ooonana WSL, `python3` is intentionally absent for now. These still
work through the shell fallback:

```bash
ooonana ai provider
ooonana ai status
ooonana ai tools
ooonana ai tool processes
ooonana-ai provider
```

Full chat, live provider calls, persistent sessions, and rewind need `python3`.

## Configure Providers

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
OOONANA_AI_PROVIDER=nim
NVIDIA_API_KEY=nvapi-your-key
GEMINI_API_KEY=your-gemini-key
OOONANA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
OOONANA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
OOONANA_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
OOONANA_GEMINI_MODEL=gemini-2.5-flash
OOONANA_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
OOONANA_MODEL_FAST=qwen/qwen3-next-80b-a3b-instruct
OOONANA_MODEL_DEEP=nvidia/nemotron-3-super-120b-a12b
OOONANA_GEMINI_MODEL_CODE=gemini-2.5-flash
OOONANA_GEMINI_MODEL_FAST=gemini-2.5-flash-lite
OOONANA_GEMINI_MODEL_DEEP=gemini-2.5-pro
OOONANA_MODEL_TINY=meta/llama-3.3-70b-instruct
OOONANA_AI_STREAM=1
```

### API Settings

Ooonana AI talks to NVIDIA NIM using OpenAI-compatible chat completions. It talks to Gemini using the REST `generateContent` shape with `x-goog-api-key`, `system_instruction`, and `contents`.

| Setting | Default | Purpose |
| --- | --- | --- |
| `NVIDIA_API_KEY` | empty | NVIDIA NIM API key. Used as `Authorization: Bearer ...`. |
| `NVIDIA_NIM_API_KEY` | empty | Alternative key name. Takes precedence if both are set. |
| `GEMINI_API_KEY` | empty | Gemini API key. |
| `GOOGLE_API_KEY` | empty | Alternative Gemini key name. Takes precedence if both are set. |
| `OOONANA_AI_PROVIDER` | `nim` | `nim`, `gemini`, or `auto`. |
| `OOONANA_NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | API base URL. Ooonana appends `/chat/completions` when needed. |
| `OOONANA_NIM_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Default chat model. |
| `OOONANA_GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Gemini API base URL. |
| `OOONANA_GEMINI_MODEL` | `gemini-2.5-flash` | Default Gemini chat model. |
| `OOONANA_MODEL_CODE` | `qwen/qwen3-coder-480b-a35b-instruct` | Model alias for coding prompts. |
| `OOONANA_MODEL_FAST` | `qwen/qwen3-next-80b-a3b-instruct` | Model alias for quick answers. |
| `OOONANA_MODEL_DEEP` | `nvidia/nemotron-3-super-120b-a12b` | Model alias for deeper reasoning. |
| `OOONANA_MODEL_<ALIAS>` | empty | Custom model alias. `OOONANA_MODEL_TINY=meta/llama-3.3-70b-instruct` makes `--model tiny` work. |
| `OOONANA_GEMINI_MODEL_CODE` | `gemini-2.5-flash` | Gemini model alias for coding prompts. |
| `OOONANA_GEMINI_MODEL_FAST` | `gemini-2.5-flash-lite` | Gemini model alias for quick answers. |
| `OOONANA_GEMINI_MODEL_DEEP` | `gemini-2.5-pro` | Gemini model alias for deeper reasoning. |
| `OOONANA_GEMINI_MODEL_<ALIAS>` | empty | Custom Gemini model alias. |
| `OOONANA_AI_MAX_TOKENS` | `1024` | Maximum generated tokens. |
| `OOONANA_AI_TEMPERATURE` | `0.2` | Sampling temperature. |
| `OOONANA_AI_STREAM` | `1` | Stream responses when possible. Set `0` to disable. |
| `OOONANA_AI_TIMEOUT` | `120` | HTTP timeout in seconds. |
| `OOONANA_ENV_CONTEXT_BYTES` | `12000` | Max size for injected Linux context. |
| `OOONANA_AI_CONFIG` | `~/.config/ooonana/ai.env` | Override config path. |
| `OOONANA_AI_STATE_DIR` | `~/.local/state/ooonana/ai` | Persistent history/session storage. |
| `OOONANA_AI_MOCK` | unset | Set to `1` for offline/mock responses. |

Check it:

```bash
ooonana ai doctor
ooonana ai config
ooonana ai ping
```

`ooonana ai config` redacts API keys.
`ooonana ai ping` makes a tiny live provider request, so it requires a real API key.

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

Switch to Gemini:

```bash
ooonana-ai provider set gemini
ooonana-ai doctor
ooonana-ai model list
ooonana-ai model set deep
ooonana-ai "who are you?"
```

One-shot provider override:

```bash
ooonana-ai --provider gemini "summarize this Linux system"
ooonana-ai --provider nim "summarize this Linux system"
```

Change the default model without opening the config file:

```bash
ooonana-ai model
ooonana-ai model list
ooonana-ai model set code
ooonana-ai model set qwen/qwen3-next-80b-a3b-instruct
```

Add a new alias:

```bash
ooonana-ai model alias tiny meta/llama-3.3-70b-instruct
ooonana-ai --model tiny "answer fast"
```

Interactive chat:

```bash
ooonana ai chat
```

Useful chat commands:

```text
/help
/agents
/agent activity
/tools
/tool processes
/tasks
/task plan inspect-system
/audit
/status
/env
/history
/rewind
/rewind 2
/provider
/provider set gemini
/models
/model code
/model set deep
/model alias tiny meta/llama-3.3-70b-instruct
/save transcript.json
/clear
/exit
```

Direct alias:

```bash
ooonana-ai-app
ooonana-ai help
ooonana-ai provider
ooonana-ai provider set gemini
ooonana-ai model
ooonana-ai model set code
ooonana-ai model alias tiny meta/llama-3.3-70b-instruct
ooonana-ai
ooonana-ai "who are you?"
ooonana-ai --model code "write a bash script that prints Ooonana"
ooonana-ai ask --model code "explain this repo"
ooonana-ai chat
ooonana-ai ping
ooonana-ai history
ooonana-ai sessions
ooonana-ai agents
ooonana-ai agent activity
ooonana-ai tools
ooonana-ai tool processes
ooonana-ai tasks
ooonana-ai audit
```

Direct alias behavior:

```text
ooonana-ai                 opens interactive chat
ooonana-ai help            shows Ooonana AI help
ooonana-ai "message"       sends a one-shot ask
ooonana-ai --model code "message"
                           sends a one-shot ask with options
ooonana-ai provider        shows active provider
ooonana-ai provider set gemini
                           switches default provider
ooonana-ai model           shows active model and aliases
ooonana-ai model set code  changes default model in config
ooonana-ai model alias N M saves alias N for model M
ooonana-ai tools           lists local CLI tools
ooonana-ai tool processes  reads process table
ooonana-ai task add TEXT   records a CLI task
ooonana-ai audit           shows permissioned action log
ooonana-ai chat            explicitly opens chat
ooonana-ai status          shows provider/UI status
```

Full-i3 app launcher:

```text
ooonana-ai-app             opens the Ooonana AI workbench or terminal fallback
Mod+Shift+a                i3 shortcut
/usr/share/applications/ooonana-ai.desktop
```

GUI workbench:

```text
Chat pane       transcript, prompt flow, clear, save
Action rail     ask, chat, tools, tasks, sessions, desktop, setup
Context pane    desktop state, tools, tasks
Safety pane     shell and desktop-control permission notes
Logs pane       app log and audit/history access
```

Terminal-only dashboard:

```bash
OOONANA_AI_APP_NO_X=1 ooonana-ai-app
OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_COMMAND=tools ooonana-ai-app
```

## History And Rewind

Ooonana stores local AI turns under:

```text
~/.local/state/ooonana/ai/history.jsonl
~/.local/state/ooonana/ai/sessions/*.jsonl
```

Show recent history:

```bash
ooonana-ai history
ooonana-ai history --limit 50
ooonana-ai history --json
```

List chat sessions:

```bash
ooonana-ai sessions
```

Open or resume a named session:

```bash
ooonana-ai chat --session workbench
```

Inside chat:

```text
/history
/rewind
/rewind 3
/clear
```

`/rewind` removes the latest turn from the active chat context and rewrites that session file. Global history remains an audit trail.

To use a different state directory:

```bash
ooonana-ai --state-dir /tmp/ooonana-ai-state history
OOONANA_AI_STATE_DIR=/tmp/ooonana-ai-state ooonana-ai chat
```

## Local Agents

Ooonana has lightweight local agents that collect context for the main AI:

```text
system      OS, WSL, command, package, and workspace context
activity    recent shell history and Ooonana AI history with secrets redacted
summarizer  system plus activity context shaped for compact summaries
tools       CLI tool registry, permission gates, and recent audit context
```

List them:

```bash
ooonana-ai agents
```

Inspect context without calling provider:

```bash
ooonana-ai agent system
ooonana-ai agent activity
ooonana-ai agent summarizer
ooonana-ai agent tools
```

Ask active provider to summarize agent context:

```bash
ooonana-ai agent summarizer --ask
ooonana-ai agent activity --ask --prompt "What was I doing lately?"
```

One-shot asks include the `activity` agent by default, so Ooonana can see recent local activity. Disable that when needed:

```bash
ooonana-ai --no-agent "answer without local activity context"
ooonana-ai --agent system "focus on the OS state"
```

Inside chat:

```text
/agents
/agent
/agent activity
/agent system
/agent none
```

## CLI Tools And Tasks

Ooonana applies the Jarvis research as CLI-first system integration, not voice or GUI. Tools default to read-only inspection. Shell execution is permission-gated and audited.
Full Ooonana adds a desktop read tool for i3/WSLg/Xorg context, so the assistant can see display/session state before helping with GUI work.

List tools:

```bash
ooonana-ai tools
```

Read-only tools:

```bash
ooonana-ai tool system
ooonana-ai tool processes
ooonana-ai tool packages
ooonana-ai tool files .
ooonana-ai tool desktop
ooonana-ai tool activity
```

Guarded shell tool:

```bash
ooonana-ai tool shell echo hi
ooonana-ai tool shell --yes 'echo hi'
ooonana-ai audit
```

The first command is blocked and audited. The `--yes` form executes and writes an audit entry. Destructive patterns such as `mkfs`, unsafe `dd`, reboot, shutdown, and recursive root removal are blocked.

Task runner:

```bash
ooonana-ai task add "inspect boot state"
ooonana-ai tasks
ooonana-ai task done TASK_ID
ooonana-ai task plan "repair provider config"
```

Tasks live under:

```text
~/.local/state/ooonana/ai/tasks.jsonl
~/.local/state/ooonana/ai/audit.jsonl
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

Inspect exact payload without calling active provider:

```bash
ooonana ai ask --dry-run --model code "what environment am I in?"
```

## System Prompt

Ooonana's built-in system prompt is intentionally explicit:

- The assistant's name is `Ooonana`.
- It must not claim to be Gemini, Claude, ChatGPT, Google, or NVIDIA NIM.
- NVIDIA NIM and Google Gemini are described only as model/API providers.
- It should treat the provided Linux environment snapshot as authoritative context.
- It should notice hostname, OS release, current directory, available commands, workspace files, and package state.
- It should give concrete commands, paths, config keys, and exact next steps.
- It should not pretend it executed commands or saw files outside the supplied context.
- It should redact secrets and avoid exposing API keys.
- It should help make Ooonana feel like its own AI CLI, not a thin rebrand.
- It should keep UI CLI-first: commands, slash commands, compact tables, status lines, JSON when requested, and copyable shell snippets.
- It should not design voice input, voice recognition, GUI dashboards, or web-first flows unless explicitly requested.
- It should aim toward Jarvis-class local-first system integration without claiming AGI.

## Jarvis-AGI Direction

The closest GitHub repo matching `jarvis-agi` is [vierisid/jarvis](https://github.com/vierisid/jarvis). Its useful ideas for Ooonana:

- Optional background daemon with CLI control
- Multi-machine sidecars for screen, app, shell, and filesystem access
- Multi-agent hierarchy with specialist roles
- CLI workflow builder and task runner
- Provider flexibility across Anthropic, OpenAI, Google Gemini, and local Ollama
- WSL/Linux install path

Another useful local-first reference is [isair/jarvis](https://github.com/isair/jarvis), which has useful memory, tool selection, screenshot OCR, web search, file access, location/time awareness, and MCP expansion ideas. Ooonana will not copy the voice-assistant direction.

Ooonana should borrow direction, not identity:

- Keep assistant name `Ooonana`.
- Keep CLI first. No voice recognition or voice UI.
- Add provider router first: NIM, Gemini, later Ollama/OpenAI-compatible.
- Add permissioned system tools next: read-only inspect, then guarded shell/file actions.
- Add optional background daemon later, controlled from CLI, after safety gates and audit history exist.
- Avoid claiming AGI; call it Jarvis-class system integration.

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

This is not yet a full Gemini CLI source fork. To become a literal Gemini fork, next step is to import Gemini CLI source or add it as an upstream subtree, then port this Ooonana prompt/UI/provider-router layer into that codebase.
