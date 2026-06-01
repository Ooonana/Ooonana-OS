# Jarvis-AGI Research Notes

Search target: `jarvis-agi`.

## Main GitHub Match

[vierisid/jarvis](https://github.com/vierisid/jarvis)

Useful concepts:

- Optional background daemon with CLI control
- System awareness through local sidecars
- Screen capture loop
- Native app control
- Shell and filesystem access
- Multi-agent specialist hierarchy
- CLI workflow builder and task runner
- Goal pursuit
- Provider support for Anthropic, OpenAI, Google Gemini, and local Ollama
- Linux, macOS, WSL, and Docker install paths

Ooonana fit:

- Use this as long-term architecture reference.
- Keep `ooonana-ai` as current user-facing CLI.
- Add daemon later as `ooonana-ai daemon`.
- Add sidecar later as `ooonana-ai sidecar`.
- Keep user-facing UI in terminal: slash commands, tables, status lines, JSON, and copyable commands.
- Put all system actions behind permission gates and audit logs.

## Local-First Assistant Reference

[isair/jarvis](https://github.com/isair/jarvis)

Useful concepts:

- Private local assistant
- Offline-capable processing
- Memory with secret redaction
- Tool selection instead of dumping every tool into context
- Screenshot OCR
- Web search
- File access
- Location and time awareness
- MCP expansion

Ooonana fit:

- Keep current redaction and history.
- Add tool registry before broad system control.
- Skip voice input and voice recognition.
- Prefer CLI commands for every feature.

## Ooonana Roadmap

Phase 1:

- Provider router: NVIDIA NIM and Google Gemini
- Provider/model CLI commands
- Provider-specific payload dry-run

Phase 2:

- Read-only system tools: process list, package state, recent files, browser history import by permission
- Memory summarizer and pruning
- Tool registry
- Implemented now: `tools`, `tool system`, `tool processes`, `tool packages`, `tool files`, and `tool activity`

Phase 3:

- Permissioned shell/file actions
- Audit history
- Rewindable task plans
- Implemented now: permission-gated `tool shell`, `audit`, `task add`, `tasks`, `task done`, and `task plan`

Phase 4:

- Optional background daemon
- Local system sidecar
- CLI task monitor
- Text-first visual context summaries

Rule:

- Ooonana may be Jarvis-class, but must not claim AGI.
- Ooonana stays CLI-first.
