# Current work - 2026-10-05

Backend first. ISO building stays with user. Audio backend stays enabled; no playback tests.

## ISO verifier repair

- User build completed the 2,504,116,224-byte ISO but stopped before promotion. Old service-smoke harness replaced BusyBox init with its test shell and treated a successful asynchronous `bunana --shutdown` return as failure. Cleanup did not cause this failure.
- Harness now keeps packaged BusyBox init as PID1, validates its shutdown hook and runs the test as a once-action. Host requires service success, shutdown request, completed init cleanup, actual kernel power-down and QEMU exit status zero. Serial CRLF is accepted; timeouts, failure markers, missing markers and prefixed false-success strings are rejected. Production shutdown implementation is unchanged.
- Predicate regression checks passed two valid LF/CRLF logs and eight rejection cases. Actual staged-ISO service smoke passed with KVM/1536 MiB: Wi-Fi profile variants, daemon/watchdog recovery, audio routing/control, Chromium, desktop runtime, privilege checks and orderly shutdown. Guest powered down at about 46 seconds. QEMU audio output remained disabled; no playback.
- Runtime packages/kernel and existing released ISO remain unchanged. Staged ISO remains available for user-owned `--resume-after-iso` verification, BIOS/UEFI matrix and promotion; no ISO rebuild or automatic promotion performed here.

## Disposable cleanup completed

- Explicit user request recycled 447 disposable files, 333.13 MiB logical: bytecode caches, generated OpenVINO build copies/metadata, abandoned `.stage-v2w1_1fn` and two stale index/checksum temporary files. Recoverable from Windows Recycle Bin; not a claim of freed disk space.
- Git history, all valid repository generations/current pointer, releases, historical PDFs/previews, models, keys, firmware/kernel caches and WSL QA environments were preserved. No source changes resulted from cleanup.

## Core 0.9.9 completion pass

