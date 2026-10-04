# Current work - 2026-10-04

Backend first. ISO building stays with user. Audio backend stays enabled; no playback tests.

## Core 0.9.8 maintenance

- Windows Controlled Folder Access write access restored. Explicit-key ISO checks now require a signature and verify that required desktop packages belong to the actual full-i3 install dependency closure.
- BusyBox natural-version sorting failure reproduced. Portable AWK comparison/index fallback added; revision, stable-source tie, long-number and BusyBox regression checks passed. GNU index processing keeps its one-sort fast path.
- WSL upgrade revealed a missing empty core manifest after bundle migration. Signed core meta-package health hook now recreates the legacy ownership guard; legacy migration regression passed. Custom desktop/network configs remained unchanged.
- Native PDF package sync passed for the first time in this native build: boot, input, arithmetic, core 0.9.8 and actual update completed in 101 seconds. PDF source/cache/state directories use bounded tmpfs; build-time source seed names preserve custom configs without 9p directory enumeration. No checksum/signature checks were removed.
- Bootable PDF UI rebuilt with opaque graphite cards, rounded keyboard controls, readable status and command input/Run action. All 141 canonical widgets have appearances; names, actions, values and nonoverlapping geometry checked. Docs-only guide generator preserved separately.
- Code/PDF committed as a4f1405; migration guard follow-up committed as 09f417f. Both pushed to GitHub and GitLab.
- Signed local generation eeb1363167c6dbf7dc2b7805644b91303576eafce5654572e52e93b87cf37d11 published atomically with clean source manifest at 09f417f. All 678 packages / 552 dependency nodes and detached signature passed; final ISO preflight passed on this generation. Existing ISO untouched.
- Ooonana WSL upgraded to core 0.9.8. Runtime/meta health hooks, file checks and runtime verification passed. i3, Polybar, NetworkManager and Bluetooth config hashes unchanged; desktop/OpenVINO launchers present. WSL engine 3.0.1 / kernel 6.18.40.1 unchanged; no audio playback.
- GitLab pipeline 2910852238 succeeded; public Pages verified at core 0.9.8 / revision a4f1405. Migration follow-up pipeline 2910863317 still running at last check; its Pages activation not yet claimed. CI/private signing enrollment stays deferred.
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
- Physical hardware checks: Wi-Fi, Bluetooth, audio routing (without playback), available RAM/zram, CPU/GPU/fans and disk/network counters. WSL/import/UI tests do not prove these.
- Real OpenVINO model loading/inference and CPU/GPU memory guards on hardware; fresh ISO dock/window/cursor/panel interaction check.
- Final migration follow-up GitLab pipeline and Pages activation verification.
- CI signing and trusted client enrollment deferred by user's choice: private key stays local; no CI secret uploaded. Public CI/Pages deployment is distinct from Git pushes and local signed publication.
- Chromium PDF-viewer interaction verification for this native build; native package sync now passed.
- Junk cleanup: about 331 MiB aborted generation, 1.2 MiB Python caches/metadata and 0.3 MiB previews. WSL QA environments are optional review candidates. Nothing deleted; previous deletion-policy rejection remains. Preserve models, keys, releases and build caches.

## Commands

User-owned ISO build, from PowerShell:

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'
```

Ooonana WSL desktop, from PowerShell:

```powershell
wsl -d Ooonana -u ooonana --exec start-ooonana-i3
```

## Verified foundation

Private local signing key generated; public trust key bundled. Atomic generation publication/cache, configuration preservation, health-check rollback, update policy/reboot reporting, memory preflight, actual zram reporting, event-driven dock/music, Health/Updates apps, native AI chat polish, WSL XDG handoff and unprivileged query-cache fixes passed scoped tests. Working PDF boots and accepts input. Latest desktop screenshot was captured from real nested WSL i3 without sound playback.

After reboot: local generation signature verified; Windows CRLF pointer compatibility fixed and regression-tested. Release preflight checks source/build inputs only, not fresh ISO boot or physical hardware functionality.
