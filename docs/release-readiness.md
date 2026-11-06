# Core 0.10.0 candidate: remaining acceptance gates

Updated November 6, 2026. Stable has not been promoted. This checklist replaces
the repeated 25-item draft; detailed historical receipts remain in
[current work](current-work.md) and [UI review](ui-whole-os-review.md).

## Revised goal

Finish Ooonana's desktop interfaces and their backend integration, then verify
the exact packaged candidate. Distinguish source/private-session passes from
installed-session, physical-device and final-image acceptance. A private pass
does not certify every driver, viewer or installed configuration.

November3 request authorizes items17–21: bounded final UI review, candidate
freeze/packages, remote push/CI, signed candidate publication, Ooonana WSL sync,
documentation/cleanup and public-asset exclusion checks. Stable promotion, ISO
creation and previously deferred VM checks remain held. Keep the private signing
key local. OpenVINO's overhaul remains deferred. No audible testing. Original
code/artwork licensing remains undecided by explicit user choice.

## Current status — original task numbers

This table supersedes older publication holds and catalog counts below.
Completed private checks remain completed. Installed acceptance is bounded to
the actual cases exercised; physical hardware and final-image claims stay open.
Rows marked passed retain those exact results. They are not requests to redo
completed work. In particular,10.5's completed lockscreen must not be conflated
with13's separate session-provider acceptance. "All11–15 done" is too broad.

| Item | Current result | Still required |
| --- | --- | --- |
| 1 Qt/custom themes | Remaining Qt style variants, controls/dialogs/pickers and compiled portal repair passed privately | Physical/mixed-display acceptance under12/23 |
| 2 GTK chooser diagnosis | Warning diagnosed upstream; investigation completed | Known upstream warning remains; diagnosis is not reopened |
| 3 Launcher/helpers | Terminal fallback, missing-browser/hardware handoff and Breakout/helper cases passed | Newly discovered Nemo integration is tracked only under17 |
| 4 Legacy tray | Modern indicators and legacy XEmbed hosting, overflow, real applets and ownership recovery passed | Physical services/devices under14/23 |
| 5 Native package integration | Compiled i3/locker/Qt/PAM packages, provenance/dependencies and private upgrade compatibility verified; candidate signed/synced | Fresh final-image acceptance under22 |
| 6 Desktop/themes | Packaged wallpaper/theme/cursor/icon checks and installed desktop capture passed | Physical cursor appearance/hotspot and real display inheritance under12/23 |
| 7 Panel/dock/window manager | Packaged grouping/previews/pins/reorder/workspace cases and installed exact restore/fullscreen/close checks passed | Physical service/display/session coverage under12–14/23 |
| 7.5 Control Center | Compact opaque flyout, normal/large text, both themes, device/permission states and volume routing guards passed | Real device actions under14/23 |
| 8 Settings/setup | Saved preferences, storage/link/error guards, layout and harmless real authorization passed | Actual account/storage/persistence mutation under15/24 |
| 9 Notifications | Private passes retained; installed actions/history/panel badge/DND/recovery and frameless flyout/Escape passed | Longer normal-use and final-image acceptance |
| 10 Packages/Health/Updates | Privileged signed fixture install/remove, config preservation, interruption/recovery/health rollback and installed VM fault cases passed | Broader whole-system/kernel upgrades and physical USB acceptance under15/24 |
| 10.5 Lockscreen | Visible password field, fixed mask, Backspace/error/Caps/layout feedback, actual PAM unlock and nine normal/scaled/compact/dual-monitor gates passed; installed native revision verified | Everyday user-session automatic lock/wake coverage under13; no unfinished password-field fix |
| 11 Tasks / AI | Task sampling/termination and native chat fixture checks passed; OpenAI provider/fallback separation, redaction and both-theme control rendering repaired | Physical metrics; live cloud streaming/cancel/recovery blocked by API credit_balance_exhausted |
| 12 Input / displays | Private GTK/Qt/Firefox input and normal/large text passed; installed nested WSLg manual receipt now confirms mouse/keyboard/Backspace/Hangul/paste | Physical mixed DPI, monitors/hotplug |
| 13 Session | Existing PAM/expiry/rotation/logout/locker/VM console passes retained; custom-init login1/Polkit startup packaged and synced with nine policy/refusal tests, native ABI closure and installed WSL safe-skip verification | Actual provider/PAM registration and transitions remain unverified while VM checks are explicitly held; physical suspend/wake |
| 14 Controls | Private wireless/audio/brightness/media cases passed | Physical credentials/reconnect/pairing/routing/brightness permissions; no audible testing |
| 15 Installer / boot | Private actual checksum installation/reinstallation, BIOS/UEFI/login/sudo/storage and recovery proofs retained | Broader system/kernel upgrade timings, actual physical installation/persistence/power transitions |
| 16 Bootable PDF | Runtime/source tests retained | Actual Chromium viewer boot, keyboard/Backspace/focus and measured command latency |
| 17 Bounded UI acceptance | Earlier18 exact-package/installed restoration passes retained; installed notification flyout passed; Nemo integration source fixed with loader/private checks | Actual Nemo layout/thumbnail/menu/wallpaper tests after storage recovery; physical/mixed-display gates |
| 18 Source / CI / packages | Freeze d9b4ae5 and both CIs passed; Nemo/core bundle built; prior signed718-package/637-node generation81a73840 retained | Finish complete signing/provenance/closure after F: read stalls resolve; stable separate |
| 19 Candidate / WSL | Previous signed81a73840 installed; earlier65 protected-file/theme/input passes retained | New Nemo candidate not installed; Ooonana WSL shares stalled F: storage; publication/sync held |
| 20 Documentation / cleanup | README/screenshots, field guide, receipts/list refreshed; disposable index scratch cleaned; latest C:/F:/both-WSL cache scan finds no additional confirmed junk | Final image/release-specific evidence after user build |
| 21 Assets | Published708 archives/75,903 entries checked; personal cursor/private-key exclusion and public cursor/source match passed | Original code/artwork license decision and broader redistribution clearance remain pending |
| 22 Final ISO | Prior signed catalog preserved | Latest source needs matching verified packages first; user fresh build and image/checksum/boot/service checks |
| 23 Hardware | Private fixtures retained | Physical radios/GPU/RAM/zram/swap/thermals/fans/displays |
| 24 Disposable USB | Private installed fixture recovery/rollback/ENOSPC proofs retained | Physical reboot/full-storage/power-loss/recovery/interrupted upgrade tests; reverify disposable target identity |
| 25 Stable promotion | Private signing key remains local | Trust enrollment and stable channel/tag approval |

