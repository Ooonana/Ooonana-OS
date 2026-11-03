# WSL /var/tmp cleanup — November 3, 2026

Both distributions were inspected separately. Ubuntu used about22.7GiB in
`/var/tmp`; Ooonana used3.2MiB. Age and temporary-directory placement alone did
not establish that files were disposable.

Removed from Ubuntu:

- 6,787 regenerable kernel object/archive/linker-intermediate files, from a
  completed build with retained source/configuration and final artifacts.
- 14 inactive Firefox QA Mesa shader-cache directories.

Selected allocation:849,342,464 bytes, about810MiB. Linux filesystem free space
increased849,338,368 bytes after sync. Each selected path was verified absent.
Active process/open-file/mount references, resolved paths, filesystem boundaries,
symlinks, hardlinks and file identities were checked before deletion. Owning QA
directories were included in reference checks, not just individual cache paths.

Final kernel, `.config`, `System.map`, release identity and compressed boot image
retain their SHA256 hashes, ownership, permissions and modification times. The
retained boot image matches the tested native VM kernel:
`bc30e38e0ff539ac3b573a03a15c763ee49c072224e2d4620ba2e2be910065a3`.
Kernel source, unstripped image, toolchains, signing material, models, histories,
profiles, test receipts and substantive checkpoints remain.

Ooonana's small `/var/tmp` contains retained sync/checkpoint receipts; no
additional disposable cache was found there. No installed release package was
updated. Existing Windows deletion rejections were not retried.

Private per-file plan and completed receipt:
`C:\Users\7ryan\AppData\Local\Temp\ooonana-vartmp-cleanup-20261103\`.
Ubuntu `/var/tmp` afterwards:22,938,208KiB, about21.9GiB. Online TRIM completed;
its962GiB output describes virtual ranges, not Windows space recovered. C:
still showed about2.55GiB free afterwards. No forced shutdown or VHD compaction
was performed.

This measures space reclaimed inside Linux, not equal immediate Windows VHD
recovery. Runtime VM checks remain pending as requested. Resumed installer
source checks and ShellCheck pass, including the unfinished identity-limit fix.
