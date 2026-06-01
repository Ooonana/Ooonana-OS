# Rootfs Tarball And Logo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sync the Ooonana ASCII logo across boot/install surfaces and publish a chroot-ready rootfs tarball like Alpine/Debian rootfs downloads.

**Architecture:** Keep the scratch rootfs as the source of truth. Add a generic tarball exporter separate from WSL export, and verify it with tar content tests. Copy the README logo into installed logo files so the boot splash, MOTD, and installer splash stay aligned.

**Tech Stack:** Bash, BusyBox rootfs, tar/gzip, QEMU test scripts.

---

### Task 1: Logo Sync

**Files:**
- Modify: `docs/logo.txt`
- Modify: `packages/ooonana/usr/share/ooonana/logo.txt`
- Modify: `scripts/build-scratch-rootfs.sh`
- Test: `tests/test-logo-sync.sh`
- Test: `tests/test-scratch-rootfs.sh`

- [x] Write failing logo sync test.
- [x] Update logo files from README.
- [x] Install logo into `/etc/motd` and `/etc/issue`.
- [x] Verify scratch rootfs includes matching logo files.

### Task 2: Generic Rootfs Tarball

**Files:**
- Create: `scripts/build-rootfs-tarball.sh`
- Test: `tests/test-rootfs-tarball.sh`
- Modify: `README.md`

- [x] Write failing rootfs tarball test.
- [x] Add exporter with `--rootfs`, `--tarball`, `--force`, and deterministic tar options.
- [x] Exclude pseudo-filesystem contents while preserving mount directories.
- [x] Document `/var/tmp/ooonana-os/release/ooonana-rootfs.tar.gz`.

### Task 3: Verification And Release Refresh

**Files:**
- Release output: `/var/tmp/ooonana-os/release/ooonana-rootfs.tar.gz`
- Release output: `/var/tmp/ooonana-os/release/SHA256SUMS`

- [x] Run focused tests.
- [x] Rebuild scratch rootfs and generic rootfs tarball.
- [x] Copy tarball to release and update checksums.
- [x] Clean build artifacts.
