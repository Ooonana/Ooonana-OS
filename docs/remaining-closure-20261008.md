# Remaining-work closure - 2026-10-08

Source/candidate: core 0.10.0 on `codex/supported-base-0-10`. Installed Ooonana WSL,
stable main/update endpoints and October 6 ISO remain 0.9.9. Ubuntu only hosts
builds/tests. No ISO, installed-distro migration, sound playback or key enrollment.

## October 12 follow-up

- Latest software pass: native AI now paints incremental replies; real GTK/CLI/CPU
  streaming, Stop, low-memory refusal and loaded-engine restart passed. New-base
  QTerminal 2.4.0-r0 composited controls and close confirmation passed; catalog
  entry added. All thirteen candidate GUI gates passed together. Current evidence:
  `/var/tmp/ooonana-native-ai-final-20261012.KGKGpMny/run.log`,
  `/var/tmp/ooonana-gui-source-freeze-20261012.v8Yv713R/run.log`.
- Nonroot package extraction preserves archive permissions through umask 077,
  including sticky `/var/tmp`, upgrade/configuration retention and rollback.
  Whole CI command suite passed with private UID1000 HOME/XDG state:
  `/var/tmp/ooonana-nonroot-ci-final-20261012.JMr2j1Eu/run.log`.
  Actual candidate BusyBox root upgrade/rollback passed too; unsupported nonroot
  BusyBox extraction refuses before payload changes. Portable proof:
  `/var/tmp/ooonana-tar-candidate-final-20261012.MPmMW4AU/{root,nonroot}.log`.
