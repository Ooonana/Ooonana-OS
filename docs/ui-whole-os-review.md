# Whole-OS UI review

Goal: inspect and improve the whole Ooonana OS UI, especially small details.
This goal remains **active**. A passing catalog is not whole-OS completion.
Preserve opaque graphite/amber, paper light mode, rounded controls and current
mascot/cursor identity. Do not build an ISO or play sound during review.

October 16 scope update: user deferred OpenVINO until its major upstream update
is finished. Do not change/setup/test that integration or download models.
Generic native Ooonana AI, cloud-provider UI fixtures and other Qt apps remain
in scope. Earlier OpenVINO evidence below is historical, not a fresh validation.

## Coverage ledger

| Surface / paths | Current evidence | Work still required |
| --- | --- | --- |
| Control proportions | Shared/native GTK 10pt typography and chat actions measured; targeted 100/125/200% scaling; Task Manager headers/values follow text metrics | Other app-specific Qt controls, panel/card/dock content proportions; no blind blanket shrink |
| Desktop wallpaper, cursor, native icons, theme | Earlier committed captures; current source inventory | Fresh composited desktop, cursor hotspot/scale, icon consistency and selection states |
| Panel / music / AI / notifications / tray | Actual source Polybar/wallpaper/dock; wide CJK labels and full counters at 640/760/900/1000/1024/1100/1280px; missing-glyph and actual AI-centering checks, bounded Wi-Fi labels and compact right controls | Real empty/playing/paused media transitions, expanded notification/service integration and physical/live-session states |
| Dock | Centered icons, bounded previews/tooltips, compact grouping, 44px targets and unchanged hover focus; follow-up action/keyboard checks below | Edge placement and actual session/display integration |
| Native Launcher | Long names bounded with full tooltips; visible no-match/empty recovery, launch rejection, arrows, Unicode Backspace/clipboard pass | Real application launch and installed keyboard/IME integration |
| Wi-Fi / Bluetooth | Managed lists/hidden/personal/TLS/PIN forms; advanced fields, bounded certificate pickers, inline validation, progress/reduced motion, service gating, duplicate/closed refusal and safe Reset/Remove pass both themes through 200% text | Actual installed authentication, advanced network activation, physical reconnect/pairing and changed-adapter integration |
| Settings: all six pages | Compact page picker, bounded/selectable source values, visible keyboard focus, managed wallpaper/log dialogs, repair/update retry and motion rollback; 100/125/200% text checks below | Real installed-session preference/authentication paths and external file/device failures |
| Setup | Compact/200% scrolling and stacked labels; focused inline validation, secret-preserving drafts, full source/routing review, default Back, reduced motion, pending/reentrant and closed-parent refusal checked both themes | Complete installed privileged setup/persistence and actual authentication/network failures; CLI backend preflight is not certified by UI validation |
| Sound / brightness / music | Verified readiness, selected-identity audio/backlight commands, unknown/empty/permission states, persistent inline retry, serialized actions, preserved drafts, stale-poll/closed refusal; keyboard and both themes through 200% text pass silent fixtures | Actual installed route/mute/volume and playback semantics, changed-device integration and real hardware; no sound playback |
| Power | Native default-Cancel, duplicate refusal, error/retry, failed lock refusal pass with mocked commands | Actual isolated lock/logout/suspend and unavailable capabilities |
| Notifications | Private real Dunst history/DND/remove/clear; long grouped messages/full expansion, unchanged refresh focus, failure persistence, unavailable/unknown DND and privacy UI checks | Archived/live mixtures under service restarts, changed-record keyboard/scroll integration, actual session notifications |
| Packages | Default-Cancel install/remove/upgrade preview; failed/empty plans cannot apply; mutating close guard and parent-dialog lifecycle pass | Actual privileged transaction/authentication UX on disposable installation |
| Health / Updates | Readable snapshot, exact raw/copy, honest attention/malformed states; metadata Cancel/approved admin dispatch pass | Actual installed-session service/repository failures and authentication UX |
| Wi-Fi / Bluetooth signal maps | 658×750 overflow fixed; populated/empty/light/dark native candidate render, bounded labels, full-name tooltips and accessibility checks pass | Real data refresh/focus integration and physical radio/session behavior |
| Task Manager | Real owned process termination regression; crowded metrics, compact navigation, keyboard/copy, filter counts, stable refresh/selection, PID reuse and parent-close confirmation checked; unavailable counters never show stale graphs | Actual hardware/GPU readings, large real /proc sampling latency and installed-session shortcut launch |
| Native AI / model UI | Generic native chat compact layout, bounded headings, no-match search, draft attachment, safe Delete, status failure/stale/closed callbacks and streaming/copy/cancel fixtures pass | Real cloud-provider session, long-running transcript navigation; OpenVINO GUI/runtime/offline checks deferred by user October 16 |
| Installer GUI / text wizard | Real font-metric 100/200% form/review/blocked fit 640×600 both themes; all 16 fields keyboard-walked, exact disk/password mapping and safe Cancel checked; disk details scroll inside form | Actual privileged preview/log lifecycle, text wizard and physical storage summary/install; bare UI fixtures never install |
| Shared dialogs / menus / tooltips | Short/unbroken and long diagnostic text fit; secret input labelled/focused, password spaces retained, Cancel verified | Remaining file pickers, menus, escape/return and scaled text |
| Third-party apps | Real Geany dark/light source profile + file picker and controls pass; Chromium sandbox/frame/actions pass. Qt6/QTerminal dark/light, density, six Preferences pages, initial small-screen placement, nested font/portal image picker cancel/select and exit actions pass. Firefox dark QA scoped onboarding, portal open/cancel, exact URL/rendered-content read and window actions pass. Local WSL canonical runtime installed; guard/selection regressions pass | Other Qt apps and scaled picker variants; Firefox light/scaling/installed-session integration, actual physical compositor and live WSLg |
| Window manager | Native/XTerm modifier drag/resize, all number/move workspace keys, cycling, click focus, tile/tab/stack, resize mode, fullscreen, exact-session restore and unfocused close pass in private compositor | Real WSLg/physical compositor, multi-display and complete session lifecycle transitions |
| GRUB: live / audio submenu | Shared live/installed branding, compact audio labels; actual EFI 640×480/1280×800, missing-font/mark fallback and unchanged kernel arguments checked. Minimal contrast repaired | Physical BIOS/UEFI, corrupted-media/runtime graphics failure and actual installed boot |
| Boot / shutdown / reboot / persistent setup | Private PTY boot/save/setup; consecutive warning retention, normal console ordering, serial/ambiguous/motion-off/small-console and exact existing waits pass | Real framebuffer/kernel-message handoff, physical shutdown/recovery and complete persistent-setup interaction |
| Bootable PDF UI | Previous source/VM fixtures; browser viewer requires manual check | Viewer rendering, keyboard/Backspace, focus, responsive controls and perceived command delay |
| Accessibility / input / displays / session | Initial accessible controls and theme captures only | Text scale, keyboard/focus, clipboard, Korean composition, WSLg input, multi-monitor/DPI/hotplug, login/lock/logout/suspend/resume |

Windows Computer Use failed during initialization with “failed to write kernel
assets … path specified (os error 3)”. No fallback Windows automation used.
Linux Xvfb fixtures remain available; live WSLg behavior is not certified.
Previously denied local-PDF browser navigation is not retried or bypassed.
October 17 updated Computer Use runtime was retried through its documented
`@oai/sky` initialization; the same kernel-assets error 3 occurred before any
app input. No Windows automation workaround or security setting change used.

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
That earlier CI success covers Batch 1 only. Batch 2 plus its updated setup
ordering fixture (`c2d42a7`) subsequently passed
[GitHub](https://github.com/Ooonana/Ooonana-OS/actions/runs/38697082040) and
[GitLab](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2949670485).

## Batch 3: usable wireless lists and stable notifications

- Tested real Ooonana candidate GTK **with owned i3**, not only WM-free page
  captures. Baseline Wi-Fi had room for one row and credentials requested a
  623px frame on a 600px display. Lower dialog buttons were clipped. Shared
  dialog sizing now reserves WM space; personal, hidden-network, enterprise TLS
  and Bluetooth PIN fixtures fit the managed small display.
- Secondary tools moved under native **More** popovers; no actions removed.
  Keyboard Space opens them, Escape closes after the native transition, and
  focus returns to More. Network/device lists retain at least three-row space.
  Compact layouts prioritize names; adapter/AP counts and Bluetooth address
  columns return at wider sizes and remain in selected details/tooltips.
- Password/PIN fields have secret input purpose and accessible names. Hidden
  network input receives focus. Busy Wi-Fi disables overlapping UI actions.
  Physical connection, pairing and firmware operations were never invoked.
- Notification center removes duplicate heading chrome. Long subjects are
  bounded, and long/multiline bodies have short previews with **Show full
  message** retaining the parser's existing full 4096-character message limit.
  Remove stays near the subject rather than below an arbitrarily tall body.
- Unchanged refreshes no longer rebuild every message or discard keyboard
  focus. A read completing after the user moves focus does not steal it back.
  Duplicate actions are refused; action errors survive the follow-up refresh.
  Unknown DND status is disabled rather than presented as false. Service failure
  has its own recovery state instead of falsely claiming normal empty history.
- Privacy toggle reflects stored state when saving fails; preference failure
  remains visible. Opt-out's request to clear saved history was checked through
  a fake state object. No user history was deleted by these fixtures. Refresh
  timer is removed when the center closes.
- Focus fixture first settles focus-in reads before trying to focus Remove;
  a disabled control is not keyboard evidence. Popover dismissal waits for its
  native transition rather than treating an intermediate visible frame as a bug.
- New `wireless-notification-ui` gate passes at 640×600 in both appearances and
  1280×800 dark. Separate private **real Dunst** action regression passes too.
  Native catalog/regression results and package publication are recorded below
  when complete, not inferred from these narrower interactions.
- Final native catalog passes all 25 pages at 640×600 in dark/light, and source
  native/backend regressions pass. Separate 1024×768 fixture verifies unknown
  DND retains its last value while disabled, with a recovery explanation.

![Wireless list with compact name priority, native candidate/i3 fixture](assets/ooonana-wireless-compact-20261015.png)

![Long grouped message with visible Remove and full-message disclosure](assets/ooonana-notifications-detail-20261015.png)

Evidence: `batch3-wireless-notification-before`, `batch3-gate-*` and
`batch3-catalog-light-resumed` under the existing private QA root. Earlier
confirmation/focus fixtures remain diagnostic history. Image-loader sandbox
warnings remain logged; no browser sandbox or host security setting changed.

## Published checkpoint after Batch 3

This supersedes earlier “source pending publication” notes, not the coverage
ledger's remaining work. Whole-OS review stays active.

- Source `265eb57c226113e9a8653108f33b61dae72a07d6` pushed to both branches.
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38727193585)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2950609245)
  passed.
