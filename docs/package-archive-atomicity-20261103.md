# Package archive publication — November 3, 2026

Package builders previously redirected `tar | gzip` into the final archive path.
Rebuilding could change other hardlinked snapshots; producer/compressor failure
could leave a partial archive. The APK importer also deleted an old archive
before fetching its replacement, losing it when the fetch failed.

Shared build helpers now create a temporary file beside the destination, require
the producer pipeline to succeed, set permissions and rename over the output.
Existing archives and other hardlinks remain intact on command failure. Symlink
and nonregular destinations are refused. Existing output permissions or the
creation umask are preserved. Normal tar flags and gzip reproducibility remain.

All ten shell package archive writers use the helper. Native i3/i3lock archive
copies also replace their destinations through a temporary file. The branding
builder propagates failures explicitly from its command-substitution context.
The APK importer retains the previous archive until a successful replacement.
These are host build changes; OpenVINO app/runtime overhaul stays deferred.

This provides per-file replacement under ordinary command failures. It does not
make archive plus metadata a power-loss transaction or make historical snapshots
immutable against arbitrary external writes. Existing verified repository
generation promotion remains the publication boundary.

Regressions cover byte-for-byte reproducibility, hardlinked snapshot retention,
fresh umask/existing permissions, tar/gzip/chmod/rename failures, missing input,
temporary cleanup and symlink/directory refusal. Actual branding rebuild/failure
and failed APK fetch tests retain prior archives and metadata. Package factory,
APK import, i3 package-set and Firefox fixture tests provide integration coverage.
Both CI definitions include the focused archive regression; remote CI stays held.

Fresh local runs pass: atomic archive, APK importer, i3 package-set, package
factory and Firefox fixture suites; warning-level ShellCheck passes all changed
shell builders/helpers and regression scripts. No VM or live device is used.
Private log: `C:\Users\7ryan\AppData\Local\Temp\ooonana-vartmp-cleanup-20261103\archive-regression.log`.

The integration run also found four missing Korean-input packages in the combined
catalog seed: `fcitx5`, `fcitx5-hangul`, `fcitx5-gtk3`, `fcitx5-qt`. They now match
the existing full-i3 profile. The current unpublished711-package stage already
contains these packages; no production generation was changed.