- Real nonroot Firefox 157.0.1 install/update passed after fixing missing sticky
  `/var/tmp` in builder/core package, with build/upgrade/unsafe-permission tests.
  Documents/FUSE, renderer kernel sandbox state, window paint and actions passed:
  `/var/tmp/ooonana-firefox-final-20261012.HgOA2mXJ/run.log`. Sandboxed picker needs
  first-run Terms consent; recommendation is defer acceptance, none accepted.
  New-base Qt file pickers/theme, physical sessions and GPU
  remain uncertified. Detailed limits: [current work](current-work.md#october-12-ai-qt-and-firefox-closure).
- C: ~4.4 GiB is below 20 GiB image-staging guard. F: ~10.8 GiB; tool-policy
  blocked removal of owned failed 6 GiB scratch image. ~367 MiB failed download
  caches removed, logs/history retained. No denied-target deletion retry.
- Remaining release gates: real PDF Chromium viewer (tool-policy blocked), Firefox
  consent/picker, Qt file pickers/theme, interactive WSLg/IME/clipboard/session,
  physical displays/input/hardware/persistence/upgrade fault tests (hardware
  explicitly skipped), and rebuilt final-image/QEMU boot matrix. Installed WSL
  migration and signing enrollment remain deferred. No further feature edits
  planned before candidate build; validation-only/docs changes do not require ISO
  rebuild, but any subsequent package/boot/runtime fix does.
- Fixed missing split `xdg-document-portal` dependency and FUSE cleanup mount
  table link. Real candidate nonroot frontend/backend/Documents activation,
  FUSE mount, focused floating picker bounds, painted controls, cancel/open and
  unchanged owned file passed on 1024x768. Proof:
  `/var/tmp/ooonana-portal-candidate-20261012.MlDoAVbo`.
- All twelve candidate GUI probes passed together, including new portal gate and
  composited Geany/Nemo/Chromium. Proof:
  `/var/tmp/ooonana-gui-portals-final-20261012.QZ9gyduI/run.log`.
- Tests install signed supplemental packages only into disposable COW upper;
  preserved candidate and installed WSL untouched. Factory/launcher/rootfs
  fixtures passed. Candidate staging: 643 packages, 611 dependency nodes.
- Earlier portal-only pass did not cover Firefox or real GUI/model journey;
  latest follow-up above supersedes that gap. Chroot Glycin sandbox warning
  remains a limitation outside proper namespace probe; no physical/audio or
  final-image certification.
- No ISO, migration, stable promotion, signing enrollment or private-key upload.

## October 11 follow-up

- User explicitly skipped hardware/physical USB checks; no physical target available.
- Fresh nonroot OpenVINO userspace setup passed verified root-image download,
  dated APT installation, hash-locked pip installation and generation promotion:
  `/var/tmp/ooonana-fresh-runtime-20261011.pXoMA9RG/setup.log`.
- Small real CPU model loading/inference, SSE, both chat/completion cancellation
  with same-engine reuse, strict memory errors and loaded-engine crash/restart
  passed on that fresh userspace through packaged bubblewrap transport:
  `/var/tmp/ooonana-fresh-inference-20261011.ua0k3JRE/run.log`.
  Current app/dependencies/assets verified; UID1000, model mount read-only,
  1280 MiB memory cap, zero swap allowance. About 224 MB disposable QA export,
  pinned revision and all selected Hub checksums verified. Saved models untouched.
- Actual inference found GenAI swallowing SSE BrokenPipeError and continuing
  generation. Both API routes now signal native stop instead of throwing through
  streamer callbacks. Regression and fresh real-runtime retest passed.
- Missing desktop portal frontend/backend found in cached candidate image.
  Firefox and full-i3 now depend on GTK portals; i3 backend configuration and
  D-Bus activation environment export added. Packaging/rootfs fixtures passed;
  old cached image does not acquire these dependencies without rebuild.
- No ISO, WSL migration, signing enrollment, audio, physical disk mutation or
  previously denied cleanup retry. Candidate 0.10.0, installed/stable 0.9.9.

## October 9 follow-up

- Offline current-app installation now passed in a disposable copy-on-write venv:
  OpenVINO Chat 0.2.1 wheel installation, `pip check`, exact pinned dependency
  versions and bundled GUI asset hashes. Real packaged bubblewrap API lifecycle,
  strict memory JSON/SSE and crash/restart passed without source override.
  Models remain read-only; preserved original venv remains 0.2.0. This is not
  complete Ubuntu/APT runtime setup or loaded-model inference. Final proof:
  `/var/tmp/ooonana-current-app-cow-20261009.lYrBbA8F/run.log` (~4.23 MiB fixture).
- Real host QTerminal 1.4.0 passed current Ooonana config/control code: painted
  buttons, minimize/restore/fullscreen/restore/floating move/close. Capture
  inspected in private nonroot Ubuntu/Xvfb, without compositor. This does not
  certify new-base Qt libraries/theme/dialogs/portals or physical sessions.
  Proof: `/var/tmp/ooonana-qt-window-20261009.HZcsOdqY`. Probe no longer silently
  skips absent expected controls. All eleven isolated candidate GUI probes
  passed again: `/var/tmp/ooonana-gui-installed-app-20261009.pmEp5a9o/run.log`.
- Removed only three redundant private cloned test venvs from this pass,
  ~1.34 GiB allocated, after metadata/path/mount/open-file checks. Original
  cached runtime, current thin COW proof, logs and user models/history retained.
  Copies reproducible, deleted files not recoverable. No VHD compaction or
  denied-target cleanup retry; Windows free space may not return immediately.
- Setup reliability patch: never install into the working runtime; stage a copy
  or fresh pinned userspace, validate readiness, retain generations and atomically
  switch the pointer. Legacy directory conversion has journal/recovery; pending
  promotion blocks launch. Actual flock/rename/sync fixtures with mocked installer
  passed three SIGKILL points, failed prepare/checksum/readiness/rename, concurrency,
  low-space and low-RAM-with-swap refusal/warning, history/config and symlink guards.
  Real packaged bubblewrap transport passed the generation pointer too.
  [Recovery and limits](openvino-runtime-safety.md); full APT/pip setup and model
  inference remain pending. No actual runtime installation or old-data deletion.
- Actual packaged bubblewrap transport now passed with real pinned runtime and
  current-source QA override, private network/PID/mount namespaces, UID1000,
  read-only models/venv. Daemon `/proc` confirms host UID1000 and its own model
  mount read-only. Ubuntu QA host, not installed Ooonana/new-image kernel proof.
  Lazy API start/status across launcher invocations,
  strict oversized-context JSON503/SSE failure, daemon survival, owned crash/
  restart, stop/state and per-command FIFO cleanup passed. Ubuntu QA rootfs
  used disposable overlay; no browser/download/weight compilation.
  Cached app remains 0.2.0: source override and synthetic readiness marker are
  QA fixtures, not proof that setup installs the current app snapshot.
  Real transport is bubblewrap, not proot. Setup/inference remain pending.
- Continuation fixed generation-time allocation failures and grammar-retry OOM:
  typed insufficient-memory errors, no OOM retry, unrelated failures preserved.
  Firefox setup/update now refuse volatile storage before Flatpak mutation;
  Firefox/OpenVINO setup also refuse unreadable/unknown/blank/dangling live-mode
  metadata. Known volatile modes alone allow explicit opt-in. No downloads.
  JSON/SSE/generation/load, launcher/setup/package/cgroup/backend regressions
  passed; both CIs now run OpenVINO package and guide fixtures.
- Docs-only guide refreshed to current evidence and pending gates; all four
  rendered pages inspected. Removed empty continuation headings caused by
  page-boundary separators, with regression coverage. Bootable PDF unchanged.
  Render evidence: `/var/tmp/ooonana-guide-20261009.PSweHJpz`.
- Actual Geany file picker requested 1098x862 at y=-44 on a 1280x800 display.
  Initial `GtkFileChooserDialog` role now uses output-relative 80%/70% bounds
  and centering. Generic message alerts and subsequent user resize remain alone.
  Real cancel/open of an owned file, focus, floating, painted controls and window
  actions passed at 1280x800 and 1024x768. All eleven isolated GUI probes passed.
  [Inspected small-display capture](assets/ooonana-geany-file-picker-20261009.png).
  This remains Xvfb/software evidence, not physical/session certification.
- Existing Linux Python 3.12 venv matches pinned OpenVINO 2026.4.1 / GenAI and
  tokenizers 2026.4.1.0. Actual Granite tokenizer encoded Korean/English text;
  five preserved model folders were read-only during real memory estimates.
  Strict excessive-context rejection, idle API health/models and SIGKILL/restart
  recovery passed without compiling weights. These use current vendored code
  and real runtime, not fake inference; the later packaged bubblewrap transport
  pass above supersedes its transport limitation. Full inference/stream/cancel
  on a loaded model remain pending. CPU only was available.
- Reproduced generic HTTP500 for strict RAM refusal. API now returns HTTP503
  `insufficient_memory`; already-started SSE sends the same type and DONE.
  CPU-fallback allocation errors now receive the same estimated RAM/context
  advice. New JSON/SSE/healthy-server/unrelated-error/fallback/no-OOM-retry unit
  tests and final real tokenizer/API probe passed. Both CIs run the unit test.
- Latest storage check: C: ~10.30 GiB free, F: ~7.97 GiB (below 8 GiB minimum).
  Host free RAM fluctuated ~7.5 to ~5.7 GiB during continuation; smallest model
  weights ~4.63 GiB plus compilation/cache/host safety margin. Earlier probes
  measured ~4.2 GiB. Heavyweight inference was not attempted.
  Guest memory allowance does not prove Windows host headroom. No unsafe full
  model attempt, new runtime/model download, ISO or deferred WSL migration.
- October 9 cleanup deletion was tool-policy rejected before execution. Identified
  ~617 MiB allocated synthetic WSL images and 254280 bytes of F: temp files remain.
  No alternate-path retry, VHD compaction, or history/model/release removal.

Evidence: `/var/tmp/ooonana-openvino-live-20261009.xZBaRy8V`,
`/var/tmp/ooonana-gui-final-20261009.2RWdAWBW` and
`/var/tmp/ooonana-geany-small-20261009.v4PKMGmE`. Failed diagnostic captures retained.

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

1. Storage: latest check C: about 4.3 GiB free, F: 10.8 GiB. F release builder needs
   at least 8 GiB; Linux release scratch needs 20 GiB, and WSL backup needs extra
   independent capacity. Supply another drive or free space before large builds.
2. Final signed candidate repository/manifest refreshed separately from stable;
   build final rootfs/image and run current-image BIOS/UEFI/service/GUI gates.
   Never resume old 0.9.9 cache as
   0.10.0, mix libraries, or promote stable endpoints based only on source CI.
   ISO building stays user-owned.
3. WSL migration remains explicitly deferred. Require verified full backup and
   independent offline target access, resolve retired APKs, migrate whole world,
   then verify installed Ooonana login/GUI/services. Do not overlay candidate core
   on live 0.9.9 libraries or force-reimport over existing data.
4. Firefox sandboxed file-picker check after explicit first-run Terms consent;
   acceptance deferred. Actual nonroot Flatpak install/update, Firefox sandbox
   state, controls and Documents/FUSE passed. OpenVINO fresh Ubuntu/APT/pip setup,
   small CPU model inference/SSE and actual GTK/CLI-to-engine streaming,
   cancellation/reuse, low-memory refusal and loaded-engine restart passed.
   Large saved-model inference and GPU remain pending;
   CPU QA proof does not certify those. Models/history must remain intact.
5. Actual Chromium PDF viewer keyboard/Backspace/startup/command latency. Local
   viewer navigation was policy-denied; no alternate-path/browser workaround.
   Docs-only guide now reflects October 9 evidence; final release-specific
   documentation still needs final image results. Historical PDFs retained.
6. New-base Qt theme/file-picker and physical desktop session checks. Composited
   QTerminal controls/close dialog passed. Real Geany file-picker cancel/open
   passed on two isolated resolutions; actual
   cursor shape/scale, wallpaper/theme consistency, multiple app sessions,
   mixed DPI, small screens, monitor hotplug, Korean IME, text scaling, clipboard,
   WSLg keyboard/mouse, lock/logout/suspend/resume. Fixture successes do not
   certify these device/session paths.
7. Physical disposable USB/installed-target power loss/full-storage/offline backup
   recovery and interrupted upgrade/rollback. QEMU never attached host disks.
   Real SSD/unrelated USB/SD safety still needs physical read-only evidence.
   User skipped these physical checks for now.
8. Physical Wi-Fi/Bluetooth reconnect/pairing, silent audio routing, GPU drivers,
   idle RAM/zram, CPU/GPU/SSD temperatures/fans. No sound or fan-curve changes.
   User skipped these hardware checks for now. See
   [hardware checklist](hardware-regression-checklist.md).
9. Signing enrollment and CI private-key upload deferred. Private key stays local;
   locally verified signatures do not enroll client trust automatically.

## Evidence

`/var/tmp/ooonana-remaining-next.Hid2Wt` stores logs, validated native runtime,
small core package and GUI captures. Failed seed/diagnostic logs retained.
`docs/assets/ooonana-candidate-*-20261008.png` are inspected isolated captures,
not physical boot proof. Valid repository generations, keys, models, history
and prior release artifacts remain untouched.

Packaged transport probe evidence: `/var/tmp/ooonana-transport-20261009.E20t3ZZC.log`.
Initial fixture mountpoint failure retained under `ooonana-transport-20261009.3YTvJzOU`;
it modified only disposable overlay, not cached userspace. Final runner guard
retest: `/var/tmp/ooonana-transport-final-20261009.X4jCaJmc.log`;
daemon host-UID/read-only-mount follow-up:
`/var/tmp/ooonana-transport-mount-20261009.CrGabZD4.log`.
New retained-generation pointer transport:
`/var/tmp/ooonana-transport-generation-20261009.YDaIdXIq.log`.

Cleanup removed only two newly created failed QEMU fixture image sets (about
1.07 GiB allocated). Logs and deleted-image checksums retained. No guest/process
held these files and paths were resolved/checked before removal. Test disks are
not recoverable after deletion, but are reproducible synthetic fixtures, not
user data or released images. VHD cleanup does not guarantee Windows space
returns immediately. Successful test fixtures self-clean only their own images.
