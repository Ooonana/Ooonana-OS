# Hardware regression gate

Run on newly built physical USB, then confirmed installed target. WSL/VM tests
prove software paths only. Keep screenshots/logs private unless sanitized.
Audio backend stays enabled. Automated checks never play sound.

## Read-only evidence

```sh
uname -a
ooonana-health --json
ooonana-service-status
ooonana-memory status
ooonana-persistence status
free -h
lsblk -o NAME,FSTYPE,MOUNTPOINTS,RO
```

- [ ] Record image checksum, core/kernel versions, machine and boot mode.
- [ ] BIOS/UEFI live boot and safe-graphics entry reach desktop.
- [ ] Internal SSD and unrelated USB/SD untouched during live boot.
- [ ] Persistence uses only matching boot USB partition.
- [ ] New/legacy ISO base mismatch refuses saved overlay without clearing data.
- [ ] Clean shutdown logs persistence read-only/cleanup markers; saved data returns.
- [ ] Silent low-space/read-only warning appears; unrelated files never deleted.
- [ ] Offline verified backup and data-only migration preserve previous overlay.
- [ ] Installer dry-run lists chosen target; password login enters UID 1000.
- [ ] Hover never focuses; dock click restores correct app session.
- [ ] Preview/right-click controls work; hidden windows stay minimized until clicked.
- [ ] Overlapping/hidden-tab windows show no controls targeting covered clients.
- [ ] Alt+F4 closes correct window; Alt+F10 enters/exits fullscreen.
- [ ] Panel fits 1280, 1024 and 768 widths; AI and essential controls remain reachable.
- [ ] Wi-Fi reconnect after suspend; enterprise profiles validate expected certificates.
- [ ] Bluetooth controller, pairing, reconnect and suspend tested with real device.
- [ ] Audio readiness checked; audible playback manual, only when explicitly permitted.
- [ ] Available RAM/cgroup limits, actual zram consumption and idle processes recorded.
- [ ] CPU/GPU/SSD temperatures and fans match hardware; unavailable counters labeled.
- [ ] OpenVINO model load/generation tested; record device/model/context/RAM/errors.
- [ ] Minor update preserves custom config; failed health check restores payload.
- [ ] Signing enrollment remains deferred until explicit trust decision; key stays local.

Readiness means endpoint responds, not successful wireless/audio/inference.
No formatting, writable mounts, stress tests or fan-curve changes during diagnostics.