Sign-in currently uses console getty/PAM. A graphical greeter has not been
implemented; it is a separate feature decision, not a lost lockscreen patch.
November6 [installed UI and storage receipt](installed-ui-acceptance-20261106.md)
records notification acceptance and the blocker for further package/WSL work.
Item13's provider startup is now implemented; its real boot/session acceptance
remains held rather than counted as completed. Remaining work includes16's
viewer acceptance and17's Nemo gaps. Item11's live cloud acceptance needs
available API balance after secure new-key setup; authentication succeeds but
generation returns credit_balance_exhausted. [Provider repair and evidence](ai-openai-provider-20261105.md).
Physical/device checks are grouped under22–24;
licensing/trust/stable decisions remain explicitly held under21/25.

[November4 items1–15 follow-up and exact boundaries](ui-1-15-completion-20261104.md)
records the new source work, completed nested input receipt and November5 signed
publication/installed verification. Earlier signed generations and private
passes remain intact. No physical/held VM acceptance is inferred from WSL.

OpenVINO remains deferred. No ISO built or stable channel promoted by this pass.
[Exact candidate receipt, screenshots and CI links](candidate-17-21-20261103.md).

## Completed source/private work: retain these passes

- Native frame color bridge/state guards; gaps, modes, geometry, fullscreen,
  workspaces and minimized-session preservation; malformed-command refusal.
- Major panel/dock/launcher cases; pin/unpin/reorder, exact restoration,
  preferred and terminal fallback launches, compact Breakout/helper review.
- Graphite/Paper, held-open GTK/browser changes, Firefox themes/scaling/pickers;
  remaining Qt Fusion/Windows-style controls/pickers and compiled portal fix.
- Real private PAM/login/locker flows. Actual installed sign-in/wake remains
  separate from these authentication and rendering proofs.
- Modern indicator and legacy XEmbed hosting, bounded overflow, real applet
  actions, ownership loss/recovery. Legacy support is included, not excluded.
- Settings storage/link preservation and wireless form/file-readiness guards.
- Private null-device audio routing, mute/volume and MPD media; actual Dunst
  privacy/DND/history/actions/recovery and stale-notification identity repair.
- Native i3/locker/Qt/PAM package provenance, dependency closure, private
  upgrades, failed-health rollback and first core adoption/config preservation.

GTK chooser-close warning was diagnosed upstream. Its investigation is done;
the warning is not fixed or suppressed. Retain it as a known limitation.

## Current source addition

Desktop quick surfaces become single-instance, opaque flyouts: launcher,
notifications, quick controls, Wi-Fi, Bluetooth, sound, brightness and power.
They are anchored to the current display, excluded from dock/task entries,
toggle from their triggers and dismiss with Escape/click-away. Full editors,
Settings and Task Manager remain ordinary application windows. Ooonana's
[own style and placement](desktop-style.md) govern composition; references
explain behavior only. Quick controls use linear connection/control rows.

