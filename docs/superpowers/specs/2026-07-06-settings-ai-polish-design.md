# Ooonana Settings And AI App Polish Design

## Goal

Upgrade the full-i3 Ooonana desktop apps so Settings feels like a real Linux control center and Ooonana AI feels like a chat-first desktop assistant.

## Scope

This work changes the generated full-i3 rootfs helpers and the packaged AI app. It keeps the current shell/yad stack, because the live ISO already ships those dependencies and the scripts work in WSL, QEMU, VMware, and native boot with small resource cost.

## Settings App

`/usr/bin/ooonana-settings` becomes an XFCE-style control center:

- A launch overview with status cards for theme, display, audio, Wi-Fi, Bluetooth, package repo, and system identity.
- A category picker with System, Hardware, Network, Appearance, Apps, Ooonana, and Logs.
- Category screens list useful actions with icons, labels, status, and descriptions.
- Existing helper commands remain the action backends: `ooonana-wifi-panel`, `ooonana-bluetooth-panel`, `ooonana-brightness-panel`, `ooonana-audio-panel`, `arandr`, `pavucontrol`, `ooonana-packages-app`, `ooonana-ai-app`, `ooonana-gui-installer`, `ooonana-wallpaper`, and `ooonana-theme-env`.
- Terminal fallback remains: when `DISPLAY` or `yad` is missing, the app opens themed terminal help.

The design should avoid a single flat action list. It should look like a control center: persistent overview first, then grouped settings panes.

## AI App

`/usr/bin/ooonana-ai-app` becomes ChatGPT-style within `yad` limits:

- Main view has a left navigation list: New chat, Chat, Ask, History, Tools, Tasks, Context, Provider, Permissions, Desktop, Logs, Shell.
- Header shows provider, model, workspace, session, and permission mode.
- Chat view shows transcript text and a bottom prompt form.
- Ask view gives one prompt and returns output in a scrollable response window.
- Tools and Desktop views expose controlled actions, not hidden commands.
- Save, clear, and logs actions remain available.
- Terminal dashboard fallback remains.

The app should not pretend to be a browser app. It should be a compact native desktop shell around the existing `ooonana ai` CLI.

## Error Handling

- Missing GUI dependencies open the terminal fallback instead of exiting.
- Missing Wi-Fi, Bluetooth, audio, or brightness services show a useful repair/status window.
- AI provider errors are captured in the chat transcript or a log window.
- Dangerous desktop actions stay explicit and visible.

## Testing

Update shell tests to assert the new UI structure by checking generated scripts and dry-run output. Verify:

- Settings dry-run mentions control center, sidebar/category layout, status cards, and category screens.
- Settings script references the existing helper commands.
- AI dry-run mentions ChatGPT-style layout, sidebar, transcript, prompt box, provider/model header, permissions, and desktop control.
- AI script syntax passes.
- Full rootfs tests pass.

## Out Of Scope

- No GTK/Qt compiled app.
- No Electron/browser shell.
- No new AI provider logic.
- No major i3/polybar redesign.
- No Secure Boot implementation in this change.
