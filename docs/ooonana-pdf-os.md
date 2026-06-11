# Ooonana OS PDF

`docs/ooonana.pdf` is reserved for the bootable Ooonana OS PDF.

The target is based on [ading2210/linuxpdf](https://github.com/ading2210/linuxpdf):

- PDF JavaScript runs TinyEMU.
- TinyEMU boots a RISC-V Linux kernel.
- The PDF exposes a simple framebuffer plus on-page keyboard controls.
- Boot is slow, often 30-60 seconds.
- Chromium PDF viewer is the main target.

Ooonana cannot embed the current x86_64 QEMU kernel directly. linuxpdf boots
RISC-V, so the PDF path injects the minimal Ooonana shell payload into the
linuxpdf RISC-V rootfs.

Build:

```bash
bash scripts/build-ooonana-pdf-os.sh --force
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

## TODO

- Build and verify `docs/ooonana.pdf` in Chromium. First Chrome smoke proof
  loads the OoonanaPDF UI and reaches the RISC-V kernel boot path.
- Add RISC-V native Ooonana kernel/rootfs instead of linuxpdf's prebuilt root.
- Add an Ooonana boot marker in the PDF console.
- Reduce payload size for faster PDF load.
- Add release artifact upload for `ooonana.pdf`.

Chrome smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1
```

The screenshot output is `docs/ooonana-pdf-chrome-smoke.png`.
