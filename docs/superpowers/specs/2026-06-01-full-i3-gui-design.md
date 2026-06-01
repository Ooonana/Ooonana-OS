# Full I3 GUI Design

## Current Truth

`ooonana get` and `ooonana install` already exist and call the same package install path.

They can install Ooonana packages from:

- builtin repo: `/usr/lib/ooonana/repo`
- local repo sources: `/etc/ooonana/sources.d/*.repo`

They support package metadata, dependencies, archives, checksums, install hooks, dry runs, upgrades, removals, file manifests, and verify.

They do not install Debian, Alpine, Arch, or random third-party packages directly. Remote HTTP repos are rejected today. Current `gui.pkg` is only metadata; it does not install a real window manager.

## Decision

Ooonana package manager stays first-party by default.

`ooonana get i3` will mean:

```text
install the Ooonana package named i3 from the Ooonana repo
```

It will not mean:

```text
call apt install i3
call apk add i3
download random internet package named i3
```

Third-party software can still ship inside Ooonana packages, but Ooonana owns the package metadata, checksums, install hooks, and file manifest.

## OS Editions

Minimal edition:

- current scratch Linux
- BusyBox userspace
- Ooonana package manager
- serial/text installer
- QEMU-tested

Full i3 edition:

- minimal base
- graphics stack
- i3 desktop
- Ooonana branding
- graphical installer
- QEMU GUI smoke path

Release artifact names:

```text
ooonana-scratch.iso
ooonana-rootfs.tar.gz
ooonana-full-i3.iso
ooonana-full-i3-rootfs.tar.gz
```

## Full I3 Stack

First full GUI target:

- Xorg
- i3
- i3status
- dmenu
- feh
- xterm first, Alacritty later
- pcmanfm later
- no display manager in first pass

First boot behavior:

- boot to root shell if GUI fails
- start X/i3 from a controlled init script
- print `OOONANA_FULL_I3_OK` when desktop init reaches expected state

LightDM waits until the base GUI works. It adds PAM/session complexity too early.

## Branding

New files:

```text
branding/logo.svg
branding/logo.png
branding/wallpaper.svg
branding/wallpaper.png
branding/i3/config
```

Logo must match the current ASCII face.

Wallpaper:

- dark readable background
- Ooonana logo visible
- not busy
- works at 1920x1080

The i3 config will set wallpaper with `feh`.

## Package Plan

Add Ooonana packages:

```text
i3.pkg
full-i3.pkg
branding.pkg
```

`branding.pkg` owns wallpapers, logo files, and i3 config.

`i3.pkg` owns the i3 package metadata and install hook.

`full-i3.pkg` depends on:

```text
base branding i3
```

`ooonana get i3 --dry-run` must show what would install.

`ooonana get full-i3 --dry-run` must show branding and i3 dependencies.

Real binary payloads can be added in stages. Metadata and installer flow come first, then the GUI rootfs builder gains the actual Xorg/i3 files.

## Graphical Installer

Keep the current serial installer as fallback.

Add a GUI installer after the i3 desktop boots:

- logo header
- target disk list
- erase confirmation
- progress output
- reboot button

The GUI installer calls the same install logic as the text installer. No separate disk-writing path.

## Testing

Add tests for:

- branding files exist
- SVG contains Ooonana logo shape/text
- PNG files are valid PNG
- i3 config references wallpaper
- repo index includes `i3`, `branding`, and `full-i3`
- `ooonana get i3 --dry-run`
- `ooonana get full-i3 --dry-run`
- full rootfs builder creates `ooonana-full-i3-rootfs.tar.gz`
- full ISO builder creates `ooonana-full-i3.iso`

QEMU GUI smoke can start headless first and only assert boot markers. Screenshot/VNC verification comes after the GUI stack is stable.

## Next Implementation Step

First implementation pass:

1. Add branding assets.
2. Add i3 package metadata.
3. Add full-i3 package metadata.
4. Add package manager tests proving `ooonana get i3` path.
5. Add full-i3 rootfs skeleton builder.

