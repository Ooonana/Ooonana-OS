# Backend update policy - core 0.9.9

## Verified behavior

- Repository generations contain archives, package metadata, hashed index, hooks and build manifest. Validation happens before `CURRENT` changes. Old generations remain available locally and in the append-only R2 publisher.
- Unchanged archive bytes can share hardlinks between immutable published generations, reducing disk duplication. Mutable staging files are never hardlinked into publication. Published files and pointer receive public-readable permissions; hooks remain executable. Never edit published archives in place.
- HTTP metadata and release-tarball caches use verified generation snapshots. Package downloads stay bound to the selected snapshot. Untrusted keys are not automatically learned from remote `repo.pub`.
- Changed or previously untracked package-owned `/etc` files survive upgrades. New defaults are written beside them as `.ooonana-new`. `/etc/os-release` intentionally follows the new release.
- Install and health-check hooks run before transaction completion. Failed upgrade checks restore old package files, metadata, config baselines and custom configuration. Hooks changing files outside package ownership cannot be automatically undone.
- Successful core/kernel updates keep private recovery checkpoints under `/var/lib/ooonana/packages/backups`; `OOONANA_KEEP_UPDATE_BACKUPS=all` retains other package checkpoints too. Checkpoints are recovery files, not an automatic disk-image restore system.
- Package writers hold a kernel-released lock; concurrent install/upgrade/remove/repair is refused. Hooks do not pass this lock into background services. Before replacement, old payload/config/metadata and checksum-verified recovery records are synced. An interrupted replacement blocks further mutations and file verification until explicitly recovered; normal inspection remains available.
- Run `ooonana recover` after an interrupted replacement. Prepared journals restore old package-owned files, metadata and custom config; completed journals are retained without undoing a committed update. Recovery records remain under `backups/recovered-*`. Corrupt, incomplete/legacy or wrong-installation checkpoints are retained and refused, not guessed or deleted. Recovery is retryable after a restore failure. If the installed CLI/loader cannot run, recovery requires external rescue media with the correct mounted target/state paths. This does not guarantee whole-OS bootability after a power cut or undo arbitrary hook effects.
- Remote metadata/archive downloads stage privately and check declared checksums before cache promotion. Interrupted/truncated transfers cannot poison the final cache; damaged older cached archives can be fetched again without changing the installed payload. GNU wget respects the configured retry budget instead of its default twenty attempts.
- `ooonana upgrade --dry-run` reviews changes; `--allow-major` explicitly permits a core version jump. Pre-1.0 minor changes such as 0.9 to 0.10 count as major. `--security-only` requires `OOONANA_PKG_SECURITY=1`; unmarked changes are never guessed to be security fixes.
- `ooonana update-status` reports pending update category and reboot requirements. Boot/kernel/core changes use `OOONANA_PKG_REBOOT=1`.

## Signing and enrollment

New RSA-3072 repository key was generated locally on 2026-10-02. Private key stays outside Git, in the owner's protected local key directory. Only public key is packaged:

`/etc/ooonana/trusted-keys/repository-20261002.pub`

Public PEM SHA-256: `951dabde44988d9db87ed146f483322a5830c8ceaaad07dde4e75aeca42ae34d`.

Existing installed clients must obtain the public key through a trusted channel, verify this fingerprint, then enroll it explicitly before using newly signed repositories:

```sh
ooonana repo add cloud https://ooonana.gitlab.io/ooonana-repo --key /trusted/path/repository-20261002.pub
```

Set `OOONANA_REQUIRE_SIGNED_REPOS=1` once every configured source is signed. Legacy unsigned sources remain compatible by default; bundling a key alone does not prohibit signature stripping on an unsigned-compatible source. CI signing secrets were not uploaded by this pass. Public Pages deployment still needs signing-key configuration and successful CI verification. GitLab Pages replaces the whole deployment; retention of old remote generations depends on hosting/artifact retention, unlike append-only local/R2 publication.

Build in a staging directory, then publish:

```sh
python3 scripts/publish-repo-generation.py --source STAGING_REPO --target PUBLISHED_REPO --public-key TRUSTED_PUBLIC_KEY
```

On Windows, `scripts/index-repo-fast.py` hashes factory metadata without executing shell assignments. It rejects dynamic metadata and published roots, supports local signing, and avoids slow per-package shell launches on drvfs.

