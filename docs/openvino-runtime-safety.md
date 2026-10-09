# OpenVINO runtime replacement - 2026-10-09

Applies to the Ooonana `openvino setup` wrapper, not Windows standalone setup.
Source/candidate core remains 0.10.0; installed Ooonana WSL/stable remains 0.9.9.
Models, sessions and user configuration outside the runtime stay separate.

## Replacement flow

1. A kernel-released writer lock serializes setup. The inner installer does not
   inherit that lock; concurrent setup refuses rather than modifying the same tree.
2. Updates copy the existing userspace into a private staging directory. APT/pip
   run only against that copy. Fresh/forced setup stages verified pinned userspace.
   Failure or a missing/mismatched readiness fingerprint cannot replace the
   working runtime. Existing runtime custom files survive ordinary copy updates.
3. Validated staged userspace becomes a retained generation under
   `~/.local/share/ooonana-openvino/.runtime-generations/runtime.XXXXXXXX/rootfs`.
   The `rootfs` symlink switches through a same-filesystem atomic rename.
   Completed generations are not automatically deleted or classified as junk.
4. Existing real-directory runtimes need a one-time conversion. A durable journal
   records the new generation before moving the old directory into its `previous`
   checkpoint. Launch refuses while that journal is present. Normal promotion
   failure rolls back; after abrupt termination, the next `openvino setup` restores
   the previous directory before trying another update. Unknown/ambiguous journal
   state refuses and retains both trees for inspection.

Run `openvino setup` after upgrading the app package; restart existing AI sessions
after successful replacement to use the new snapshot. `--force` stages fresh
userspace but still retains the previous runtime. It is not a model/profile reset.

## Space and memory

- Fresh setup requires at least 4 GiB free before download/staging. Updates require
  a full measured copy of the runtime plus 512 MiB reserve. These are safety floors,
  not promises that every future package set fits. Retained generations consume
  disk; no automatic history deletion or unsafe in-place fallback is used.
- WSL virtual filesystem free space does not establish Windows backing-drive
  headroom. Check C:/F: separately before a real setup/backup/release build.
- A low-physical-RAM warning cannot be suppressed by large free swap. Swap is
  reported separately, never described as extra physical RAM. Model-specific
  allocation preflight and JSON/SSE insufficient-memory handling remain separate.

## Evidence and limitations

`tests/test-openvino-setup.py` uses actual files, kernel flock, rename and sync,
with mocked downloads/inner installer. It covers staged failure, readiness refusal,
force checksum failure, retained generations/config/history, concurrent setup,
low-space refusal, low RAM with abundant swap, rename rollback and SIGKILL before
the legacy move, after the move and after pointer installation. Corrupt journals
and unsafe lock/generation symlinks refuse. These fixtures do not install APT/pip.
The full fixture passed on Ubuntu and isolated Alpine 3.24 candidate userspace,
including GNU/BusyBox writer-lock rejection. It uses a private HOME. GitLab smoke
provides `xz`, required by GNU tar for the fresh userspace archive fixture.

Real pinned Linux runtime through the packaged bubblewrap launcher passed with
the generation symlink, UID1000 daemon and read-only model mount: lazy API lifecycle,
strict memory JSON/SSE refusal, cross-invocation daemon survival, owned crash/restart,
stop/state cleanup and bridge FIFO cleanup. Existing cached app required an explicit
current-source QA override in the initial run. A later opt-in run built/installed
current app 0.2.1 offline into a disposable copy-on-write venv, verified pinned dependency
versions and bundled web assets, and passed the same transport gates without that
override. Set `OOONANA_TRANSPORT_INSTALL_APP=1` for the opt-in runner; original
venv stays unchanged. Complete Ubuntu/APT userspace setup, heavyweight
inference/stream/cancel, new-image kernel and physical storage checks remain pending.
Process-kill fault tests are not physical power-loss certification.
