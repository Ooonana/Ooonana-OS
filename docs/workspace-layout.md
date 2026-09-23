# Local workspace layout

Active source remains `C:\Users\7ryan\OneDrive\문서\Ooonana OS`.
`F:\Ooonana\ooonana-os\source` is a Windows junction to the same checkout.
Use one branch history for active work; this alias is not an independent copy.

Build caches and local package repository remain under
`F:\Ooonana\ooonana-os\build`; promoted ISOs remain in `release-current`.
The full local map and manual build launcher are
`F:\Ooonana\ooonana-os\WORKSPACE.md` and `Build-ISO.ps1`.

On 2026-09-21, the previous F: source and Gemini edition were snapshot into
`codex/recovery-legacy-source-20260921` and `codex/recovery-gemini-20260921`.
Verified complete Git bundles and original working directories are retained in
`F:\Ooonana\ooonana-os\archive\2026-09-21`. Their unique changes were not merged.
Original dirty indexes/worktrees were preserved; ignored files remain with them.
The old Gemini location is a junction to its archived directory.

Old Ooonana build artifacts directly under Ubuntu `/` were moved intact to
`/var/tmp/ooonana-os/archive/2026-09-21-root-artifacts`.
Active native release staging remains `/var/tmp/ooonana-release-stage`.
Other project families and installed model/runtime stores were left in place.

Ooonana WSL was updated through the local core package to `0.8.28`, with backups
under `/var/backups/ooonana`. A BusyBox empty-archive incompatibility found during
deployment was corrected; metadata-only package upgrades now have regression
coverage. The stale D-Bus launch-helper group was repaired to `0:81:4750`, and
`update-installed-wsl.sh` now performs the same validation/repair.