- Clean source-only manifest, no bundled models, coherent Alpine v3.24 inputs;
  signed **654 packages / 612 dependency nodes** validated and atomically
  published to the local candidate repository. Generation:
  `9d355bc29e79694f5d36d989856bd543fbaeac8825022a6414a1d5fb1540a312`.
  Prior generation/checksum manifest unchanged. Private signing key stays local;
  wider client enrollment and stable promotion remain deferred.
- Ooonana WSL native signed snapshot:
  `/var/lib/ooonana/candidate-ui-whole-20261015.46QKweEA`.
  Existing trusted public-key digest matched; detached signature and every
  manifest checksum passed before installation. Core/runtime were reinstalled
  separately through native CLI transactions, with all update checkpoints kept;
  both package verification and both health hooks passed.
- Installed common, Wi-Fi, Bluetooth, Notifications, Setup and controls source
  hashes match current repository files. Actual installed GTK modules import.
  Cloud source now points at the verified native snapshot and existing trusted
  key. Local WSL compositor/launcher adaptation refreshed after the transaction.
  Previous native snapshot unchanged; previous source config retained in logs.
- Logs: `/var/tmp/ooonana-ui-sync-20261015.WL1JZjn4` inside Ooonana WSL. First
  preflight stopped because minimal userland lacks `cmp`; no transaction had
  started. Resumed trust comparison used pinned public-key SHA256, followed by
  the same detached signature/full checksum validation. No checks bypassed.
- Ubuntu/Ooonana disk locations unchanged. No models downloaded, audio played,
  running GUI/WSL forcibly restarted, physical storage modified or ISO built.
  Existing ISO does not acquire these changes through resume. Fresh manual ISO
  build belongs after the remaining source/UI work, not this partial checkpoint.

GUI launch after closing the older nested desktop:

```powershell
wsl -d Ooonana --exec /usr/local/bin/start-ooonana-i3 --nested
```

This is a launch command, not proof of WSLg mouse, keyboard, IME or clipboard.
Current source application improvements are installed; live-input/physical
gates still need their own evidence.

## Batch 4: package change review and readable Health

- Install, Remove and Upgrade first request a dry-run plan. Native review keeps
  the full plan scrollable, defaults to Cancel, and names the explicit action.
  Failed/empty previews never apply; no-upgrades avoids an unnecessary approval.
  Final transaction still rechecks dependencies and major-upgrade policy.
- Package IDs reject option-like/multiple/overlong input. Duplicate requests are
  refused. Normal close waits during a mutation, but read-only previews can
  close. Destroying the parent also destroys its review without submitting work.
- Health defaults to a structured report with section hierarchy, binary memory
  units and explicit physical zram consumption versus logical capacity. Raw
  output and Copy retain the exact diagnostic payload, including unknown fields.
  A successful probe is not a declaration that physical hardware works.
- Unready services, incomplete memory and restart requirements produce attention
  states. Unrecognized successful output stays a warning/raw report, not green
  success. Secondary tools and policy disclosure leave useful report space on
  640×600. Metadata confirmation defaults to Cancel; approval uses admin helper.
- Private native GTK/i3 checks pass compact dark/light and desktop light, including
  real isolated read-only backend schema, copy fidelity, reduced motion, rejected
  previews, approval/cancel, lifecycle and error recovery. Source native tests
  and pure malformed/extreme-value report tests pass. No real package mutation,
  radio operation or sound playback was performed by these interaction fixtures.

![Readable Health snapshot with sample values and honest attention state](assets/ooonana-health-summary-20261015.png)

![Native package removal review; sample plan only](assets/ooonana-package-review-20261015.png)

Evidence: `batch4-close-parent`, `batch4-gate-*` and
`batch4-layout-functional-*` under the existing QA root. This batch is source
work pending the next signed runtime publication; Batch 3 remains the installed
checkpoint until that publication is recorded.

## Batch 5: compact dock groups and keyboard actions

- Compact dock hides selected pins to preserve 44px targets. Its Other button
  previously displayed those sessions but the command helper excluded every
  pinned app. Both open and right-click now pass the actually visible pin set;
  hidden-pin sessions remain restorable and actionable.
- `Super+Ctrl+D` opens a themed keyboard dock picker with app names, running
  counts and minimized counts. Selection reaches the same session/window actions
  as right-click. Keyboard popups identify their input source and select the
  first enabled item; pointer dock still never accepts or steals focus.
- Cancelled/failed rofi output cannot select a window from stale stdout. Invalid
  visible-pin arguments are rejected. Unit fixtures cover both command dispatch
  and minimized compact overflow, with no real user windows touched.
- Real owned i3 windows pass selection among two terminal sessions, minimize,
  restore, fullscreen/restore and target-only close. Real rofi-to-GTK keyboard
  path reaches Close; Escape cancels both stages without closing any app.
  Compact dark 640×600 and light 1024×768 confirmations pass.
- Old preserved QA root had common rofi data but lacked `rofi-x11-wayland`.
  Current signed repository and full-desktop profile already contain both; no
  release-package regression inferred. Runner installs the X11 payload only in
  a disposable overlay. Native popup tests wait for mapping rather than assuming
  that a CLI exit means the GTK child has finished starting.

Evidence: `batch5-dock-keyboard-mapped`, `batch5-dock-confirm-*`. Real-session
display hotplug/WSLg input still needs separate evidence. Batch 4/5 source edits
remain pending the next signed runtime refresh; no ISO built.

![Keyboard window actions on owned Music fixture, opaque dark appearance](assets/ooonana-dock-keyboard-20261015.png)

## Published checkpoint after Batch 5

Supersedes the preceding Batch 4/5 source-pending notes. Whole-OS review remains
active; software coverage is not physical/session certification.

- Source `49748aa8a04d80ac78b2c4de73e48d03e6f4393a` pushed to both branches.
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38732716980)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2950779363)
  passed. Native package/health, content/detail and source regressions also pass.
- Clean source-only manifest, no bundled weights, coherent Alpine v3.24 inputs;
  signed local repository validates **654 packages / 612 dependency nodes**.
  New generation:
  `3bbaadda499b28f7f8e885fed33690f1b446a7832bc722dacd1b781eb69fb782`.
  Prior generation checksum manifest unchanged; no stable promotion/enrollment.
- Native WSL snapshot:
  `/var/lib/ooonana/candidate-package-dock-20261015.xr0wY3b1`.
  Pinned public-key hash, detached signature, all 1302 checksums and clean
  source revision passed before native CLI transactions. Both core/runtime
  reinstall, verification and explicit health hooks pass. All rollback
  checkpoints and the prior source config remain.
- Installed Packages, Health/summary, dock, action popup, window helper and i3
  config hashes match source. Actual installed GTK imports pass unprivileged.
  Existing trusted cloud source points at the new native snapshot. WSL-local
  launcher/compositor adaptation refreshed; no forced desktop/WSL restart.
- Logs: `/var/tmp/ooonana-package-dock-sync-20261015.3Kj6Vc2S` in Ooonana.
  First transfer preflight found the optional F: mount absent, before transfer
  or installation. Mount existence is now checked in that transfer step.
  Ubuntu/Ooonana disks stay put. No model download, sound, physical disk change
  or ISO construction. Fresh ISO remains user's later step after UI review.

## Batch 6: proportional controls and Settings details (October 16)

User requested less oversized objects relative to text and asked to try UI/UX
Pro Max alongside Impeccable. Existing opaque Graphite/Paper identity stays.
Impeccable guided bounded refinement; UI/UX Pro Max's focus/semantic guidance
informed interaction checks. Its desktop-size search had no verified GTK match;
off-topic mobile guidance was rejected, not treated as a desktop size standard.

Actual candidate GTK measurements at normal text scale:

| Control | Native before → after | Generated GTK theme before → after |
| --- | --- | --- |
| Button | 42 → 32 px | 42 → 32 px |
| Entry | 52 → 32 px | 50 → 32 px |
| Dropdown | 46 → 33 px | 42 → 33 px |

Text line remains 17px. Font declarations remain Sans 10.5 for native apps and
Sans 10 for the generated user profile. Removed excess padding/inherited
minimum height, not text size. Native helper actions now fit their labels
(sample Apply: 86px wide including icon), while editable fields can still expand.
Font scaling grows the controls naturally: 200% native text line 33px gives
45px buttons/entries and a 49px dropdown. Existing window-control sizes, dock
targets, toolbar-specific styling and contrast roles remain unchanged.

Settings baseline exposed clipped managed picker/log windows, extremely tall
source values, misleading BlueZ-running output after a failed query, duplicate
service repairs/metadata requests, a failed motion preference staying selected,
and a delayed package dialog after Settings closed. Repairs:

- Narrow windows use an accessible native page picker; larger windows retain
  sidebar navigation. Returning to wide layout shows every row. Settings actions
  wrap without forcing three columns. Theme/layout fields have accessible names
  and cannot change while an appearance operation is pending.
- Source/status values have bounded lines, full selectable text, tooltips and
  accessible descriptions. Repository configuration is neutral, not proof of
  repository health. Native focus adjustments scroll the focused value into view.
- Wallpaper uses native GtkFileChooserWidget inside a monitor-bounded modal
  shell: fixed reachable Cancel/Apply, explicit scrollbars, default Cancel,
  proper image filtering/selection and parent-close cleanup. No custom filesystem
  browser or disk installer was introduced.
- Service log wraps inside bounded native dialog, has Copy log and closes with
  its parent. Repair/Reprobe buttons share a pending guard and retry feedback.
  Bluetooth query failure no longer claims BlueZ is running.
- Failed motion saving restores its checkbox; failed theme/wallpaper operations
  preserve saved state. Metadata action explicitly says Refresh metadata; success
  says no packages installed, failures retain retry, late callbacks stay silent.

Native private i3/GTK evidence: `batch6-settings-before`, `batch6-density-before`,
`batch6-focus-width-*`, `batch6-final-*` under the existing QA root. Proportion
checks cover native/generated themes and 100/125/200% text; Settings checks cover
real keyboard page navigation, full focused-value visibility, Cancel/selection,
copy, duplicate refusal, failures/retry and parent destruction. Actual Geany
picker/window controls also pass with the new generated theme. All commands
that would change packages/services/wallpaper in these interaction fixtures are
mocked; no sound, model download, physical disk writes or ISO build.

Final shared-style regression: all **25 native pages** pass at 640×600 in both
appearances after content-fit actions. Package/Health, shared detail, native
window controls, editor/profile and installer source regressions pass. Those
catalog captures are normal-text initial states; 200% interaction evidence is
the targeted Settings/proportion fixture, not a claim about every app at 200%.

![Compact Settings with proportional action controls, native candidate](assets/ooonana-settings-proportions-20261016.png)

![Reachable wallpaper picker actions and explicit scrolling at 125% text](assets/ooonana-settings-picker-20261016.png)

This batch is source work pending the next signed runtime refresh. Batch 5
remains the installed checkpoint until a later publication record supersedes it.

## Published checkpoint after Batch 6

