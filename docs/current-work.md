# Current work - 2026-10-02

Backend first. ISO building stays with user. Audio backend stays enabled; no playback tests.

## Next tasks

- Cursor: increase current size by **110%**, preserving shape and hotspot proportions. Personal theme 19 -> 21 px; public theme 17 -> 19 px. Regenerate actual Xcursor frames, then update GTK/Xresources/WSL defaults and tests. Queued; not applied yet.
- Native RISC-V64 PDF kernel/rootfs: builds succeed, TinyEMU boot still times out. Preserve working 32-bit PDF until native candidate passes boot/input checks.
- Verify installed password-login/nonroot desktop path in VM or newly built image.
- Physical USB checks: Wi-Fi, Bluetooth, audio, available RAM, zram, fans and OpenVINO inference. WSL/import/UI tests do not prove these.
- Configure CI signing and enroll existing clients through trusted public-key delivery. Private key remains outside Git; no CI secret uploaded.
- Extend reproducibility beyond pinned core OpenVINO bindings to complete first-install Python/system dependency locks.
- Third-party window titlebar buttons: still pending. Current dock/window menus provide minimize/fullscreen/close.
- Temporary build/QA cleanup: automatic recursive removal was blocked by tool policy. Preserve verified generations and user files; no deletion workaround.

## Verified foundation

Private local signing key generated; public trust key bundled. Atomic generation publication/cache, configuration preservation, health-check rollback, update policy/reboot reporting, memory preflight, actual zram reporting, event-driven dock/music, Health/Updates apps, native AI chat polish, WSL XDG handoff and unprivileged query-cache fixes passed scoped tests. Working PDF boots and accepts input. Latest desktop screenshot was captured from real nested WSL i3 without sound playback.

After reboot: local generation signature verified; Windows CRLF pointer compatibility fixed and regression-tested; `OOONANA_RELEASE_PREFLIGHT_OK` passed. This proves build inputs/source checks, not fresh ISO boot or physical hardware functionality. Cursor enlargement remains queued.