Acceptance includes external command handoff, nested/password dialogs, pending
request lifetime, exact focus/fullscreen preservation, normal/large text,
small screens and both themes. Existing standalone windows remain available
for diagnostic/tests; launcher and notifications accept `--window`.

These new source/private gates now pass, including actual cold/warm CLI
dispatch, separate askpass cancellation, worker process lifetime and installed
payload comparison in a disposable package upgrade. Matching core/native
packages are rebuilt in an unpublished stage; closure is654 packages/612
dependency nodes. Installed panel/session verification remains below.

## Remaining UI/integration work, in order

Latest items10–15 follow-up: [installed integrity repair](installer-integrity-20261102.md)
and [disk-tool repair and WSLg/VM checks](ui-10-15-recheck-20261031.md).
Private live Task Manager, GTK/Qt Korean input and full installer GUI lifecycle
are no longer open source/probe tasks. Installed/physical acceptance remains.
The unpublished catalog now has711 packages/630 nodes; earlier654/612 counts above and
in older receipts describe their own checkpoints.

### Original items6–10.5, including new7.5: October28 status

- **6 desktop/themes:** packaged private live-theme and saved wallpaper/theme
  checks pass. Installed application icons decode at16/32px. Public cursor
  aliases render exact19×19 pixels/hotspot2,2 through real Xcursor/XFixes.
  Physical appearance, personal cursor variant and session-wide inheritance
  remain separate manual gates.
- **7 panel/dock/window manager:** packaged private panel/media, dock and
  workspace probes pass. Grouping, pins/reorder, keyboard menu, exact minimized
  restoration and flyout focus/fullscreen guards retain their passed status.
  Actual user-session service/device integration remains pending.
- **7.5 Control Center:** source upgrade and packaged private checks pass.
  Opaque linear controls, output identity, Refresh, fixed footer and unavailable
  backlight disclosure reviewed with Impeccable4.8.0 at normal Graphite and
  200% text/760×600 Paper. Volume Apply changes only volume, preserving routes.
- **8 Settings/setup:** packaged private storage/reopen/failure and setup-layout
  probes pass. Real Settings authorization refreshes signed metadata, refuses
  index tampering, recovers on retry and installs no package. Account/disk/
  persistence setup mutation remains untested; layout fixtures do not close it.
- **9 notifications:** actual packaged private Dunst actions, opt-in history,
  privacy/storage failures, DND, panel badges and daemon restart/ID reuse pass.
  Stale actions refuse changed messages. Normal/large-text Paper and Graphite
  checks retain their passed status; real user-session integration stays held.
- **10 Packages/Health/Updates:** actual signed private GUI install/remove,
  config-preserving upgrade, failed-health rollback, forced interruption,
  recovery cancellation/restore/retry, Health refresh and live snapshot pass.
  Packages exposes recovery under More, defaults confirmation to Cancel and
  preserves actual authentication. Recovery/metadata confirmations now fit
  760×600 at200% text; Health leaves useful report space. This does not replace
  full installed-system or physical USB upgrade/power-loss acceptance.
- **10.5 lockscreen/sign-in/unlock — source/private checks pass:** compact
  Graphite/Paper, clock/date, persistent password field/fixed mask, separate layout/modifier rows,
  bounded UTF-8 labels and actual packaged Korean glyphs, actual password/error/Caps/
  layout/Backspace, duplicate-launch guard, automatic locking and virtual
  dual-monitor coverage. Real private PAM/custom-policy and three kernel/getty
  expiry/rotation/logout cases pass. New Power Suspend path confirms lock and
  respects login1 authorization; current custom-init image lacks a running
  provider, so actual suspend integration/wake remains open. Sign-in stays
  console getty/PAM; no graphical greeter introduced. [Detailed evidence and
  limits](lock-session-review-20261029.md). Installed/physical acceptance below
  remains pending; active user desktop was never locked during QA.

These are installed-package tests on a disposable X11 candidate, not an update
or acceptance of installed Ooonana WSL. Remaining work below is retained.

### Other outstanding acceptance

1. Broader installed-system/kernel/bootloader upgrades and rollback. Actual
   installed signed-fixture health rollback, preserved configuration, prepared
   checkpoint power loss/recovery and bounded ext4 ENOSPC rollback now pass.
   Keep these with private GUI/engine/native upgrade proofs; arbitrary fault
   timings, an entirely full system root and physical USB remain open.