Supersedes the preceding source-pending note, not the remaining whole-OS work.

- Source `8cc3b177e8ceba40f47c7215df0b074991ad975a` pushed to both branches;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38824635241)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2953124816)
  passed.
- Clean source-only manifest, no bundled models, coherent Alpine v3.24 inputs;
  signed **654-package / 612-dependency-node** generation validated/published:
  `c518fe57962e40589f80a2c53c4f158fcdca4cc3568c5b913c0059fbe3600733`.
  Prior generation checksum manifest unchanged. Signing key remains local;
  stable promotion and broader enrollment remain deferred.
- Ooonana WSL snapshot:
  `/var/lib/ooonana/candidate-proportions-20261016.5Udsm91e`.
  Pinned key hashes, detached signature, all 1302 checksums and source manifest
  verified before native CLI dry-runs/reinstalls. Both core/runtime verification
  and explicit health hooks pass; all rollback checkpoints remain.
- Installed common, Settings, Packages and i3 config hashes match source. Actual
  dark/light CSS parsing and GTK imports pass as UID1000; ordinary unprivileged
  package search returns installed Geany. Cloud source points at the new signed
  native snapshot. WSL-local compositor/launcher adaptation refreshed without
  restarting a running desktop, WSL or Windows.
- Logs: `/var/tmp/ooonana-proportions-sync-20261016.BOFyrrjd` inside Ooonana.
  Ubuntu stays on C:, Ooonana stays at its existing F: location. No sound,
  model download, physical media modification or ISO construction. Relaunch old
  desktop/apps for current code/generated theme; existing ISO remains unchanged.

## Batch 7: generic native chat details; OpenVINO deferred

- Impeccable refinement preserves fonts, opaque Graphite/Paper and amber. UI/UX
  Pro Max's verified cross-platform Empty States result informs search recovery;
  GTK has no supported stack result, so actual desktop geometry supplies sizing.
- Native chat sidebar/composer actions now follow shared control density rather
  than oversized per-app padding. Compact navigation shows chats/tools separately
  from the conversation instead of pushing both beyond the screen. Empty-chat
  spacing/composer height leave useful conversation room.
- Long speaker/code-language captions ellipsize with full tooltip/accessibility
  descriptions. Message/code contents stay selectable/copyable and unchanged.
- Search explains no matches and clearing restores saved chats. Delete defaults
  to Cancel. Attachment uses bounded native chooser with fixed actions, default
  Cancel, managed parent lifecycle and UTF-8 text inserted into editable draft;
  no automatic request submission.
- Provider/model query failures remain unavailable rather than inventing a
  successful selection; retry recovers, stale responses cannot overwrite newer
  status and callbacks ignore closed windows. Offline-specific methods unchanged.
- Private UID1000 real GTK/i3 fixture passes dark/light at 640×600 and 1280×800;
  targeted 1024×768 checks pass 125% light and 200% dark. Existing native chat
  streaming, Enter/Shift+Enter, full code copy, owned-child cancellation and UTF-8
  split-stream regression passes. All providers/status actions mocked; no engine
  setup, OpenVINO tests, downloads, user history changes or audio.
- QA: `batch7-ai-baseline`, `batch7-ai-verified-*`, `batch7-ai-chat-regression`
  under the existing QA root. Initial fixture cleanup caused a GTK garbage-
  collection crash after checks; removing redundant toplevel destruction and
  draining queued GTK events made the process exit cleanly. Failed logs retained.

This source batch awaits signed runtime publication; Batch 6 remains installed
until a later checkpoint supersedes it. Whole-OS review remains active.

![Compact native chat search with explicit recovery](assets/ooonana-ai-search-20261016.png)

![Bounded native attachment picker, Paper appearance, mocked conversation](assets/ooonana-ai-attachment-20261016.png)

## Batch 8: smaller native type, no width-triggered AI zoom

User requests smaller text after Batch 7. Large 200% stress screenshots are not
default configuration. A separate actual wide-window baseline also confirms an
unwanted 14.5pt automatic AI enlargement; that rule is removed, not replaced
with forced DPI or disabled accessibility scaling.

- Native body 10.5→10pt, matching generated desktop GTK; page headings 19→16pt,
  card headings 12→11pt, hero 24→20pt, launcher search 16→14pt. Control targets,
  user text scaling, font family, palette and native roles stay intact.
- Impeccable preserves incumbent identity. UI/UX Pro Max's Typography / Font
  Size Scale result supports coherent hierarchy; its mobile 16px floor does not
  apply to native desktop. ui-styling contributes hierarchy/shared-token
  principles only: GTK is not shadcn/Tailwind, no web stack or dependency added.
- Generic catalog fixtures now select mocked NIM rather than OpenVINO. No
  offline integration/runtime/model tests resumed.

Confirmation passes all 25 native pages at 640×600 in both appearances, resolved
text/surface contrast in both, native/generated 10pt control proportions, wide
AI at 1600×900 and compact AI at 640×600. Targeted AI/control checks still pass
200% user text scale. QA directories `batch8-type-before-wide` and
`batch8-confirm-*` retain measurements, captures and logs. The baseline resize
needed fixture-only recentering; off-screen baseline geometry is not a claimed
product bug. Earlier screenshots/unchanged-type statements are historical to
their named batch. Signed runtime refresh remains pending.

![Native chat at normal 100% text, smaller shared typography](assets/ooonana-native-typography-20261016.png)

## Published checkpoint after Batches 7 and 8

Supersedes preceding pending-publication notes, not remaining whole-OS work.

- Source `f39e99bc63ad6f7098ef9bc5ec53d1eea45144c1` pushed to GitHub/GitLab;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38827783754)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2953185769)
  passed. Clean source-only manifest; coherent v3.24 inputs, no models bundled.
- Signed 654-package/612-dependency-node generation:
  `a23b66494a11b1381da781f2a666712658b9b9c01efa210c2f3c4a475c570054`.
  Previous generation checksum manifest remains unchanged. Private key local;
  stable promotion and enrollment deferred.
- Ooonana WSL snapshot:
  `/var/lib/ooonana/candidate-native-chat-20261016.YCqjSPA4`.
  Pinned keys, signature, all 1302 checksums and exact clean-source revision
  verified before native core/runtime dry-runs, reinstalls, verification and
  health hooks. All checkpoints retained; configured file source updated.
- Installed common/chat/app/i3 hashes match source. Actual GTK imports and both
  CSS variants parse as UID1000, native typography is 10pt with no wide zoom;
  unprivileged package search succeeds. WSL-local adapter refreshed, not restarted.
- Logs: `/var/tmp/ooonana-native-chat-sync-20261016.vSKi62N9` in Ooonana.
  No OpenVINO integration changes, runtime/model downloads, sound playback,
  physical disk changes, WSL disk relocation or ISO build. Relaunch apps for
  updated code/text; broader UI and interactive-session ledger stays active.

## Batch 9: Task Manager detail and lifecycle checks

- Compact page picker replaces sidebar; keyboard Home/End tested. Performance
  changes to one column where needed. Sensor/status values stay within three
  lines, selectable with full tooltip/accessibility text. Native 10pt retained.
- Name/user/command columns ellipsize instead of swallowing numeric columns;
  default widths use actual text metrics so 200% headers/PIDs/RAM stay readable.
  Compact row tooltips summarize identity; actual Ctrl+C provides full
  identity/command access without a screen-filling popup. Keyboard tooltips are
  display-bounded at normal/200% text, with full accessibility descriptions.
- Search states show matching/total counts and actionable no-match text. Row
  updates are incremental, preserving selected PID/start-time and scroll. Reused
  identities clear selection; owner changes recalculate permission feedback.
- End task defaults to Cancel, blocks duplicate/refresh re-enabling, retains the
  originally confirmed identity and closes with parent. Native process-control
  backend still revalidates identity; no broader termination authority added.
- Missing CPU/RAM/disk/storage counters have honest unavailable states. No valid
  disk device no longer reports measured zero. Missing samples clear old graphs
  and hide meaningless percentage bars; recovery begins fresh samples.
- Private GTK/i3 checks pass dark/light compact/desktop and targeted 200% text.
  Actual keyboard navigation/clipboard, cancel/reused identity/parent close,
  stable scroll, ownership-change refusal and measured numeric widths tested
  with mocked sensors/processes. Initial raw multiline tooltip overflow was
  caught by actual keyboard invocation, replaced with a compact summary and
  retested in `batch9-task-tooltip-final-*`.
  Existing owned-child SIGTERM/removal and shared chart regression pass; separate
  identity-bound process-control/IPC test passes. No real hardware stress.
- QA `batch9-task-before`, `batch9-task-confirm-*`, `batch9-task-keyboard-*` and
  `batch9-task-regression-*` under existing root. Baseline parent destruction
  stranded confirmation until timeout; later keyboard test needed its own window
  mapped before sending keys. Failed evidence retained, not counted as passes.

![Compact Task Manager with bounded sensor values, mocked data](assets/ooonana-task-compact-20261016.png)

![Compact task table with bounded names and numeric columns](assets/ooonana-task-details-20261016.png)

## Batch 10: real window interaction paths

- All 20 workspace select/move keys were absent. Source now provides Super+1…9/0
  and Super+Shift+1…9/0 (0 means workspace 10), plus Super+Ctrl+Left/Right cycling.
- Real pointer test found a separate production bug: bare `move` / `resize`
  mouse commands overrode native handling and raised i3 error bars. Removed
  invalid overrides; existing `floating_modifier $mod` supplies the intended
  [native drag/resize behavior](https://i3wm.org/docs/userguide.html#floating_modifier).
  Branding regression previously required the bad lines; now rejects them and
  checks all workspace bindings instead. Configuration parsing alone missed this.
- Private UID1000 i3/XRender checks pass both themes: every number/move key,
  cycling, actual native/XTerm modifier pointer drag/resize, hover without focus
  theft, tile/tab/stack and keyboard resize-mode exit, fullscreen/restore, hidden
  client fullscreen, exact original client restore with two minimized sessions,
  unfocused overlay close and Alt+F4. Overlay targets follow visible tabs,
  workspaces and final geometry; no detached fullscreen controls or i3 errors.
- Native window-controls regression also passes. Test-only XRender full-redraw
  policy handles WSL/Xvfb; not physical GPU/animation-performance certification.
  XTerms here are interaction fixtures, not evidence of application color/profile
  consistency. No real user session, disk, radio or audio action.
- QA `batch10-workspace-before`, `batch10-workspace-confirm-*`,
  `batch10-workspace-final-*`, `batch10-native-and-thirdparty-*` and
  `batch10-window-controls-regression`. Pointer fixture timing and nonexistent
  i3 `pid` field corrected before final confirmation. Baseline/red-bar evidence
  remains; successful runs reject i3 command-error messages explicitly.

![Owned native/XTerm drag-resize interaction fixture, no error bar](assets/ooonana-window-interactions-20261016.png)

These source batches await signed publication. Previous Batches 7/8 remain the
installed checkpoint until a publication record supersedes it. Broader review
stays active; physical/WSLg/displays/boot/PDF and other ledger gaps remain.

## Published checkpoint after Batches 9 and 10

Supersedes preceding pending-publication note; broader ledger remains active.

- Source `b6f186f872ac5f0ec864aae5a97e5ec6e1fecc67` on both remotes;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38853580245)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2953727515)
  passed. Clean source-only manifest, coherent v3.24 inputs, no bundled models.
