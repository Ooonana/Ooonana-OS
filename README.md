# Ooonana OS

AI-built Linux experiment.

## WSL Rootfs Boot

```bash
bash scripts/install-wsl-deps.sh
bash scripts/build-rootfs.sh
bash scripts/run-qemu.sh --smoke
bash scripts/build-iso.sh --smoke
bash scripts/run-qemu.sh --iso /var/tmp/ooonana-os/build/ooonana.iso --smoke
truncate -s 4G /var/tmp/ooonana-os/build/install.ext4
bash scripts/build-iso.sh --install --force
bash scripts/run-qemu.sh --install --iso /var/tmp/ooonana-os/build/ooonana.iso --disk /var/tmp/ooonana-os/build/install.ext4 --smoke
bash scripts/run-qemu.sh
```

Windows root command:

```powershell
wsl.exe -u root bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash scripts/build-rootfs.sh'
```

Build output:

```text
/var/tmp/ooonana-os/build/rootfs
/var/tmp/ooonana-os/build/ooonana-rootfs.ext4
/var/tmp/ooonana-os/build/ooonana.iso
```
