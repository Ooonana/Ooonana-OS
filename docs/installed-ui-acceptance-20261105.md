# Installed UI acceptance checkpoint — 2026-11-05

Core 0.10.0 candidate. Stable promotion remains held. Work paused at user request before internet disconnection.

## Verified

- Actual installed Dunst/session-bus integration: notification action, history, panel badge, Do Not Disturb queue and daemon recovery passed. Original pause level restored; only test-owned messages removed. No audio played.
- Native GVfs metadata daemon, Glycin thumbnailer and HEIF thumbnailer reached their entry points against installed libraries. This proves loader compatibility, not successful thumbnails or folder-layout persistence.
- Package schema-cache regression passed: install, upgrade without reboot, failed-health rollback, SIGKILL followed by explicit recovery, and removal. ShellCheck and whitespace checks passed.
- Nemo action safety test passed, including quoted/Korean filenames and silent failure notification. Rootfs, package factory, i3 bundle and existing update-interruption regressions also passed during this work.

## Source changes awaiting packaging

- Added GVfs metadata and image-thumbnail support to desktop package profiles. Bundle version becomes 0.1.6 so existing installations acquire these dependencies.
- Added Ooonana wallpaper actions and helper; disabled Cinnamon-only actions through factory defaults. Factory defaults disable automatic mounting/opening and autorun; explicit user preferences retain precedence.
- Refresh GSettings/GIO caches during package transactions and recovery. Core health hook bootstraps caches when an older CLI performs this upgrade.
- Added runtime-closure requirements and CI coverage for these changes.

These edits are uncommitted and have not been installed. Installed WSL and published candidate remain generation `81a738401be5d57114240e673e38f03fb3b7afe8542957e2676add68234e95b1` from runtime freeze `9051f6dc9c2d4d3ade7699b3b046e43afe1d96bc`.

## Resume order

1. Review and commit source changes; preserve executable mode on `ooonana-nemo-wallpaper`. Push candidate and verify both CIs when internet returns.
2. Finish the private package stage, rebuild core and i3 bundle, record matching provenance, reindex/sign locally and verify closure. Preserve existing native library/PAM/OpenVINO packages.
3. Install the matching experimental WSL candidate; verify protected configuration hashes. Test actual Nemo folder-layout persistence, wallpaper actions, thumbnail output and schema preference precedence.
4. Complete notification-center flyout and bounded desktop/app visual acceptance when host RAM permits.
5. Complete actual Chromium PDF boot/input/Backspace/focus/latency checks. Windows Computer Use stopped because browser URL could not be validated; do not bypass that stop. Linux viewer acceptance remains separate and pending.
6. Update final image-specific documentation and screenshots after integrated verification.

VM and physical tests remain held at user request. Live cloud AI remains blocked by API credit balance. OpenVINO overhaul, ISO building, stable promotion and trust enrollment remain deferred. Private signing key stays local; no licensing decision made.

## Preserved receipts and staging

- Controller and receipts: `%LOCALAPPDATA%\Temp\ooonana-installed-acceptance-20261105`.
- Mutable package stage: `F:\Ooonana\ooonana-os\build\native-files-stage-20261105.awauc8pd`; 16 imported dependencies, not a completed signed generation.
- Successful Ubuntu import: `/var/tmp/ooonana-files-import-20261105.uuYSRB9x`; retain until packaged bytes are verified.
- Disposable ABI scratch roots and private regression fixtures cleaned by their test finalizers. Earlier junk scan found no further confirmed junk; no additional space reclamation claimed.

Existing models, history, signing material and release/recovery checkpoints remain preserved. Current installed desktop was not replaced by these source edits. No ISO built.
