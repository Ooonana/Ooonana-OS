# UI and optional catalog refresh — October 8

Core 0.9.9 source refresh, not production ISO or physical hardware certification.

## Design verification

[Concept](assets/ooonana-desktop-concept-20261008.png) uses built-in ImageGen from previous turn, reused without another generation. [Desktop](assets/ooonana-desktop-20261008.png) and [Appearance](assets/ooonana-appearance-20261008.png) use real source GTK/i3/Polybar on isolated Xvfb, original JPEG and native dock. Panel values are fixture data. Browser/IAB cannot render native X11 desktop; native capture replaces browser verification here. No audio played.

Opaque tokens: `#101317`/`#1b1f26` backgrounds, `#f5f5f7` text, `#ffb21a` accent, `#343b46` dividers. Sans 10.5pt body, 19pt page heading, 12pt section title; existing compact traffic-light controls retained.

| Comparison | Concept/render evidence | Repair or intentional difference |
| --- | --- | --- |
| Layout | Sidebar and three Appearance sections | Same order; open sections replace nested boxes |
| Copy | Appearance, Color theme, Motion, Wallpaper, Apply, Refresh | Preserved; original Choose image/Default actions retained |
| Typography | Heading, white section titles, muted descriptions | Shared tokens; actual GTK/font metrics retained |
| Palette | Graphite/white/orange | Flat opaque fills, no generated gradient/blur |
| Dock | Restrained capsule and separate icons | No button outlines; native vector family; browser explicitly changed to blue globe |
| Motion | Short eased hover | 180ms cubic 4px lift, constant dimensions, no idle timer; Reduce motion disables it |
| Wallpaper | Original yellow mascot on black | Original scale preserved, not miniature concept logo; fit clears panel/dock |
| Responsive | Desktop and narrow continuation | 1280×800 and 640×600 bounds; narrow actions stack/wrap with vertical scrolling |

Concept and latest native captures were inspected using `view_image`. Layout/copy/type/palette/icons/spacing were verified against concept with intentional differences listed above, not a pixel-identical generated mockup or hardware animation benchmark. Existing product labels only; no invented marketing copy. Redundant full-path/layout text becomes filename plus full-path tooltip and mode selector. Concept-native 1600×1000 capture and 640px long-Wi-Fi panel also completed owned teardown; software Mesa warnings are not physical GPU certification.

## Repairs and checks

- Theme startup now calls canonical wallpaper setter; default fit previously bypassed existing panel/dock-clear helper. Missing saved paths fall back to original default without overwriting preference. Explicit missing image still refuses.
- Save preferences only after setter success. Failure preserves prior choice. Individual files replace atomically; pair is not a power-loss transaction.
- Blue browser icon resolves in source dock/launcher. Restart/reload running apps to load updated assets.
- Dock hover preserves geometry/focus/bounded RAM-only preview. Appearance footer fits desktop; narrow controls stack and descriptions wrap. Panel 36px/radius 12px.
- Fixture teardown terminates only owned children, escalating only those children. Ubuntu test-host `i3-msg` was a 100-byte no-op stub; preserved it under owned QA evidence and restored exact cached installed-package ELF. Stub origin not established. Controls fixture checks real IPC and waits for initial floating rules.
- Passed scoped checks: Firefox command/remote/root/argv/missing-runtime/reproducibility, wallpaper success-only saving, icons/preferences, dock/reduced motion/focus/previews, GTK/CSS/reflow, third-party controls/actions/movement, native UI shell suite, package factory/full-i3 rootfs fixture, optional catalog dependency closure. New pure tests enter GitHub/GitLab CI.
- Follow-up: incomplete WSL staging omitted core health hooks; repaired staging and all three installed package verifications passed with the existing local public key. Updater now refuses absent/nonexecutable core hooks before changes and pins `CURRENT` snapshot through synchronization. Custom configs and checkpoints retained.
- Remote GitHub run exposed importer fixture ignoring new optional catalog arguments; fixture now models requested imports, leaving dependency checks enabled. Alpine CI also needs GNU tar for reproducible Firefox archives (BusyBox `--sort=name` failure reproduced locally); smoke-job dependencies corrected.

## Packages and safety

[common-tools.list](../configs/packages/common-tools.list) adds 16 optional CLI packages outside default desktop closure. Staging: 701 packages; full-i3/core/AI closure: 552 nodes. Builder checks optional closure too.

Firefox 1.0.0 is setup-launcher version, not browser-engine version. `ooonana get firefox` installs launchers/Flatpak dependency. Nonroot `ooonana-firefox setup` explicitly downloads browser/runtime with normal confirmation. No silent first-launch download, sandbox disabling, model download or profile deletion. Unexpected Flathub URL refuses; failed remote inspection does not silently mutate it. `firefox` forwards args; status/update expose user-owned lifecycle.

Existing local public key matches prior generation; private key stays outside Git/CI. Trust enrollment deferred. Verify archives/metadata/source manifest/checksums/signature together before atomic promotion. Historical generations stay.

## Remaining

1. Coherent supported-base migration: legacy Chromium 131/libraries are not current-security-certified. Firefox isolation does not fix host/kernel/sandbox support ([lifecycle](https://alpinelinux.org/releases/)).
2. Real Firefox runtime download/launch, portals/dialogs and per-user updates on persistent Linux storage; fixtures are not browser execution.
3. Fresh user-built ISO BIOS/UEFI/Rufus, physical cursor/wallpaper/third-party visuals/smoothness. No old-stage resume.
4. Mixed DPI/monitors/hotplug, Korean IME, lock/suspend/WSLg stability, Qt/OpenVINO inference/pressure/recovery.
5. Disposable physical persistence power loss/full storage/recovery and interrupted installed upgrade; radios/audio/GPU/thermals/fans remain physical gates.

Histories/models/custom configs/checkpoints/old screenshot evidence retained. No sound playback.
