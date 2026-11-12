# GitLab smoke repair - 2026-10-15

## Finding and boundary

User screenshot reports [pipeline 2948699262](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2948699262)
and failed [ci-smoke job 17185957127](https://gitlab.com/Ooonana/ooonana-repo/-/jobs/17185957127)
for 2f891ed. Public API confirms failure; trace requires additional access.
GitHub counterpart 38653445543 succeeded on Ubuntu.

Matching Alpine 3.24.2 with the original CI dependency list reproduces exit 127
in `tests/test-verification-media.sh`: `findmnt: not found`. `test-iso-launcher.sh`
calls this fixture, so the first smoke command cannot complete. Added util-linux
and explicit findmnt/mountpoint readiness; production storage guards unchanged.
Node/gcc/musl-dev now run PDF JavaScript and compiled time-CSR checks in CI,
instead of their local-tool-unavailable skip paths.

Both providers explicitly run WSL regressions. New coverage exposed a fixture
dependency on real host wsl.exe during dry runs. Mocks now precede every installer
probe, cover cmd.exe/wslpath too, and exercise stdin retention with a deliberately
input-draining fake Windows tool. No regression test modifies registered distros.

Complete patched GitLab smoke command list passed in an isolated Alpine 3.24.2
root with its declared dependencies and container-like proc/shm mounts.
Node PDF harness and compiled time-CSR checks ran, not skipped. Persistence
backup/xattr/hardlink/tamper/atomic-migration/shutdown fixtures passed too.
Temporary fixture filesystems were normally unmounted and discarded afterward.
Remote post-push pipeline outcome remains separate from this local proof.

Commit eccf95c then passed both remote providers:
[GitLab 2948761455](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2948761455),
[GitHub 38655509434](https://github.com/Ooonana/Ooonana-OS/actions/runs/38655509434).
GitHub reported deprecated checkout Node runtime and upcoming ubuntu-latest
rollover. Follow-up pins both workflows to tested Ubuntu 24.04 and full verified
checkout commit `3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1, Node 24).
[Runner announcement](https://github.com/actions/runner-images/issues/14748),
[official checkout release](https://github.com/actions/checkout/releases/tag/v7.0.1).
Package publishing workflow is not dispatched; stable release controls unchanged.

## Docs and cleanup

Guide updated to current installed/stable distinction, WSL-local launch command,
completed ISO/WSL checks and separate pending gates. Four pages rendered and
visually checked. Bootable docs/ooonana.pdf is unchanged.

Read-only inventory confirms old replacement QA registration, VHD, raw image and
rootfs tarball are gone. Replacement plan/logs remain; active Ooonana/Ubuntu disks
are retained. No previously denied cleanup retried. Fresh isolated CI fixtures
are unmounted and removed after each run, not retained as junk.

Only CI/tests/docs changed: no kernel or packaged runtime input change and no
ISO remake needed. Stable channel remains 0.9.9; installed WSL/candidate 0.10.0.
Private key remains local. No sound or model downloads.

Final installed-WSL read-only check again passed default UID1000, version 0.10.0,
core/core-runtime/OpenVINO archive verification and local GUI launcher presence.
ShellCheck and guide fixture passed. Four guide preview PNGs (about 584 KiB)
remain at `C:\Users\7ryan\AppData\Local\Temp\ooonana-guide-qa-20261015` because
cleanup was policy-rejected before execution. No deletion retry or bypass.

## Remaining work

1. Remote CI rerun after push; local matching-environment success is separate.
2. Real Chromium PDF-viewer boot, input/Backspace and command latency; earlier
   viewer-access restriction remains, not bypassed.
3. Interactive WSLg input/clipboard, Korean IME, text scaling, lock/logout and
   suspend/resume. Process readiness alone does not certify these.
4. Firefox first-run consent/picker and remaining Qt picker/dialog journeys.
   Prior nonroot Flatpak install/update and separate Documents portal passed.
5. Fresh WSL OpenVINO runtime setup when wanted; no model weights are installed.
   Prior isolated small-model CPU streaming/cancel/recovery passed. Heavyweight/
   GPU inference remains untested, not implied by app installation.
6. Physical display/DPI/hotplug, radios/silent audio routing, GPU/thermals/fans,
   persistent USB power-loss/full-storage/recovery and interrupted physical
   upgrades/rollback: skipped until disposable hardware is available.
7. Signing enrollment and stable major-channel promotion remain deferred.
8. Optional manual removal of the four guide preview PNGs above; no OS effect.

Do not rebuild merely for pending validation. A future packaged-runtime/kernel
fix discovered by those checks would require another ISO; this pass does not.
