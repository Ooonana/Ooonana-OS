# OpenVINO Chat

Local terminal chat app for OpenVINO GenAI models.

Runs local models through OpenVINO on Intel GPU, NPU, or CPU. Includes streaming chat,
reasoning display, model and session pickers, tool use, web search, file editing,
permissions, task tracking, and live hardware status.

## Requirements

- Windows 10/11 and PowerShell 7
- Python 3.12+
- Intel GPU driver supporting OpenVINO GPU inference
- `openvino-genai`, `prompt_toolkit`, `rich`, and `huggingface_hub`

Install project dependencies:

```powershell
F:\LM\.venv\Scripts\python.exe -m pip install -e C:\Users\7ryan\openvino-chat
```

Editable install registers a real `openvino` console program through
`pyproject.toml`, in addition to supplied launchers.

### Windows Setup

Run setup script from Downloads:

```powershell
& "F:\7ryan\Downloads\setup-openvino-chat.ps1"
```

Script creates/reuses virtual environment, installs package, writes
`C:\Users\7ryan\.local\bin\openvino.cmd`, sets `OPENVINO_HOME`, and adds launcher
directory to user PATH. Open new terminal after setup.

Repository copy:

```powershell
& "C:\Users\7ryan\openvino-chat\scripts\setup-windows.ps1"
```

### Linux Setup

```bash
cd /path/to/openvino-chat
bash scripts/setup-linux.sh
```

Defaults:

```text
venv:    ~/.local/share/openvino-chat/venv
runtime: ~/.openvino
command: ~/.local/bin/openvino
```

Direct repository launcher:

```bash
./openvino.sh chat --device CPU
```

Command launcher:

```text
C:\Users\7ryan\.local\bin\openvino.cmd
```

## Runtime Home

All app-owned runtime files live under one folder:

```text
F:\7ryan\Downloads\.openvino
```

Layout:

```text
F:\7ryan\Downloads\.openvino
├─ api\
├─ config.json
├─ exports\
├─ models\
│  ├─ qwen3.5-9b-int4-ov\
│  ├─ gemma-4-e2b-it-qat-int4-ov\
│  ├─ glm-4.1v-9b-thinking-int4-ov\
│  └─ gemma-4-e4b-it-int4-ov\
├─ reports\
└─ sessions\
```

Environment overrides:

```powershell
$env:OPENVINO_HOME="F:\7ryan\Downloads\.openvino"
$env:OPENVINO_MODEL_ROOT="F:\7ryan\Downloads\.openvino\models"
$env:OPENVINO_CHAT_CONFIG="F:\7ryan\Downloads\.openvino\config.json"
$env:OPENVINO_CHAT_REPORT_DIR="F:\7ryan\Downloads\.openvino\reports"
$env:OPENVINO_CHAT_SESSION_DIR="F:\7ryan\Downloads\.openvino\sessions"
$env:OPENVINO_CHAT_EXPORT_DIR="F:\7ryan\Downloads\.openvino\exports"
$env:OPENVINO_CHAT_API_DIR="F:\7ryan\Downloads\.openvino\api"
```

## Models

| Name | Repo | Local path |
| --- | --- | --- |
| `qwen` | `OpenVINO/Qwen3.5-9B-int4-ov` | `F:\7ryan\Downloads\.openvino\models\qwen3.5-9b-int4-ov` |
| `tiny` | `HarmenWessels/gemma-4-E2B-it-qat-int4-ov` | `F:\7ryan\Downloads\.openvino\models\gemma-4-e2b-it-qat-int4-ov` |
| `glm` | `zai-org/GLM-4.1V-9B-Thinking` *(export to OpenVINO first)* | `F:\7ryan\Downloads\.openvino\models\glm-4.1v-9b-thinking-int4-ov` |
| `gemma` | `OpenVINO/gemma-4-E4B-it-int4-ov` | `F:\7ryan\Downloads\.openvino\models\gemma-4-e4b-it-int4-ov` |

## Start