## Memory, idle work and runtime inputs

OpenVINO preflight estimates weight, KV-cache and overhead against available RAM and cgroup limits. Estimates are conservative, not guarantees. `OPENVINO_MEMORY_POLICY=warn` preserves compatibility; `strict` blocks an estimated oversized load and `off` disables the guard. OOM errors recommend lower context, supported cache precision or smaller quantized models instead of blindly retrying on CPU. Swap is not physical RAM.

CLI, Task Manager and Health show zram's real resident/compressed consumption. Logical compressed-swap capacity is never added to physical RAM. Fields follow [kernel zram documentation](https://docs.kernel.org/admin-guide/blockdev/zram.html); inference estimates follow [OpenVINO memory guidance](https://docs.openvino.ai/nightly/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.html).

Dock subscribes to i3 events; music subscribes to MPD idle events. Reconnects remain bounded. Health checks run on demand, not in a permanent polling loop.

Native dock keeps bounded hover images in RAM; hidden/unavailable windows fall back to text without focus or restore. Responsive panel selects compact layouts at smaller widths. AI elapsed phase ticks only during activity; available RAM includes cgroup limits, never swap capacity.

Health probes bounded service replies: system D-Bus, NetworkManager/BlueZ/supplicant ownership and explicit audio-server reply. No repair, playback or auto-spawn is requested. Readiness does not prove hardware functionality.

Native index merge uses stable natural-version sort plus one pass; identical versions retain source order. Signed/declared indexes verify before merge. Legacy unsigned indexes without index checksum remain compatible. Builtin-only sources avoid a redundant pipeline.

Manifest format 2 hashes Git-selected source inputs, including branding/CI, excluding generated caches and unrelated output. Public artifact creation no longer alone marks source dirty; actual edited/new source does. [Hardware checklist](hardware-regression-checklist.md) remains a physical release gate.

Core/branding/app archives normalize ordering, ownership and timestamps. Repository manifest records source revision/digest and package versions. Linux x86_64/Python 3.12 runtime uses a complete 36-wheel version/hash lock, including import-tested OpenVINO 2026.4.1 / GenAI 2026.4.1.0. Fresh offline hash-checked installation and full app imports passed. Ubuntu runtime image is pinned by release URL and SHA-256; APT dependencies resolve against the dated `20261002T000000Z` snapshot using Ubuntu's [snapshot service](https://ubuntu.com/server/docs/how-to/software/snapshot-service/). Setup records the installed system/Python dependency lists after validation. `OOONANA_OPENVINO_REFRESH_DEPENDENCIES=1` permits refreshing local resolved constraints within the release's hash lock, not arbitrary latest packages. This pins runtime inputs; it is not a claim of bit-identical rootfs output or successful model inference.

## Installed login and live safety

Installer requires username and nonempty password before any formatting. Installed system removes live passwordless sudo/doas rules, locks root password login, and uses console authentication before desktop startup. Graphical sudo uses a private password prompt; passwords are neither stored nor logged. Live media retains its explicit passwordless administration policy without broad environment preservation. No SSH/telnet listener was added.

Existing systems without an installed-mode marker are not silently converted to password login during package upgrades. Systems already marked installed now use BusyBox init/getty rather than the old root-shell loop. Diskless QEMU authentication test rejected a wrong fixture password and started the desktop launcher as UID 1000 after correct login. Actual nonroot Xorg still requires a newly built image/hardware check. Third-party titlebar buttons passed isolated i3 close/minimize/fullscreen/restore checks; native and dock/window controls remain available.

USB live memory policy still avoids creating swapfiles or modifying unrelated disks. Disk swap operates only on explicitly configured installer/setup targets. Physical Wi-Fi, Bluetooth, audio, fan sensors, memory pressure and OpenVINO inference require hardware checks. No audio playback occurred during this pass.

`tests/test-update-interruption.py` exercises actual CLI transactions in private installation roots: concurrent-writer refusal, TERM rollback, KILL recovery, wrong-root/corrupt-snapshot refusal, failed recovery retry, truncated localhost transfer and successful retry. The QEMU persistence fixture also abruptly stops a real guest upgrade during its health hook, reboots that disposable installation, and restores old payload/custom configuration with the shipped CLI. Host disks and installed WSL packages are not update targets for these fault tests.
