# OpenVINO Chat

Local terminal and browser chat app for OpenVINO GenAI models.

Runs local models through OpenVINO on Intel GPU or CPU. Includes streaming chat,
reasoning display, model and session pickers, tool use, web search, file editing,
four-level permissions, expandable tool timeline, media attachment tray, crash
recovery, task tracking, and live hardware status.
Ooonana Linux default context is 4,096 tokens to reduce model memory pressure.
Local document retrieval works offline.

## Requirements

- Windows 10/11 and PowerShell 7, or Linux x86_64
- Python 3.12+
- Intel GPU driver supporting OpenVINO GPU inference
- `openvino-genai`, `prompt_toolkit`, `rich`, and `huggingface_hub`

Install project dependencies:

```powershell
python -m pip install -e .
```

Editable install registers a real `openvino` console program through
`pyproject.toml`, in addition to supplied launchers.

### Windows Setup

Run setup bundle from Downloads:

```powershell
.\setup-openvino-chat.ps1
```

Script creates/reuses virtual environment, upgrades package, writes
`$HOME\.local\bin\openvino.cmd`, sets `OPENVINO_HOME`, and adds launcher
directory to user PATH. Bundle includes Ornith 1.5 9B OpenVINO INT4 payload,
installs it into central model folder, then selects `ornith` as initial model.
App is copied into virtual environment, so bundle can be removed after setup.
Open new terminal after setup.

Windows defaults:

```text
venv:    %LOCALAPPDATA%\openvino-chat\venv
runtime: %USERPROFILE%\.openvino
command: %USERPROFILE%\.local\bin\openvino.cmd
```

Override defaults with `-VenvDir`, `-OpenVinoHome`, or `-LauncherDir`.

Repository copy:

```powershell
.\scripts\setup-windows.ps1
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
models:  ~/.openvino/models
config:  ~/.openvino/config.json
command: ~/.local/bin/openvino
```

Linux installer requires Ornith archive beside setup script unless model already
exists. Override archive path with `OPENVINO_ORNITH_ARCHIVE`. It honors
`OPENVINO_MODEL_ROOT` and `OPENVINO_CHAT_CONFIG` and preserves both in launcher.
On Ooonana, use `openvino setup` instead; Ooonana's isolated Ubuntu runtime and
models remain in user home. Browser GUI opens in host desktop; Windows-only
computer-control tools are unavailable on Linux.

Direct repository launcher:

```bash
./openvino.sh chat --device CPU
```

Command launcher:

```text
%USERPROFILE%\.local\bin\openvino.cmd
```

## Runtime Home

All app-owned runtime files live under one folder:

```text
%USERPROFILE%\.openvino
```

Layout:

```text
%USERPROFILE%\.openvino
├─ api\
├─ config.json
├─ exports\
├─ knowledge\
│  ├─ index.json
│  └─ models\
├─ models\
│  ├─ qwen3.5-9b-int4-ov\
│  ├─ qwen3.8-9b-int4-ov\
│  ├─ qwen3.8-4b-int4-ov\
│  ├─ ornith-1.5-9b-int4-ov\
│  └─ gemma-4-e4b-it-int4-ov\
├─ reports\
├─ recovery.json       temporary; removed after clean exit
└─ sessions\
```

Environment overrides:

```powershell
$env:OPENVINO_HOME="$HOME\.openvino"
$env:OPENVINO_MODEL_ROOT="$HOME\.openvino\models"
$env:OPENVINO_CHAT_CONFIG="$HOME\.openvino\config.json"
$env:OPENVINO_CHAT_REPORT_DIR="$HOME\.openvino\reports"
$env:OPENVINO_CHAT_SESSION_DIR="$HOME\.openvino\sessions"
$env:OPENVINO_CHAT_EXPORT_DIR="$HOME\.openvino\exports"
$env:OPENVINO_CHAT_API_DIR="$HOME\.openvino\api"
$env:OPENVINO_CHAT_BENCHMARK_PATH="$HOME\.openvino\benchmarks.json"
$env:OPENVINO_CHAT_KNOWLEDGE_INDEX="$HOME\.openvino\knowledge\index.json"
$env:OPENVINO_CHAT_KNOWLEDGE_MODELS="$HOME\.openvino\knowledge\models"
$env:OPENVINO_CHAT_RECOVERY_PATH="$HOME\.openvino\recovery.json"
```

## Models