- Signed 654-package/612-dependency-node generation:
  `cdfa85aabf54ab923f879028fb215481ca4e83e2da8c0aae147622c9fc3a54bd`.
  Prior generation checksum manifest remains unchanged. Keys stay local; stable
  promotion/enrollment deferred.
- Ooonana WSL native snapshot:
  `/var/lib/ooonana/candidate-tasks-workspaces-20261016.WBpyPnQO`.
  Pinned key hashes, detached signature, all 1302 checksums and exact clean
  source manifest verified before core/runtime dry-runs/reinstalls. Both package
  verifications and health hooks pass; rollback checkpoints retained.
- Installed Task Manager/i3 config hashes match source. Actual GTK imports and
  both CSS variants parse as UID1000; ordinary package search succeeds. Configured
  local repository source and WSL adapter refreshed without GUI/WSL restart.
- Logs: `/var/tmp/ooonana-tasks-workspaces-sync-20261016.CFPSdFRR` in Ooonana.
  Relaunch desktop/apps for code and bindings. No OpenVINO work/model download,
  sound playback, physical-media changes, disk relocation or ISO construction.
  C: approximately 1.1 GiB free during sync; further heavy QA/builds need space.

## Smaller-heading refinement

- User still finds text oversized. Shared page/hero/search roles now use
  14/18/12pt instead of 16/20/14pt. Body remains 10pt and card titles 11pt;
  user DPI, focus rings, control targets, fonts and color identity stay intact.
  Search padding changes 10×14px to 8×12px to retain proportions.
- Impeccable typography guidance, ui-styling shared-role consistency and
  ui-ux-pro-max's verified Typography / Font Size Scale guidance informed this
  bounded adjustment. No web stack or new font dependency added to GTK.
- Private `control-density-ui` passes both themes at 100% and 200%, resolving
  exact role sizes from actual GTK and checking unchanged DPI/control overhead.
  Actual compact Task Manager interaction regression passes both themes.
  Final type detector reports no findings. Representative normal/200% captures
  inspected; large stress text remains intentional accessibility scaling.
- QA: `/var/tmp/ooonana-typography-20261016.AUwWADL4` in Ubuntu.
  Existing wireless baseline work stays separate and unfinished. No physical
  radio action, OpenVINO/model work, sound, disk relocation or ISO construction.
- Source refinement not yet incorporated into signed candidate or installed
  Ooonana WSL. Earlier publication record describes the preceding checkpoint,
  not this patch. Broader coverage ledger remains active.

## Batch 11: wireless details and lifecycle

- Reproduced overlapping startup/refresh/action dispatch, controls re-enabled
  while pending, selection overwriting progress, stale callbacks reopening UI
  and a Bluetooth callback touching a destroyed tree. Shared lifecycle now guards
  these paths, removes progress timers on idle/close and honors reduced motion.
  Repair stays available when services fail; radio/device actions reflect actual
  controller/service state. List refresh retains selected SSID/device identity.
- Reset and Bluetooth Remove use bounded parent-owned confirmations with default
  Cancel and close refusal. Remove no longer silently forgets a saved pairing.
  Pair/manual/credentials dialogs are destroyed with their parent. Wi-Fi
  disconnect lookup moves off the GTK thread; existing backend authority,
  activation, retry and secret transport remain unchanged.
- All seven security selections/four enterprise EAP visibility combinations
  checked. IPv4 interface/gateway/DNS and required proxy input receive inline,
  secret-preserving errors with focused, fully visible fields. Custom CA/client
  certificate/private-key selection uses native local-only file chooser content
  in a bounded scrollable shell; Cancel preserves the prior file.
- Large-text form labels stack. Bluetooth secondary selected-device actions
  stay under Device actions rather than growing the window. Scrollable main
  content, titlebar-aware height reserve and one-time post-map placement clamp
  fix real 640×600 overflow/negative initial CSD position. Later manual movement
  is not continuously constrained.
- Private actual UID1000 GTK/i3 checks pass dark/light at normal and 200% text:
  advanced values/focus, picker/reset/remove Cancel, service failure/recovery,
  repeated actions, reduced motion, late completion and confirmation parent
  close. Existing wireless/notification menu-keyboard regression passes both
  themes. Shared busy/error/plot/dialog and scaled Settings regression pass both
  themes; complete native source/backend regression passes. Final detector empty.
- QA under `/var/tmp/ooonana-whole-ui-20261015.n7zRUus3`: initial failing
  `batch11-wireless-baseline`, subsequent confirmation evidence, final
  `batch11-wireless-placement-*`, `batch11-wireless-bounds-*` and
  `batch11-shared-placement-*`. Failed captures retained, not counted as passes.
  Existing wireless fixture was corrected to model native adapters explicitly;
  installed WSL host-radio protections were not disabled.
- Source batch awaits signed candidate/WSL publication. No live radio changes,
  sound playback, OpenVINO integration/model download, physical storage changes,
  WSL relocation or ISO build. Broad review and physical/session gates remain.

![Advanced Wi-Fi error with visible field at intentional 200% text](assets/ooonana-wireless-validation-200-20261017.png)

![Compact parent-owned Bluetooth removal confirmation](assets/ooonana-bluetooth-confirmation-20261017.png)

## Published checkpoint after Batch 11

Supersedes preceding pending-publication notes for smaller headings and Batch 11.
Broader UI coverage remains active, not certified complete.

- Source `617dabef8e9da3252111e38b76e6f4c2bf2608e5` is on both remotes;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38989705803)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2957559272)
  passed. Clean source-only manifest, coherent v3.24 base, no bundled models.
- Signed 654-package/612-dependency-node generation:
  `6bf47130fc3e1fa0d5ac5dc10445d1f11dfaf4fdb24735e3a9014320ecf2076a`.
  Previous `cdfa85a…` checksum manifest remains
  `acbe575cfa2a65d1b0fdf319f32a39c01ec4136c102fddfb039e6b18b37d11cb`.
  Private key local; stable promotion/signing enrollment still deferred.
- Native Ooonana WSL snapshot:
  `/var/lib/ooonana/candidate-wireless-ui-20261017.XIV7pHV5`.
  Pinned public-key hashes, detached signature, all 1302 checksums and exact
  clean source revision verified before separate core/runtime dry-runs,
  reinstalls, package verification and explicit health hooks. All checkpoints
  retained. First transfer attempt found absent Ubuntu F: mount and extracted
  nothing; explicit-mount retry passed complete signature/checksum validation.
- Installed common/Wi-Fi/Bluetooth/shared-wireless module hashes match source.
  Actual GTK imports and both style variants parse as UID1000; compact heading
  roles and shared lifecycle inheritance verified. Nonroot Geany search passes.
  Default package metadata cache refreshed and core runtime resolves to the new
  local cloud snapshot. WSL adapter refreshed without GUI/WSL restart.
- Logs: `/var/tmp/ooonana-wireless-ui-sync-20261017.Ox1fMm9X` in Ooonana.
  Build stage/transfer retained under F: `build/ui-wireless-stage-20261017.ayfWOZ4z`
  and `build/ui-wireless-transfer-20261017.SEp6Wai6.tar`. No model download,
  sound, live-radio/device change, physical-disk operation, WSL relocation or ISO
  construction. Relaunch desktop/apps; physical/session/display gates remain.

## Batch 12: Sound, Brightness and Music details

- Baseline silent fixtures reproduced enabled startup writes, overlapping
  actions, old-default volume shown for a newly selected output, mute targeting
  the moving default, absent-device brightness guesses, unlabeled sliders and
  music polls re-enabling pending playback/overwriting drafts. These were
  actual fixture failures, not physical hardware findings.
- Shared control lifecycle now gates startup/actions, keeps progress and inline
  errors persistent, respects reduced motion and ignores closed callbacks.
  Compact More menus fit content; Sound and Brightness secondary tools no
  longer force oversized rows. Native scrollable content keeps focused footer
  actions reachable at 200% text. Labels, selected names, errors and full-value
  tooltips remain accessible; text scale and opaque theme are unchanged.
- Sound captures selected output/input identities and does not use a changing
  default for mute. Selection-specific reads reject stale results; device-list
  permission failures remain errors instead of being called missing hardware.
  Unknown volume/mute never presents guessed state as verified. Partial route
  failures preserve input and tell users to Refresh/check routing or retry.
  Existing ALSA/Pulse readiness and explicit Repair behavior are retained.
- Brightness verifies the backlight class and exact device before enabling
  Apply. Keyboard LED results are rejected; zero current brightness is reported
  honestly with recovery through the existing 1–100% selectable range.
  No unavailable device receives a guessed 75% write.
- Music gates startup/actions, separates pending epochs from periodic reads,
  retains uncommitted volume and persistent errors, and offers Refresh library
  for service retry rather than promising automatic restart. Decorative art
  and action spacing are smaller without reducing body text or focus targets.
- Final private UID1000 GTK/i3 fixtures pass dark/light at 640×600, 100/200%
  text. They cover keyboard arrows/menu Space/Escape, selected-target binding,
  unknown/input-only/empty/permission states, draft retention, repeated actions,
  stale reads and late parent close. Commands are queued/mocked and unexpected
  actual command launches fail the fixture. No playback, actual route/mute or
  brightness write occurred. Installed brightnessctl help was read-only.
- Full native/backend source regression, shared content and wireless menu
  regressions pass. All 25 native catalog pages pass both appearances at
  640×600. The first final-copy rerun lacked its output directory and failed
  before GTK; creating that owned QA directory made the same probe pass.
- Evidence in Ubuntu: `ooonana-controls-baseline-20261017.mVNwBcdS` (expected
  failures), `ooonana-controls-release-20261017.f1uYMOYW` (four control variants
  and shared wireless regression), `ooonana-controls-catalog-20261017.zO4M8bZB`
  (25-page both-theme catalog), and `ooonana-controls-copy-20261017.AFeunWFQ`
  under `/var/tmp`. Earlier confirmation outputs remain diagnostic history.
- Source/signed-candidate/WSL publication pending. Cleanup inventory identifies
  duplicate agent staging/transfers and ignored bytecode only; no cleanup has
  yet occurred. Published generations, rollback checkpoints, ISO/resume media,
  models, signing keys and evidence/history are excluded. Broad review continues.

![Sound controls at normal text scale, silent private fixture](assets/ooonana-sound-details-20261017.png)

## Published checkpoint and cleanup after Batch 12

Supersedes Batch 12 pending-publication/cleanup notes above. Whole-OS UI review
remains active; signed candidate and installed Ooonana WSL now include this batch.

