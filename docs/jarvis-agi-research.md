# Jarvis-AGI Research Notes

Search target: `jarvis-agi`.

## Main GitHub Match

[vierisid/jarvis](https://github.com/vierisid/jarvis)

Useful concepts:

- Always-on autonomous daemon
- Desktop awareness through sidecars
- Screen capture loop
- Native app control
- Shell and filesystem access
- Multi-agent specialist hierarchy
- Visual workflow builder
- Goal pursuit
- Provider support for Anthropic, OpenAI, Google Gemini, and local Ollama
- Linux, macOS, WSL, and Docker install paths

Ooonana fit:

- Use this as long-term architecture reference.
- Keep `ooonana-ai` as current user-facing CLI.
- Add daemon later as `ooonana-ai daemon`.
- Add sidecar later as `ooonana-ai sidecar`.
- Put all system actions behind permission gates and audit logs.

## Local-First Voice Reference

[isair/jarvis](https://github.com/isair/jarvis)

Useful concepts:

- Private local voice assistant
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
- Add voice after daemon, memory pruning, and permissions.

## Ooonana Roadmap

Phase 1:

- Provider router: NVIDIA NIM and Google Gemini
- Provider/model CLI commands
- Provider-specific payload dry-run

Phase 2:

- Read-only system tools: process list, package state, recent files, browser history import by permission
- Memory summarizer and pruning
- Tool registry

Phase 3:

- Permissioned shell/file actions
- Audit history
- Rewindable task plans

Phase 4:

- Always-on daemon
- Desktop sidecar
- Voice input/output
- Visual context

Rule:

- Ooonana may be Jarvis-class, but must not claim AGI.
