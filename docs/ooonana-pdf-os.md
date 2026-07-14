# Ooonana OS PDF

`docs/ooonana.pdf` is reserved for the bootable Ooonana OS PDF.

Current 0.5 build is based on [ading2210/linuxpdf](https://github.com/ading2210/linuxpdf):

- PDF JavaScript runs TinyEMU.
- TinyEMU boots a RISC-V Linux kernel.
- The PDF exposes a real 80x30 serial terminal plus on-page keyboard controls.
- Boot uses accelerated VM batches and shows live elapsed time before kernel logs.
- Chromium PDF viewer is the main target.
- Injected shell payload carries Ooonana package manager 0.8.4 and current logo/help.
- Boot console prints `OOONANA_PDF_BOOT_OK` after Ooonana init starts.
- Terminal uses bright orange monospaced text on black.
- Kernel log stays visible during boot, then hands off to Ooonana shell.
- Full boot logs and fixed 80x30 terminal geometry keep status readable.

Ooonana cannot embed the current x86_64 QEMU kernel directly. linuxpdf boots
RISC-V, so the PDF path injects the minimal Ooonana shell payload into the
linuxpdf RISC-V rootfs.

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
- Add RISC-V native Ooonana kernel/rootfs instead of linuxpdf's prebuilt root.
- Reduce payload size for faster PDF load.
- Add release artifact upload for `ooonana.pdf`.

Chrome smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1
```

The screenshot output is `docs/ooonana-pdf-chrome-smoke.png`.
