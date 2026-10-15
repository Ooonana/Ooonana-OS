# Boot UI refinement — October 15

Impeccable refinement preserves opaque graphite/amber and the existing mascot.
No ISO was built. A fresh user build is required to include these changes.

## Shipped changes

- GRUB: removed duplicate title, decorative accent rail/dot and nested footer
  backing. Quieter instructions, slightly more menu spacing, rounded backdrop.
  Centered the brand-name line independently of the ASCII mascot's indentation;
  removed the unused 32px icon gutter and aligned heading/menu text baselines.
- Countdown: actual seconds in a small text label. GRUB's built-in progress bar
  has a hardcoded 28px minimum, so setting `height = 4` was not sufficient.
  [Upstream progress-bar renderer](https://github.com/rhboot/grub2/blob/master/grub-core/gfxmenu/gui_progress_bar.c)
  and [label timeout support](https://github.com/rhboot/grub2/blob/master/grub-core/gfxmenu/gui_label.c)
  informed the implementation; real EFI captures confirmed it.
- Live startup: centered mascot and named storage/session stages. Removed the
  arbitrary ten-step filled bar. Small three-position activity pulse runs only
  during the existing one-second media retry waits.
- Shutdown/reboot: the same stage presentation during the existing two-second
  writer grace period, then “Saving changes” while existing cleanup proceeds.
  There is no additional wait, fake completion percentage, sound, daemon,
  hidden cursor or animation background process.
- Serial consoles (`ttyS`, `hvc`, `ttyAMA`), unavailable/small VTs, or kernel
  argument `ooonana.motion=off` use plain messages. The shell environment
  `OOONANA_CONSOLE_MOTION=off` also disables animation.
- Warnings remain below the status; stage transitions do not clear the whole
  console. Final status stops activity before handoff. BusyBox init guards,
  persistence selection, failure-held rescue and unmount ordering are unchanged.
- Persistent storage-file shutdown copies the tiny UI helper, logo and required
  console applets to its RAM root. UI functions retain no file descriptor or
  worker that could pin the writable old root during pivot/unmount.
- Rufus verification accepts the new countdown and earlier/minimal bar themes.

## Verification

- Production GRUB theme/config rendered in disposable EFI/QEMU at **640×480**
  and **1280×800**, main menu and audio submenu. No real kernel or ISO build in
  that fixture. Its capture-only 60-second timer replaces production's five
  seconds; the screenshot number is not the production boot timeout.
- POSIX shell and actual BusyBox shell fixtures: three distinct pulse frames,
  exact existing waits, motion-off, serial variants, invalid/small geometry,
  stage reset, no hidden cursor, no helper traps/background jobs.
- Full live-initramfs assembly and ISO-menu fixtures passed. Persistence
  maintenance tests passed, including repeated rescue-shell exits staying held.
  Storage/UUID and Rufus verification regression fixtures passed too.
- A private Xvfb/xterm PTY rendered boot/shutdown stage layout. This is a console
  UI fixture, **not** proof of physical GPU handoff or an actual power cycle.
- Impeccable detector reported no findings for the GRUB generator.

![Current production GRUB theme in 640×480 EFI fixture](assets/ooonana-grub-refined-20261015.png)

Physical framebuffer handoff, visible shutdown VT switching, power-loss and
reboot timing still need the disposable USB session. No physical drives were
modified and no WSL/host shutdown action was invoked by these tests.

## Reproduce focused checks

```sh
python3 tests/test-console-ui.py
bash tests/test-full-i3-live-initramfs.sh
bash tests/test-full-i3-iso.sh
bash tests/test-rufus-iso-verify.sh
python3 tests/test-persistence-maintenance.py
# Output folders must be new; fixtures own only their private processes/files.
python3 tests/check-grub-ui.py /var/tmp/ooonana-grub-ui-example
OOONANA_GUI_TEST_DISPLAY=1 xvfb-run -a -s '-screen 0 1000x650x24' \
  python3 tests/check-console-ui.py /var/tmp/ooonana-console-ui-example
```
