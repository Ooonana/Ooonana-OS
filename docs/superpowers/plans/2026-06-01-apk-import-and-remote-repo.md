# APK Import And Remote Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate Ooonana package creation from Alpine `.apk` packages and let minimal Ooonana install Ooonana packages from a cloud-hosted repo.

**Architecture:** Add an importer that reads an Alpine `APKINDEX.tar.gz`, downloads package archives, converts metadata into Ooonana `.pkg` files, stores payloads under `archives/`, and regenerates `index.tsv` plus `SHA256SUMS`. Extend `ooonana update/get` so HTTP repo sources are cached locally before install, keeping install logic first-party and checksum-verified.

**Tech Stack:** Bash, tar/gzip, curl/wget, SHA256, GitHub Actions, GitHub Releases.

---

### Task 1: Importer Tests

**Files:**
- Create: `tests/test-import-apk-package.sh`
- Create: `tests/test-fixtures/apk-repo/`

- [x] Write a test that builds a fake Alpine repo with `APKINDEX.tar.gz`, `nano-1.0-r0.apk`, and `libncurses-1.0-r0.apk`.
- [x] Assert `scripts/import-apk-package.sh --repo-url file://... --out-dir ... nano` creates `nano.pkg`, dependency metadata, `archives/nano-1.0-r0.tar.gz`, `index.tsv`, and `SHA256SUMS`.
- [x] Run test and verify failure because importer does not exist.

### Task 2: Importer Script

**Files:**
- Create: `scripts/import-apk-package.sh`

- [x] Implement repo fetching for `file://`, local paths, `http://`, and `https://`.
- [x] Parse `APKINDEX.tar.gz` package records: `P`, `V`, `A`, `S`, `D`, `o`.
- [x] Download selected package and runtime dependencies.
- [x] Convert each `.apk` to deterministic Ooonana payload archive under `archives/`.
- [x] Write `.pkg` metadata with Ooonana id, version, kind, summary, deps, archive, sha256, components, notes.
- [x] Run `ooonana repo index` on output repo.
- [x] Run importer test and verify pass.

### Task 3: Remote Repo Tests

**Files:**
- Modify: `tests/test-ooonana-pkg.sh`

- [x] Add test source file under temp `sources.d/cloud.repo` with `OOONANA_REPO_URI="http://127.0.0.1:PORT/repo"`.
- [x] Serve the generated fake repo with `python3 -m http.server`.
- [x] Assert `ooonana update` downloads cloud `index.tsv` and `SHA256SUMS` into cache.
- [x] Assert `ooonana get nano --dry-run` finds the remote package.
- [x] Assert `ooonana get nano` downloads metadata/archive, installs files, writes manifest, and `ooonana verify nano` passes.
- [x] Run test and verify failure because HTTP repo support is rejected.

### Task 4: Remote Repo Support

**Files:**
- Modify: `packages/ooonana/usr/bin/ooonana`
- Modify: `scripts/build-scratch-rootfs.sh`

- [x] Keep builtin and local file repos working unchanged.
- [x] Add downloader helper using `curl -fsSL` or `wget -q -O`.
- [x] Make `ooonana update` cache remote indexes in `$CACHE_DIR/repos/<name>/`.
- [x] Make `load_pkg` fetch remote `.pkg` and archives into cache before validation/install.
- [x] Add BusyBox `wget` symlink to minimal rootfs.
- [x] Run package manager tests and verify pass.

### Task 5: Package Factory Workflow

**Files:**
- Create: `.github/workflows/build-ooonana-packages.yml`
- Modify: `README.md`

- [x] Add manual GitHub Actions workflow with package input, Alpine branch/arch input, and release tag input.
- [x] Workflow runs importer, uploads repo files as artifacts, and publishes them to a GitHub Release.
- [x] Document commands for importing `nano` locally and in cloud.
- [x] Run YAML/text smoke checks.

### Task 6: Final Verification

**Files:**
- All modified files

- [x] Run focused package tests.
- [x] Run full shell test suite.
- [x] Run `git diff --check`.
- [x] Clean temporary package build artifacts.
- [x] Commit and push.
