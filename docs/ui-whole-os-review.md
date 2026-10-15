# Whole-OS UI review

Goal: inspect and improve the whole Ooonana OS UI, especially small details.
This goal remains **active**. A passing catalog is not whole-OS completion.
Preserve opaque graphite/amber, paper light mode, rounded controls and current
mascot/cursor identity. Do not build an ISO or play sound during review.

## Coverage ledger

| Surface / paths | Current evidence | Work still required |
| --- | --- | --- |
| Desktop wallpaper, cursor, native icons, theme | Earlier committed captures; current source inventory | Fresh composited desktop, cursor hotspot/scale, icon consistency and selection states |
| Panel / music / AI / notifications / tray | Existing panel fixture, not rerun in this pass | Short/long content, empty/playing/paused media, expanded notifications, 640/1024/1280 layouts |
| Dock | Existing owned-window fixture, not rerun in this pass | Tooltips, previews, multi-window menu, active/minimized states, edge placement and keyboard path |
| Native Launcher | Fresh initial-state render at 640×600 and 1024×768, dark/light | Empty/no-match/long labels, keyboard navigation, launch failure |
| Wi-Fi / Bluetooth | Fresh initial-state windows, enterprise credentials and pairing dialog | Populated lists, hidden-network form, permission/service failure, long device names, focus/keyboard |
| Settings: all six pages | Fresh initial-state captures, 640×600 dark/light and 1024×768 dark | Scaled text, completion/error/rollback, file chooser, long system values, keyboard navigation |
| Setup | Fresh initial-state capture | Static-network expansion, validation/review/apply/failure and scaled text |
| Sound / brightness / music | Fresh initial-state captures, no audio playback | Device/track overflow, unavailable/disabled states, mute/route semantics, keyboard and responsive controls |
| Power | Fresh initial-state capture | Confirmation/cancel, pending/error states, unavailable actions, lock/logout/suspend in isolated session |
| Notifications | Fresh populated sample | Long/multiline messages, grouping, actions, unavailable service, privacy toggle and keyboard |
| Packages | 771px overflow fixed; compact captures and native candidate busy/error/retry/reduced-motion/lifecycle tests pass | Install/remove/upgrade dialogs and close-in-flight UX |
| Health / Updates | 735px overflow fixed; compact/native candidate pending/error/retry and default-Cancel tests pass | Readable real health results, full metadata confirmation interaction |
| Wi-Fi / Bluetooth signal maps | 658×750 overflow fixed; populated/empty/light/dark native candidate render, bounded labels, full-name tooltips and accessibility checks pass | Real data refresh/focus integration and physical radio/session behavior |
| Task Manager | Process/performance pages fit tested layouts; real plotted theme background and contrast checked in native candidate | Live graphs, crowded values, sorting/filtering, selected-process changes, terminate confirmation |
| AI / offline setup / model UI | Fresh initial native chat shell | Real transcript/code rendering, long titles, composer, loading/low RAM/cancel/restart and offline dialogs; bundled OpenVINO Qt UI |
| Installer GUI / text wizard | Builder-generated entry points identified | Step-by-step render, disk/swap/persistence summary, safe default focus, validation/back/cancel/failure; no physical install |
| Shared dialogs / menus / tooltips | Common helpers and missing catalog paths identified | Short/long errors, prompt focus/secret labels, file pickers, escape/return, text scale, clipping |
| Third-party apps | Existing Geany/Nemo/Chromium/Qt/Firefox fixtures, not rerun now | Current base decorations/menus/dialogs, file picker, native theme adaptation and controls |
| Window manager | Existing owned i3 control fixtures, not rerun now | Drag/resize, tiling/tabs, workspaces, focus, maximize/fullscreen/restore and transient modal behavior |
| GRUB: live / audio submenu | Most recent mascot patch has 640×480 and 1280×800 real EFI captures | Compare current output; installed/minimal boot menus remain separate review targets |
| Boot / shutdown / reboot / persistent setup | Most recent wordmark/prompt source and PTY captures | Error/serial/reduced motion, install paths and real framebuffer handoff; physical USB tests separate |
| Bootable PDF UI | Previous source/VM fixtures; browser viewer requires manual check | Viewer rendering, keyboard/Backspace, focus, responsive controls and perceived command delay |
| Accessibility / input / displays / session | Initial accessible controls and theme captures only | Text scale, keyboard/focus, clipboard, Korean composition, WSLg input, multi-monitor/DPI/hotplug, login/lock/logout/suspend/resume |