```powershell
openvino
openvino chat
openvino chat --device GPU
openvino chat --device NPU
openvino chat --device CPU
openvino chat --ctx 4096
openvino chat --ctx 4096 --max-new-tokens 4096
openvino chat --kv-cache u4
```

`--ctx` is total prompt plus response capacity. `/max-tokens` sets response ceiling. Old conversation turns are omitted automatically when needed, while saved session history stays intact.

Models load lazily. Starting `openvino` does not put model weights in RAM or GPU
memory. First normal message, `/plan`, `/review`, or `/bench` loads selected model.
`/model unload` releases it.

One-shot prompt:

```powershell
openvino chat "explain this folder"
```

## Model Commands

Top-level:

```powershell
openvino models
openvino download qwen
openvino download tiny
openvino download gemma
openvino delete qwen
openvino status
```

Inside chat:

```text
/model
/models
/model load qwen
/model load tiny
/model load glm
/model load gemma
/model use qwen
/model unload
/model download qwen
/model delete qwen
```

`glm` points to `GLM-4.1V-9B-Thinking`, but it must be exported to OpenVINO first. `openvino download glm` is blocked because the upstream `zai-org/GLM-4.1V-9B-Thinking` repo is not a ready OpenVINO snapshot.

`/model` opens picker:

```text
Enter  load
i      download
d      delete
u      unload
Esc    cancel
```

Chat history: use `PageUp`, `PageDown`, mouse wheel, `Ctrl+Home`, or `Ctrl+End`.

Type `/` to open command palette. Use Up/Down and Enter. Palette shows at most
15 rows and scrolls its viewport as selection moves through all commands.

## Local API

OpenAI-compatible endpoints:

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
POST /v1/completions
```

Inside chat, start API for selected model:

```text
/api
/api start
/api start 18080
/api status
/api stop
```

`/api start` unloads chat model first, starts background server, then loads model
only when first API generation arrives. Default base URL:

```text
http://127.0.0.1:11435/v1
```

Standalone commands:

```powershell
openvino api start
openvino api status
openvino api stop
openvino serve
openvino serve --port 18080 --device GPU --ctx 4096 --kv-cache u4
```

OpenAI Python client:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:11435/v1", api_key="local")
response = client.chat.completions.create(
    model="gemma-4-e2b-it-qat-int4-ov",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

Clients requiring environment variables:

```powershell
$env:OPENAI_BASE_URL="http://127.0.0.1:11435/v1"
$env:OPENAI_API_KEY="local"
```

Server accepts OpenAI function tools and converts Gemma native calls back into
OpenAI `tool_calls`. Tool execution belongs to API client. Server serializes model
requests. Streaming emits live `content` and `reasoning_content` deltas while
keeping native tool syntax hidden. Binding outside localhost requires `--api-key` or
`OPENVINO_CHAT_API_KEY`.

## Chat Commands

```text
/help
/commands
/copy
/raw
/rewind
/reset
/clear
/archive
/exit
/mode
/mode chat
/mode agent
/ctx 4096
/max-tokens 4096
/kv
```

`Esc` stops generation. `Ctrl+C` interrupts current input. Chat and status remain
inside one full-screen terminal application.

## Sessions

```text
/session
/sessions
/new
/save
/load <name>
/delete
/delete <name>
/export
```

Saved sessions:

```text
F:\7ryan\Downloads\.openvino\sessions
```

Exports:

```text
F:\7ryan\Downloads\.openvino\exports
```

Current session saves automatically on exit. `/session` opens resume/delete/new
picker. `/rewind` restores chat and mutable runtime settings to state before most
recent command.

## System Prompt

```text
/system
/system set <text>
/system append <text>
/system reset
/system save
/system load <path>
```

## Tools

```text
/tools
/pwd
/ls [path]
/read <path>
/scan [path]
/grep <pattern> -- [path]
/write <path> <text>
/append <path> <text>
/shell <command>
/storage [path]
/web <query>
/fetch <url>
/diff
/undo tool
```

Tool permission mode:

```text
/permissions
/permissions ask
/permissions allow
```

Default is `ask`.

Read-only tools can run directly. Shell commands, writes, appends, and undo follow
permission setting. Destructive shell commands remain blocked even in `allow` mode.
Tool paths cannot escape configured workspace.

Model-native tool formats supported:

- Qwen `<tool_call><function=...>`
- Gemma 4 `<|tool_call>call:tool{key:value}<tool_call|>` including `<|"|>` strings
- OpenAI `tool_calls`/function JSON
- Legacy `{"tool":"name","args":{...}}`

