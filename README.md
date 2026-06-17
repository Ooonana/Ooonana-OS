# Ooonana OS

```
Ooonana OS
      __________________
     |    __      __    |
     |   /  \    /  \   |
   / |                  |\
  /  |     \______/     | \
     |__________________|
          |        |
```

Lightweight scratch-built Linux for QEMU, WSL, installer experiments, and AI-first terminal work.

## Quick Links

- [Download / Release Files](#download--release-files)
- [What Ooonana Is](#what-ooonana-is)
- [Current Status](#current-status)
- [Install And Test](#install-and-test)
- [Ooonana Command](#ooonana-command)
- [Package Factory](#package-factory)
- [Full I3 Edition](#full-i3-edition)
- [Rufus USB](#rufus-usb)
- [Ooonana AI](#ooonana-ai)
- [Build From Source](#build-from-source)
- [Project Files](#project-files)

## Download / Release Files

Current release artifacts on this machine live in:

```text
F:\Ooonana\ooonana-os\release-current
/mnt/f/Ooonana/ooonana-os/release-current
```

If WSL `/mnt/f` does not show the Windows F: drive, mount it manually:

```bash
sudo mkdir -p /mnt/winf
sudo mount -t drvfs F: /mnt/winf
```

Main full-i3 live/install ISO:

```text
F:\Ooonana\ooonana-os\release-current\ooonana-full-i3.iso
/mnt/f/Ooonana/ooonana-os/release-current/ooonana-full-i3.iso
```

Minimal scratch installer ISO:

```text
/var/tmp/ooonana-os/release/ooonana-scratch.iso
```

Live environment status:

```text
ooonana-full-i3.iso    live desktop by default, persistent live second, installer third
ooonana-scratch.iso    minimal shell plus installer menu
full-i3 live desktop   i3, polybar, rofi, wallpaper, GUI installer launcher
full-i3 install menu   live GUI installer session, VGA-first fallback, safe graphics fallback
rufus usb              ISOHybrid/DD mode, BIOS/UEFI, Secure Boot off
full-i3 VM RAM         2048 MB tested after live rootfs moved outside initramfs
```

Release files:

```text
ooonana-scratch.iso                minimal installer-only GRUB ISO
ooonana-scratch-disk.raw           minimal installed raw disk image
ooonana-rootfs.tar.gz              minimal chroot/container rootfs tarball
ooonana-wsl-rootfs.tar.gz          minimal WSL import rootfs
ooonana-full-i3-rootfs.tar.gz      full-i3 package-installed rootfs tarball
ooonana-full-i3-disk.raw           full-i3 installed raw disk image
ooonana-full-i3.iso                full-i3 live/install ISO, embeds compressed install disk
ooonana-full-i3-wsl-rootfs.tar.gz  full-i3 WSL import rootfs
vmlinuz-ooonana                    Ooonana Linux kernel
SHA256SUMS                         checksums for release artifacts
SHA256SUMS.full-i3                 checksums for full-i3 artifacts
qemu-rootfs-boot.log               direct rootfs QEMU boot proof
qemu-scratch-ext4-boot.log         minimal ext4 disk QEMU boot proof
qemu-installer.log                 installer ISO QEMU proof
qemu-iso-fallback-shell.log        installer failure shell proof
qemu-installed-boot.log            installed disk QEMU proof
qemu-full-i3-gui-smoke.log         full-i3 Xorg/i3 serial proof
qemu-full-i3-live.log              full-i3 live ISO boot proof
qemu-full-i3-live-iso.log          full-i3 live ISO boot proof
qemu-full-i3-uefi-installer.log    full-i3 UEFI installer proof
qemu-full-i3-installer-vmware.log  full-i3 VMware-style installer proof
qemu-full-i3-installed-sata.log    full-i3 VMware-style installed boot proof
qemu-full-i3-vnc.log               full-i3 VNC boot proof
qemu-full-i3-vnc.png               full-i3 VNC screenshot proof
```

Verify files:

```bash
cd /mnt/f/Ooonana/ooonana-os/release-current
sha256sum -c SHA256SUMS
sha256sum -c SHA256SUMS.full-i3
```

## What Ooonana Is

Ooonana OS is a small scratch-built Linux project. Target system is not Debian or Alpine. Debian/Ubuntu packages are only host build tools used from WSL while Ooonana grows its own userspace and package manager.

Core pieces:

- Linux kernel
- BusyBox-style minimal userspace
- Custom `ooonana` package manager
- GRUB boot disk and installer ISO
- WSL rootfs export
- QEMU verification flow
- Optional AI CLI with provider routing

## Current Status

Working now:

- Scratch rootfs boots in QEMU
- GRUB raw disk boots in QEMU
- Installer ISO writes Ooonana to blank disk
- Installer ISO opens a fallback shell on install failure or cancel
- Installer has a serial-safe xterm UI with logo, disk picker, user/password, hostname, theme, cloud repo picker, progress, logs, fail shell, and reboot prompt
- Live/install ISO keeps interactive prompts on the VGA console for VMware while smoke tests log through serial
- GRUB uses a stable orange-on-black text menu with Ooonana logo text, BIOS/UEFI hybrid support, live/install/safe graphics menus, and a persistent USB boot entry. Full-i3 does not force `gfxmode` or `gfxpayload=keep`, so VMware keeps its normal display size.
- Rufus support has a DD-mode note inside the ISO, USB-friendly volume labels, and `scripts/verify-rufus-iso.sh`
- Full-i3 live starts eudev before Xorg and ships libinput config for PS/2 keyboard and mouse discovery
- Full-i3 now ships an Ooonana i3 baseline: polybar-first bar, rofi launcher, picom shadows/fades, dunst notifications, Chromium launcher, Nemo launcher, Wi-Fi/Bluetooth/settings helpers, wallpaper changer, and dark Ooonana colors
- Installed disk boots in QEMU
- `ooonana-install` can partition a raw/whole disk, install to an existing root partition, mount optional home/swap/EFI partitions, format or keep selected filesystems, copy rootfs, install kernel, write GRUB, and persist user, hostname, and theme
- Generic `ooonana-rootfs.tar.gz` can be unpacked for chroot/container-style use
- Minimal and full-i3 WSL distro exports can be imported
- `ooonana` package manager has repo add/remove/doctor, repo index, checksums, install/add, remove/uninstall, purge, upgrade, fix, check, files, verify
- Minimal and full rootfs include Ooonana shell helpers: `bunana`, `clear`, installer-based `oonana` brickout game, and Ooonana neofetch logo fallback
- `ooonana update` can sync local repos, HTTP repos, and GitHub Release repo tarballs into cache
- Alpine `.apk` packages can be imported into Ooonana `.pkg` repos
- Full-i3 branding assets, package profiles, input drivers, package-installed rootfs, boot disk, live/install ISO, GUI installer wizard, AI desktop launcher, and real QEMU boot proof exist as a separate edition path
- First-boot setup can create a user, prompt for password, write basic network config, and add a cloud package repo
- `ooonana-ai` supports NVIDIA NIM, Google Gemini, tools, tasks, audit, shell fallback for scratch WSL, and a full-i3 GUI app with home/actions/ask/provider-model/log panels

Next work:

- Better graphical installer layout inside live desktop
- Full ISO export/install polish for VMware and other hypervisors
- More first-party packages
- Service manager, login defaults, security hardening
- Native RISC-V Ooonana rootfs for the PDF OS path

Detailed numbered roadmap:

```text
docs/ooonana-roadmap.md
```

## Install And Test

Run QEMU installer from repo root:

```bash
truncate -s 512M /var/tmp/ooonana-os/install-target.raw
bash scripts/run-qemu.sh \
  --install \
  --iso /var/tmp/ooonana-os/release/ooonana-scratch.iso \
  --disk /var/tmp/ooonana-os/install-target.raw \
  --smoke
bash scripts/run-qemu.sh \
  --disk-boot \
  --image /var/tmp/ooonana-os/install-target.raw \
  --smoke
```

Boot release disk directly:

```bash
bash scripts/run-qemu.sh \
  --disk-boot \
  --image /var/tmp/ooonana-os/release/ooonana-scratch-disk.raw \
  --smoke
```

Use the generic rootfs tarball:

```bash
mkdir -p /tmp/ooonana-rootfs
sudo tar -xzf /var/tmp/ooonana-os/release/ooonana-rootfs.tar.gz -C /tmp/ooonana-rootfs
sudo mount -t proc proc /tmp/ooonana-rootfs/proc
sudo mount --rbind /sys /tmp/ooonana-rootfs/sys
sudo mount --rbind /dev /tmp/ooonana-rootfs/dev
sudo chroot /tmp/ooonana-rootfs /bin/sh
```

Import minimal WSL rootfs, optional:

```bash
bash scripts/install-wsl-distro.sh --distro OoonanaMinimal --force \
  --tarball /var/tmp/ooonana-os/release/ooonana-wsl-rootfs.tar.gz
wsl.exe -d OoonanaMinimal -- /usr/bin/ooonana me
wsl.exe -d OoonanaMinimal -- /usr/bin/ooonana ai tools
```

Import full-i3 WSL rootfs as `Ooonana`, recommended:

```bash
bash scripts/install-wsl-distro.sh --distro Ooonana --force \
  --tarball /var/tmp/ooonana-os/release/ooonana-full-i3-wsl-rootfs.tar.gz
wsl.exe -d Ooonana -- /usr/bin/ooonana me
wsl.exe -d Ooonana -- /usr/bin/start-ooonana-i3
```

Full-i3 WSL GUI launch needs WSLg or an X server with `DISPLAY` set.

## Ooonana Command

```bash
ooonana me
ooonana setup
ooonana setup --first-boot --gui
ooonana setup --user ryan --password --network dhcp --cloud-repo https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz --done
ooonana version
ooonana wsl status
ooonana update
ooonana sources
ooonana list
ooonana list --installed
ooonana list --upgradeable
ooonana search gui
ooonana info ai
ooonana depends gui
ooonana get gui --dry-run
ooonana install ai
ooonana files ai
ooonana verify ai
ooonana check ai
ooonana upgrade --dry-run
ooonana remove ai
ooonana uninstall ai
ooonana purge ai
ooonana fix ai --reinstall
ooonana repo add cloud https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz
ooonana repo doctor
ooonana repo remove cloud
ooonana clean --dry-run
ooonana clean
ooonana repo index /usr/lib/ooonana/repo
```

Small terminal commands:

```bash
bunana                 # exit login shell function
bunana --shutdown      # power off
bunana --restart       # reboot
clear                  # clear terminal
oonana                 # Ooonana brickout game, two-o command
neofetch               # Ooonana logo fallback
```

`oonana` starts the terminal brickout game from the installer game engine. Bricks spell `OOONANA OS`, the ball is the Ooonana logo sprite, supported terminals use ANSI cursor-home redraw, and repeated hits build combo scoring. The game uses multiple colors for bricks, HUD, paddle, and ball when color is available. Controls are `a/d`, left/right arrows, and `q` quit.

Install package flow:

```bash
ooonana update                 # sync builtin and cloud repo indexes
ooonana search nano            # find package
ooonana show nano              # inspect metadata, deps, archive
ooonana get nano --dry-run     # preview install
ooonana get nano               # install package and deps
ooonana files nano             # list owned files
ooonana verify nano            # check owned files still exist
ooonana check nano             # verify one package
ooonana check                  # verify every installed package
ooonana upgrade nano           # upgrade one package
ooonana upgrade                # upgrade all installed packages
ooonana remove nano            # remove files and installed marker
ooonana uninstall nano         # remove alias
ooonana purge nano             # remove files, marker, and Ooonana config dirs
ooonana fix nano --reinstall   # resync repo and reinstall package
ooonana repo add cloud URL     # add repo source
ooonana repo doctor            # check configured repos
ooonana repo remove cloud      # remove repo source
ooonana clean                  # remove cached repo indexes and tarball extracts
```

Help is split by task so new users do not have to read one huge page:

```bash
ooonana help packages
ooonana help get
ooonana help upgrade
ooonana help remove
ooonana help repo
ooonana help ai
ooonana help ui
```

`ooonana get` installs from Ooonana repos only. To bring an Alpine package into Ooonana, build or publish an Ooonana repo first with `ooonana repo build` or `scripts/build-package-repo.sh`.

Package metadata lives inside Ooonana:

```text
/usr/lib/ooonana/repo/*.pkg
/usr/lib/ooonana/repo/index.tsv
/usr/lib/ooonana/repo/SHA256SUMS
/etc/ooonana/sources.d/*.repo
/var/lib/ooonana/packages/installed
/var/cache/ooonana/index.tsv
/var/cache/ooonana/repos/NAME
```

Release tarball repo source example:

```sh
cat >/etc/ooonana/sources.d/cloud.repo <<'EOF'
OOONANA_REPO_NAME="cloud"
OOONANA_REPO_URI="https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz"
EOF

ooonana update
ooonana get nano
```

Private GitHub release repos need a token while the repo stays private:

```bash
OOONANA_REPO_TOKEN="$(gh auth token)" ooonana update
```

Direct HTTP directory repos also work when the URL contains `index.tsv`,
`SHA256SUMS`, `*.pkg`, and `archives/` as normal files.

## Package Factory

Build an Ooonana repo from Alpine packages:

```bash
bash scripts/build-package-repo.sh \
  --out-dir /tmp/ooonana-repo \
  --package-profile configs/packages/ooonana-cloud.list \
  --cloud-url https://github.com/YOUR/YOUR_REPO/releases/download/packages-latest/ooonana-package-repo.tar.gz \
  --clean
```

Default cloud package profile:

```text
configs/packages/ooonana-cloud.list
```

The default seed now includes `python3` so AI and repo tooling can run once the cloud repo is published.

This creates:

```text
/tmp/ooonana-repo/nano.pkg
/tmp/ooonana-repo/archives/*.tar.gz
/tmp/ooonana-repo/index.tsv
/tmp/ooonana-repo/SHA256SUMS
/tmp/ooonana-repo/SHA256SUMS.sig
/tmp/ooonana-repo/cloud.repo
```

`scripts/import-apk-package.sh` is the low-level APK importer. `scripts/build-package-repo.sh` is the normal repo builder. It loads a profile, adds extra package names, imports dependencies, writes indexes and checksums, and can write cloud repo hints.

Signed repos:

```bash
bash scripts/build-package-repo.sh \
  --out-dir /tmp/ooonana-repo \
  --package-profile configs/packages/ooonana-cloud.list \
  --sign-key /root/ooonana-repo.key \
  --public-key /root/ooonana-repo.pub \
  --clean

ooonana repo add cloud https://example.test/ooonana-repo /etc/ooonana/trusted-keys/cloud.pem
OOONANA_REQUIRE_SIGNED_REPOS=1 ooonana update
```

CLI dry run:

```bash
OOONANA_SOURCE_ROOT="$PWD" ooonana repo build --dry-run nano
```

The GitHub Actions workflow `Build Ooonana Packages` can run the same importer in cloud from a package profile, upload the generated repo as artifacts, publish `ooonana-package-repo.tar.gz` to GitHub Releases, and optionally deploy the repo to GitHub Pages. Release tarball repos are the default cloud path because free/private GitHub Pages can be blocked by account plan. Pages still works as a direct HTTP repo when enabled.
The generated repo includes `cloud.repo` and `README.txt` so the repo source can be copied straight into `/etc/ooonana/sources.d/cloud.repo`.

Cloud build defaults are repo-wide seed packages, not nano-only:

```text
package_profile=configs/packages/ooonana-cloud.list
packages="" for optional extras
```

Use `packages` for quick extras or change `package_profile` to another `.list` file. The builder imports requested packages plus dependencies; it does not mirror all Alpine packages. `ooonana get PACKAGE` installs from configured Ooonana repos. It does not live-fetch Alpine APKs on the target OS.

Older seed profile:

```text
configs/packages/ooonana-repo.list
```

## Full I3 Edition

Minimal and full are separate.

```text
minimal   ooonana-scratch.iso, ooonana-rootfs.tar.gz, ooonana-wsl-rootfs.tar.gz
full-i3   ooonana-full-i3.iso, ooonana-full-i3-disk.raw, ooonana-full-i3-rootfs.tar.gz, ooonana-full-i3-wsl-rootfs.tar.gz
```

The full-i3 path adds branding, i3 config, X input drivers, package automation, live desktop, GUI installer tools, Ooonana AI app launcher, and a package-installed rootfs. It does not replace the minimal release.
The full-i3 ISO boots live i3 by default. The GRUB menu includes normal live, persistent live, installer, and safe graphics installer entries. From the live desktop, launch `ooonana-gui-installer` to install through the graphical wizard.
The full-i3 ISO stages the installed raw disk as `images/ooonana-full-i3-disk.raw.gz` and streams it through `gzip -dc` during install. This keeps Rufus/DD USB behavior while avoiding a second uncompressed 6GB image inside the ISO.

Default full-i3 apps and tools:

```text
chromium, nemo, python3, py3-pip, alacritty
polybar, rofi, yad, picom, dunst, feh
networkmanager, network-manager-applet, blueman
bluez, wpa_supplicant, wireless-regdb, linux-firmware
linux-firmware-i915, linux-firmware-amdgpu, linux-firmware-brcm
linux-firmware-rtlwifi, sof-firmware, mesa-dri-gallium
mesa-va-gallium, mesa-vulkan-intel, alsa-utils
geany, maim, mpd, mpc, ncmpcpp, ranger, htop, vim
arandr, xrandr, pavucontrol, brightnessctl
parted, e2fsprogs, dosfstools, util-linux
```

Ooonana also ships `hsetroot` and `xsettingsd` fallback commands because Alpine v3.20 does not publish those packages in the enabled main/community repos.

Build full-i3 package repo locally:

```bash
bash scripts/import-i3-package-set.sh \
  --out-dir /var/tmp/ooonana-os/build/full-i3-repo
```

Build full-i3 rootfs:

```bash
bash scripts/build-scratch-rootfs.sh --force
bash scripts/build-full-i3-rootfs.sh \
  --repo /var/tmp/ooonana-os/build/full-i3-repo \
  --force
```

Output:

```text
/var/tmp/ooonana-os/build/full-i3-rootfs
/var/tmp/ooonana-os/build/ooonana-full-i3-rootfs.tar.gz
```

Build full-i3 disk and live/install ISO:

```bash
bash scripts/build-full-i3-disk.sh \
  --rootfs /var/tmp/ooonana-os/build/full-i3-rootfs \
  --disk-image /var/tmp/ooonana-os/build/ooonana-full-i3-disk.raw \
  --size 6144M \
  --force
bash scripts/build-full-i3-live-initramfs.sh \
  --rootfs /var/tmp/ooonana-os/build/full-i3-rootfs \
  --initramfs /var/tmp/ooonana-os/build/ooonana-full-i3-live-initramfs.cpio.gz \
  --force
bash scripts/build-full-i3-iso.sh \
  --disk-image /var/tmp/ooonana-os/build/ooonana-full-i3-disk.raw \
  --live-initramfs /var/tmp/ooonana-os/build/ooonana-full-i3-live-initramfs.cpio.gz \
  --iso /var/tmp/ooonana-os/build/ooonana-full-i3.iso \
  --force
```

UEFI support:

```bash
bash scripts/install-wsl-deps.sh
bash scripts/build-full-i3-iso.sh --uefi --force
bash scripts/verify-vmware-uefi-input.sh
bash scripts/verify-rufus-iso.sh
```

`grub-mkrescue` builds BIOS boot support always. When `grub-efi-amd64-bin` provides `/usr/lib/grub/x86_64-efi` and `mtools` provides `mformat`, the ISO becomes hybrid BIOS/UEFI. `ovmf` is only needed for local UEFI QEMU proof.

Headless GUI-capable QEMU smoke path:

```bash
bash scripts/build-full-i3-disk.sh --smoke --gui-smoke --force
bash scripts/build-full-i3-live-initramfs.sh --force
bash scripts/build-full-i3-iso.sh --smoke --live-smoke \
  --iso /var/tmp/ooonana-os/build/ooonana-full-i3-live-smoke.iso \
  --force
bash scripts/run-qemu.sh \
  --disk-boot \
  --image /var/tmp/ooonana-os/build/ooonana-full-i3-disk.raw \
  --smoke \
  --vnc :7
bash scripts/run-qemu.sh \
  --iso /var/tmp/ooonana-os/build/ooonana-full-i3-live-smoke.iso \
  --smoke
```

Current full-i3 release proof files:

```text
/var/tmp/ooonana-os/release/SHA256SUMS.full-i3
/var/tmp/ooonana-os/release/qemu-full-i3-live.log
/var/tmp/ooonana-os/release/qemu-full-i3-live-iso.log
/var/tmp/ooonana-os/release/qemu-full-i3-persistent-smoke.log
/var/tmp/ooonana-os/release/qemu-full-i3-uefi-installer.log
/var/tmp/ooonana-os/release/qemu-full-i3-installer-vmware.log
/var/tmp/ooonana-os/release/qemu-full-i3-installed-sata.log
/var/tmp/ooonana-os/release/qemu-full-i3-gui-smoke.log
/var/tmp/ooonana-os/release/qemu-full-i3-installer.log
/var/tmp/ooonana-os/release/qemu-full-i3-installed-boot.log
/var/tmp/ooonana-os/release/qemu-full-i3-vnc.log
/var/tmp/ooonana-os/release/qemu-full-i3-vnc.png
```

Inside full-i3, the GUI installer launcher is:

```bash
ooonana-installer-gui
ooonana-gui-installer
ooonana-install-wizard
```

`ooonana-installer-gui` uses `yad` windows for install mode, target/root partition, optional `/home`, swap, EFI, format/keep toggles, user/password, hostname, theme, cloud repo, and source root. It shows the exact `ooonana-install --dry-run` preview before install, writes logs, and offers a fallback shell if install fails.

Inside full-i3, the GUI package manager launcher is:

```bash
ooonana-packages-app
```

`ooonana-packages-app` uses `yad` for update, search, install, remove, upgrade, source listing, and repo doctor. It falls back to terminal package help when GUI pieces are missing.

The terminal wizard still exists as fallback. It opens in a themed xterm under i3, walks disk picker, user/password, hostname, theme, cloud repo picker, source root, confirmation, install progress, and reboot prompt steps, logs to `/var/log/ooonana-install-wizard.log`, and blocks installing over the current root disk unless `OOONANA_INSTALL_ALLOW_ROOT_TARGET=1` is set. If install fails, it prints `OOONANA_INSTALL_WIZARD_FAIL` and drops to a fallback shell.

Custom partition backend example:

```bash
sudo ooonana-install \
  --target /dev/sda2 \
  --home-part /dev/sda3 \
  --swap-part /dev/sda4 \
  --efi-part /dev/sda1 \
  --keep-root \
  --keep-home \
  --keep-efi \
  --bootloader none \
  --source / \
  --user ryan \
  --hostname ooonana-lab \
  --theme dark \
  --yes
```

Default full-i3 UI is dark: black background, orange text/cursor, Ooonana polybar/rofi/picom/dunst config, and a new black/orange Ooonana wallpaper. `Mod+d` opens a patched Ooonana rofi launcher with orange selection, Ooonana labels, icon rows, and matching black/orange mode tabs. The old sunset look is light mode:

```bash
ooonana help ui
ooonana-theme-env toggle
OOONANA_THEME=light ooonana-gui-installer
OOONANA_THEME=light ooonana setup --first-boot --gui
```

The installer persists the chosen theme in `/etc/ooonana/theme`; i3 reads it through `ooonana-theme-env` on boot. Inside i3, `Mod+Shift+T` toggles dark/light, `Mod+Shift+A` opens the Ooonana AI app through `ooonana-ai-launch`, `Mod+Shift+S` opens settings through `ooonana-settings-launch`, `Mod+Shift+O` opens the package manager app, and `Mod+Shift+I` opens the installer.
Extra i3 keys:

```text
Mod+Shift+F  Nemo file manager
Mod+Shift+W  Chromium browser
Mod+N        Network settings
Mod+B        Bluetooth settings
Mod+Shift+S  Display/audio settings
Mod+Shift+O  Package manager app
Mod+Shift+P  Wallpaper changer
Print        Screenshot
Mod+Shift+G  Geany/Vim editor
Mod+Shift+M  MPD music client
Mod+Shift+X  htop process monitor
Mod+Shift+U  ranger file manager
```

`ooonana-settings` opens a GUI settings menu when `yad` is available. It can switch theme, choose wallpaper, open display/audio/Wi-Fi/Bluetooth tools, open package manager, launch Ooonana AI, open Chromium/Nemo/terminal, set brightness, take screenshots, open editor/music/process/file-manager helpers, write the cloud repo source, and show Ooonana info. It falls back to the terminal help path when GUI pieces are missing.

Persistent live USB:

```text
GRUB entry: Ooonana OS Full i3 Live (persistent USB)
Kernel arg: ooonana.persistence=1
Persistence label: OOONANA_PERSIST
```

For Rufus/native USB, flash the ISO normally, then add an ext4 persistence partition labeled `OOONANA_PERSIST`. Ooonana bind-mounts `/home`, `/etc/ooonana`, `/var/lib/ooonana`, and `/var/cache/ooonana` from that partition.

## Rufus USB

Use the full-i3 ISO:

```text
F:\Ooonana\ooonana-os\release-current\ooonana-full-i3.iso
/mnt/f/Ooonana/ooonana-os/release-current/ooonana-full-i3.iso
```

Rufus settings:

```text
Image mode: Write in DD Image mode
Secure Boot: off
Target system: BIOS or UEFI
```

If Rufus shows `ISOHybrid image detected`, choose `Write in DD Image mode`.
The ISO includes `RUFUS.md` at the USB root with the same notes.

Installed-system boot matrix helper:

```bash
bash scripts/verify-installed-boot-matrix.sh --disk /path/to/ooonana-installed.raw --iso /path/to/ooonana-full-i3.iso --dry-run
```

Secure Boot is optional and requires user-owned MOK keys. Prepare signed assets with:

```bash
bash scripts/build-secure-boot-assets.sh \
  --efi-dir /boot/efi \
  --kernel /boot/vmlinuz \
  --key /root/MOK.key \
  --cert /root/MOK.crt \
  --out-dir /tmp/ooonana-secure-boot \
  --dry-run
```

Verify before uploading or flashing:

```bash
bash scripts/verify-rufus-iso.sh \
  --iso /mnt/f/Ooonana/ooonana-os/release-current/ooonana-full-i3.iso
```

Expected marker:

```text
OOONANA_RUFUS_ISO_OK
```

More:

```text
docs/rufus-usb.md
```

VMware note:

```text
No EFI environment detected
```

This line is harmless only for legacy BIOS boot. Hybrid BIOS/UEFI ISO support needs `grub-efi-amd64-bin` installed before `grub-mkrescue`. Current full-i3 GRUB uses console text output with orange colors, the Ooonana logo, and serial fallback; it does not set `gfxmode` or keep a graphics payload, because that can resize VMware displays. Full-i3 live now uses a tiny initramfs plus `/images/ooonana-full-i3-live-rootfs.ext4`, so the desktop rootfs is no longer unpacked into RAM. QEMU BIOS and UEFI live smoke both pass at 2048 MB, and the kernel fragment enables EFI/simple framebuffer plus USB HID/storage for native/Rufus boot. If you see `Initramfs unpacking failed: write error` or `libxcb.so.1` errors, you are booting an old ISO. If live boot reaches `Run /init` and then looks stuck, rebuild with the latest console fix; interactive init mounts `/proc` before choosing `tty1`, and smoke logs use `ttyS0` directly. If persistent live drops to shell with `mkdir: not found`, rebuild the full-i3 rootfs/ISO; package install can overwrite early boot applet links, and the current builder restores BusyBox links for `/bin/mkdir`, `/bin/cat`, `/bin/sleep`, and other init-critical commands. If i3 starts but input is dead, rebuild the full-i3 package repo/rootfs; the profile now includes eudev and starts it before Xorg. The full-i3 panel includes Wi-Fi, Bluetooth, network, audio, brightness, battery, date, and tray items. The full-i3 installer auto-detects `/dev/vd*`, `/dev/sd*`, `/dev/xvd*`, and `/dev/nvme*` targets, then installed GRUB boots by `PARTUUID` instead of hardcoding `/dev/vda1`. If install fails or is cancelled outside smoke mode, the ISO opens a BusyBox shell instead of rebooting. The release ISO should not include `ooonana.smoke=1`; smoke ISOs are only for automated QEMU proof and reboot after markers.

Non-interactive installed-disk proof path:

```bash
truncate -s 900M /var/tmp/ooonana-os/build/ooonana-installer-created.raw
sudo packages/ooonana/usr/sbin/ooonana-install \
  --target /var/tmp/ooonana-os/build/ooonana-installer-created.raw \
  --source /var/tmp/ooonana-os/build/full-i3-rootfs \
  --kernel /var/tmp/ooonana-os/release/vmlinuz-ooonana \
  --hostname ooonana-lab \
  --user ryan \
  --theme light \
  --smoke \
  --gui-smoke \
  --yes
bash scripts/run-qemu.sh \
  --disk-boot \
  --image /var/tmp/ooonana-os/build/ooonana-installer-created.raw \
  --smoke \
  --vnc :8
```

First-boot setup launches from the full-i3 session through xterm when possible:

```bash
ooonana setup --first-boot --gui
```

It can create a user, prompt for a password, write `/etc/network/interfaces`, write `/etc/ooonana/theme`, and add `/etc/ooonana/sources.d/cloud.repo` so `ooonana update` can use a published cloud package repo. In full-i3 it opens a `yad` setup form first, then falls back to themed xterm when GUI pieces are missing.

Cloud package build:

```text
GitHub Actions -> Build Ooonana Packages -> full_i3_profile=true
```

The package workflow now defaults to the full-i3 profile, publishes `ooonana-package-repo.tar.gz` to the `packages-latest` GitHub Release, and writes repo hints for:

```text
https://github.com/Ooonana/Ooonana-OS/releases/download/packages-latest/ooonana-package-repo.tar.gz
```

Inside Ooonana OS:

```sh
ooonana update
ooonana upgrade
```

When `full_i3_profile=true`, the cloud build uses:

```text
configs/packages/full-i3.list
```

The full-i3 profile includes desktop basics plus common hardware support: NetworkManager, Bluetooth, Wi-Fi regulatory data, selected Linux firmware families, SOF audio firmware, Mesa DRI/VA, Intel Vulkan, and ALSA tools.

After the generated repo tarball is published to GitHub Releases and added to `/etc/ooonana/sources.d/cloud.repo`, this path is intended to work:

```bash
ooonana update
ooonana get full-i3
start-ooonana-i3
```

## Ooonana AI

Ooonana AI is CLI-first. It can run as `ooonana ai ...` or direct `ooonana-ai ...`.

```bash
ooonana-ai-app
ooonana ai setup
ooonana ai doctor
ooonana ai status
ooonana ai provider
ooonana ai provider set gemini
ooonana ai models
ooonana ai model
ooonana ai agents
ooonana ai tools
ooonana ai tool processes
ooonana ai tool desktop
ooonana ai task add "inspect system"
ooonana ai tasks
ooonana ai audit
ooonana ai ask "what system am I in?"
ooonana-ai --model code "write a shell script"
ooonana-ai chat
```

Full-i3 includes an Ooonana AI app launcher:

```text
/usr/bin/ooonana-ai-app
/usr/bin/ooonana-ai-launch
/usr/share/applications/ooonana-ai.desktop
i3 shortcut: Mod+Shift+a
```

The launcher opens a `yad` GUI dashboard when the full desktop is available,
then falls back to the native terminal dashboard. The GUI has home, action,
ask, provider/model, and log flows. It can show status, tools registry, task
board, audit/history, desktop context, and env output in Ooonana dialogs.
Chat, setup, and shell still use a themed terminal. For terminal-only launch:

```bash
OOONANA_AI_APP_NO_X=1 ooonana-ai-app
OOONANA_AI_APP_NO_X=1 OOONANA_AI_APP_COMMAND=tools ooonana-ai-app
```

Config:

```text
~/.config/ooonana/ai.env
docs/ooonana-ai.env.example
```

Minimal WSL does not include `python3` yet. `provider`, `status`, and `tools` still work through shell fallback. Full-i3 WSL carries the full package-installed rootfs, GUI scripts, wallpaper, and current `ooonana-ai` desktop context tool; full chat and live provider calls still need `python3` present in that package set.

More:

```text
docs/ooonana-ai.md
docs/jarvis-agi-research.md
```

## Build From Source

Install host tools in WSL:

```bash
bash scripts/install-wsl-deps.sh
```

Build kernel:

```bash
bash scripts/fetch-kernel-source.sh --force
bash scripts/build-kernel.sh \
  --config-fragment configs/kernel/ooonana-minimal-x86_64.fragment \
  --force
```

Build scratch rootfs, WSL tarball, disk, and installer ISO:

```bash
bash scripts/build-scratch-rootfs.sh --force
bash scripts/build-scratch-initramfs.sh --force
bash scripts/build-rootfs-tarball.sh --force
bash scripts/build-wsl-rootfs.sh --force
bash scripts/build-scratch-disk.sh --smoke --force
bash scripts/build-scratch-grub-iso.sh \
  --install \
  --disk-image /var/tmp/ooonana-os/build/ooonana-scratch-disk.raw \
  --iso /var/tmp/ooonana-os/build/ooonana-scratch.iso \
  --force
```

Build full-i3 WSL tarball:

```bash
bash scripts/build-wsl-rootfs.sh \
  --edition full-i3 \
  --rootfs /var/tmp/ooonana-os/build/full-i3-rootfs \
  --tarball /var/tmp/ooonana-os/build/ooonana-full-i3-wsl-rootfs.tar.gz \
  --force
```

Build output:

```text
/var/tmp/ooonana-os/build
```

Clean generated build files:

```bash
bash scripts/clean-build-artifacts.sh --yes
```

Keep kernel source/cache while cleaning images:

```bash
bash scripts/clean-build-artifacts.sh --keep-source --yes
```

## Verification

Fast tests:

```bash
bash tests/test-ooonana-pkg.sh
bash tests/test-ooonana-ai.sh
bash tests/test-scratch-rootfs.sh
bash tests/test-installer.sh
```

QEMU proof markers:

```text
OOONANA_CLI_OK
OOONANA_BOOT_OK
OOONANA_INSTALL_OK
```

## Project Files

Top-level files:

```text
README.md                         project homepage
.gitignore                        generated artifact ignores
.gitattributes                    repo text/binary rules
AGENTS.md                         local Codex instruction file
```

Kernel and package config:

```text
configs/kernel/ooonana-minimal-x86_64.fragment
configs/packages/core.list
configs/packages/ooonana-repo.list
configs/packages/ooonana-cloud.list
configs/packages/full-i3.list
```

Ooonana package:

```text
packages/ooonana/usr/bin/ooonana
packages/ooonana/usr/bin/oonana
packages/ooonana/usr/bin/bunana
packages/ooonana/usr/bin/clear
packages/ooonana/usr/bin/neofetch
packages/ooonana/usr/bin/ooonana-ai
packages/ooonana/usr/bin/ooonana-ai-app
packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py
packages/ooonana/usr/lib/ooonana/repo/*.pkg
packages/ooonana/usr/lib/ooonana/repo/index.tsv
packages/ooonana/usr/lib/ooonana/repo/SHA256SUMS
packages/ooonana/usr/sbin/ooonana-install
packages/ooonana/etc/neofetch/config.conf
packages/ooonana/usr/share/ooonana/logo.txt
```

Build scripts:

```text
scripts/install-wsl-deps.sh
scripts/fetch-kernel-source.sh
scripts/build-kernel.sh
scripts/build-scratch-rootfs.sh
scripts/build-scratch-initramfs.sh
scripts/build-rootfs-tarball.sh
scripts/build-wsl-rootfs.sh
scripts/build-scratch-disk.sh
scripts/build-scratch-grub-iso.sh
scripts/install-wsl-distro.sh
scripts/run-qemu.sh
scripts/clean-build-artifacts.sh
scripts/import-apk-package.sh
scripts/import-i3-package-set.sh
scripts/build-full-i3-rootfs.sh
scripts/build-full-i3-live-initramfs.sh
scripts/build-full-i3-disk.sh
scripts/build-full-i3-iso.sh
scripts/verify-rufus-iso.sh
scripts/generate-ooonana-pdf.py
scripts/build-ooonana-pdf-os.sh
scripts/inject-ooonana-pdf-root.sh
scripts/test-ooonana-pdf-chrome.ps1
scripts/lib/common.sh
```

Tests:

```text
tests/test-ooonana-pkg.sh
tests/test-ooonana-ai.sh
tests/test-import-apk-package.sh
tests/test-package-factory.sh
tests/test-i3-package-set.sh
tests/test-branding-assets.sh
tests/test-full-i3-rootfs.sh
tests/test-full-i3-live-initramfs.sh
tests/test-full-i3-disk.sh
tests/test-full-i3-iso.sh
tests/test-rufus-iso-verify.sh
tests/test-gui-installer.sh
tests/test-qemu-gui.sh
tests/test-logo-sync.sh
tests/test-ooonana-pdf.sh
tests/test-ooonana-pdf-os.sh
tests/test-ooonana-pdf-chrome-smoke.sh
tests/test-rootfs-tarball.sh
tests/test-scratch-rootfs.sh
tests/test-scratch-initramfs.sh
tests/test-scratch-disk.sh
tests/test-scratch-grub-iso.sh
tests/test-wsl-distro.sh
tests/test-rootfs-qemu.sh
tests/test-iso.sh
tests/test-installer.sh
tests/smoke-cli.sh
```

Docs:

```text
docs/logo.txt
docs/ooonana.pdf                bootable Ooonana OS PDF target
docs/ooonana-guide.pdf          docs-only field guide PDF
docs/ooonana-pdf-os.md
docs/ooonana-roadmap.md
docs/rufus-usb.md
docs/ooonana-ai.md
docs/superpowers/plans/2026-06-11-installer-gui-settings-ai.md
docs/ooonana-ai.env.example
docs/jarvis-agi-research.md
docs/superpowers/plans/2026-05-21-rootfs-qemu.md
```
