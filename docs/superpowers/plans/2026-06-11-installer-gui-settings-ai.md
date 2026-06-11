# Ooonana GUI Installer, Settings, And AI App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real GUI entrypoints for installer, settings, and Ooonana AI while giving the installer usable custom partition choices.

**Architecture:** Keep the installer backend in `packages/ooonana/usr/sbin/ooonana-install` and add partition options there. Generate full-i3 GUI helper scripts from `scripts/build-full-i3-rootfs.sh`, using `yad` when available and falling back to xterm/terminal flows.

**Tech Stack:** POSIX shell, Bash installer backend, `yad` GTK dialogs, xterm fallback, existing i3 desktop helpers and shell tests.

---

### Task 1: Backend Partition Options

**Files:**
- Modify: `packages/ooonana/usr/sbin/ooonana-install`
- Test: `tests/test-installer.sh`

- [ ] Add installer options `--home-part`, `--swap-part`, `--efi-part`, `--keep-root`, `--keep-home`, `--keep-swap`, and `--keep-efi`.
- [ ] For partition installs, format/mount the root partition by default; mount optional home and EFI partitions; initialize optional swap; write matching `/etc/fstab` lines.
- [ ] Keep dry-run output explicit so the GUI can preview commands before destructive action.

### Task 2: GUI Installer App

**Files:**
- Modify: `scripts/build-full-i3-rootfs.sh`
- Test: `tests/test-full-i3-rootfs.sh`
- Test: `tests/test-gui-installer.sh`

- [ ] Add `/usr/bin/ooonana-installer-gui`, a `yad` form with erase-disk and custom-existing-partitions modes.
- [ ] Show a dry-run preview, ask for confirmation, then run `ooonana-install` with logs.
- [ ] Make `/usr/bin/ooonana-gui-installer` prefer the GUI when `DISPLAY` and `yad` exist; keep xterm wizard fallback.

### Task 3: GUI Settings App

**Files:**
- Modify: `scripts/build-full-i3-rootfs.sh`
- Test: `tests/test-full-i3-rootfs.sh`

- [ ] Upgrade `/usr/bin/ooonana-settings` into a `yad` menu for theme, wallpaper, display, audio, Wi-Fi, Bluetooth, repo, and about.
- [ ] Add `/usr/share/applications/ooonana-settings.desktop`.
- [ ] Keep terminal fallback when `yad` or `DISPLAY` is missing.

### Task 4: GUI Ooonana AI App

**Files:**
- Modify: `packages/ooonana/usr/bin/ooonana-ai-app`
- Test: `tests/test-ooonana-ai.sh`

- [ ] Add `yad` dashboard mode with quick actions for chat, ask, tools, tasks, sessions, setup, desktop, audit, history, provider, model, env, and shell.
- [ ] Keep native terminal dashboard fallback.

### Task 5: Package Profile And Docs

**Files:**
- Modify: `configs/packages/full-i3.list`
- Modify: `README.md`
- Test: `tests/test-package-factory.sh`

- [ ] Add `yad` to the full-i3 package profile.
- [ ] Document custom partition GUI, settings GUI, and AI GUI.

### Task 6: Verification

**Files:**
- Test: all `tests/*.sh`

- [ ] Run `bash -n` on modified scripts.
- [ ] Run focused tests.
- [ ] Run full `for t in tests/*.sh; do bash "$t"; done`.
