# Remaining-work closure - 2026-10-08

Source/candidate: core 0.10.0 on `codex/supported-base-0-10`. Installed Ooonana WSL,
stable main/update endpoints and October 6 ISO remain 0.9.9. Ubuntu only hosts
builds/tests. No ISO, installed-distro migration, sound playback or key enrollment.

## Completed in this pass

- PDF cold builtin queries read one private verified metadata/index snapshot.
  Signature, checksum, index/version mismatch, missing checksum, external-source
  precedence and cleanup regressions passed. Legacy unsigned policy unchanged.
  Extra AWK processes used only to split hashes were removed.
- Query caches now use private random `mktemp` directories, not predictable PID
  paths. Existing symlinks/unrelated files remain untouched; failed allocation
  refuses, and privilege handoff allocates no leaked caller cache. Scratch root
  includes the required `mktemp` applet. Symlink/cleanup/handoff tests passed.
- Cache hardening exposed an actual guest illegal instruction: `0xc01027f3`
  (`rdtime`). TinyEMU lacked `time/timeh` CSRs and masked off the enable bit.
  Added reads via the existing CLINT clock callback, including RV32 high word,
  RV64 high-word refusal and both machine/supervisor permission gates. No guessed
  instruction-count clock, kernel RNG bypass or unverified native binary change.
  Patch idempotence/unknown-source refusal and compiled privilege/width matrix
  passed. Actual rebuilt PDF sync exercises the previously failing `mktemp` path;
  guest illegal instructions now fail the harness immediately, not after timeout.
- Native RISC-V runtime reused after hash/config validation; current CLI embedded
  in bootable PDF. Shipped-code boot/stable input/native and virtual Backspace,
  middle editing/version/package sync passed in 87 seconds. Canonical 116 form
  fields/actions/appearances and blank input checked; final page rendered/inspected.
- Node benchmark under QA load: list 129.9 -> 45.4 seconds, sync 86.2 -> 56.7,
  bare command 2.4, help 3.3, version 2.2. Not Chromium viewer timings. A later
  stricter missing-checksum guard passed the full shipped-code suite; timings
  vary with host load. Verification was not removed for speed.
- Reproduced genuine black Nemo controls/bottom edge after earlier captures
  looked healthy. Control popup now chooses available RGBA visual before realize
  and explicitly damages changed X11 shape. Buttons remain opaque; no glass UI.
  Nemo passed repeated compositor/action tests; Geany and Chromium passed too.
- Chromium 152 shader disk-cache isolation removed the `pwritev2` sandbox crash.
  Global Alpine wrapper configuration and generated browser helper disable only
  optional shader disk cache. Normal GPU selection/user flags retained; existing
  software fallback remains. No product sandbox-disable or plaintext-password
  flag. [Upstream switch definition](https://chromium.googlesource.com/chromium/src.git/+/refs/heads/main/gpu/config/gpu_switches.cc).
- Renderer and GPU children reported `Seccomp=2`, `NoNewPrivs=1` in the private
  namespace. Probe waits for sandbox initialization, not merely a window/flag.
  This is software/Xvfb on WSL's kernel, not physical GPU or image-kernel browser
  certification. Glycin sandbox availability inside chroot remains a limitation.
- All eleven isolated GUI probes passed together: native GTK, AI indicators/chat,
  desktop input/interactions, notifications, window controls, dock, long-label
  panel, Geany, Nemo, Chromium. Fresh captures inspected and linked from README.
- Actual kernel 6.18.37 disposable QEMU upgrade interruption restored old package
  payload/config; authenticated nonroot login rejected a wrong password first.
  Partition persistence passed save/reboot, temporary-overlay isolation, abrupt
  power loss/recovery, full-storage refusal/recovery and UUID-identity rejection.
  Full ext4 and FAT file-persistence suites passed creation/cancel, reboot,
  temporary overlay, abrupt power loss, full-storage refusal/recovery, corrupt
  image refusal and late-handoff cleanup. Dirty FAT stayed unchanged until
  explicit offline repair. Three rescue-shell exits still held failed shutdown.
  Outer/inner filesystems stayed clean after orderly stops, saved data/unrelated
  USB hash retained. Final random-cache CLI also passed real interrupted upgrade.
- Broad backend/kernel/boot/package tests passed. Fresh small core package contains
  current CLI, control popup, browser helper and global compatibility config.
  This package is QA output, not a promoted complete repository generation.

## Still required / not authorized or unavailable

1. Storage: latest check C: about 6.9 GiB free, F: 4.2 GiB. F release builder needs
   at least 8 GiB; Linux release scratch needs 20 GiB, and WSL backup needs extra
   independent capacity. Supply another drive or free space before large builds.
2. Rebuild final signed candidate repository/rootfs/manifest from committed source;
   run current-image BIOS/UEFI/service/GUI gates. Never resume old 0.9.9 cache as
   0.10.0, mix libraries, or promote stable endpoints based only on source CI.
   ISO building stays user-owned.
3. WSL migration remains explicitly deferred. Require verified full backup and
   independent offline target access, resolve retired APKs, migrate whole world,
   then verify installed Ooonana login/GUI/services. Do not overlay candidate core
   on live 0.9.9 libraries or force-reimport over existing data.
4. Real nonroot Firefox Flatpak download/update/portal/file-picker checks; real
   OpenVINO Linux runtime/model load/stream/cancel, low-memory and API recovery.
   Fixtures are not inference; models/history must remain intact.
5. Actual Chromium PDF viewer keyboard/Backspace/startup/command latency. Local
   viewer navigation was policy-denied; no alternate-path/browser workaround.
   Docs-only guide remains prior candidate snapshot until release documentation
   refresh; historical PDF artifacts retained.
6. Interactive new-base Qt/dialog/file-picker and desktop session checks; actual
   cursor shape/scale, wallpaper/theme consistency, multiple app sessions,
   mixed DPI, small screens, monitor hotplug, Korean IME, text scaling, clipboard,
   WSLg keyboard/mouse, lock/logout/suspend/resume. Fixture successes do not
   certify these device/session paths.
7. Physical disposable USB/installed-target power loss/full-storage/offline backup
   recovery and interrupted upgrade/rollback. QEMU never attached host disks.
   Real SSD/unrelated USB/SD safety still needs physical read-only evidence.
8. Physical Wi-Fi/Bluetooth reconnect/pairing, silent audio routing, GPU drivers,
   idle RAM/zram, CPU/GPU/SSD temperatures/fans. No sound or fan-curve changes.
   See [hardware checklist](hardware-regression-checklist.md).
9. Signing enrollment and CI private-key upload deferred. Private key stays local;
   locally verified signatures do not enroll client trust automatically.

## Evidence

`/var/tmp/ooonana-remaining-next.Hid2Wt` stores logs, validated native runtime,
small core package and GUI captures. Failed seed/diagnostic logs retained.
`docs/assets/ooonana-candidate-*-20261008.png` are inspected isolated captures,
not physical boot proof. Valid repository generations, keys, models, history
and prior release artifacts remain untouched.

Cleanup removed only two newly created failed QEMU fixture image sets (about
1.07 GiB allocated). Logs and deleted-image checksums retained. No guest/process
held these files and paths were resolved/checked before removal. Test disks are
not recoverable after deletion, but are reproducible synthetic fixtures, not
user data or released images. VHD cleanup does not guarantee Windows space
returns immediately. Successful test fixtures self-clean only their own images.
