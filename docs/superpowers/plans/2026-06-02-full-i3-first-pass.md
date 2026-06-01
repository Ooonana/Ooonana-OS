# Full I3 First Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ooonana branding assets, an i3 package-set automation path, and a full-i3 rootfs skeleton so UI work can continue on top.

**Architecture:** Keep minimal Ooonana unchanged as the base. Generate full-i3 package repos from Alpine APK imports plus Ooonana wrapper packages, then build a full-i3 rootfs skeleton that carries branding/config files and can later receive real Xorg/i3 payloads from the cloud repo.

**Tech Stack:** Bash, SVG/PNG assets, ImageMagick `convert`, Ooonana `.pkg`, Alpine APK importer, BusyBox rootfs.

---

### Task 1: Branding Assets

**Files:**
- Create: `tests/test-branding-assets.sh`
- Create: `branding/logo.svg`
- Generate: `branding/logo.png`
- Create: `branding/wallpaper.svg`
- Generate: `branding/wallpaper.png`
- Create: `branding/i3/config`

- [x] Write failing branding asset test.
- [x] Add SVG logo, SVG wallpaper, and i3 config.
- [x] Generate PNGs from SVG with ImageMagick.
- [x] Run branding test and verify pass.

### Task 2: I3 Package Set Automation

**Files:**
- Create: `tests/test-i3-package-set.sh`
- Create: `scripts/import-i3-package-set.sh`
- Modify: `.github/workflows/build-ooonana-packages.yml`

- [x] Write failing test with fake APK repo.
- [x] Add package set importer that calls `scripts/import-apk-package.sh`.
- [x] Add wrapper packages: `i3.pkg`, `branding.pkg`, `full-i3.pkg`.
- [x] Update workflow so `full_i3_profile=true` builds the package set.
- [x] Run package-set test and verify pass.

### Task 3: Full I3 Rootfs Skeleton

**Files:**
- Create: `tests/test-full-i3-rootfs.sh`
- Create: `scripts/build-full-i3-rootfs.sh`

- [x] Write failing rootfs skeleton test.
- [x] Add builder that starts from scratch rootfs, copies branding assets, writes edition marker, start script, and package markers.
- [x] Add tarball output `ooonana-full-i3-rootfs.tar.gz`.
- [x] Run rootfs test and verify pass.

### Task 4: Docs And Cleanup

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-06-02-full-i3-first-pass.md`

- [x] Document branding, package set, and full-i3 rootfs commands.
- [x] Run focused tests.
- [x] Run full shell test suite.
- [x] Remove temporary build artifacts.
- [x] Commit and push.
