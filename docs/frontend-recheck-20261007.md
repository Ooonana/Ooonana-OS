# Frontend recheck - 2026-10-07

Targeted source/installed-WSL verification, not hardware certification. No audio playback, user-model changes, production ISO build or private-key enrollment.

| Requested area | Verified | Still requires verification |
| --- | --- | --- |
| Desktop | Updated browser icon, existing cursor/icon/theme regressions; native controls reduced | Physical wallpaper/cursor appearance and complete theme consistency |
| Panel | 1280-pixel long-label render captured; existing status sanitization/compact-layout regressions | Clean small-screen render matrix, teardown timeout, actual music/notification placement across displays |
| Dock | 640/1024/1280 isolated previews; hover preserves focus; other-window grouping/actions fixed | Interactive multiple real sessions and minimized-session previews across displays |
| Third-party apps | Real Geany/Nemo/Chromium frames and close/minimize/fullscreen/restore/movement; GTK CSD dialog not duplicated | Qt/OpenVINO, real file-picker workflows, GPU browser rendering |
| Window manager | Native/foreign actions, move tracking, hidden/fullscreen/occluded target predicates, click focus | Human drag/resize feel, full tiled/tabbed/workspace interaction matrix |
| Displays | 640x600 native layouts fit, virtual dock widths tested | Mixed DPI, multiple monitors and physical hotplug |
| Native apps | Settings reversible reflow, launcher filtering/arrows, existing notification/preferences/failure regressions | Notification actions and package failures in a complete fresh desktop session |
| AI | Fixture chat streaming/cancel, code copy/history, elapsed loading/RAM/storage warnings; narrow sidebar toggle | Real Linux model loading, memory pressure and live API restart recovery |
| Task Manager | Live samples, process filter/sort, cancel confirmation and SIGTERM of its own disposable child | Physical GPU/fan/network accuracy, long-running responsiveness |
| Input/accessibility | Unicode GTK Backspace, clipboard, launcher arrows; button tooltips/accessible names | Korean IME engine, keyboard-only complete journey, scaling/screen-reader audit |
| Session | Guarded WSL package sync and matching installed-source hashes; existing native login regression | Interactive WSLg stability, lock/logout and physical suspend/resume |

## Frame fix

Small independent popup windows had rectangular backgrounds. They now use X11 paint/input shapes covering only circular opaque buttons. Gaps reveal the titlebar instead of hiding it or intercepting dragging. Compositor excludes the controls from additional corner clipping. Rounded client frames use blended edges with orange focused title text, not an orange rectangular perimeter.

The actual real-client test uses a dedicated Xephyr display, temporary profiles, source i3 config and extracted packaged picom policy. Chromium uses software rendering for this frame check. Geany/Nemo retain stock application widgets. Controls work with and without the compositor. The fixture's close/terminate actions target only its own clients; it refuses an existing window manager.

![Current source Chromium rounded frame and circular controls](assets/ooonana-third-party-rounded.png)

## Evidence and limitations

- Windows QA captures: `F:\Ooonana\ooonana-os\qa-frontend-20261007-full`.
- Actual private-profile rounded captures: `C:\Users\7ryan\AppData\Local\Temp\ooonana-wsl-gui-a74f0f747b6e486ba38bc485277bc10f\{geany,nemo,chromium}-rounded.png`, matching JSON/logs beside them.
- Isolated GUI/runtime regressions are not proof that physical USB, GPU drivers, IME or WSLg have no bugs. Earlier WSLg session crashed in Weston/libwinpr; update check reported latest engine already installed. No unrelated WSL session was shut down.
- Initial GPU Chromium capture was rejected because content was blank. Software-rendered retry passed and was visually inspected. The 1280 panel capture rendered, but teardown timed out; that run is not reported as a clean pass.
- Installed package transactions preserved custom config and recoverable checkpoints. Source and installed `/etc/i3/config` plus `window_controls.py` hashes match. Existing nested sessions need restart to use updated processes.
- Older released ISO remains stale. Build normally, not by resuming pre-fix stages:

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'
```