- Fixed stale boot-parser regression fixture. Shared helper and current parsing order are exercised without host mounts.
- Larger third-party titlebar targets; hidden tabs, fullscreen-covered clients and floating-window occlusion no longer expose incorrect controls. Destroyed popup XIDs are released. Alt+F4/Alt+F10 support close/fullscreen without dock access.
- AI low-memory warning styling and live-space badge; Settings storage card; silent, rate-limited once-per-minute free-space/inode/read-only monitoring. No automatic cleanup or audio playback.
- BusyBox init owns shutdown in fresh minimal/full images. Standard bunana actions no longer force shutdown; guarded init cleanup stops writers, syncs, disables swap, remounts live persistence read-only and unmounts. Known legacy shutdown action migration preserves installed getty/custom actions.
- Root-image UUID locks saved overlays to matching bases. Verified offline metadata/hardlink/xattr backups and atomic data-only home migration preserve complete previous overlays. No disks mounted/formatted/repaired/selected by maintenance tools.
- Core version advances to 0.9.9 for update delivery. Guide and bootable PDF refreshed; legacy lite PDF remains explicitly labeled. Hardware checklist and per-push GitHub regression gate added.
- Final shell sweep passed 48/48 suites. Package-sort fixture now rejects only version-sort options, not uppercase `V` in temporary filenames; 30 repeated runs passed. Additional radio/audio, readiness, index/memory, update-safety and 116-field PDF checks passed.
- Eight USB-image VM cases passed with the current live runtime on ext4 and FAT32 boot media. Successful shutdown requires both cleanup and persistence-read-only markers; unrelated USB image hash stayed unchanged. Installer-seed BusyBox is not a substitute for the live-runtime test seed. Failed fixtures retain diagnostic logs.
- Windows/WSL newline-only source differences were normalized; CSS/HTML/cursor-theme/AWK files now have explicit LF checkout policy for clean release manifests.
- Clean-checkout CI exposed missing executable modes on existing launchers and musl's missing `renameat2` wrapper. Launcher modes are corrected; verified Linux atomic syscall fallback keeps no-overwrite/exchange semantics without unsafe two-step renames. Unknown ABIs refuse.
- Backup manifests now verify hardlink relationships; data-only migration verifies the copied home tree before exchange. Source game wrapper prefers its own adjacent payload, preventing stale installed games from masking regressions. Shutdown validates actual init command and registered hook, rejecting BusyBox PID1 shell/container contexts. CI declares comparison-tool dependency; native BusyBox fallback is exercised.
- Isolated GTK/i3 native and third-party close/minimize/restore/fullscreen controls, hover previews, low-RAM/storage indicators and Settings checks passed. Component screenshots refreshed; the main desktop image remains the explicitly labeled earlier WSL capture. Both final PDFs were rendered and visually checked; the actual embedded native PDF boot/input/Backspace/version/package-sync suite passed in 113 seconds.
- Final clean Linux checkout at `a0c6dfc` passed all 48 suites. Persistence backup/migration also passed on native musl; supported xattrs and hardlink relationships were verified. CI tmpfs probes skip only unsupported xattr assertions, not other persistence checks.
- GitHub [run 37278143738](https://github.com/Ooonana/Ooonana-OS/actions/runs/37278143738) and GitLab [pipeline 2912436524](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2912436524) succeeded at `a0c6dfc`. Public Pages serves core 0.9.9, generation `90ed2498d89396d2e222089a7ad0975c3a01ccb284a9038e32480a49e014cd71`. CI publication remains unsigned under the deferred enrollment policy.
- Local signed generation `ee9cbdfa3c6de9518ca2fcbb2d31fe12ce458de021b6515cbc36da20e28ffb4d` pins clean source `a0c6dfc`. All 678 packages / 552 dependency nodes, detached signature and final ISO preflight passed. Published generations and existing production ISO were not overwritten.
- Ooonana WSL upgraded to core 0.9.9; package verification and runtime/meta health hooks passed. Default i3 config refreshed; custom environment/keycode/inittab/neofetch configs were preserved with update candidates. Polybar, NetworkManager and Bluetooth config hashes stayed unchanged. Nonroot GTK 3 X11 display/keyboard readiness and AI/Settings/window-control imports passed; Mesa acceleration warnings remain, so GPU acceleration is not claimed. WSL engine/kernel were not changed or restarted; no audio playback or model files changed.
- Final PDF payload remains current: later desktop/persistence fixes are excluded from its explicit minimal portable CLI/repository input set. No unnecessary kernel/PDF rebuild claimed. Later explicit disposable cleanup is recorded above.
- Physical BIOS/UEFI, disconnect/power-loss, radio/audio/sensor and OpenVINO model-load checks remain manual. Private signing key stays local; trust enrollment/CI signing stays deferred. ISO remains user-built.

## Persistent USB safety pass

- GRUB passes boot-filesystem UUID; writable overlays require matching removable/USB media and exactly one eligible same-parent ext4 persistence partition. Duplicate/cloned boot UUIDs across drives and duplicate persistence partitions stop boot before writable mounting.
- Persistent mode now fails clearly instead of silently using RAM when identity/storage is missing, unmountable, unwritable or below 16 MiB free. Saved/temporary overlay paths and mount-handoff paths reject symlinks/non-directories. Saved overlays are never auto-cleared or fsck-repaired.
- Base image loop is read-only with `ro,noload`; image paths cannot escape boot media. Required BusyBox applets are linked explicitly. Critical bind/move failures are no longer ignored, and rcS cannot print persistence success after a failed bind.
- Storage helper belongs to release resume fingerprint. Fixture suite covers exact flags, identity/parent selection, wrong filesystem, duplicates, unsafe paths, low space, failed probes and rcS status; wired into release preflight and GitLab smoke.
- Eight isolated QEMU USB-image checks passed: save, reboot restore, temporary first boot/reset, saved data surviving temporary boots, missing UUID, missing partition and cloned UUID rejection. Unrelated same-label USB image stayed byte-identical. Tests use current live-init source/current x86 kernel and release BusyBox, not a production ISO rebuild.
- Initial boot-identity pass left production ISO, physical disks, WSL installation, swap policy and private signing key untouched. Later core 0.9.9 work updates WSL and verifies orderly shutdown, storage warnings and offline migration in fixtures/VMs, not physical hardware. See [persistent USB safety](persistent-usb-safety.md).

## PDF input follow-up

- User screenshot exposed an upstream timer restoring the keyboard hint every second. Prior static blank-widget checks did not catch runtime mutation. Timer is now removed from the embedded script; VM tests keep input populated beyond 2.2 seconds to detect recurrence.
- Native input now forwards Backspace/deletion ranges instead of dropping empty-change events; bounds protect Delete past end. Middle edits position the guest cursor around the selected range. Virtual Backspace sends DEL once and updates input; virtual Enter clears it. Commit/blur events cannot resend typed text.
- Final Node VM suite passed boot, stable input beyond the reset deadline, arithmetic, native/virtual Backspace, middle deletion, core version and actual package sync in 90 seconds. UI actions and runtime bounds/idempotence checks passed. Actual Chromium clicks/keyboard interaction remain a manual gate; no browser-policy workaround used.
- Existing native kernel hashes/config verified: 100 Hz, tmpfs/sysctl, no SMP/modules/debug symbols/sanitizers/ftrace. Linux EXPERT selects DEBUG_KERNEL as a menu flag; no new debug instrumentation or fresh kernel trim claimed. RAM-cached CLI/help/repo, bounded VM batches and 20 Hz rendering retained. Desktop/ISO/WSL unchanged.

## PDF-only latency pass

- Bare `ooonana` now uses a small PDF shell front door; genuine topic help is extracted at build time. All other commands retain the byte-identical source package backend, including checksum/signature checks.
- Removed unsupported GTK/Python/AI/desktop payload and non-RISC-V bundles from the PDF root; base metadata is reindexed with matching checksums. Named CLI/help/repository/trust files are seeded into bounded tmpfs. No desktop package bundle, WSL installation or ISO changed.
- Serial output no longer repaints on every character. Dirty-row widget references are cached, painting is capped at 20 Hz, CPU slices are bounded, and loader diagnostics stay in a bounded memory buffer rather than 25 hidden widgets.
- Removed redundant keyboard-input hints; canonical input remains blank. Final form has 116 interactive canonical widgets with matching appearances/actions; opaque layout rendered and inspected.
- Node VM benchmark: bare command 35,905 -> 2,395 ms; package help 51,795 -> 3,046 ms; version 2,269 ms; base-only list 63,399 ms; actual package sync 51,067 ms. Bare-command terminal writes fell from 968 to 11. Earlier full list exceeded 240 seconds. Final rebuilt boot/input/arithmetic/version/package-sync suite passed in 98 seconds. Browser timing is unverified; package-operation latency remains a follow-up.
- Fresh minimal runtime reuses manifest-checked Linux/BusyBox binaries and applet links only; original runtimes/data remain untouched. Payload root shrank about 35%; PDF shrank about 7% (5,967,364 -> 5,546,677 bytes). Runtime reuse, tamper refusal, rendering bounds/idempotence, payload and form tests passed.
- Chromium interaction remains manual because local browser navigation was policy-blocked; no alternate browser/proxy workaround used. Signing enrollment stays deferred; private key remains local. Existing junk-cleanup policy block remains; no material junk deleted.

## Core 0.9.8 maintenance

- Windows Controlled Folder Access write access restored. Explicit-key ISO checks now require a signature and verify that required desktop packages belong to the actual full-i3 install dependency closure.
- BusyBox natural-version sorting failure reproduced. Portable AWK comparison/index fallback added; revision, stable-source tie, long-number and BusyBox regression checks passed. GNU index processing keeps its one-sort fast path.
- WSL upgrade revealed a missing empty core manifest after bundle migration. Signed core meta-package health hook now recreates the legacy ownership guard; legacy migration regression passed. Custom desktop/network configs remained unchanged.
- Native PDF package sync passed for the first time in this native build: boot, input, arithmetic, core 0.9.8 and actual update completed in 101 seconds. PDF source/cache/state directories use bounded tmpfs; build-time source seed names preserve custom configs without 9p directory enumeration. No checksum/signature checks were removed.
- Bootable PDF UI rebuilt with opaque graphite cards, rounded keyboard controls, readable status and command input/Run action. All 141 canonical widgets have appearances; names, actions, values and nonoverlapping geometry checked. Docs-only guide generator preserved separately.
- Code/PDF committed as a4f1405; migration guard follow-up committed as 09f417f. Both pushed to GitHub and GitLab.
- Signed local generation eeb1363167c6dbf7dc2b7805644b91303576eafce5654572e52e93b87cf37d11 published atomically with clean source manifest at 09f417f. All 678 packages / 552 dependency nodes and detached signature passed; final ISO preflight passed on this generation. Existing ISO untouched.
- Ooonana WSL upgraded to core 0.9.8. Runtime/meta health hooks, file checks and runtime verification passed. i3, Polybar, NetworkManager and Bluetooth config hashes unchanged; desktop/OpenVINO launchers present. WSL engine 3.0.1 / kernel 6.18.40.1 unchanged; no audio playback.
- GitLab pipelines 2910852238 and 2910863317 succeeded. Public Pages verified at core 0.9.8 / revision 09f417f, generation 75a1a99ec5a677c601f32ebdd25c560eeb5bb428e45c484601527c4c19e794a6; the core meta health hook is present and covered by the checksum manifest. Private CI signing/client enrollment stays deferred.
- Cleanup still blocked by previous deletion-policy rejection. Nothing material removed. Preserve models, keys, releases, kernel/firmware caches and valid generations.

## ISO cache repair - 2026-10-03

- User build stopped before full rootfs: cached i3 bundle omitted OpenSSL, although archive existed. Refresh only mutable staging metadata, then re-index/re-sign and atomically publish a new generation; old published generations remain untouched.
- Release preflight now checks complete profile, dependency closure, package/index/checksum consistency, core version and detached signature before rootfs writes.
- Import helper refuses published roots/generation directories. Staged full-rootfs metadata now includes BUILD-MANIFEST.json, matching checksum manifest.
- Cache repair completed in 695da59; signed generation and ISO preflight reverified October 4. PDF work subsequently resumed; cleanup remains policy-blocked.

## Core 0.9.7 pass

- Native dock: bounded RAM-only hover previews, tooltips, running indicators, restore and right-click actions. Isolated i3 hover focus checks passed.
- Responsive wide/compact/small panel layouts and bounded music title length. Hidden top-bar shortcuts remain accessible in native windows, dock menus and Control Center.
- AI elapsed request/model-start phase and physical/cgroup-aware RAM badge; timer only during activity. GTK low-RAM fixture checks passed; no inference claimed.
- Backend: bounded endpoint readiness, one-sort index merge (10,004 fixture rows in about 35 ms), signed index checks and source-only manifests. Generated public/bytecode/egg-info outputs no longer alone mark source dirty.
- Native PDF SHMEM/tmpfs/sysctl resolved; standalone/nofork BusyBox and RAM-backed temporary mounts added. Boot/input/version/actual tmpfs mount passed; 140-field PDF structure reopened and static layout inspected. Package-sync timeout remains; interactive viewer check blocked by browser file-URL policy.
- Core code/PDF pass committed as fc3e8dc and pushed to GitHub/GitLab. Signed local generation published; WSL core upgrade/health check and ISO preflight passed. GitLab pipeline 2908742342 build jobs passed; Pages activation still pending at final check (public endpoint still served 0.9.6).
- Hardware regression checklist added. Private signing key stays local; enrollment/CI signing deferred.

## Completed foundation in core 0.9.6

- Cursor increased to **110% of previous size**, preserving original shape and hotspot proportions: personal 19 -> 21 px; public 17 -> 19 px. Actual Xcursor frames regenerated; WSL personal theme updated. Preserved native Windows frames were used, not a stretched enlargement of the previous small frame.
- Nineteen matching native SVG icons added to application entries and window headers; WSL icon cache refreshed.
- Missing BusyBox `find` link repaired in WSL/scratch base. OpenSSL included in core dependencies/cloud profiles so target clients can verify signed repository updates; failed package verification now propagates cleanly.
- Third-party titlebar close/minimize/fullscreen buttons added with focus-neutral, event-driven positioning. Isolated i3/xterm interaction checks passed.
- Installed boot now hands off to BusyBox init/getty instead of the legacy root shell. Diskless QEMU test rejected wrong password, accepted fixture password, and entered desktop launcher as UID 1000. Physical Xorg login remains untested.
- OpenVINO Chat 0.2.1: complete Linux x86_64/Python 3.12 wheel lock with hashes, pinned Ubuntu runtime image/checksum and dated APT snapshot. Fresh full-app imports and snapshot dependency resolution passed; no model inference performed.
- Native RISC-V64 Linux 6.18.37 / BusyBox 1.37.0 PDF regenerated. TinyEMU boot, keyboard input, arithmetic and core 0.9.6 version checks passed. Full package-sync check remains too slow to pass its timeout. Emulator-only RV64 clock scaling makes guest time 16x slower; not an x86 desktop/kernel change.

## Remaining gates

- Physical USB boot: BIOS/UEFI/GRUB, persistence, unrelated-drive protection and installer swap. New ISO build and real installed nonroot Xorg login. User performs ISO build.
- Existing saved USB overlays require verified offline backup and explicit data-only migration before using a rebuilt ISO; backup before flashing, because imaging can erase the persistence partition. No automatic legacy-overlay conversion or power-loss durability guarantee.
- Physical hardware checks: Wi-Fi, Bluetooth, audio routing (without playback), available RAM/zram, CPU/GPU/fans and disk/network counters. WSL/import/UI tests do not prove these.
- Real OpenVINO model loading/inference and CPU/GPU memory guards on hardware; fresh ISO dock/window/cursor/panel interaction check.
- CI signing and trusted client enrollment deferred by user's choice: private key stays local; no CI secret uploaded. Public CI/Pages deployment is distinct from Git pushes and local signed publication.
- Chromium PDF-viewer interaction verification for this native build; native package sync now passed.
- Actual WSLg accelerated rendering: GTK 3 X11/keyboard readiness passed, but Mesa reported acceleration warnings; no forced graphics backend or global software-rendering override applied.
- Optional storage review: WSL QA environments remain review-only. Disposable cleanup completed above; historical PDFs/previews, models, keys, releases and useful build caches remain intentionally preserved.

## Commands

User-owned ISO build, from PowerShell:

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'
```

Resume the completed October 5 staged ISO after the verifier fix, without rebuilding:

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1' --resume-after-iso
```

Ooonana WSL desktop, from PowerShell:

```powershell
wsl -d Ooonana -u ooonana --exec start-ooonana-i3
```

## Verified foundation

Private local signing key generated; public trust key bundled. Atomic generation publication/cache, configuration preservation, health-check rollback, update policy/reboot reporting, memory preflight, actual zram reporting, event-driven dock/music, Health/Updates apps, native AI chat polish, WSL XDG handoff and unprivileged query-cache fixes passed scoped tests. Working PDF boots and accepts input. Latest desktop screenshot was captured from real nested WSL i3 without sound playback.

After reboot: local generation signature verified; Windows CRLF pointer compatibility fixed and regression-tested. Release preflight checks source/build inputs only, not fresh ISO boot or physical hardware functionality.