| Name | Repo | Local path |
| --- | --- | --- |
| `qwen3.5` | `OpenVINO/Qwen3.5-9B-int4-ov` | `~\.openvino\models\qwen3.5-9b-int4-ov` |
| `qwen3.8` | Local import from `results (1).zip` | `~\.openvino\models\qwen3.8-9b-int4-ov` |
| `tiny` | Local INT4 export of `empero-ai/Qwen3.8-4B-Distill` | `~\.openvino\models\qwen3.8-4b-int4-ov` |
| `gemma` | `OpenVINO/gemma-4-E4B-it-int4-ov` | `~\.openvino\models\gemma-4-e4b-it-int4-ov` |
| `oxcoder` | Local OpenVINO export of `OrionLLM/OxCoder-9B` | `~\.openvino\models\oxcoder-9b-int4-ov` |
| `granite` / `granite4.2` | Local text-only OpenVINO export | `~\.openvino\models\granite-4.2-8b-int4` |
| `ornith` | Local installer payload from `ornith-ai/Ornith-1.5-9B` | `~\.openvino\models\ornith-1.5-9b-int4-ov` |

### Image, Video, and Audio Input

Drop or type a local media path directly into an ordinary message. Quoted paths
with spaces work, including paths inserted by Windows Terminal drag and drop:

```text
Describe "F:\Media\screen shot.png"
Summarize F:\Media\demo.mp4
```

`/media` shows modalities accepted by the selected OpenVINO model folder and
installed runtime. Current Gemma 4, Qwen 3.5, Qwen 3.8, and Ornith VLM exports
accept images and videos. Video is sampled at about one frame per second, up to
60 frames. Gemma 4 supports audio at the base-model level, but the installed
OpenVINO export/runtime must also expose audio input; the app reports audio as
unavailable instead of pretending to process it. Media applies to the current
turn, so include the path again when a follow-up needs the same media.
Detected paths appear in an attachment tray before submission, then show
`processing`, `used`, or `failed` state during the turn.

### Sampling Presets

Defaults activate when `--temperature` and `--top-p` are omitted:

| Model | Profile | Settings |
| --- | --- | --- |
| Gemma 4 E4B | general/coding | `temperature=1.0`, `top_p=0.95`, `top_k=64` |
| Qwen 3.5 thinking | general | `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0`, `presence_penalty=1.5`, `repetition_penalty=1` |
| Qwen 3.5 thinking | coding | `temperature=0.6`, `top_p=0.95`, `top_k=20`, `min_p=0`, `presence_penalty=0`, `repetition_penalty=1` |
| Qwen 3.5 direct | general | `temperature=0.7`, `top_p=0.8`, `top_k=20`, `min_p=0`, `presence_penalty=1.5`, `repetition_penalty=1` |
| Qwen 3.5 direct | coding/reasoning | `temperature=1.0`, `top_p=1.0`, `top_k=40`, `min_p=0`, `presence_penalty=2`, `repetition_penalty=1` |
| Imported Qwen 3.8 9B / 4B tiny | general/coding | `temperature=0.6`, `top_p=0.95`, `top_k=20` |
| Official Qwen 3.8 graded thinking | all effort levels | `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0`, `presence_penalty=0`, `repetition_penalty=1` |
| Official Qwen 3.8 direct | off | `temperature=0.7`, `top_p=0.8`, `top_k=20`, `min_p=0`, `presence_penalty=1.5`, `repetition_penalty=1` |
| Ornith 1.5 | general | `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0`, `presence_penalty=1.5`, `repetition_penalty=1` |
| Ornith 1.5 | coding | `temperature=0.6`, `top_p=0.95`, `top_k=20`, `min_p=0`, `presence_penalty=0`, `repetition_penalty=1` |

Interactive chat chooses Ornith coding profile for coding requests. Local API
defaults to general; pass `"profile": "coding"` to select coding preset. Explicit
sampling fields override preset. Qwen 3.8 supports long reasoning output; use
`--ctx 32768 --max-new-tokens 16384` only when enough RAM is available.

`/effort` changes model-card sampling presets without pretending temperature is
native reasoning depth:

| Effort | Sampling behavior |
| --- | --- |
| `low` | Always use precise/coding preset. Lower randomness on Qwen and Ornith. |
| `medium` | Automatically choose general or coding preset from request. Default. |
| `high` | Always use general/reasoning preset. Broader sampling on Qwen and Ornith. |
| `custom` | Manually edit all six sampling values. Saved separately for each model folder. |