- Source `9d02988ed3f42e5bd7fe2166914ecd970621d0c8` pushed to both remotes;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38991693350)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2957617970)
  pass. Clean source-only manifest: v3.24, no bundled models.
- Signed local 654-package/612-dependency-node generation:
  `8cc58fc2caf8b8b7fd600bfe8925fa9fa4d5fadd2116bd315374953a9b61a2b3`.
  Publication validates hashes, index/closure and detached signature before
  promoting CURRENT. Previous `6bf47130…` SHA256SUMS remains
  `6f185bb9461443447bf7288cf75f84a34ac6e9c4d32bb15f5cec8ff2be3c4a97`.
  Signing key stays local; no enrollment or stable-channel promotion.
- First native Ooonana startup returned
  `Wsl/Service/CreateInstance/ERROR_TIMEOUT` before executing the preparation
  script. After filesystem operations settled, a read-only startup retry
  succeeded without forced GUI/WSL restart. Signed native snapshot:
  `/var/lib/ooonana/candidate-controls-ui-20261017.KPwtkH7z`.
  Pinned key, detached signature, all 1302 checksums and exact clean source
  manifest verified before separate core/runtime dry-runs, reinstalls,
  package verification and explicit health hooks; all checkpoints retained.
- Installed common/controls hashes match source. Actual GTK imports and both
  CSS variants parse as UID1000; nonroot Geany query and metadata-only update
  pass. Default cache contains 654 packages from two sources and core/runtime
  resolves to the new local cloud snapshot, not stale builtin metadata. WSL
  adapter refreshed after install, without launching/restarting GUI. Logs:
  `/var/tmp/ooonana-controls-ui-sync-20261017.xHtnm1XP` in Ooonana.
  These checks do not certify live WSLg pointer/IME/session behavior.
- Cleanup targets were agent-owned duplicates, with matching retained signed
  generations, exact validated absolute paths and no unknown/reparse children.
  Seven old `build/ui-*-stage-*` copies and six named transfer archives removed.
  Transfers total 4,321,280 bytes; five ignored project bytecode files total
  69,929 bytes. Final controls staging copy also removed after matching the
  verified new generation: eight stage copies removed in total. Logical
  sizes of hardlinked stages are not counted as physical space reclaimed.
  OneDrive cloud placeholders initially tripped an overstrict parent check;
  that attempt deleted nothing. Exact nonlinked bytecode files were subsequently
  removed without changing cloud directories or unrelated files.
- All signed generations, native rollback snapshots, Git/diagnostic/screenshot
  history, ISO/resume media, WSL disks, models and keys retained. OpenVINO subtree
  untouched. New stage/public metadata can be regenerated; no material user
  data was deleted. C: about 1.55 GiB, F: about 25.09 GiB free during publication;
  these concurrent-work snapshots are not a claimed net-reclaimed amount.
- Review resumed: actual private Polybar/dock/wallpaper at 1024×768 passes both
  appearances with long sample Wi-Fi/media. Scoped panel reload, sibling
  preservation, owned-child recovery and UTF-8 media truncation regressions pass.
  Evidence: `/var/tmp/ooonana-panel-resume-20261017.AspRnmNt` in Ubuntu. No
  real playback/radio action. Real empty/playing/paused service transitions,
  physical/WSLg/input/display gates and remaining coverage rows still open.

## Batch 13: Setup form and review

- Fresh baseline exposed whole-form/review overflow at 200%, validation that
  did not focus its field, an orphan review and a closed-parent approval that
  still queued administrative work. Tests queue workers and reject command
  execution; no account/network/password/disk changes were made.
- Welcome now scrolls with the form, leaving room for Account at normal small
  size. Wide labels stack by measured text, checkbox text wraps, fields follow
  focus adjustments and initial placement uses shared titlebar-aware bounds.
  Existing typography, themes, targets and mascot/cursor remain unchanged.
- Inline validation retains password spaces/drafts, identifies/focuses the
  offending field and checks IPv4/prefix/gateway/DNS plus repository input.
  This is UI feedback, not a claim of a new server-side/CLI security boundary.
  The authoritative setup CLI and password stdin transport are unchanged.
- Scrollable parent-owned review includes exact manual routing, source URI,
  theme, capped RAM policy and existing disk-swap choice. Password is reported
  only as supplied/not supplied. Back remains default; reentrant Apply and
  any approval after parent close cannot dispatch. Partial backend failure
  remains visible with drafts and retry, instead of implying rollback.
- Private actual UID1000 GTK/i3 passes dark/light at 640×600, 100/200% text:
  every field's visible focus, invalid entries, DNS normalization, secret
  retention, complete review, Back, pending/duplicate refusal, reduced motion,
  failure recovery and parent-close. Prior content/dialog regression passes
  both themes; full native source/backend suite passes. No physical/session
  or real privileged transaction is certified by these mocked results.
- Ubuntu evidence: `/var/tmp/ooonana-setup-baseline-20261017.CuR92Nvh`
  (expected failures) and `/var/tmp/ooonana-setup-confirm-20261017.Rc2GznpK`
  (confirmation and regressions). Candidate/WSL publication pending for this
  patch; Batch 12 publication above remains the previous runtime checkpoint.
- First GitHub run on `e58642b` failed because its AST-isolated backend test
  still mocked the old MessageDialog and omitted review state. Updated that
  fixture for the real Dialog/lifecycle instead of weakening production guards.
  Local backend regression passes, including setup completion only after
  successful password change and exact preservation of password spaces via
  stdin. No fixture dispatches a real privileged setup command.

![Setup at normal text scale, private GTK fixture](assets/ooonana-setup-details-20261017.png)

## Published checkpoint after Batch 13

Supersedes Batch 13 pending-publication notes. Whole-OS review remains active.

- Source `a57c0cb2f56fdb8cd00dbc800c7d77ba1cda9e1f` is on both remotes;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/39022235329)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2958238333)
  pass after repairing the stale backend test mock, without weakening guards.
- Clean source-only, v3.24, model-free 654-package/612-node generation:
  `6515c1e66d0770af57ddc3544ba2446d91a4492108cbb4d73d7fc4412fc4bf80`.
  Signature, archive/index checksums and closure pass before atomic promotion.
  Prior `8cc58fc2…` SHA256SUMS stays
  `035cbef3d30d3143c68c94f16367160ef9cfb240ed8bb8b56d844ef8b91cf51e`.
- Native snapshot `/var/lib/ooonana/candidate-setup-ui-20261017.YZrR8O7r`:
  pinned trust key/signature, all 1302 checksums and source manifest verified
  before core/runtime dry-runs, reinstalls, package checks and health hooks.
  Common/Setup/Controls hashes match source; actual UID1000 GTK imports/CSS,
  nonroot package search and default cloud metadata cache pass. Adapter updated
  without forced GUI/WSL restart; all rollback checkpoints retained. Logs:
  `/var/tmp/ooonana-setup-ui-sync-20261017.GjKQWl8X` in Ooonana.
- Slow agent-owned staging loop was identified by exact command and Codex parent,
  stopped with terminal confirmation, then its same scratch tree was completed
  using verified native hard links. No active repo or user process was stopped.
  Final staging copy and five-file temporary payload were removed only after
  verified publication; generation, source, evidence and native snapshots stay.
  No key upload/enrollment, stable promotion, model download, playback, physical
  disk operation or ISO build. Live Windows/WSLg/input/display gates remain.

## Batch 14: Installer fit and retained presentation preferences

- 200% means an isolated accessibility stress fixture, not a new shipped scale.
  Default body remains 10pt at 100%; no global font/control enlargement.
  Impeccable guided bounded layout/interaction repair; UI Styling and UI/UX Pro
  Max guided keyboard focus, proportional controls and reduced-motion handling,
  adapted to existing GTK/YAD rather than adding a web framework.
- Probe now checks effective rendered font pixels, not just a requested DPI.
  An earlier nominal 200% fixture was actually 96 DPI/17px. Corrected private
  GDK font override produces 192 DPI/32px and exposed real overflow. GTK/GDK
  versions are explicitly selected before measuring monitor workarea/glyphs.
- Installer wraps warning/review text by measured font, uses shorter meaningful
  labels and keeps all detected disk details in a selectable scrolling row.
  No automatic target is selected. Review buttons remain visible on small
  screens; Cancel is explicit default. Enter in read-only review does not
  approve installation, Escape cancels. Log copy now explains hiding does not
  cancel work; fallback shell defaults No. Log directories use private mktemp.
- Read-only row is deliberately excluded from semantic field numbering. A
  counted control separator replaces pipe splitting, preserving a password
  containing `|` plus leading/trailing spaces; malformed output is refused
  before backend dispatch. Long/punctuated disk labels remain literal display
  data, not YAD field/tooltips markup. No real device was enumerated in QA.
- Theme apply now merges its own presentation keys while retaining saved font,
  DPI, icon choice, unknown settings/comments/sections and file modes. GTK and
  XSettings get matching retained font/DPI. Invalid settings or linked targets
  are retained with a non-secret diagnostic. Both outputs are prepared/fsynced
  before individual replacement; this is not an atomic two-file transaction.
  Existing reduced-motion preference also reaches third-party GTK animation
  settings on theme apply. Existing 180ms color feedback stays; no entrance
  choreography, transparency or idle animation loop was introduced.
- Eight private-file regressions pass: defaults/idempotency, preference/mode
  preservation, XSettings defaults, duplicate keys, reduced motion, invalid
  settings, links and preparation failure with temp cleanup. Full native source,
  full-rootfs generation and backend service/setup regressions pass.
- Actual owned UID1000 GTK/YAD/i3 at 640×600 passes both appearances at 100/200%:
  form bounds, all 16 field values, password spaces/pipe, final review/blocked
  bounds and keyboard cancellation. No install/dry-run/admin/disk command is
  executed. Evidence in Ubuntu:
  `/var/tmp/ooonana-installer-confirmed-20261017.ufLf1fgk`.
  Source changes still await signed candidate publication and installed WSL
  refresh; Batch 13 remains last published checkpoint. Whole-OS review stays
  active; real installation, text wizard and live session gates remain open.

![Installer at normal 100% text on private 640×600 display](assets/ooonana-installer-details-20261017.png)

## Batch 15: Terminal installer input and completion

- Isolated baseline reproduced secret trimming plus an injected leading newline,
  forced reboot/poweroff on EOF or unknown input, and ignored reboot failure.
  Tests extract only individual functions, mock every power command and never
  execute installer/device enumeration. These findings are not a hardware test.
- Hidden password entry now uses exact line input, sends prompt/newline only
  to terminal output and restores saved TTY state, rather than blindly enabling
  echo. EOF fails safely. Actual private PTY tests cover native Backspace, spaces,
  no password echo and state restoration after SIGTERM to the owned test session.
