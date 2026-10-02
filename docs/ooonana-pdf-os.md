# Ooonana OS PDF

`docs/ooonana.pdf` is reserved for the bootable Ooonana OS PDF.

Current 0.6 build is based on [ading2210/linuxpdf](https://github.com/ading2210/linuxpdf):

- PDF JavaScript runs TinyEMU.
- TinyEMU boots a RISC-V Linux kernel.
- The PDF exposes a real 80x30 serial terminal plus on-page keyboard controls.
- Boot uses accelerated VM batches and shows live elapsed time before kernel logs.
- Chromium PDF viewer is the main target.
- Injected shell payload carries Ooonana package manager 0.9.5 and current logo/help.
- Boot console prints `OOONANA_PDF_BOOT_OK` after Ooonana init starts.
- Terminal uses bright orange monospaced text on black.
- Kernel log stays visible during boot, then hands off to Ooonana shell.
- Full boot logs and fixed 80x30 terminal geometry keep status readable.

Ooonana cannot embed the current x86_64 QEMU kernel directly. linuxpdf boots
RISC-V, so the PDF path injects the minimal Ooonana shell payload into the
linuxpdf RISC-V rootfs.

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
- Native RISC-V64 Linux 6.18.37 and static BusyBox 1.37.0 now cross-build with manifests using `scripts/build-native-pdf-runtime.sh`. Native PDF boot has not passed TinyEMU verification; working 32-bit PDF remains release output. Do not treat successful cross-compilation as boot proof.
- Reduce payload size for faster PDF load.
- Add release artifact upload for `ooonana.pdf`.

Native candidate workflow (not release-ready):

```sh
bash scripts/build-native-pdf-runtime.sh --source VERIFIED_LINUX_6_18_37_TREE
bash scripts/build-ooonana-pdf-os.sh --native-runtime BUILT_RUNTIME --out /var/tmp/ooonana-native-candidate.pdf
node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 180000
```

Native configuration includes legacy SBI console, PLIC, virtio/9p, and `no4lvl` for TinyEMU paging compatibility. Current candidate timed out before console output. Kernel/emulator compatibility remains unresolved; original working PDF is never replaced by unverified candidate.

Chrome smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1
```

The screenshot output is `docs/ooonana-pdf-chrome-smoke.png`.