Gemma keeps `temperature=1.0`, `top_p=0.95`, and `top_k=64` at every effort because
its model card specifies one standardized preset across use cases. Explicit CLI or
API sampling parameters override effort preset.

`/thinking` separately controls model-native reasoning. App reads local
`chat_template.jinja`; binary templates expose `on/off`, while graded templates
expose `xhigh/medium/low/off`. Saved `on` maps to native `xhigh` where supported.
Unsupported native thinking tiers are rejected instead of simulated with prompt text.
Model picker and `/model list` show both effort and thinking modes.

`/duck on` enables Quack, an intentionally loud personality with a yellow-orange UI theme
across every task:
general conversation, explanations, learning, writing, brainstorming, planning,
research, creative work, coding, and computer actions. English replies use frequent
`quack`; Korean replies use `꽥` and `꽥꽥`. Quack never mixes English and Korean in
one reply, except unavoidable code, commands, paths, URLs, and proper names. Quack
mode adds responsive full and compact two-tone ASCII portraits with raised wings,
orange bill, and small feet. In Quack mode, an active portrait stays centered in
the chat area, blinks, bobs vertically while speaking, and streams replies through
speech balloons that grow with available space; each spoken paragraph gets its own
bubble. Portrait position stays fixed as speech grows. Eyes react to listening,
thinking, and tool outcomes; the beak stays still. Speech is white, with
yellow-orange borders and labels. Bubble and caption wrapping use terminal-cell width, so Korean and other
wide characters keep borders aligned. Very short panes switch to compact portraits
without overflowing chat. Transcript remains available with normal history scrolling.
Press `F1` or enter `/help` for a scrollable reference of every command, tool, and shortcut.
Use `/help model`, `/help quack`, `/help keys`, `/help api`, or another topic to filter.
Help opens at the beginning, leaves chat and rewind/redo untouched, and closes with `F1` or `Esc`.
Press `F2` for the complete latest reply, including content beyond the bubble preview.
The reader supports Markdown, code colors, `PageUp`/`PageDown`, and
`Ctrl+Home`/`Ctrl+End`. `F2` or `Esc` returns to the character without erasing input.
Latest reply is also restored when resuming or rewinding a session.
On wide terminals, `F3` cycles **Chat**, **Tools**, and **Charts** sidebar tabs.
Chat holds user and assistant turns, preserves scroll position during streaming,
and counts new rows while scrolled up. Tools shows commands, outcomes, and durations;
`F4` opens full timeline details while idle. Current tool activity has a separate
elapsed-time badge beneath the bubble, so it never replaces Quack's spoken text.
`/chart`, `/big`, `/tilt`, and model-generated charts, diagrams, or tables appear
in Charts. Each tab scrolls independently. New visuals do not interrupt scrolled-up
conversation reading. Press `Esc` while
idle to dismiss a visual without clearing typed input. `/sidepanel on|off` toggles the
panel; the typo-compatible `/sidepannel` alias also works. Normal OpenVINO mode uses
the panel only for active tasks. On narrow terminals, visuals stay in the transcript
and other panels collapse automatically so chat remains usable. User turns
use a blue `>` marker, including the bottom line of the Quack scene.
Quack voice never enters code, commands,
JSON, tool arguments, URLs, paths, raw tables, or file contents. Native thinking
automatically stays off while Quack mode is active. Every fresh launch starts in
normal mode; `/duck on` affects current session only. `/duck off` restores normal
personality and UI colors. Running `/duck` opens an on/off picker.

When Luci is installed, OpenVINO Chat exposes a read-only `luci_history` tool for
questions about what the user previously did, saw, heard, opened, or worked on.
The app resolves Luci through its per-user discovery file, so no personal path is
stored in code or installer. When a query needs Luci and it is closed, the tool
starts it, waits until the CLI is ready, performs the read-only query, and stops
only that temporary instance. Luci is one optional evidence source for past
computer activity; it does not define Quack or limit Quack to computer work. Quack
must ground Luci-backed memory claims in returned results.

