# Ooonana OS Roadmap

Selected next work from the current build pass:

1. Keep minimal scratch OS bootable and separate from full-i3.
2. Keep full-i3 live/install path bootable on BIOS and UEFI.
3. Skip XFCE/GNOME for now. i3 remains the full edition desktop.
4. Keep package manager Ooonana-native; Alpine APKs are import inputs only.
5. Polish live graphical installer layout.
6. Polish first-boot setup for user, password, network, theme, and cloud repo.
7. Improve full-i3 WSL GUI startup.
8. Improve Ooonana AI native app dashboard.
9. Add better browser/Chrome proof for PDF and web-style artifacts.
10. Keep README and help commands understandable for new users.
11. Keep workspace cleanup scripts strict so disk use stays low.
12. Keep package repo automation release-friendly.
13. Add more first-party packages after repo automation is stable.
14. Move PDF OS toward native RISC-V Ooonana kernel/rootfs.
15. Make `docs/ooonana.pdf` a real bootable Ooonana OS PDF.

Status now:

- Items 1, 2, 4, 10, 11, 12, and 15 are working first passes.
- Items 5, 6, 7, 8, 9, and 14 are active improvement targets.
- Item 15 uses linuxpdf TinyEMU RISC-V today; native RISC-V Ooonana is item 14.
