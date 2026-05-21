# Rootfs QEMU Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a WSL-first Debian rootfs pipeline and QEMU smoke boot for Ooonana OS.

**Architecture:** Shell scripts drive a small, testable pipeline. Shared helpers parse package profiles, choose a WSL-native build directory, and enforce Linux dependency checks. QEMU boots an ext4 image created directly from the rootfs directory.

**Tech Stack:** Bash, debootstrap, apt, mkfs.ext4, QEMU, systemd.

---

### Task 1: Red Tests

**Files:**
- Create: `tests/test-rootfs-qemu.sh`
- Create: `tests/smoke-cli.sh`

- [x] **Step 1: Write failing rootfs/QEMU script tests**

Create `tests/test-rootfs-qemu.sh` with package parsing, help output, and QEMU dry-run assertions.

- [x] **Step 2: Write failing CLI smoke test**

Create `tests/smoke-cli.sh` expecting `packages/ooonana/usr/bin/ooonana` to run `version`, `doctor`, and AI guard paths.

- [ ] **Step 3: Run tests to verify failure**

Run: `wsl.exe bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash tests/test-rootfs-qemu.sh'`

Expected: fails because `scripts/lib/common.sh` does not exist.

### Task 2: Script Implementation

**Files:**
- Create: `scripts/lib/common.sh`
- Create: `scripts/install-wsl-deps.sh`
- Create: `scripts/build-rootfs.sh`
- Create: `scripts/run-qemu.sh`
- Create: `configs/packages/core.list`
- Create: `.gitignore`

- [ ] **Step 1: Add shared helpers**

Implement logging, dependency checks, root re-exec helpers, and package-profile filtering.

- [ ] **Step 2: Add WSL dependency installer**

Install `debootstrap`, `qemu-system-x86`, `qemu-utils`, `e2fsprogs`, `rsync`, `ca-certificates`, and `xz-utils`.

- [ ] **Step 3: Add rootfs builder**

Use `debootstrap --variant=minbase`, chroot apt install, configure hostname, serial getty, smoke boot service, Ooonana CLI, and ext4 image.

- [ ] **Step 4: Add QEMU runner**

Find kernel/initrd under rootfs, boot ext4 through virtio, support `--smoke` and `--dry-run`.

- [ ] **Step 5: Run tests to verify pass**

Run: `wsl.exe bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash tests/test-rootfs-qemu.sh && bash tests/smoke-cli.sh'`

Expected: both pass.

### Task 3: Real WSL Build And Boot

**Files:**
- Build output defaults to `/var/tmp/ooonana-os/build`

- [ ] **Step 1: Install missing WSL deps as root**

Run: `wsl.exe -u root bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash scripts/install-wsl-deps.sh'`

- [ ] **Step 2: Build rootfs**

Run: `wsl.exe -u root bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash scripts/build-rootfs.sh'`

- [ ] **Step 3: Smoke boot QEMU**

Run: `wsl.exe bash -lc 'cd "/mnt/c/Users/7ryan/OneDrive/문서/Ooonana OS" && bash scripts/run-qemu.sh --smoke'`

Expected: QEMU log contains `OOONANA_BOOT_OK`.