Final-turn thoughts are excluded from model history; tool-call thoughts stay
attached to their tool turn. Gemma thought-channel output and Ornith/Qwen
`<think>` output render separately from final answer. Behavior follows the
[Qwen 3.8 model card](https://huggingface.co/Qwen/Qwen3.8-27B-FP8),
[Qwen 3.5 model card](https://huggingface.co/Qwen/Qwen3.5-9B),
[Gemma 4 model card](https://huggingface.co/google/gemma-4-E4B), and
[Ornith model card](https://huggingface.co/ornith-ai/Ornith-1.5-9B).

Select a converted model without copying its large files:

```text
/model import F:\path\to\openvino-model
```

Import accepts folders containing `openvino_model.xml` or
`openvino_language_model.xml`. `/model use <name|path>` remains an equivalent
compatibility command. Incomplete folders show as `invalid` and cannot be selected.

Every visible folder created directly under `~\.openvino\models` appears in
`/model` and `openvino models` automatically. Restart is not required. Folder name
becomes model name. Hidden folders beginning with `.` are ignored so unfinished
downloads never enter model picker.

Download OpenVINO-ready Hugging Face model by repo ID or URL:

```text
/model import OpenVINO/example-int4-ov
/model download https://huggingface.co/OpenVINO/example-int4-ov
openvino download OpenVINO/example-int4-ov
```

Download first checks repository file list. Source Transformers repositories are
rejected before large weights download. Convert those separately with Optimum Intel,
then place resulting folder under model root. Imported Hub models use
`owner--repository` folder names and retain repository ID in local manifest.

## Start

```powershell
openvino
openvino chat
openvino chat --device GPU
openvino chat --device CPU
openvino chat --ctx 16384
openvino chat --ctx 16384 --max-new-tokens 4096
openvino chat --kv-cache u4
```

`--ctx` is total prompt plus response capacity. Default is `16384`; Ornith can
address much more, but very large context is impractical on a 16 GB machine.
`/max-tokens` sets response ceiling. Old conversation turns are omitted
automatically when needed, while saved session history stays intact.

Models load lazily. Starting `openvino` does not put model weights in RAM or GPU
memory. First normal message, `/plan`, `/review`, or `/bench` loads selected model.
Open `/model`, then press `u` to release it.

One-shot prompt:

```powershell
openvino chat "explain this folder"
```

## Model Commands

Top-level:

```powershell
openvino models
openvino download qwen3.5
# tiny is a local converted model; import its OpenVINO folder or conversion archive
openvino download gemma
openvino delete qwen3.5
openvino status
```

Inside chat:

```text
/model
```

`/model` opens picker:

```text
Enter  load
i      download
d      delete
u      unload
Esc    cancel
```

Model and session pickers also support `Home`, `End`, `PageUp`, and `PageDown`.

Press `F4` or run `/timeline` for tool history. Select a call, press Enter to
expand command and result, or press `r` to retry it. Rows retain duration,
success state, and retry count.
Expanded details wrap to terminal width; `PageUp`/`PageDown` scroll command and
result. Failed commands appear in red. One retry runs at a time; close timeline
after it finishes. Retries still require permission and tracked file edits can
be rewound. Opening a permission dialog preserves unfinished input.

Drag normally to select terminal text. Chat history uses `PageUp`, `PageDown`,
`Ctrl+Up`, `Ctrl+Down`, `Ctrl+Home`, or `Ctrl+End`. Press `F6` to enable mouse
wheel history scrolling; use `Shift+drag` to select while that mode is active.

Long input expands and soft-wraps up to eight rows. Plain Up/Down moves through
wrapped input rows. `Ctrl+J` inserts a real newline; Enter submits.

Type `/` to open command palette. Use Up/Down or `Ctrl+N`/`Ctrl+P`, `Tab` to
complete, Enter to run, and Esc to close. Palette shows at most 15 rows, shrinks
on short terminals, and scrolls its viewport through all commands. Rows show one
base command per feature; required usage appears after selection.

Live status uses two compact bottom rows so hardware metrics do not cover chat.
`/sidepanel on|off` controls the responsive panel. Quack mode has Chat/Tools/Charts tabs (`F3`);
normal mode shows active tasks. Completed task panels collapse automatically.

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
openvino serve --port 18080 --device GPU --ctx 16384 --kv-cache u4
```

OpenAI Python client:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:11435/v1", api_key="local")
response = client.chat.completions.create(
    model="qwen3.8-4b-int4-ov",
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

Server accepts OpenAI function tools and converts model-native calls back into
OpenAI `tool_calls`. Tool execution belongs to API client. Server serializes model
requests. Streaming emits live `content` and `reasoning_content` deltas while
keeping native tool syntax hidden. Binding outside localhost requires `--api-key` or
`OPENVINO_CHAT_API_KEY`.

OpenAI `tool_choice` supports `auto`, `none`, `required`, and a named function.
Named or required choices constrain Qwen/Ornith structural tool generation and add
a direct instruction for models using native text tool syntax.

API also accepts `top_k`, `min_p`, `presence_penalty`, `repetition_penalty`,
`profile` (`general` or `coding`), `effort` (`low`, `medium`, or `high`), and
model-native `reasoning_effort` in request body. It also accepts `knowledge_mode`
(`offline`, `auto`, or `web`) and
uses the same local document index. Chat requests auto-compact old turns by
default; send `"auto_compact": false` to disable it for one request. Supported
native reasoning values come from active model template. `high` maps to native
`xhigh` for OpenAI-client compatibility; unsupported values return an error.
API server inherits saved Duck mode. Send `"duck": true` or `"duck": false`
to override it for one chat-completion or text-completion request.

## Chat Commands

`/help` or `F1` opens complete scrollable help in both modes. `/help <topic>` filters
by feature or command; try `/help keys`, `/help tools`, `/help model`, or `/help quack`.
Use `PageUp`/`PageDown`, `Ctrl+Home`/`Ctrl+End`, or mouse wheel with `F6` enabled.
Close with `F1` or `Esc`. Help does not change chat, consume a rewind step, or clear redo.

```text
/help
/commands
/copy
/raw
/timeline
/rewind
/redo
/compact
/compact status
/compact auto off
/reset
/clear
/archive
/exit
/ctx 16384
/max-tokens 4096
/kv
/effort
/effort high
/effort custom
/effort custom temperature=0.8 top_p=0.95 top_k=20 min_p=0 presence_penalty=0 repetition_penalty=1
/thinking
/thinking off
/duck
/duck on
/duck off
```

`Esc` stops generation. `Ctrl+C` interrupts current input. Chat and status remain
inside one full-screen terminal application.

## Context Compaction

Automatic compaction is enabled by default. Near 90% of context capacity, or
earlier when response-token reserve requires it, OpenVINO Chat summarizes older
complete turns into hidden working memory. Four recent turns stay verbatim. Full
chat transcript, export, and session history remain visible and unchanged.
Requested output space is reserved before generation, and the engine clamps output
to remaining context so compaction does not interrupt a response mid-stream.

```text
/compact
/compact status
/compact auto on
/compact auto off
```

`/compact` runs it immediately. `state: compacting` is shown while summary is
generated; completion appears as a transient notice instead of cluttering chat
history. The status bar shows cached context use and `compact: auto`. `Esc` cancels
without changing compaction state. If runtime still
reports context-limit failure before any output or tool action, automatic mode
compacts and retries once. Rewind, redo, exit, and session resume preserve compact
memory state. OpenAI chat API applies same policy to request copy and protects its
four newest user turns.

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
%USERPROFILE%\.openvino\sessions
```

Exports:

```text
%USERPROFILE%\.openvino\exports
```

Current session saves automatically on exit. `/session` opens resume/delete/new
picker. `/rewind` undoes the previous submitted chat turn or slash command;
repeat it to move back through up to 50 checkpoints. `/redo` moves forward
through rewound checkpoints and can also be repeated until no newer checkpoint
remains. Saved sessions retain the styled transcript and rewind timeline, so a
resumed session rewinds its previous turn instead of the `/session` command.
Thought color, tool rows, chat/runtime settings, and restored input survive the
resume. In the current process, rewind also covers tracked `write`/`append` edits
and knowledge-index changes. Those filesystem checkpoints are intentionally not
replayed after restarting the app. Any new turn or command clears redo. Arbitrary
shell side effects, downloads, deletions, exports, and external processes cannot be reversed.
`/undo` separately reverses the latest tracked file-tool edit.
Session files use atomic replacement, so an interrupted save keeps previous valid
copy. Missing or corrupt sessions report error and return to chat.
While typing, unfinished input is saved with a short debounce so keystrokes stay
responsive. A submitted prompt is checkpointed immediately. After a crash, next
launch restores the active saved session and places unfinished input back in the
editor. Clean exit removes `recovery.json`.
Recovery writes are serialized; disk failures report a warning instead of crashing
chat. Attachment detection runs in the background so slow drives do not block typing.
Saved sessions never restore old permission grants. One-shot `openvino chat "..."`
runs deny write/shell actions unless always-allow permission was explicitly saved.

## System Prompt

```text
/system
/system set <text>
/system append <text>
/system reset
/system save
/system load <path>
```

Default prompt gives models a compact tool workflow and the active shell syntax.
It includes current date and active knowledge policy.
`/system set`, `/system append`, and `/system load` replace it until
`/system reset`. Session resume upgrades saved default prompt to current version;
custom prompts remain unchanged.

## Knowledge And Local RAG

```text
/knowledge
/knowledge mode offline
/knowledge mode auto
/knowledge mode web
/knowledge add <file-or-folder>
/knowledge search <query>
/knowledge list
/knowledge setup
/knowledge reindex
/knowledge clear
```

`offline` uses indexed local documents and never exposes web tools. `auto` uses
local documents and exposes web tools only for explicit web requests or unstable
facts such as news, prices, weather, and current versions. `web` exposes web
tools on every turn. Default is `auto`.

Indexing supports common text, Markdown, source-code, JSON, YAML, TOML, CSV, and
HTML files up to 2 MB each. Retrieval uses a persistent lexical index immediately.
`/knowledge setup` optionally downloads OpenVINO INT8 BGE embedding and reranking
models, about 425 MB total, then reindexes current sources for semantic retrieval.
These models load only during indexing/search and do not load at app startup.

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
/startup
/web <query>
/fetch <url>
/diff
/undo tool
```

`luci_history` is model-invoked, read-only, and appears in `/tools` when the
assistant needs personal computer history. Luci starts on demand when installed.
When the tool starts Luci, it stops Luci again after the query. A Luci instance
already running before the query is left running.

Tool permission mode:

```text
/permissions
/permissions ask
/permissions allow
/permissions always
```

Default is `ask`.

`/permissions` opens a temporary picker and closes after selection. `allow`
lasts for current process. `always` persists in `config.json`. In `ask` mode,
risky tool requests offer `Deny`, `Allow once`, `Allow session`, and
`Always allow`. Use arrows and Enter; shortcuts are `n`, `y`, `s`, and `a`.

Read-only tools can run directly. Shell commands, writes, appends, and undo follow
permission setting. Destructive shell commands remain blocked even in `allow` mode.
Tool paths cannot escape configured workspace.

Model-native tool formats supported:

- Qwen `<tool_call><function=...>`
- Ornith `<tool_call><function=...>` and JSON tool calls
- Gemma 4 `<|tool_call>call:tool{key:value}<tool_call|>` including `<|"|>` strings
- OpenAI `tool_calls`/function JSON
- Legacy `{"tool":"name","args":{...}}`

Tool calls stay hidden from normal answer. Requested tool and arguments appear in
gray. Result returns to model as structured tool response. Each turn receives only
intent-relevant tool schemas. Tool name, required arguments, extra arguments, and
argument types are validated before execution. Qwen and Ornith tool blocks also use
OpenVINO structural-tag guidance once `<tool_call>` generation begins. Gemma keeps
its native `call:name{...}` format and uses strict validation after parsing.

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
/ctx 16384
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

`/kv` opens picker. Context and KV changes persist to `.openvino\config.json`.
Changing KV unloads loaded model and applies on next model load. `/ctx` and `/kv`
show expected KV and total memory. Live bar shows selected model, active state
(`lazy`, `ready`, `loading model`, `compacting`, `thinking`, `generating`, or tool activity),
process RAM, system RAM, and active GPU or CPU every second. Active states show
elapsed seconds without animated dots.

Native model turns use OpenVINO `ChatHistory`, allowing runtime reuse of common
conversation state when supported. Every completed generation records input/output
tokens, elapsed time, first-token latency when streaming, tokens per second, and
peak observed process RAM. `/bench` runs a short sample and shows accumulated
profile data. Profiles are stored at `.openvino\benchmarks.json`.

Memory values are planning estimates. OpenVINO runtime buffers, hybrid-attention
state, GPU driver allocations, and temporary compile memory can make real usage
higher. Model-list and welcome surfaces omit estimated RAM; `/ctx`, `/kv`, and
`/perf` retain it.

TurboQuant is not integrated into OpenVINO. It is a KV-cache compression algorithm,
not model-weight compression. This app uses supported OpenVINO `KV_CACHE_PRECISION`
instead.

Reports:

```text
%USERPROFILE%\.openvino\reports
```

## Reducing RAM

Best controls, strongest first:

1. Open `/model` and select smaller INT4 model.
2. Use `/kv u4` for long context.
3. Lower context with `/ctx 8192` or `/ctx 4096`.
4. Open `/model` and press `u` when finished.
5. Run only one local model process at a time.
6. On Linux, use allocator tuning only after measuring real memory.

OpenVINO IR weights use memory mapping by default, reducing compilation RAM and
allowing mapped pages to be released or shared by operating system. Model compile
still needs temporary memory. `/ram`, `/gpu`, and process RAM in live bar show real
usage; planning estimates exclude compiler and driver allocations.

## UI Helpers

### Desktop And Browser GUI

Start `openvino`, then enter `/gui` for a dedicated desktop window. Keep terminal running.
Use `/gui browser` for the browser fallback. Windows desktop uses pywebview with
WebView2; rerun setup when upgrading to install dependencies. Linux requires a
supported pywebview GTK/Qt backend; browser fallback remains available.
Normal mode opens `openvino.html`; Quack mode opens `duck.html`.
Switching personality updates the page without restarting or loading another model.
Use `/tui` or the TUI button to return to the same terminal session. Desktop closes
when returning to terminal, without unloading the model. Closing browser
restores terminal control after 15 seconds without a browser heartbeat.

GUI shares the existing command handler, history, rewind/redo, model, permissions,
tool execution, compaction, and settings. No separate chat backend or second model
process is started. `/api` remains the separate OpenAI-compatible API feature.
GUI renderer uses additional RAM; model weights are not duplicated by `/gui`.

- Enter sends; Shift+Enter or Ctrl+J adds a line. Slash menu shows up to 15 matches.
- During generation, type and press Enter to queue another message. Up to eight
  messages (64,000 characters each) run FIFO after current turn. GUI queue tray
  supports Edit, Remove, Pause, Resume and Clear. In TUI use
  `/queue [pause|resume|clear|remove ID|edit ID]`. Esc or permission denial pauses
  queued work. Resume explicitly. Queue is in-memory and does not survive exit.
- Models, Sessions, Effort, and permission choices use dialogs. All slash commands
  remain available through input and `/help`.
- Quack has round blinking eyes, orange ASCII beak, and speaking bob. Pause button
  and operating-system reduced-motion preference stop animation. Beak never moves independently.
- One paragraph appears per speech bubble. Previous/Next, Latest, Read reply, and
  Copy full reply keep long responses accessible without covering character.
- Reply area uses available height; character scales down when input or queue needs
  room. Input grows to roughly one-third of the window before scrolling. TUI
  bubbles keep fixed width and use free rows above the lower character position.
- Chat, Tools, and Charts scroll independently. Normal mode shows tasks only when
  present. On narrow windows the side panel starts closed and opens as a drawer.
- Attach button, paste, or file drop uploads supported media to
  `~/.openvino/attachments/gui`, limited to 256 MiB per file. Uploaded copies stay
  there for session reuse; remove unused copies manually when no longer needed.

HTML files must be opened through `/gui`, not by double-clicking them. GUI server
binds only to `127.0.0.1` on a free port, requires a per-run token for data/actions,
rejects foreign origins/hosts, and serves only bundled assets. No CDN is required.
Do not share the token-bearing launch link or expose GUI through a network proxy.

### Terminal Controls

```text
/ui
/ui window
/ui statusline
/ui side
/sidepanel on
/sidepanel off
/chart a=2 b=4
/big text
/tilt text
```

## Agent Workflows

### Tool Reliability

Grammar failures fall back for the current request, not the engine lifetime.
Generic JSON tool calls must be the complete response, a standalone JSON fence,
or follow a recognized reasoning block; explicit native tool markers remain supported.
Explanatory prose is not scanned for generic JSON calls. Python debug logging under
`openvino_chat.engine` records `native_tool_template_failed` and `structured_tool_fallback`
diagnostics without showing them in ordinary chat.

Native templates receive tool schemas; fallback prompts now receive complete
argument schemas too. Korean requests and follow-ups route to relevant tools.
Unambiguous `content` arguments for write/append normalize to `text`. All calls
validate before approval. Denied/stopped actions do not retry through another
tool, and identical failed calls stop after two attempts. Persona affects spoken
replies only, never tool protocol or approvals.

Additional model tools: `file_info`, `edit_text`, `processes`, `system_info`, and
`computer`. `edit_text` requires exactly one match and participates in rewind.
Process listing returns names/IDs only, not command lines.

### Computer Use

Windows-only local implementation, independent of Codex's computer-use service.
Requires pywinauto, installed by Windows setup. Typed `computer_*` tools expose
app discovery/launch, window metadata/state, screenshots, click, insert/replace
text, supported keys, scrolling, native dragging, secondary actions and activation.
`computer_capabilities` describes support without interacting. Desktop calls follow
state-based routing: discovery first, inspection after discovering windows, then
only actions supported by observed controls. Discovery remains available for recovery.
The legacy `computer` wrapper remains internal compatibility, not a normal model tool.
Only the first tool call in each model response executes; subsequent actions require
a new generation after receiving that result. Desktop access follows
separate computer permissions: **Ask** (default), **Allow session**, or **Always
allow**. Automatic access requires warning confirmation and registered global stop
shortcut. File/shell permissions remain separate. Approval shows observed targets
and exact arguments. `/computer status` reports access and shortcut availability;
`/computer ask` revokes automatic access. Rewind cannot restore revoked access.

Snapshots expire after 60 seconds and each mutation consumes its snapshot. Changed
window identity, changed controls, protected/password fields, and OpenVINO's own
windows are rejected. No secure-desktop access or automatic administrator elevation.
Invalid/stale targets are rejected before asking permission and checked again after
approval. Worker input/output uses UTF-8, including Korean window/control names.
Vision-capable exports receive screenshots; text-only models must use observed
accessibility IDs and cannot perform coordinate clicks. Some custom app controls
may not expose usable accessibility information.

**Alt+Shift+S stops current work globally and pauses queued messages.** Stop does
not revoke saved Always access. F8 also stops active computer workers; Esc stops
through the app window. Automatic access is disabled if another app owns the global
shortcut. `/computer stop` also requests interruption from the composer.
Timeout is 15 seconds per call. Already-completed clicks cannot be undone by Esc
or chat rewind. User must handle purchases, security changes, password entry and
irreversible actions manually. Screen/app contents are untrusted data, not commands.
One rolling screenshot per process is kept in `~/.openvino/attachments/computer`;
these captures may contain private data and are not uploaded to a cloud service.
These controls are not an operating-system sandbox. File tools enforce workspace
boundaries; approved shell commands and computer actions can affect resources outside
that workspace. Review automatic-access warnings before enabling broader access.

Background UIA/native-message actions do not inject global mouse or keyboard input.
Visible agent marker now persists between computer actions and model thinking once
a target has been observed. It runs in a separate click-through renderer, tracks
observed target positions without moving the physical mouse, and closes when the
turn completes, fails, or stops. Renderer failure retains temporary-marker fallback.
This is not a second Windows cursor. Explicit activation and app
launch can change focus. Some apps reject background input/capture; OLE drag/drop
and arbitrary global shortcuts are unsupported. Full independent control across
all apps requires a separate Windows session or VM, not this shared-desktop backend.

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

GUI source and request flow:

```text
src/openvino_chat/
  cli.py            shared slash commands and session worker
  tui.py            terminal event loop, buffer, input, dialogs
  gui.py            authenticated loopback bridge into same event loop
  desktop.py        native window hosting same HTML, no duplicate model
  computer.py       snapshot validation and cancellable computer worker
  computer_worker.py Windows UI Automation adapter
  web/
    openvino.html   normal-mode GUI entry
    duck.html       Quack-mode GUI entry
    duck.css        responsive layout, themes, character motion
    duck.js         streaming view, browser input, dialogs, uploads
  agent.py          context, model interaction, tool loop
  engine.py         OpenVINO inference
  tools.py          permission-gated tool execution
  sessions.py       persistence and recovery

Browser -> gui.py -> tui.py mediator -> cli.py -> agent.py/engine.py/tools.py
Shared chat buffer and status -> gui.py -> browser rendering
```

Check installation and paths:

```text
/doctor
/status
/model
```

Model load can take minutes on first GPU compile. CLI remains open and shows
estimated `loading model ~N%`, then exact elapsed seconds. Estimate learns from
previous successful load. Later loads may still take time because OpenVINO performs
device transformations.

For out-of-memory or long-context failures:

1. Use `/kv u4` or `/kv u8`.
2. Reduce `/ctx`.
3. Open `/model` and select smaller Gemma E2B model.
4. Open `/model`, press `u`, then retry.

For poor tool use, verify `/tools`. For blocked writes, verify
`/permissions`. For GPU failure, run `/gpu`, `/doctor`, then try
`openvino chat --device CPU`.

Debug reports go to:

```text
%USERPROFILE%\.openvino\reports
```
