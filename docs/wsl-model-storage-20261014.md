# WSL model storage - 2026-10-14

## Verified inventory

Ubuntu's native filesystem contains one testing-only model store:
`/var/tmp/ooonana-hf-cpu-20261011.KKwmcB1u/models/smollm2-360m-qa`.
Store allocation: 218,728 KiB (~214 MiB); primary `openvino_model.bin`:
217,157,840 bytes (~207 MiB). Retained for real CPU inference, streaming/cancel
and engine-recovery QA, not personal production use.

Read-only searches covered native `/root`, `/home`, `/opt`, `/srv`, `/var/lib`,
`/var/tmp` and `/usr/local`: large GGUF/safetensors/ONNX/OpenVINO/PyTorch weights
and extensionless Hugging Face/Ollama/Torch cache blobs. No personal weights
found in that scope. Windows mounts, symlinks and active F-backed build mounts
were excluded. Directory names in pip/kernel sources and transport-state
fixtures do not themselves indicate downloaded weights. No models deleted or
downloaded. Ooonana WSL stays stopped; its native model storage is unverified.

## Locations and policy

- Ubuntu distro stays at `C:\Users\7ryan\AppData\Local\wsl\Ubuntu`.
- Ooonana distro already resides at `F:\Ooonana\WSL\Ooonana`; not moved.
- F-backed scratch `F:\Ooonana\ooonana-os\build-storage\release-stage.ext4`
  is separate build storage, not a WSL distro disk.
- Personal Windows C:/F: model stores remain untouched. Mounted access alone
  does not duplicate weights into a WSL VHD.
- WSL development should reuse existing Linux-compatible models through an
  explicit mounted path, not download/copy production weights into native WSL
  storage. Any native QA model must be small, identifiable and testing-only.
- Python wheels, isolated userspace and retained runtime generations also use
  space but are not model weights; recovery generations are not automatic junk.
  Physical Linux/USB installs may legitimately keep their models in persistent
  Linux storage. Fresh ISO/package manifests declare no bundled models.

Installed WSL migration remains deferred until verified backup and independent
headroom exist. Initial C: free space ~2.49 GiB; virtual guest `df` is not Windows
headroom. During the user's ongoing build, documentation only: no build-input,
signed-repository, mount or process changes. Final release verification pending.
