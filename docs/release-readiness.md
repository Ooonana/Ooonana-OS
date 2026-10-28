# Core 0.10.0 candidate: remaining acceptance gates

Updated October 28, 2026. Stable has not been promoted. This checklist replaces
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

### Original items6–8, including new7.5: October28 status

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

These are installed-package tests on a disposable X11 candidate, not an update
or acceptance of installed Ooonana WSL. Remaining work below is retained.

### Other outstanding acceptance

1. Packages/Health/Updates: successful privileged GUI transactions, visible
   authentication/errors and interrupted recovery/rollback in a disposable
   installation. Retain already-passed package engine/native upgrade proofs.
2. Task Manager: large live process lists, real sampling/overhead, sorting,
   filtering, process turnover and terminate confirmation. Native cloud AI:
   authorized real provider session, long transcript, stream/cancel/recovery.
   OpenVINO is excluded from this pass.
3. Installed desktop/themes: wallpaper/icons/cursor geometry/hotspot; held-open
   apps; panel services/media/AI/notifications; dock grouping/previews/actions,
   pins/reorder and restoration; workspace/focus/drag/fullscreen behavior.
4. Installed Settings/setup and notifications: saved preferences, privileged
   actions, storage/persistence setup, external-file failures, history/privacy,
   DND/action routing and daemon recovery with actual installed services.
5. WSLg/input/displays: keyboard/mouse, clipboard, Korean IME, keyboard focus,
   text scaling, mixed DPI, multiple displays and hotplug where available.
6. Installed sign-in/unlock, expiry/custom authentication, logout/wake and
   suspend/resume. Preserve real authentication; do not lock the user's session
   as a substitute for an isolated test.
7. Hardware-control interfaces: Wi-Fi credentials/reconnect, Bluetooth pairing,
   adapter/signal-map changes, brightness permissions, silent audio routing and
   device changes. Real hardware acceptance remains separate below.
8. Installer/boot/power: actual preview/log and text-wizard lifecycle,
   persistence setup, BIOS/UEFI GRUB, framebuffer handoff and shutdown/reboot.
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