Tool calls stay hidden from normal answer. Requested tool and arguments appear in
gray. Result returns to model as structured tool response.

## Workspace

```text
/workspace
/workspace set <path>
/cd <path>
/project
```

## Performance

```text
/status
/perf
/ram
/cpu
/gpu
/ctx
/ctx 8192
/kv
/kv auto
/kv u4
/kv u8
/kv f16
/bench
/doctor
/report
/stats
/config
/config set <key> <value>
```

KV-cache precision controls memory used by conversation context:

| Mode | Approximate bytes/value | Use |
| --- | ---: | --- |
| `auto` | Device default | Safest compatibility |
| `u4` | 0.5 | Largest context, smallest cache, possible accuracy loss |
| `u8` | 1 | Balanced memory and quality |
| `f16` | 2 | Highest fidelity, largest cache |

`/kv` opens picker. Changing value persists to `.openvino\config.json`, unloads
loaded model, and applies on next model load. `/ctx` and `/kv` show expected KV and
total memory. Live bar shows process RAM, system RAM, and active GPU or CPU every
second.

Memory values are planning estimates. OpenVINO runtime buffers, hybrid-attention
state, GPU driver allocations, and temporary compile memory can make real usage
higher. Model-list and welcome surfaces omit estimated RAM; `/ctx`, `/kv`, and
`/perf` retain it.

TurboQuant is not integrated into OpenVINO. It is a KV-cache compression algorithm,
not model-weight compression. This app uses supported OpenVINO `KV_CACHE_PRECISION`
instead.

Reports:

```text
F:\7ryan\Downloads\.openvino\reports
```

## Reducing RAM

Best controls, strongest first:

1. Select smaller INT4 model using `/model tiny`.
2. Use `/kv u4` for long context.
3. Lower context with `/ctx 4096` or less.
4. Release model using `/model unload` when finished.
5. Run only one local model process at a time.
6. On Linux, use allocator tuning only after measuring real memory.

OpenVINO IR weights use memory mapping by default, reducing compilation RAM and
allowing mapped pages to be released or shared by operating system. Model compile
still needs temporary memory. `/ram`, `/gpu`, and process RAM in live bar show real
usage; planning estimates exclude compiler and driver allocations.

## UI Helpers

```text
/ui
/ui window
/ui statusline
/ui side
/chart a=2 b=4
/big text
/tilt text
```

## Agent Workflows

```text
/plan <goal>
/task
/task add <text>
/task done <n>
/task clear
/review
```

## Reasoning And Rendering

Reasoning text renders gray. Normal answer starts with green `>` marker. Supported
reasoning wrappers include `<think>...</think>`, malformed `<think/>` closing tags,
`<analysis>`, and Gemma thought channels. Markdown, fenced code, diff additions,
and removals receive terminal formatting after streaming completes.

## Troubleshooting

Check installation and paths:

```text
/doctor
/status
/models
```

Model load can take minutes on first GPU compile. CLI remains open and shows
`loading model`. Later loads may still take time because OpenVINO performs device
transformations.

For out-of-memory or long-context failures:

1. Use `/kv u4` or `/kv u8`.
2. Reduce `/ctx`.
3. Use `/model tiny` for Gemma 4 E2B QAT INT4.
4. Use `/model unload`, then retry.

For poor tool use, verify `/mode agent` and `/tools`. For blocked writes, verify
`/permissions`. For GPU failure, run `/gpu`, `/doctor`, then try
`openvino chat --device CPU`.

Debug reports go to:

```text
F:\7ryan\Downloads\.openvino\reports
```
