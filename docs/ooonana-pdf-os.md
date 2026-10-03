# Ooonana OS PDF

`docs/ooonana.pdf` is reserved for the bootable Ooonana OS PDF.

Current 0.6 build is based on [ading2210/linuxpdf](https://github.com/ading2210/linuxpdf):

- PDF JavaScript runs TinyEMU.
- TinyEMU boots a RISC-V Linux kernel.
- The PDF exposes a real 80x30 serial terminal plus on-page keyboard controls.
- Boot uses accelerated VM batches and shows live elapsed time before kernel logs.
- Chromium PDF viewer is the main target.
- Native RISC-V64 Linux 6.18.37 / static BusyBox 1.37.0 rootfs carries Ooonana package manager 0.9.7 and current logo/help.
- Boot console prints `OOONANA_PDF_BOOT_OK` after Ooonana init starts.
- Terminal uses bright orange monospaced text on black.
- Kernel log stays visible during boot, then hands off to Ooonana shell.
- Full boot logs and fixed 80x30 terminal geometry keep status readable.

Ooonana cannot embed the x86_64 QEMU kernel directly. The current main PDF
uses its separately built native RISC-V64 kernel/rootfs. The builder also
retains the upstream 32-bit runtime as a fallback when no native runtime is supplied.

The PDF remains a minimal RISC-V terminal edition, not the x86_64 i3 desktop.
Native GTK panels, cursor theme, and OpenVINO models are not supported inside
the PDF emulator. `docs/ooonana-lite.pdf` remains the older 0.5 lite build until
separately rebuilt.

Build:

```bash
bash scripts/build-ooonana-pdf-os.sh --force
node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js
```

Keep the work dir outside the repo:

```bash
OOONANA_PDF_WORK_DIR=/var/tmp/ooonana-os/linuxpdf bash scripts/build-ooonana-pdf-os.sh --force
```

Docs-only guide:

```bash
python3 scripts/generate-ooonana-pdf.py
```

That writes `docs/ooonana-guide.pdf`.

## Status

- Build and Chromium smoke verification are automated by included scripts.
- Native RISC-V64 Linux 6.18.37 and static BusyBox 1.37.0 cross-build with manifests using `scripts/build-native-pdf-runtime.sh`. Main `docs/ooonana.pdf` now uses this runtime. Host TinyEMU and JavaScript VM checks passed boot; JavaScript checks also passed keyboard input, arithmetic and core version. Full package-sync check timed out and remains pending. PDF-viewer behavior still requires a fresh Chromium check.
- Reduce payload size for faster PDF load.
- Add release artifact upload for `ooonana.pdf`.

Native build workflow:

```sh
bash scripts/build-native-pdf-runtime.sh --source VERIFIED_LINUX_6_18_37_TREE
bash scripts/build-ooonana-pdf-os.sh --native-runtime BUILT_RUNTIME --out docs/ooonana.pdf
OOONANA_PDF_BOOT_ONLY=1 node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 90000
# Full package-sync check (still timing out; boot/input/version are separate):
node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 300000
```

Native configuration includes legacy SBI console, PLIC, virtio/9p, 100 Hz tick and ISA fallback. Runtime uses `hvc1` when available for keyboard input. Slow RV64 JavaScript otherwise starves CPU progress with timer interrupts, so only the Emscripten RV64 emulator clock is scaled down 16x. Guest wall clock is therefore slower than real time; native host TinyEMU and RV32 are unchanged. Init injection unlinks the BusyBox init symlink before replacing it, preserving the BusyBox executable.

Core 0.9.7 native runtime resolves SHMEM/tmpfs and sysctl dependencies. Temporary mounts use bounded RAM-backed tmpfs; BusyBox standalone/nofork avoids repeated applet ELF loading. Cached kernel reuse validates resolved options; matching emulator sources are not rewritten merely to trigger rebuilds. Static PDF form/render checks are separate from runtime execution. Local PDF browser navigation was blocked by browser security policy; no alternate browser/proxy workaround was used. Chromium interactive verification remains manual/pending.

Chrome smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1
```

The screenshot output is `docs/ooonana-pdf-chrome-smoke.png`.
