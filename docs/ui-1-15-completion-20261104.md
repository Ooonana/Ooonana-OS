# Items1–15 follow-up — November4,2026

Core0.10.0 candidate; stable unpromoted. Completed1–10.5 software/private
checks remain completed. This pass addresses actual remaining software rather
than rerunning every passed screen. OpenVINO, audible tests and ISO creation
remain excluded. The user explicitly keeps VM checks pending.

## 12 — Installed nested input acceptance

The installed nested Ooonana desktop now has a complete manual receipt:
mouse, keyboard, Backspace, Hangul composition and clipboard paste all true.
The user completed the actual GTK form. Only booleans and the fixed QA text
are retained; arbitrary typed/clipboard content is not logged.

The first adapted probe omitted `GTK_IM_MODULE_FILE`, losing the per-user
Fcitx GTK cache setup from the original test. Its disabled Copy button also
unnecessarily coupled clipboard testing to composition. The probe now restores
the real IME environment; Copy works independently. Fcitx reports a connected
input context, and the refreshed end-to-end manual check passes. This was a
probe defect, not proof that all normal desktop applications lost Korean input.

![Completed installed nested input check](assets/ooonana-nested-input-20261104.png)

Physical mixed-DPI, multiple displays and hotplug remain hardware acceptance.
Earlier normal/large-text and GTK/Qt/Firefox input passes remain valid.

## 13 — Custom-init session-provider integration

Full desktop/core dependencies now include pinned elogind and Polkit services,
alongside the existing matching libraries. No musl, vendor PAM, native window
manager, locker, Qt or OpenVINO payload is replaced by an upstream reimport.
The existing vendor `base-session` already has optional `pam_elogind.so`;
its authentication policy is preserved.

The new root-only `ooonana-session-services start` runs after system D-Bus and
before installed console login, with a25-second global startup bound. It
prepares unified cgroups without replacing legacy/admin mounts, creates a
nonprivileged Polkit identity if needed and activates/probes login1/Polkit
through D-Bus. Existing providers are probed without replacing their identity.
Frozen/replaced owners are refused. WSL skips physical power services.

APK import normalizes group ownership. Only the known root:root0750 local
Polkit rules directory is repaired to root:polkitd0750. Custom inaccessible
policy is preserved and refused, never made broadly writable/readable.
No blanket authorization rules are added.

Automatic provider lid/power-key/idle actions are disabled by the Ooonana
drop-in. Explicit Power→Suspend retains the existing confirmed PAM lock,
fresh permission recheck and inhibitor enforcement. Automatic lid sleep is
not certified or enabled by this pass; physical power/wake acceptance remains.

Nine startup/refusal/policy tests and four existing lock-before-sleep tests
pass. The real pinned elogind/loginctl/busctl executables report255.24; Polkit
127-r2 native CLI/loader and the actual PAM module link successfully in a
disposable extracted dependency root. That root is cleaned after retaining
receipts. No daemon boot, host lock, suspend or VM test is inferred from ABI
checks. Rootfs and package-factory regressions pass.

Upstream integration contracts: [elogind](https://github.com/elogind/elogind),
[pinned service packaging](https://raw.githubusercontent.com/alpinelinux/aports/3.24-stable/community/elogind/APKBUILD).

## Boundaries still open

- 11: real cloud streaming/cancel/recovery needs secure new-key confirmation;
 existing credentials are not silently reused.
- 13/15: actual provider/PAM registration, inhibitors, installed transitions and
 broader system/kernel upgrades require the held VM checks and real hardware.
- 14/15: radios, sound routes, backlight permissions, physical installation,
 persistence and power-loss cases need the appropriate running device.
- Graphical greeter remains a separate feature decision. Native lockscreen
 password field/masking/PAM work is already completed, not reopened.

## November5 — Signed package and installed receipt

Source freeze `ad1e04cb5babc9c0180477395d000212503ebebf` passes
[GitHub CI](https://github.com/Ooonana/Ooonana-OS/actions/runs/41836473260) and
[GitLab CI](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/3027221267).
The signed catalog validates718 packages/637 dependency nodes. Generation
`210cf50980114af2e0c165cf5a3bc8858a0e2f36e86a336cebf7d2bf4d87a9c9`
is published on F: and under installed Ooonana's `/usr/lib/ooonana/repo`.
Previous generation72702203 and its signed checksum manifest are preserved.

Six pinned packages are added: busctl, elogind, elogind-common, polkit-common,
polkit-elogind and shadow. i3 bundle0.1.5 adds upgradeable provider dependencies.
The only changed existing payload is core-runtime: its factory rcS plus three
new session-provider files. UI/theme/icon payload stays byte-identical, retaining
earlier visual passes without claiming new physical acceptance.

The installed dry-run names only the expected additions. Actual upgrade and
core refresh verify all nine selected packages. All57 preexisting protected
configuration, account database, PAM policy/module, trust and OpenVINO hashes
remain unchanged. Factory rcS advances without a pending custom default.
`ooonana-session-services start` returns `unsupported-wsl` and
`power_requests:false`; no provider activation, power request or VM is inferred.
Recovery checkpoints remain. No model weights are downloaded.

Transfer reuses701 verified archive hardlinks and copies only seven archives,
1,955,918 bytes total. The published asset audit checks708 archives/75,903 entries:
private cursor/key excluded, public cursor matches source. Original licensing
decision remains pending. Disposable ABI/index roots were already cleaned;
candidate generations, receipts and recovery data are retained.

Item11 cloud credentials,13's held VM/provider transitions and14/15 physical
acceptance remain open. Other completed1–10.5 software results remain completed.
This follow-up does not certify all1–15 or promote stable.

Private receipts remain under
`C:\Users\7ryan\AppData\Local\Temp\ooonana-release-17-21-20261103\`.
