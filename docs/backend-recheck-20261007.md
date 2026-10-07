# Backend recheck - 2026-10-07

Scope: repository backend sources, generated core runtime, existing signed package
generation and available isolated Linux/VM regressions. No production ISO/kernel
build, audible/recording test, host radio change, raw host disk operation, model
load, private-key enrollment or installed-WSL replacement. Testing cannot prove
absence of all bugs; the pending gates below are not software passes.

## Coverage inventory

| Backend area | Rechecked evidence | Remaining gate |
| --- | --- | --- |
| Kernel sources/config/build policy | x86 source/build/smoke predicates; existing kernel boots in all guests; native RISC-V config resolution | Fresh compiled release kernel; physical drivers |
| BIOS/UEFI/GRUB/Secure Boot | boot matrix, UUID, ISO/disk/GRUB builder regressions and refusal policy | Fresh ISO firmware boot; actual Secure Boot trust/signing |
| Rootfs/initramfs/runtime dependency layout | scratch/full/rootfs/tar/initramfs regressions; generated runtime syntax | Fresh release-image runtime closure and physical boot |
| Live media identity and filesystem selection | synthetic USB ext4/FAT and unrelated same-label media unchanged | Real Rufus ISO/DD layout and real USB controller |
| Persistence and shutdown | 61 fresh VM case runs: power-cut, ENOSPC, file/partition, corruption, temporary/saved, rescue holds | Physical disposable USB power loss, offline backup/recovery |
| Installer/accounts/partition/swap safeguards | installer/setup regressions; real guest wrong-password refusal and UID 1000 login | Disposable full physical installation/bootability |
| Package dependency/conflict/version/archive handling | full package/CLI/factory tests; archive paths, checksums, config/ownership behavior | Third-party hooks and all installed package combinations |
| Upgrade locks/journals/rollback/health hooks | TERM/KILL, writer conflict, wrong-root/corrupt/failed recovery, download retry and VM reboot recovery | Full OS upgrade interruption/rescue on disposable installation |
| Repository/index/atomic generations | publication/index/signature/policy fixtures; real 678-package closure and 1,351 checksums | Signing enrollment deferred; actual client enrollment/remote upgrade |
| Release inputs/reproducibility/publishing | manifests, package factory, cleanup safety and both baseline CI successes | Next rebuilt artifacts and post-push CI |
| PID1/startup/service readiness/watchdog | actual VM D-Bus/NM/BlueZ/supplicant/audio endpoints and recovery, clean shutdown | Real device functionality and suspend/resume |
| Wi-Fi/auth/secrets/firmware policy | wireless action/utils/secrets fixtures and responsive service VM | Real connection/reconnect, enterprise auth, firmware on hardware |
| Bluetooth | controls fixtures; unresponsive BlueZ detected/recovered in guest | Real pairing, reconnect and suspend |
| Audio/music/media | controls/status fixtures; actual endpoint reply, MPD/helper readiness; no playback | Real devices/routes/volume/mute; playback only if authorized |
| RAM/cgroups/zram/swap/storage health | memory/cgroup/metrics/storage fixtures, RAM versus compressed-capacity reporting | Physical idle usage, actual zram/swap and large model headroom |
| GPU/CPU/fans/thermals/battery/brightness/input | kernel/backend source policy, metrics and generated helper checks | Real GPU rendering, sensors, fan behavior, brightness/touchpad |
| AI model loading guard/API/agent state | memory estimates, cgroups, metrics/API, chat/session/knowledge/checkpoint recovery fixtures | Linux runtime fresh install, real model CPU/GPU inference/cancel/tools |
| OpenVINO/first-party/compatibility packaging | package builders, Linux path policy, hash locks, vendored syntax; Wine/DeviceChat/BunanaChat fixtures | Actual application/runtime integration, Windows-only tools on Linux |
| Desktop backend IPC/process/session/notifications | window list, bounded IPC, panel supervisor, actions/preferences/notifications/task metrics fixtures | Rendered frontend, real third-party clients, multimonitor/IME |
| WSL build/install/sync | distro/rootfs/wrapper regressions; custom configuration preservation policy | Latest installed sync and interactive WSLg; WSL is not OS kernel proof |
| PDF native runtime and input transport | config/reuse fault tests and real cached reuse; embedded JS VM boot/input/Backspace/version/package sync | Chromium/Acrobat interaction and viewer-specific latency |
| Cleanup/build path containment | cleaner/release/rootfs safety regressions; source status/whitespace checks | No deletion of unrelated data authorized |

## Repairs and evidence

- Package archive test falsely failed when `grep -q` closed before tar finished.
  Actual `PIPESTATUS` was `141 0`; draining grep returned `0 0`. Corrected archive
  predicates; complete factory passed twice without changing payload assertions.
- PDF runtime reuse formerly accepted a checksum-valid kernel lacking current
  requirements. All build/reuse paths now check fragment settings, reject duplicate
  options and correctly interpret disabled/omitted symbols. Missing tmpfs and
  enabled modules are rejected even after updating the fixture checksum manifest.
- Linux source explicitly selects `RISCV_ALTERNATIVE` for non-XIP RISC-V and
  `DEBUG_KERNEL` from EXPERT. Fragment now records these unavoidable flags rather
  than falsely asking reuse to reject the existing working kernel. Debug symbols,
  sanitizers and tracing were not enabled. Fresh Kconfig resolution is checked;
  no kernel binary was rebuilt.
- 85 regression entrypoints passed after repairs. Existing embedded PDF VM passed
  in 136 seconds during concurrent QA; this measures the whole scripted sequence,
  not Enter latency in the user's viewer. Source-patched service VM powered down
  cleanly. Persistence matrices completed 30 ext4 plus 31 FAT32 guest cases.
- Baseline commit `7057da0`: GitHub run 37614583576 and GitLab pipeline 2922088046
  reported success before this recheck's fixes. New commit CI must be checked
  separately. Existing production ISO remains the October 6 artifact.
- First follow-up GitHub run 37617630268 passed. GitLab smoke failed with the new
  PDF reuse test and deployment was skipped. Alpine's BusyBox find lacks the
  `-printf` used by the injector; this rejection was reproduced locally. Added
  GNU findutils to smoke bootstrap and a dependency assertion. Follow-up pipeline
  status is separate from the local software results above.

Logs remain under `/var/tmp/ooonana-full-backend-20261007.K4f5J0JB` in Ubuntu WSL.
Synthetic media never represent F:, which contains project/releases/models and is
not disposable. Original seeds, caches, kernels, models and history are retained.

Fresh user ISO command (never resume old release staging):

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'
```

Before reflashing, back up persistent data. Follow
[physical hardware checklist](hardware-regression-checklist.md) and
[persistent USB safety](persistent-usb-safety.md). Whole-OS upgrade recovery and
hardware/controller failure guarantees are not implied by package fixtures.
