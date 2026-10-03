# Current work - 2026-10-03

Backend first. ISO building stays with user. Audio backend stays enabled; no playback tests.

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

- Physical USB checks: Wi-Fi, Bluetooth, audio, available RAM, zram, fans and OpenVINO inference. WSL/import/UI tests do not prove these.
- New ISO build and real installed nonroot Xorg login. User performs ISO build.
- CI signing and trusted client enrollment deferred by user's choice: private key stays local; no CI secret uploaded. Public CI/Pages deployment is distinct from Git pushes and local signed publication.
- Native PDF package-sync performance and Chromium PDF-viewer interaction verification for this native build.
- Junk scan only: about 331 MiB aborted generation, 1.2 MiB Python caches/metadata and 0.3 MiB previews. WSL QA environments are optional review candidates. Nothing deleted; latest request asked for scan. Preserve models, keys, releases and build caches.

## Verified foundation

Private local signing key generated; public trust key bundled. Atomic generation publication/cache, configuration preservation, health-check rollback, update policy/reboot reporting, memory preflight, actual zram reporting, event-driven dock/music, Health/Updates apps, native AI chat polish, WSL XDG handoff and unprivileged query-cache fixes passed scoped tests. Working PDF boots and accepts input. Latest desktop screenshot was captured from real nested WSL i3 without sound playback.

After reboot: local generation signature verified; Windows CRLF pointer compatibility fixed and regression-tested. Release preflight checks source/build inputs only, not fresh ISO boot or physical hardware functionality.