Windows Computer Use failed during initialization with “failed to write kernel
assets … path specified (os error 3)”. No fallback Windows automation used.
Linux Xvfb fixtures remain available; live WSLg behavior is not certified.
Previously denied local-PDF browser navigation is not retried or bypassed.

## Current batch evidence

- Clean starting source: `f5fb618`.
- Private QA root: `/var/tmp/ooonana-whole-ui-20261015.n7zRUus3`.
- Baseline catalog: 25 pages at 1024×768 dark passed bounds; both 640×600 themes
  exposed Packages, Health, Updates and both signal-map overflows.
- Impeccable bounded pass: one initial batch, one confirmation batch; no repeated
  cosmetic loops. Functional regressions are repaired and retested separately.
- New focused tests use mocked queues and owned windows only: pending/disabled
  controls, duplicate action refusal, error/retry styling, reduced-motion timer
  suppression, ignored late callbacks and default-Cancel metadata confirmation.
- Plot tests check text/data contrast, bounded nonoverlapping labels, full-name
  tooltip/accessibility text, empty state and the real painted chart background.
- This evidence does not prove real hardware, physical USB recovery or every
  application action. Remaining rows stay in scope rather than being marked done.

## Batch 1 results

- All **25 named pages** pass window bounds at 640×600 in dark and light;
  1024×768 dark and 1024×768 light at **125% text** also pass. These are 100
  initial-state checks, not 100 distinct interaction flows.
- Action wrapping is explicitly scoped. A shared one-column experiment made
  Wi-Fi/Sound too tall; regression captures caught it, original defaults were
  restored, and the entire catalog passed again.
- Real Ooonana Alpine v3.24 GTK libraries passed the focused detail fixture in
  private mount/PID/network namespaces, UID1000, dark and light. The keyboard
  fixture gives its owned X11 window actual focus before walking all six action
  buttons; no extra FlowBox wrapper Tab stops. This is not WSLg keyboard proof.
- Signal-map compass letters removed because layout angles are not measured
  bearings. Existing explanatory copy and stable node placement remain. Names
  ellipsize by rendered width, avoid other labels, and remain available through
  hover/keyboard tooltips and accessibility descriptions. Singular/plural counts
  no longer use `(s)` placeholders. Empty maps explain how to populate them.
- Task Manager and map plots share opaque semantic colors. Text/data contrast
  checked without GTK, and real candidate chart pixels confirm theme background.
- Existing native source regressions pass; new tests are available through
  `OOONANA_GUI_ONLY=ui-details-runtime`. `OOONANA_GUI_THEME=light` now explicitly
  selects candidate appearance rather than silently testing dark only.
- Confirmation artifacts: `repair-dark-small`, `repair-light-small`,
  `repair-dark-desktop`, `repair-light-scaled`, `candidate-details`,
  `candidate-details-light`, and `candidate-keyboard-focused` under the QA root.
  Candidate image-loader sandbox warnings were retained; no browser sandbox or
  host security setting was disabled.

![Compact Packages failure state, native candidate GTK](assets/ooonana-packages-compact-20261015.png)

![Readable light signal map with crowded multilingual sample names](assets/ooonana-signal-map-paper-20261015.png)

Both captures use mocked data. This batch is source work pending runtime-package
publication; do not rebuild an ISO yet merely to pick up half-finished whole-OS
review work. Goal continues with the remaining ledger rows.