- Completion distinguishes explicit Enter/reboot from EOF/stay/typos. Only the
  existing orderly privileged `bunana --restart` path is used; no forced reboot
  or fallback poweroff. Restart failure remains visible/nonzero. Waiting copy
  points to the real log instead of printing all six supposed phases before
  installation begins. No new animation or text enlargement was added.
- Seven focused shell/PTY regressions pass, plus native source and full-rootfs
  generation regression. Generated-wizard assertions now require safe completion
  and reject force flags, rather than requiring the retired standalone sync.
  Full interactive text-wizard/install lifecycle, actual log streaming and real
  installed reboot remain separate gates. GUI source `6263ec9` is pushed to both
  remotes; [GitHub checks pass](https://github.com/Ooonana/Ooonana-OS/actions/runs/39089217414).
  Signed candidate and installed WSL refresh for Batches 14–15 remain pending.

## Published checkpoint after Batches 14-15

Supersedes pending-publication notes for installer/presentation changes above.

- Source `806606627db790eddf2a504fbb1e7cacb5a82de7` is on both remotes;
  [GitHub](https://github.com/Ooonana/Ooonana-OS/actions/runs/39089480931) and
  [GitLab](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2959504799) pass.
- Signed local generation
  `5eaba3fa8900ea4c10ee9a21b9f932df80d8a44828d025ffe2f536eb2ef53ec8`
  has 654 packages/612 dependency nodes, clean exact source manifest, v3.24
  userland and no bundled models. Native release gate/all 1302 checksums pass;
  publisher re-verifies before promotion. Prior `6515c1e6…` SHA256SUMS remains
  `3842d516802db4886e029518cd4c2725eda6d720773848612ab1f27c35d0147b`.
- Native snapshot `/var/lib/ooonana/candidate-installer-ui-20261018.gwiXK7io`
  uses fast native hardlink staging, not a second large F: transfer. Exact
  current public key pins/signature verified before separate runtime/core
  dry-runs, reinstalls, verification and explicit health hooks; backups retained.
  Theme/YAD/wizard installed bytes exactly match source. OpenVINO installed
  metadata checksum is unchanged; no engine/model work was performed.
- Actual UID1000 GTK imports/CSS and Geany query pass. Cloud source points to
  new native snapshot; default metadata update passes (654 packages/two sources).
  A stricter all-source probe refused unsigned packaged builtin metadata;
  normal policy was not changed/weakened, and cloud retains its pinned key.
  Adapter refreshed after installation without launching/restarting GUI. Logs:
  `/var/tmp/ooonana-installer-ui-sync-20261018.EmYLoNQ5` in Ooonana.
- Removed only redundant Ubuntu package-build copy after all 658 files matched
  retained signed generation: 779,948 logical bytes, regenerable artifacts.
  No F: staging copy was needed. Source bytecode scan found no removable output;
  screenshots/logs, signed generations, rollback history, models, keys, ISO and
  WSL disks retained. No global restart, audio playback or ISO build.

## Batch 16: Minimal and installed GRUB evidence

- Extended existing EFI-only renderer with minimal/installed variants. Installed
  case extracts pure config writers, never sources/runs installer. Kernel files
  are harmless placeholders and never booted; no ISO or disk installer is built.
- Baseline minimal theme left menu item colors unspecified: actual EFI showed
  nearly black ordinary and selected text against black. Set explicit readable
  graphite/paper-text roles, amber selection, 16px Unifont rows and clear key
  hints. Boot arguments, installer defaults and countdown behavior unchanged.
  No larger font or additional boot animation introduced.
- Actual 640×480/1280×800 minimal captures pass normal/selected role-pixel checks,
  plus generated-config regression. Installed menu/audio submenu at both sizes
  are readable in existing text fallback. That is not a polished installed theme
  or physical boot certification; branded installed menu remains open.
- Ubuntu baseline: `/var/tmp/ooonana-grub-ui-other-20261018.xtaZP1RU`.
  Confirmation: `/var/tmp/ooonana-grub-ui-minimal-verified-20261018.RiMlxkj6`.
  This minimal-ISO builder change does not alter installed WSL/core payload;
  previous signed runtime checkpoint remains exact source `8066066`. Future
  fresh minimal builds use this source; whole-OS review stays active.

![Minimal boot menu, actual private EFI at 640×480](assets/ooonana-grub-minimal-20261018.png)

## Batch 17: Consistent installed boot branding

- Installed root previously wrote an unused minimal theme and always displayed
  generic GRUB. It now stages the same canonical `grub.theme`, official mark and
  background as live media, with readable compact audio labels. Shared asset
  replaces the old inline live-theme duplicate; existing live layout unchanged.
- Rootfs and core package explicitly include branding PNGs. Installed full-i3
  already has GRUB's 2.14 `Unifont Regular 16`; no new package/font download.
  Installer copies that target-owned font to `fonts/ooonana.pf2`, leaving custom
  `fonts/unicode.pf2` untouched. Text size stays 16px in GRUB; desktop stays 10pt.
- Graphical theme requires all target assets plus font and successful font load/
  graphics setup. Missing font/mark keeps readable console/serial menu. No boot
  entry/default/timeout/kernel argument change; no installer/disk/power operation
  executed during QA. Four writer regressions cover completeness, missing assets,
  custom font retention and exact normal/audio kernel arguments.
- Actual private EFI main/audio menu captures pass 640×480 and 1280×800, with
  selected/normal role pixels verified. Missing font and mark fallback pass both
  sizes. Renderer now gives VGA explicit preferred size: relying only on GRUB's
  gfxmode falsely assumed text fallback changed firmware framebuffer mode.
  Live main/audio regression passes both sizes. Tests use host GRUB 2.12/OVMF,
  not a physical installed GRUB 2.14 boot certification.
- Ubuntu evidence: `/var/tmp/ooonana-grub-ui-installed-confirm-20261018.o9aczJ2P`
  (complete); `/var/tmp/ooonana-grub-ui-installed-recovery-20261018.FjjNHddn`
  (fallback/live); `/var/tmp/ooonana-grub-ui-owned-font-20261018.9785yGQ7`
  (final namespaced-font main/audio and missing-font recovery).
- Installer, full-ISO fixture, rootfs/branding, native UI and backend/initramfs
  regressions pass. Source still awaits signed package/WSL refresh for this batch.

![Installed boot branding, private EFI at 640×480](assets/ooonana-installed-grub-20261018.png)

## Batch 18: Console motion and visible warnings

- Baseline private PTY showed second warning overwriting first. Status redraws
  now save/restore cursor and attributes instead of rewinding diagnostic output;
  end clears both status rows without moving warning position. A held live
  shutdown ends cosmetic feedback before showing failure/recovery text. Storage,
  stop-writer ordering, waits and fail-closed shutdown loop remain unchanged.
- Previous any-serial-argument check suppressed animation on ordinary desktop
  boots (`ttyS0` first, `tty0` last). Now standard one-console-per-type ordering
  is handled; serial-last, unknown/duplicate console types, motion-off and small/
  unavailable VT stay plain text. This follows the documented normal ordering;
  duplicate types are deliberately treated as ambiguous, not guessed.
  [Kernel console ordering](https://docs.kernel.org/admin-guide/serial-console.html).
- No worker, trap, input read, disk write or artificial waiting added to the
  console helper. Existing pulse only runs during existing waits. Real private
  xterm/PTY confirmation shows both fixture warnings visible; shell/BusyBox
  tests cover console/motion/geometry gates, cursor preservation, exact waits and
  disappearing-device refusal. Backend and live-initramfs regressions pass.
- Ubuntu baseline `/var/tmp/ooonana-console-ui-baseline-20261018.RQjYveQB` and
  confirmation `/var/tmp/ooonana-console-ui-confirm-20261018.usBkpv6G` retain
  boot/closing/save/warnings/persistence-prompt captures. These are not physical
  framebuffer, asynchronous kernel-printk or power-loss certification.
  Source publication/installed WSL refresh pending; broader review stays active.

![Both diagnostics retained after status redraw, private PTY](assets/ooonana-console-warnings-20261018.png)

## Published checkpoint after Batches 17-18

Supersedes pending-publication notes immediately above. Whole-OS review remains active.

- Source `9930c089d562f2dc670f35b348e6d3a8b4d08b09` pushed to both remotes;
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/39091329011)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2959538917)
  pass. Core archive contains current shared theme and both branding PNGs.
- Signed 654-package/612-node generation
  `1a0c0a9b91244d6e105e2c0aeeec8468240903218f4f112d529a9d8ae8284ba6`
  verifies exact clean source manifest, v3.24 base, no bundled models, all 1302
  checksums and trust pins. Publisher verifies before/after staging and promotes
  only completed generation. Prior `5eaba3fa…` SHA256SUMS stays
  `7370ebcdd14a1d7bd3ceb198f2626b3c9ea6432f5856ad3604cca8a5f90d428b`.
- Native snapshot `/var/lib/ooonana/candidate-boot-ui-20261018.gcCsxf1K` passed
  signature/key verification before separate core/runtime dry-runs, transactions,
  file verification and explicit health hooks. Installed installer, console
  helper, shared theme and PNG hashes exactly match source. OpenVINO installed
  metadata checksum unchanged; no runtime/model work. Actual UID1000 GTK/CSS and
  Geany query pass; default metadata cache resolves new local cloud snapshot.
  Adapter refreshed after install, without starting/restarting GUI or WSL.
  Logs: `/var/tmp/ooonana-boot-ui-sync-20261018.HndY06Nd` in Ooonana.
- Removed only Ubuntu package-build duplicate after all 658 files matched
  retained generation: 784,431 logical bytes, regenerable. No source bytecode,
  partial files or leftover F: publication staging found in scoped scan. All
  screenshots/logs, generations/checkpoints, models, keys, ISO/resume files and
  WSL disks retained. Ubuntu manifest proof:
  `/var/tmp/ooonana-boot-ui-publication-20261018.5EHMoWzN`.
- No actual disk install, host power operation, sound, model download or release
  ISO build. No stable promotion or trust enrollment. Remaining coverage ledger,
  especially third-party dialogs, live session/display/input and physical boot,
  is not marked complete by this checkpoint.

## Batch 19: Qt appearance and first-run proportions

- Baseline actual Qt6/QTerminal at 1024×768 showed light menus/confirmation in
  dark mode, a fixed 500px single tab and 12pt terminal default. Both appearances
  were inspected; initial light exit-dialog paint stalled under XDamage. IPC
  success alone was not counted as painted UI success.
- Selected appearance now reaches GSettings/Settings portal. Qt's packaged
  `xdgdesktopportal` plugin is selected only when present and no custom
  `QT_QPA_PLATFORMTHEME` exists. User override is shell-quoted, never evaluated
  unescaped. Existing widgets/styles, fonts/DPI and custom platform themes stay.
  This follows upstream [Qt portal color-scheme handling](https://github.com/qt/qtbase/blob/6.11/src/plugins/platformthemes/xdgdesktopportal/qxdgdesktopportaltheme.cpp)
  and the [GTK portal's GSettings source](https://github.com/flatpak/xdg-desktop-portal-gtk/blob/main/src/settings.c),
  rather than trying to theme Qt using GTK CSS.
- Fresh QTerminal configurations use opaque Graphite/Paper palettes, 11pt
  monospace, 6px text margin, hidden single-tab strip and natural multi-tab
  widths. No saved configuration is changed, including on theme toggles.
  Linked file/directory refusal, exclusive concurrent-safe creation, mode 0600,
  temporary cleanup, safe override export and readable normal ANSI colors have
  thirteen combined preference/palette regression tests. No global scale
  increase, Qt stylesheet, extra runtime dependency or default sound added.
- One confirmation batch, both appearances at normal 100%/1024×768, uses the
  existing private WSL/Xvfb full-redraw/redirection adaptation, not a physical
  compositor change. Both actual minimize/restore, fullscreen/restore, movement,
  close, bounded/focused exit dialog, Escape cancel and explicit confirmation
  pass. Source staging includes the exact current two palettes; retained lower
  candidate and installed Ooonana WSL are not modified.
- Baseline: `/var/tmp/ooonana-qt-ui-baseline-20261018.jlEkuXfa`.
  Confirmation: `/var/tmp/ooonana-qt-ui-confirm-20261018.fc0Qe9aY`.
  Native, rootfs and package-factory regressions pass, including exact palette
  bytes in built rootfs and core archive. Logs:
  `/var/tmp/ooonana-qt-{native,rootfs,factory}-regression-20261018.log`.
- Trusted cached repository signature, exact pinned key and all checksums pass
  before use. No runtime/model download. Firefox reuses only the existing
  disposable QA Flatpak home; fresh isolated profile has diagnostic preferences
  off. Real UID1000 renderer seccomp=2/no-new-privs=1 and painted frame pass.
  First-run Terms still blocks Ctrl+O: picker remains unverified, no Terms
  accepted in this batch. Fresh capture/log:
  `/var/tmp/ooonana-firefox-ui-20261018.I9z01qzx`.
- Windows currently sees Realtek reader but no SD disk/F:. No formatting,
  repair, letter reassignment, media writes, Ooonana WSL startup or host/WSL
  restart. Cached/source work continues; signed repository publication and
  installed WSL refresh of this batch await media availability. Prior generation
  is preserved, not assumed accessible/healthy. No release ISO built.
- Removed only this batch's five completed, unmounted disposable package
  overlays: 432,846,104 logical bytes (about 413 MiB), regenerable from retained
  verified cache. Screenshots, logs, cached repo/rootfs, Firefox QA home, user
  history/models/keys, generations and WSL disks retained. This does not claim
  immediate Windows free-space gain or a WSL disk compaction.

![Qt dark exit confirmation, actual private candidate](assets/ooonana-qt-dark-20261018.png)
![Qt light exit confirmation, actual private candidate](assets/ooonana-qt-light-20261018.png)

## Published checkpoint after Batch 19

Supersedes Batch 19's F:-unavailable/publication-pending notes. Whole-OS goal
remains active; no general SD-card health or hardware certification implied.

- Runtime source `f30dc7cf082de46f10a178e15811880d098b36e1` passes
  [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/39096763946)
  and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2959663303).
  Signed local generation:
  `4245766927382e2806c6891ee027acd37d6e2761e4331ed3458a2b7946797454`.
  Clean source manifest records 299 source files, v3.24 base and no bundled
  models. All 1302 checksum entries, signature/trust pin and 654-package/612-node
  dependency closure pass. Prior `1a0c0a9b…` SHA256SUMS remains
  `cb03326f21e1e42add0b3ee5e0a71f10642176abb449d3112def20dfa70bdde5`.
- Native Ooonana snapshot:
  `/var/lib/ooonana/candidate-qt-ui-20261018.oR1CSwmD`.
  Logs: `/var/tmp/ooonana-qt-ui-sync-20261018.A3bFKYC7`.
  All checksums/signature verified before sequential core/runtime dry-runs,
  reinstalls, file verification and explicit health hooks. Exact installed
  helper/palette hashes pass; OpenVINO installed metadata stays unchanged.
  A post-install comparison command lacked `cmp`; continuation used SHA256
  against the already verified install, without rerunning transactions.
  Default cloud metadata now uses this retained native snapshot (654 packages,
  two sources). Adapter refreshed without GUI/WSL restart or disk relocation.
- Actual UID1000 imports/parses installed GTK/control CSS in both appearances;
  fresh private GTK settings remain Sans 10. Nonroot Geany metadata query passes.
  `/var/tmp/ooonana-qt-user-20261018.Q1V4887U` (Ooonana). This is not an
  interactive WSLg mouse/keyboard or real display check.
- Firefox QA inspection discovered its diagnostic checkbox remained checked
  despite seeded diagnostic prefs. New opt-in QA flow visibly unchecks it
  before explicit Continue; no preference-based Terms bypass. Human's earlier
  disposable-profile-only consent applies; actual user profile/defaults remain
  untouched, network is isolated, renderer seccomp=2/no-new-privs=1 persists.
  Initial/expanded/off captures and consent log:
  `/var/tmp/ooonana-firefox-qa-consent-20261018.UHHFV6AX` (Ubuntu).
- Actual portal is floating/focused/bounded at 1024×768 and Escape cancels.
  Its action is Select, not Geany's Open; corrected QA mnemonic. Home-runtime
  baseline selection showed Firefox's read-permission error. Documents portal lists the exact owned
  fixture with read/write permissions; native root/by-app FUSE views and
  `flatpak enter` reads succeed. Namespace entry is diagnostic, not proof of the
  browser's seccomp-restricted operation. Canonical `/run/user/1000` resolves
  the actual read error: diagnostic screenshots already show a loaded document,
  but the old filename-in-WM-title assertion falsely failed private Firefox.
  This distinction was established by inspecting rendered evidence, not by
  accepting an earlier narrow failing proxy as the product result.
  Diagnostic evidence: `/var/tmp/ooonana-firefox-documents-20261018.MCWnzVQd`.
  Upstream [FileChooser](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.FileChooser.html)
  and [Documents](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Documents.html)
  contracts guide read-only diagnostics; no filesystem-wide permission grant or
  disabled sandbox used.
- One scoped read-only `access` trace on the owned Firefox parent confirms
  selected FUSE file `R_OK = 0`. No filter or privilege setting changed. Trace:
  `/var/tmp/ooonana-firefox-access-trace-20261018.WS2qTWKN/access.trace`.
  Final **untraced** confirmation uses actual browser URL and selected rendered
  content via the private X11 clipboard instead of altering privacy/title prefs.
  Scoped Terms consent with diagnostics visibly off, focused/bounded picker,
  Escape cancel, selected-file read and actual minimize/restore/fullscreen/move/
  close all pass at 1024×768 dark/100%. Renderer filtering/no-new-privs checked
  before and after file selection. Full redraw mirrors the existing WSL-only
  adaptation; no physical GPU/Windows clipboard certification implied.
  `/var/tmp/ooonana-firefox-picker-confirm-20261018.Oo7uatCV`.
  Geany picker/window and native-source regression also pass:
  `/var/tmp/ooonana-geany-picker-regression-20261018.ZZhp1kak`.
- QA now waits for actual onboarding dismissal, not Continue's hover color,
  and repeats only the non-mutating Open request during cold shortcut setup.
  Installed nested WSL launcher still sets a home-based runtime; `/run/user`
  is transient and UID1000 runtime is absent after cold startup. A safe local
  adapter/startup-preparation correction is the next required implementation;
  do not claim installed WSL Firefox picker is fixed by the isolated result.
- Confirmed F: staging duplicate has exactly 1305 expected files, no unexpected
  files/reparse children and manifest identical to retained generation. Removal
  rejected by execution policy before any action, so no deletion claimed or
  alternate deletion route attempted. Regenerable Ubuntu package copy also
  retained; logs/history, all generations/checkpoints, models, keys and disks stay.
  If desired, remove only the verified staging duplicate manually in PowerShell:

  ```powershell
  Remove-Item -LiteralPath 'F:\Ooonana\ooonana-os\build\qt-publish-stage-20261018-a9825212' -Recurse -Force
  ```

No release ISO built, sound played, model downloaded or physical storage/power
operation performed. Stable promotion and signing enrollment remain deferred.

![Untraced Firefox opens exact portal-selected fixture, private candidate](assets/ooonana-firefox-picker-20261018.png)

## Batch 20: local WSL document runtime

- Corrected the installed-session precursor identified above: local adapter
  derives canonical `/run/user/UID` selection and prepares it inside the existing
  privileged socket-namespace setup before dropping to the desktop user.
  A missing runtime now also triggers that existing setup path. No new boot
  command, system service, daemon, broad `keepenv` or packaged-launcher change.
- Embedded guards validate numeric identities, safe parent ownership/modes and
  nonlinked directory types. Final runtime is user-owned mode0700. Unknown
  owners, symlinks and writable parents are refused without taking them over.
  Existing same-owner runtime contents survive mode correction and repeat runs.
- When changing runtime, clear only inherited `DBUS_SESSION_BUS_ADDRESS` and
  `OOONANA_DBUS_SESSION`; canonical inherited bus state stays unchanged.
  Production audio remains enabled; no audio settings changed or playback run.
- Actual generated selection block, missing/valid/wrong-owner/linked/unsafe
  runtime cases and retained sentinel contents pass under Ubuntu root and
  Ooonana UID1000 BusyBox. `bash tests/test-wsl-distro.sh` also passes.
- Adapter installed with `sh scripts/install-wsl-desktop-adapter.sh`. Actual
  `/run/user/1000` is `1000:1000 700`; packaged `/usr/bin/start-ooonana-i3` and
  `/etc/wsl.conf` hashes unchanged. No desktop/WSL restart or model operation.
  This is a WSL-local correction, not an additional package/ISO payload patch;
  signed Qt runtime generation above remains current.
- Isolated Firefox portal URL/content proof above supports canonical runtime;
  actual installed Firefox/WSLg picker and input remain separate integration
  gates. Whole-OS review stays active, with Qt variants and other ledger rows
  still open. No release ISO built or physical storage/power test performed.

## Batch 21: Qt settings placement and categories

- Actual QTerminal 2.4.0 Preferences at 640×600 opened at y=-13 with its titlebar
  clipped in both appearances. Qt's subsequent positioning defeated a plain i3
  map-centering rule; removed that ineffective experiment rather than shipping it.
- Existing event-driven window-controls service now applies one delayed bounds
  correction only to newly observed, floating QTerminal dialogs that fit their
  output but open outside it. No size, font, widget stylesheet or native dialog
  content changes. Existing windows at service startup and later user geometry
  are not continuously clamped; changed/hidden/closed/fullscreen/oversized cases
  are refused. Output origins, including negative coordinates, are respected.
- Pure guard/callback tests cover scope, bounds, negative outputs, changed user
  geometry and closed/restarted sessions. Both CI workflows include the test.
  Native UI, rootfs, package-factory and existing decoration regressions pass.
- Opt-in `OOONANA_QT_DETAILS=1` private QA opens the observed native Session menu
  and Preferences, walks all six categories by keyboard, checks complete modal
  bounds, preserves deliberate later off-edge movement, restores it and cancels.
  Actual minimize/restore/fullscreen/move and exit cancel/confirm still pass at
  640×600 and 1024×768, dark and light, normal100% text. Native Alt-letter behavior
  and duplicate menu mnemonics required correcting QA navigation, not remapping
  user shortcuts. Upstream [menu](https://github.com/lxqt/qterminal/blob/2.4.0/src/forms/qterminal.ui)
  and [settings implementation](https://github.com/lxqt/qterminal/blob/2.4.0/src/propertiesdialog.cpp)
  were checked; settings rejection may remember private dialog size but does not
  apply edited options. No actual user profile is used.
- Baseline `/var/tmp/ooonana-qt-small-settings-20261018.lcWkSA5e`; final complete
  matrix `/var/tmp/ooonana-qt-placement-final-20261018.gv2JJQsd` (Ubuntu). Captures
  show actual Qt pages, not mocks. WSL full redraw remains a QA adaptation, not
  physical compositor/hardware certification. Font/background/portal pickers,
  other Qt applications and broader ledger integration gates remain open.
- Removed 17 completed owned QA overlays after exact-path and unmounted checks:
  1,905,788 KiB logical. Captures/logs/history retained; no Windows free-space or
  disk-compaction claim. Previously policy-blocked F: staging is untouched.
- This runtime source patch awaits signed candidate/installed WSL refresh.
  Local runtime adapter commit `fe50d7c` is pushed to both remotes and passes
  GitHub [39100755659](https://github.com/Ooonana/Ooonana-OS/actions/runs/39100755659)
  and GitLab [2959738246](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2959738246).
  No release ISO, audio playback, model download or physical power/storage test.

![Qt Preferences complete titlebar/actions at 640×600, dark](assets/ooonana-qt-settings-small-dark-20261018.png)
![Qt Preferences complete titlebar/actions at 640×600, light](assets/ooonana-qt-settings-small-light-20261018.png)

## Published checkpoint after Batches 20–21

Supersedes Batch 21's pending-publication note. Whole-OS review stays active.

- Runtime source `5c48b593c18dc1dee220c11f0567936000a0aa53`; GitHub
  [39101690490](https://github.com/Ooonana/Ooonana-OS/actions/runs/39101690490)
  and GitLab [2959754329](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2959754329)
  both pass, including new placement tests.
- Signed local candidate `CURRENT`:
  `5a66c5817a8a9fd0672c86378b18daf876b61ecef0a12fa504ab6a19e485b4c9`.
  SHA256SUMS digest:
  `f8116be9fb56442867085a30ba14576310a36ca74db9c25252113e0f04210ac0`.
  Signature/pinned public key and all 1302 checksums verified before and during
  atomic promotion; 654 packages/612 dependency nodes pass. Exact clean source
  manifest has 300 files, supported v3.24 base and no bundled models.
  Previous generation SHA256SUMS remains
  `9f7a6d421433494793a6c081784c4438079bb0ba0687e31db2f4f199ee500f3b`.
- Native Ooonana snapshot:
  `/var/lib/ooonana/candidate-qt-placement-20261018.DcvmDt9C`.
  Reuses 643 matching immutable native archives; copies 659 other entries.
  Full signature/1302-checksum verification precedes separate runtime/core
  dry-runs, reinstall, file verification and explicit health hooks; all pass.
  Installed window-controls SHA256:
  `c70c1533fa34b12129e557e98748d00c3a001ef7e3f1cf9437d65a7b1f8819fa`.
  OpenVINO installed metadata unchanged. Default cloud source points to new
  snapshot; default update resolves 654 packages from two sources and core info
  selects cloud. Backup checkpoints and previous source config retained.
  Logs: `/var/tmp/ooonana-qt-placement-sync-20261018.gDHUZcGQ` (Ooonana).
- Local adapter regenerated after package installation; canonical runtime guard
  extracted from the installed helper also prepares UID/GID1000 mode0700 after
  cold startup. `/run` is transient: directory absence before launch is expected,
  not a reason to add a boot daemon. Existing privileged socket setup prepares
  it on launch. No GUI/WSL restart or boot-config rewrite.
- Four final completed QA overlays removed after exact-path/unmounted checks
  (448,416 KiB logical), in addition to 17 earlier. All captures/logs/history
  remain. No immediate Windows-space gain or compaction asserted. New small
  build-only package copy and F: publication staging are retained; earlier
  policy-blocked staging was not retried through another deletion method.
- No release ISO built, audio played, model downloaded or physical power/storage
  test performed. Existing ISO cannot acquire this runtime patch via resume;
  user needs a fresh build from this candidate. Actual WSLg/browser integration,
  Qt picker variants and remaining ledger gates are not certified by this batch.

## Batch 22: Qt pickers and wide-label panel details

- Actual Qt6/QTerminal font chooser and GTK portal image picker pass 640×600 and
  1024×768, both appearances, normal100% text. Both are floating/focused, fully
  bounded and transient to the settings window. Escape returns focus to settings;
  image picker reopens and selects a private PNG with spaces in its name. Private
  clipboard confirms the exact pending path; outer Cancel does not persist it.
  Six category navigation and normal window/exit actions remain passing.
  No picker restyling was needed. Upstream [font dialog](https://github.com/lxqt/qterminal/blob/2.4.0/src/forms/fontdialog.ui)
  and [image selection](https://github.com/lxqt/qterminal/blob/2.4.0/src/propertiesdialog.cpp)
  informed the scoped QA. This does not certify Korean IME/Windows clipboard.
  Evidence: `/var/tmp/ooonana-qt-picker-baseline-20261018.vy31P9Vh` (Ubuntu).
- Panel's existing font list dropped Korean/Japanese/Chinese status characters
  even though `font-noto-cjk` is already bundled. Added the actual shipped Noto
  Sans CJK KR family after existing Latin/icon faces; existing text/icon sizes and
  font indices stay intact. No new font dependency or download.
- Correctly rendered wide labels exposed clipped right controls at 760px and AI
  displacement at middle thresholds. A new 760–999px layout prioritizes battery,
  Wi-Fi, notifications, settings, clock and power; RAM/audio details remain in
  existing controls/apps. Wi-Fi name budgets narrow below 1280px; normal native
  Wi-Fi app still provides full names. Reduced global gaps below 1280px keep
  middle-width full status groups/window controls without shrinking typography.
- QA now captures broken panels before asserting. Missing-glyph checks alone
  were inadequate: Polybar silently shifted its supposedly fixed-center group.
  An actual accent-glyph pixel check requires AI within5px of screen center.
  Final observed optical centers differ by2.5–3.5px; all right actions remain
  visible. High-count/100% status and CJK samples are explicit fixtures, not live
  hardware readings or proof of media backend transitions.
- Coverage spans 640/760/900/1000/1024/1100/1280px, both native app appearances.
  Graphite panel/dock framing stays the existing default across app themes; no
  pretend Paper panel or unrequested palette replacement. Medium-width baseline:
  `/var/tmp/ooonana-panel-middle-baseline-20261018.PJ2lOgPO`; rendered font baseline
  `/var/tmp/ooonana-panel-middle-fonts-20261018.7UNdcfA9`. Final evidence combines
  `/var/tmp/ooonana-panel-wide-confirm-20261018.ODYkdPh6` (640/760/900),
  `/var/tmp/ooonana-panel-wide-final-20261018.igsYYALU` (1000/1024/1280), and
  `/var/tmp/ooonana-panel-threshold-final-20261018.SsNoUJ5y` (1100).
  New README normal-sample capture:
  `/var/tmp/ooonana-desktop-current-20261018.pjDDHZ9q`.
- Geometry boundary and supervisor propagation tests cover the new Wi-Fi budget;
  native UI, rootfs and package-factory regressions pass. Four completed owned
  Qt QA overlays removed after exact-path/unmounted checks (448,416 KiB logical);
  captures/logs/history retained. No Windows compaction/free-space claim.
- This source runtime batch awaits signed candidate and installed WSL refresh.
  No audio playback, model download, release ISO or physical device operation.
  Live media/session/notification integration and broader ledger remain open.

![Compact 760px panel with explicit wide-label/high-counter samples](assets/ooonana-panel-cjk-small-20261018.png)
![Actual Qt-owned portal image picker, light appearance](assets/ooonana-qt-image-picker-20261018.png)

## Published checkpoint after Batch 22

Supersedes Batch 22's source-pending note. Whole-OS review remains active.

- Runtime source `55c25b0f27a25dd98a643377fe4e7fc5e4044345` passes GitHub
  [39118144999](https://github.com/Ooonana/Ooonana-OS/actions/runs/39118144999)
  and GitLab [2960068445](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2960068445).
- Signed local `CURRENT`:
  `0d8e862e06fa7e8bc068fea77308ed4119a78af728e034a4953f32b1ce5b800d`.
  SHA256SUMS digest:
  `82fc7560d5ec2ec3755e5211e1f8a43cf8039bf646619cacf595ef5e683ab12d`.
  All 1302 checksums, signature/pinned public key, clean 300-source-file manifest,
  supported v3.24 base, model-free declaration and 654-package/612-node closure
  verified. Prior generation's SHA256SUMS remains
  `f8116be9fb56442867085a30ba14576310a36ca74db9c25252113e0f04210ac0`.
- Native snapshot:
  `/var/lib/ooonana/candidate-panel-detail-20261018.6sdXSDEc`.
  Reuses 643 unchanged immutable archives, copies 659 other entries. Full
  signature/checksum verification precedes separate core/runtime dry-runs,
  reinstall, file verification and explicit health hooks; all pass. Installed
  source window-list/supervisor bytes and signed-archive Polybar configuration
  match exactly. UID1000 actual imports confirm 760/1024/1100/1280 budgets.
- Native installed hashes: window-list
  `ca8a5b4c14de451e6cd6b7ad23532fdce2d1fe6a284e71c3b244ab634d565fc6`;
  supervisor `c5eaece669ee2f9ebd07f1e284764d7a2be9ef30e4154b967d0728f319e6cb42`;
  Polybar config `82e5f71efe227b4b4687ea6a3cce0596d89689721afa580b623cf8c568201610`.
  OpenVINO installed metadata and boot configuration unchanged. Default cloud
  source points to new native snapshot, resolving 654 packages/two sources.
  Logs: `/var/tmp/ooonana-panel-detail-sync-20261018.y0eB4Yqr` (Ooonana).
- Canonical WSL adapter regenerated, not restarted. Relaunch desktop/apps for
  updated code/configuration. Private signing key stays local; stable channel
  remains 0.9.9 and enrollment/major promotion deferred. No release ISO built,
  model downloaded, sound played or physical storage/power operation performed.
  Live media/session/device and other ledger gates remain separate work.