2. Task Manager: private192-worker sampling, sorting/filtering, process turnover,
   safe termination/cancel and shortcut pass; physical hardware remains.
   Native cloud AI:
   authorized real provider session, long transcript, stream/cancel/recovery.
   New-key local saving was declined; no key created or existing key reused.
   OpenVINO is excluded from this pass.
3. Installed desktop/themes: wallpaper/icons/cursor geometry/hotspot; held-open
   apps; panel services/media/AI/notifications; dock grouping/previews/actions,
   pins/reorder and restoration; workspace/focus/drag/fullscreen behavior.
4. Installed Settings/setup and notifications: saved preferences, privileged
   actions, storage/persistence setup, external-file failures, history/privacy,
   DND/action routing and daemon recovery with actual installed services.
5. WSLg/input/displays: keyboard/mouse, clipboard, Korean IME, keyboard focus,
   text scaling, mixed DPI, multiple displays and hotplug where available.
   Actual private GTK/Qt Hangul, Backspace, clipboard and active-IME unlock now
   pass. Firefox Flatpak composition/Backspace/clipboard now also pass after
   the host module-cache boundary repair. Epoch-zero host font cache repair
   also passes exact-package normal/scaled checks with Korean font coverage.
   A rootless WSLg manual check records mouse/keyboard/Backspace; the user confirms
   Hangul/paste, while its exact-text receipt stays incomplete. Nested desktop,
   scaling and display integration remain separate. [Fresh receipts](ui-10-15-recheck-20261031.md).
6. Complete item10.5's installed sign-in/unlock, expiry/custom authentication,
   automatic locking and logout acceptance. Integrate a real login1/seat
   provider before claiming suspend support, then test physical wake/inhibitors/
   output coverage. Preserve private PAM/idle-lock passes and real authentication.
7. Hardware-control interfaces: Wi-Fi credentials/reconnect, Bluetooth pairing,
   adapter/signal-map changes, brightness permissions, silent audio routing and
   device changes. Real hardware acceptance remains separate below.
8. Installer/boot/power: completed installation/persistence mutation, BIOS/UEFI
   GRUB, framebuffer handoff and shutdown/reboot. Whole GUI preview/auth/log/
   completion passes with an inert device-free backend and real PAM; text
   wizard input/echo/signal tests pass. Actual checksum reinstall, BIOS/UEFI
   boot, UUID-mounted EFI/swap, wrong-password/root-login refusal, nonroot login,
   sudo and clean shutdown now pass in a file-backed native VM. Earlier slow
   copy failures remain historical receipts, not current whole-install blockers.
   Persistence-setup mutation and physical framebuffer/power behavior remain.
9. Bootable PDF: actual Chromium viewer boot, keyboard/Backspace, input focus,
    responsive controls and measured command latency. Source emulator tests
    alone do not close this gate.
10. Final bounded acceptance of bundled native/third-party/helper surfaces in
    both themes, normal/large text and small screens; loading/empty/error/
    permission states, keyboard focus and reduced motion. Repeat a passed gate
    only for changed code, new failures or unresolved evidence gaps.

## Earlier release-gate breakdown

The November4 table above supersedes the earlier source/publication holds in
this historical breakdown. It does not waive physical, final-image, licensing
or stable-promotion gates.

1. Approve source freeze; commit/push the final candidate, pass both remote CIs
   and build the matching signed generation with verified provenance/closure.
2. Approve publication and Ooonana WSL sync when stable-ready; verify the exact
   installed packages and current session. No Ubuntu product migration.
   Review preserved custom `rcS.ooonana-new` before claiming boot-time font-cache
   repair and installed-storage mounting/guard are active in a custom installation.
3. Refresh final README/screenshots, guides/PDFs, release notes and known
   limitations. Clean only confirmed generated junk; keep history, models,
   credentials, keys, source/build provenance and recovery checkpoints.
4. Verify public artifacts exclude private Windows cursor assets. Personal
   builds do not establish redistribution permission.
5. User builds a fresh final ISO; verify closure/checksums, BIOS/UEFI boot and
   service/GUI smoke tests. Do not reuse an image predating the final patches.
6. Manual hardware acceptance: radios, silent audio routing, GPU, idle
   RAM/zram/swap, temperatures/fans and real displays.
7. Disposable USB/install acceptance: reboot persistence, full storage, power
   loss/disconnect, backup/recovery and interrupted updates/rollback. Confirm
   unrelated disks remain untouched; destructive permission remains scoped to
   the previously confirmed disposable device, whose current identity must be
   reverified after reconnect/reboot.
8. Approve client trust enrollment and stable channel/tag promotion. Keep the
   private signing key local. Candidate version alone is not stable acceptance.

Goal stays unfinished while these gates remain open. No completed private work
is reset merely because an integrated or physical check is still pending.
