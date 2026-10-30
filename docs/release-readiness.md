# Core 0.10.0 candidate: remaining acceptance gates

Updated October 30, 2026. Stable has not been promoted. This checklist replaces
the repeated 25-item draft; detailed historical receipts remain in
[current work](current-work.md) and [UI review](ui-whole-os-review.md).

## Revised goal

Finish Ooonana's desktop interfaces and their backend integration, then verify
the exact packaged candidate. Distinguish source/private-session passes from
installed-session, physical-device and final-image acceptance. A private pass
does not certify every driver, viewer or installed configuration.

Current authorization holds installed Ooonana WSL updates, remote push/CI,
production signing/publication and ISO creation. Keep the private signing key
local. OpenVINO's overhaul remains deferred. No audible testing.

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

Latest items10–15 follow-up: [password-field/input/process/installer review](ui-10-15-review-20261029.md).
Private live Task Manager, GTK/Qt Korean input and full installer GUI lifecycle
are no longer open source/probe tasks. Installed/physical acceptance remains.
The unpublished catalog now has705 packages/624 nodes; earlier654/612 counts above and
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

1. Full installed-system package upgrades and rollback in a disposable
   installation. Private packaged GUI transactions/authentication/recovery now
   pass; retain them together with earlier package-engine/native upgrade proofs.
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
   Host WSLg remains separate. [Fresh10–15 receipts](ui-10-15-recheck-20261030.md).
6. Complete item10.5's installed sign-in/unlock, expiry/custom authentication,
   automatic locking and logout acceptance. Integrate a real login1/seat
   provider before claiming suspend support, then test physical wake/inhibitors/
   output coverage. Preserve private PAM/idle-lock passes and real authentication.
7. Hardware-control interfaces: Wi-Fi credentials/reconnect, Bluetooth pairing,
   adapter/signal-map changes, brightness permissions, silent audio routing and
   device changes. Real hardware acceptance remains separate below.
8. Installer/boot/power: real partition/install/persistence mutation, BIOS/UEFI
   GRUB, framebuffer handoff and shutdown/reboot. Whole GUI preview/auth/log/
   completion passes with an inert device-free backend and real PAM; text
   wizard input/echo/signal tests pass. Those do not prove actual disk writes.
9. Bootable PDF: actual Chromium viewer boot, keyboard/Backspace, input focus,
    responsive controls and measured command latency. Source emulator tests
    alone do not close this gate.
10. Final bounded acceptance of bundled native/third-party/helper surfaces in
    both themes, normal/large text and small screens; loading/empty/error/
    permission states, keyboard focus and reduced motion. Repeat a passed gate
    only for changed code, new failures or unresolved evidence gaps.

## Release gates: held or manual

1. Approve source freeze; commit/push the final candidate, pass both remote CIs
   and build the matching signed generation with verified provenance/closure.
2. Approve publication and Ooonana WSL sync when stable-ready; verify the exact
   installed packages and current session. No Ubuntu product migration.
   Review preserved custom `rcS.ooonana-new` before claiming the boot-time font
   cache repair is active in an upgraded custom installation.
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
