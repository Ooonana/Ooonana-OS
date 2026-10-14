# Ooonana WSL replacement - 2026-10-14

## Authority and boundary

User explicitly requested replacing experimental `Ooonana` and waived its
backup. This is a fresh replacement, not live cross-base library migration.
Only that distro's old experiments are in deletion scope. Ubuntu/default WSL,
Windows models, local private signing key, repositories and ISO stay unchanged.
Target location remains `F:\Ooonana\WSL\Ooonana`; Ubuntu stays on C:.

## Source and preparation

Verified published ISO SHA256:
`96dc45a2f27f0cd6e0e2e4e76b78af0604b3cbe79231c3eddadd1fc85c94c86d`.
Extracted full-i3 ext4 passed read-only filesystem check and core 0.10.0 identity.
WSL archive SHA256:
`3598703a87de6f071ce5b39ca51d4323f23dc4e6fb986ec75bc70688fcf8c0c2`.

Temporary distro: `OoonanaFreshQA-402a45e1`.
Local evidence/staging: `F:\Ooonana\WSL\ooonana-wsl-replace-20261014-402a45e1`.
No AI weights downloaded; native home/root filename inventory found no weights.
OpenVINO application is installed; its inference runtime/models are not set up.

## QA and adaptations

- Cold nonroot UID1000/default `ooonana`, core 0.10.0 and GTK/WSLg passed.
- Real nonroot package installation (`neofetch`) and core/runtime/app verification
  passed. Runtime health hook passed; package catalog contains 654 entries.
- Complete local signed snapshot verified: 1302 checksum entries. Source is
  pinned generation `5f8074ffabc6ed5848360cd1666d0c7f74ae9f2961656b6ade612efc192dbe8f`.
- Repository snapshot lives at `/var/lib/ooonana/candidate-repo-0.10`, outside
  package-owned paths. A QA deployment under `/usr/lib/ooonana/repo` collided
  with runtime bootstrap files; generation metadata was restored and installation
  retested successfully using the corrected location. No production repo changed.
- Removable F: boot mounts were unreliable here. Final configuration has no boot
  mount command and keeps `mountFsTab=false`; native snapshot needs no host drive
  mount for normal package operations. Setup defaults marked complete.
- Fresh machine ID generated. Packaged launcher remains unchanged. WSL-local
  `/usr/local/bin/start-ooonana-i3` uses a bounded 60-second Xephyr wait, local
  recursion and X11/XCB for nested toolkits. Original 5-second wait timed out on
  cold F: reads. Reproducible adapter: `scripts/install-wsl-desktop-adapter.sh`.
- Actual nested i3 4.24 IPC, dock and Polybar readiness passed. QA audio override
  was process-local; no audio playback, permanent muting or model loading.

GTK shutdown errors after deliberately closing test display are not startup
failures. Interactive keyboard/mouse, Korean IME, clipboard and full session
logout/suspend behavior remain separate gates, not certified by readiness checks.

## Completed replacement and remaining cleanup

Verified export: 3,370,123,264 bytes, SHA256
`c87c8d560333946109b4692a47d0fc7151960bf6879bc7ecb6c9224088d3ee5b`.
QEMU VHDX check found no errors. First export hit a stale sharing handle;
idle-engine shutdown was used only after confirming all distros stopped.

Old experimental Ooonana was unregistered, with no backup per explicit waiver.
Normal VHD copy-import then stalled at ~20 MiB. Cancelled it, shut down the idle
engine and unregistered only its incomplete target. Moved the tested export
within F: into `F:\Ooonana\WSL\Ooonana\ext4.vhdx`, then used supported
`--import-in-place`. No registry-state bypass or Ubuntu disk movement.

Final actual `Ooonana` cold startup passed: default UID1000, core 0.10.0,
local source/neofetch, core/runtime/OpenVINO/neofetch verification, and actual
nested i3/dock/Polybar readiness. Kernel is WSL's shared
`6.18.54.1-microsoft-standard-WSL2`, not the ISO's separately tested kernel.
Stable package channel remains 0.9.9; installed Ooonana WSL now 0.10.0.

Final cleanup command was policy-rejected before execution. Temporary QA distro,
old generated raw image and WSL tarball remain (~6.5 GiB). No deletion retry or
bypass. Local logs/config history remain too. Manual PowerShell cleanup:

```powershell
wsl --unregister OoonanaFreshQA-402a45e1
Remove-Item -LiteralPath 'F:\Ooonana\WSL\ooonana-wsl-replace-20261014-402a45e1\live-rootfs.ext4' -Force
Remove-Item -LiteralPath 'F:\Ooonana\WSL\ooonana-wsl-replace-20261014-402a45e1\ooonana-full-i3-wsl-rootfs.tar.gz' -Force
```

These targets are generated QA only, not active Ooonana or Ubuntu disks. Do not
delete the stage recursively: retain logs, configurations and replacement plan.

Launch audio-enabled desktop normally:

```powershell
wsl -d Ooonana --exec /usr/local/bin/start-ooonana-i3 --nested
```

Host-only adapter/installer fixes and WSL configuration do not require remaking
the already verified physical ISO. No AI weights downloaded or sound played.
