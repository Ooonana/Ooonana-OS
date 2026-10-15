# Whole-OS UI review

Goal: inspect and improve the whole Ooonana OS UI, especially small details.
This goal remains **active**. A passing catalog is not whole-OS completion.
Preserve opaque graphite/amber, paper light mode, rounded controls and current
mascot/cursor identity. Do not build an ISO or play sound during review.

## Coverage ledger

| Surface / paths | Current evidence | Work still required |
| --- | --- | --- |
| Desktop wallpaper, cursor, native icons, theme | Earlier committed captures; current source inventory | Fresh composited desktop, cursor hotspot/scale, icon consistency and selection states |
| Panel / music / AI / notifications / tray | Source Polybar/wallpaper/dock at 640×600 and 1280×800; long Wi-Fi/media sample, no overlap/missing glyphs | Real empty/playing/paused media transitions, expanded notification integration and middle widths |
| Dock | Native owned-window fixture passes centered icons, previews, long/minimized multi-session tooltips, compact/other slot, 44px targets and unchanged hover focus | Multi-window context-menu actions, edge placement and complete keyboard path |
| Native Launcher | Long names bounded with full tooltips; visible no-match/empty recovery, launch rejection, arrows, Unicode Backspace/clipboard pass | Real application launch and installed keyboard/IME integration |
| Wi-Fi / Bluetooth | Fresh initial-state windows, enterprise credentials and pairing dialog | Populated lists, hidden-network form, permission/service failure, long device names, focus/keyboard |
| Settings: all six pages | Fresh initial-state captures, 640×600 dark/light and 1024×768 dark | Scaled text, completion/error/rollback, file chooser, long system values, keyboard navigation |
| Setup | Native compact overflow fixed; static fields labelled; validation, default-Back review, mocked pending/failure/late completion tested | Complete real setup/persistence and scaled-text interaction path |
| Sound / brightness / music | Long selected device/track names bounded; full-name tooltips, music error/retry/closed-callback behavior; no audio playback | Empty device lists, permission errors, actual route/mute/volume semantics and keyboard |
| Power | Native default-Cancel, duplicate refusal, error/retry, failed lock refusal pass with mocked commands | Actual isolated lock/logout/suspend and unavailable capabilities |
| Notifications | Private real Dunst history, DND, remove/clear pass | Long/multiline messages, grouping, unavailable service, privacy toggle and keyboard |
| Packages | 771px overflow fixed; compact captures and native candidate busy/error/retry/reduced-motion/lifecycle tests pass | Install/remove/upgrade dialogs and close-in-flight UX |
| Health / Updates | 735px overflow fixed; compact/native candidate pending/error/retry and default-Cancel tests pass | Readable real health results, full metadata confirmation interaction |
| Wi-Fi / Bluetooth signal maps | 658×750 overflow fixed; populated/empty/light/dark native candidate render, bounded labels, full-name tooltips and accessibility checks pass | Real data refresh/focus integration and physical radio/session behavior |
| Task Manager | Real owned process filter/sort/sample/cancel/SIGTERM/removal pass; both tabs fit; plots follow theme | Crowded values, selection races and actual hardware/GPU graphs |
| AI / offline setup / model UI | Native fixture chat streaming, composer, search/code copy/cancel and status indicators pass | Real engine transcript/long titles, loading/low RAM/restart/offline dialogs; bundled OpenVINO Qt UI |
| Installer GUI / text wizard | 720×724 form overflow fixed; real themed YAD form fits 640×600 and 1280×800, scrollable fields/visible Cancel + Review; no install executed | Keyboard through all fields, preview/log/blocked UI, text wizard and actual storage summary; no physical install |
| Shared dialogs / menus / tooltips | Short/unbroken and long diagnostic text fit; secret input labelled/focused, password spaces retained, Cancel verified | Remaining file pickers, menus, escape/return and scaled text |
| Third-party apps | Real Geany dark/light source profile + file picker and controls pass; Chromium sandbox/frame/actions pass. Nemo requires WSL/Xvfb full-redraw/redirection adaptation | Qt/Firefox current-source integrated rerun, menu/dialog variants, actual physical compositor and live WSLg |
| Window manager | Native minimize/fullscreen/close and native/third-party transient decoration checks pass | Drag/resize, tiling/tabs, workspaces, focus/session/display transitions |
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

