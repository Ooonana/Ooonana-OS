# Backend update policy - core 0.9.5

## Verified behavior

- Repository generations contain archives, package metadata, hashed index, hooks and build manifest. Validation happens before `CURRENT` changes. Old generations remain available locally and in the append-only R2 publisher.
- HTTP metadata and release-tarball caches use verified generation snapshots. Package downloads stay bound to the selected snapshot. Untrusted keys are not automatically learned from remote `repo.pub`.
- Changed or previously untracked package-owned `/etc` files survive upgrades. New defaults are written beside them as `.ooonana-new`. `/etc/os-release` intentionally follows the new release.
- Install and health-check hooks run before transaction completion. Failed upgrade checks restore old package files, metadata, config baselines and custom configuration. Hooks changing files outside package ownership cannot be automatically undone.
- Successful core/kernel updates keep private recovery checkpoints under `/var/lib/ooonana/packages/backups`; `OOONANA_KEEP_UPDATE_BACKUPS=all` retains other package checkpoints too. Checkpoints are recovery files, not an automatic disk-image restore system.
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

Core/branding/app archives normalize ordering, ownership and timestamps. Repository manifest records source revision/digest and package versions. Linux runtime constraints pin import-tested OpenVINO 2026.4.1 / GenAI 2026.4.1.0, tokenizers, NumPy and psutil. Setup records complete resolved dependency versions after import validation and reuses that lock on refresh. `OOONANA_OPENVINO_REFRESH_DEPENDENCIES=1` explicitly refreshes the resolved dependency set within release constraints. System apt packages and all first-install auxiliary Python dependencies are not yet a fully hermetic lock. Import validation does not prove model inference.

## Installed login and live safety

Installer requires username and nonempty password before any formatting. Installed system removes live passwordless sudo/doas rules, locks root password login, and uses console authentication before desktop startup. Graphical sudo uses a private password prompt; passwords are neither stored nor logged. Live media retains its explicit passwordless administration policy without broad environment preservation. No SSH/telnet listener was added.

Existing installed systems are not silently converted to the new login policy during package upgrades. Installed nonroot Xorg/login still requires boot verification on a newly built image. Third-party titlebar buttons remain separate window-manager work; dock/window action menus provide current controls.

USB live memory policy still avoids creating swapfiles or modifying unrelated disks. Disk swap operates only on explicitly configured installer/setup targets. Physical Wi-Fi, Bluetooth, audio, fan sensors, memory pressure and OpenVINO inference require hardware checks. No audio playback occurred during this pass.
