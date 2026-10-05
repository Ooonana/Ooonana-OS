# Ooonana OS PDF

`docs/ooonana.pdf` is reserved for the bootable Ooonana OS PDF.

Current 0.6 build is based on [ading2210/linuxpdf](https://github.com/ading2210/linuxpdf):

- PDF JavaScript runs TinyEMU.
- TinyEMU boots a RISC-V Linux kernel.
- The PDF exposes a real 80x30 serial terminal plus on-page keyboard controls.
- Boot uses accelerated VM batches and shows live elapsed time before kernel logs.
- Chromium PDF viewer is the main target.
- Native RISC-V64 Linux 6.18.37 / static BusyBox 1.37.0 rootfs carries Ooonana package manager 0.9.8 and current logo/help.
- Boot console prints `OOONANA_PDF_BOOT_OK` after Ooonana init starts.
- Opaque graphite cards, orange monospaced terminal, rounded keyboard controls and a blank command input with Run / Enter; redundant input hints removed.
- Kernel log stays visible during boot, then hands off to Ooonana shell.
- Full boot logs and fixed 80x30 terminal geometry keep status readable.

Ooonana cannot embed the x86_64 QEMU kernel directly. The current main PDF
uses its separately built native RISC-V64 kernel/rootfs. The builder also
retains the upstream 32-bit runtime as a fallback when no native runtime is supplied.

The PDF remains a minimal RISC-V terminal edition, not the x86_64 i3 desktop.
Native GTK panels, cursor theme, and OpenVINO models are not supported inside
the PDF emulator. `docs/ooonana-lite.pdf` remains the older 0.5 lite build until
separately rebuilt.

Native build (preferred):

```bash
bash scripts/build-native-pdf-runtime.sh --source VERIFIED_LINUX_6_18_37_TREE
# Use the fresh runtime path printed by the previous command:
bash scripts/build-ooonana-pdf-os.sh --native-runtime BUILT_RUNTIME --out docs/ooonana.pdf
node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 240000
```

For payload-only changes, reuse verified binaries without rebuilding Linux/BusyBox:

```bash
bash scripts/build-native-pdf-runtime.sh --reuse-runtime EXISTING_VERIFIED_RUNTIME
# Embed the newly printed runtime, not the original:
bash scripts/build-ooonana-pdf-os.sh --native-runtime NEW_RUNTIME --out docs/ooonana.pdf
```

Reuse verifies manifest-covered kernel/config/BusyBox hashes, architecture/version
and standalone/nofork options, then creates a fresh applet-only root and injects
current PDF files. It never copies prior desktop/custom data or edits the original.
The default work directory stays outside Git at `/var/tmp/ooonana-os`; set
`OOONANA_PDF_WORK_DIR` for a different emulator build location. Omitting
`--native-runtime` selects the older upstream RISC-V32 fallback, not the native build.

Docs-only guide:

```bash
python3 scripts/generate-ooonana-pdf.py
```

That writes `docs/ooonana-guide.pdf`.

## Status

- Native Linux/BusyBox build manifests, JavaScript VM boot/input/version/package-sync tests and static form/render checks are included. Chromium interaction remains manual/pending; automation availability is not proof of viewer behavior.
- PDF payload carries only portable CLI/comparator/help/logo, base metadata, source configs and public trust keys. Desktop GTK/Python/icons/wallpapers/installer/WSL extras and unsupported AI/dev/GUI bundles are excluded. Base indexes/checksums are rebuilt consistently; real package checksum/signature verification is unchanged.
- Real CLI backend, help and repository inputs are copied by explicit names into bounded tmpfs, avoiding repeated 9p reads/enumeration. Dirty terminal rows paint at most 20 Hz with cached widget references; VM batches have a 12 ms deadline and 32-call cap. Loader diagnostics no longer update invisible form fields.
- All 116 canonical widgets were reopened with matching values/appearances/actions; the final static layout was inspected. PDF size fell about 7%; payload root about 35%.
- Add release artifact upload for `ooonana.pdf`.

Runtime checks:

```sh
OOONANA_PDF_BOOT_ONLY=1 node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 90000
node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 240000
OOONANA_PDF_BENCHMARK=1 node scripts/test-ooonana-pdf-vm.js /var/tmp/ooonana-os/linuxpdf/linuxpdf/out/compiled.js 240000
```

October 5 host Node VM measurements (not browser timings):

| Command | Before | Minimal runtime |
| --- | ---: | ---: |
| `ooonana` | 35.9 s / 968 terminal writes | 2.4 s / 11 writes |
| `ooonana help packages` | 51.8 s | 3.0 s |
| `ooonana version` | 2.3 s | 2.3 s |
| `ooonana list` | exceeded 240 s | 63.4 s |
| `ooonana update` | prior native boot/input/sync suite passed | 51.1 s command |

Final rebuilt boot/input/arithmetic/version/package-sync suite passed in 98 seconds.
Actual package sync passes, but package operations still cost much more than simple
help/version. Browser field IPC and machine speed can change latency; measure the
user's Chromium viewer separately before claiming the two-minute issue resolved.

Native configuration includes legacy SBI console, PLIC, virtio/9p, 100 Hz tick and ISA fallback. Runtime uses `hvc1` when available for keyboard input. Slow RV64 JavaScript otherwise starves CPU progress with timer interrupts, so only the Emscripten RV64 emulator clock is scaled down 16x. Guest wall clock is therefore slower than real time; native host TinyEMU and RV32 are unchanged. Init injection unlinks the BusyBox init symlink before replacing it, preserving the BusyBox executable.

Native runtime resolves SHMEM/tmpfs and sysctl dependencies. Temporary mounts use bounded RAM-backed tmpfs; BusyBox standalone/nofork avoids repeated applet ELF loading. `--reuse-runtime` verifies the existing binary manifest rather than rebuilding kernels for PDF-only changes; `--reuse-kernel` retains its separate fragment/config guard and can reject a cache when Kconfig selected an option differently. Matching emulator sources are not rewritten merely to trigger rebuilds. Static PDF form/render checks are separate from runtime execution. Local PDF browser navigation was blocked by browser security policy; no alternate browser/proxy workaround was used. Chromium interactive verification remains manual/pending.

Chrome smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1
```

The screenshot output is `docs/ooonana-pdf-chrome-smoke.png`.