## Batch 2: long content and incomplete task states

- Real candidate baseline exposed Sound at **2132px wide** from long device
  names and Music at **777px high** from repeated track metadata. Labels now
  ellipsize without discarding full tooltip/accessibility text. Music actions
  wrap, Play/Pause icons agree with state, MPD failures remain failures rather
  than empty-library success, retry restores controls and closed callbacks stop.
- Spotlight now distinguishes an empty catalog from no search matches and
  gives recovery guidance. Names/descriptions stay bounded, visible result
  rows remain mapped after clearing search, and launch errors retain retry.
- Secret prompts have explicit accessible names, input focus and password
  input purpose. Leading/trailing password spaces are no longer stripped.
  Short/unbroken and long diagnostic-dialog captures fit the compact display.
- Installer's real initial YAD form was **720×724** on 640×600: lower fields
  and buttons were off-screen. The form now scrolls inside monitor-bounded
  dimensions; Mode stays initially visible and Cancel/Review remain reachable.
  Preview/log windows also use bounded dimensions. Fields, parsing and storage
  safety checks are unchanged. This fixture executes only the form, not the
  installer, a storage probe or an install command.
- Candidate Setup's **676px** footer overflow was missed by the Ubuntu-host
  baseline. Footer now bounds its hint. Static-network labels, default-Back
  review, duplicate refusal, disabled pending fields, Reduce Motion, failure
  retry and ignored late completion have native GTK tests with deferred workers.
- Source-generated theme/editor wrappers now run in the third-party fixtures.
  Bare-profile Geany captures were not evidence of the Ooonana editor palette.
  Real Geany source profiles and actual cancel/open file pickers pass in both
  appearances. User editor profiles are never overwritten by this fixture.
- Themed Nemo exposed a nested Xrender paint issue: IPC/actions and colored
  titlebar controls could pass while client areas stayed blank. The probe now
  requires painted blue folders from its owned Adwaita fixture. No-compositor
  and full-redraw **with redirection retained** variants paint correctly.
  A CLI-only flag was insufficient in this fixture. WSL adapter derives a
  separate config with both optimizations off, only for the known packaged
  desktop invocation. Physical defaults, packaged config, custom wrappers and
  custom local configs remain untouched. Actual physical GPU/session QA remains.
- Candidate image-loader sandbox warnings and optional Nemo thumbnailer/action
  warnings remain in logs. No browser sandbox was disabled, no sound played,
  no model downloaded and no disk formatted. This batch still awaits signed
  runtime publication after whole-OS source review.

![Bounded long music metadata, real candidate GTK with sample data](assets/ooonana-music-details-20261015.png)

![Scrollable installer form in real candidate YAD; fixture disks only](assets/ooonana-installer-compact-20261015.png)

Current private evidence lives under the same QA root: `batch2-before-*`,
`batch2-content-functional-*`, `batch2-integrated-*`, `batch2-setup-functional`,
`batch2-nemo-always-redirect` and `batch2-catalog-final-*`. Earlier failed and
superseded fixture captures remain as history, not current UI certification.

Final batch regression: all **25 pages pass on actual candidate GTK** at
640×600 in both appearances. Extended content/setup/prompt interaction checks,
native source tests, installer tests and WSL-adapter guard tests pass. Installed
Ooonana WSL received only the local compositor/launcher adaptation; existing
packaged compositor config hash stayed unchanged. This applies on the next GUI
launch; no running desktop or WSL instance was restarted. New application UI
source remains pending signed runtime-package publication.

Preceding batch source `57b2cde` passed
[GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38693731125)
and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2949578827).
That earlier CI success is not a claim about this batch's uncommitted source.
