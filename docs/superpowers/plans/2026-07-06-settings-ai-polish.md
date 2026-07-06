# Ooonana Settings And AI App Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ooonana Settings feel like an XFCE-style control center and make Ooonana AI feel like a ChatGPT-style desktop chat app while preserving terminal fallbacks.

**Architecture:** Keep the current POSIX shell plus `yad` architecture. Generate `ooonana-settings` from `scripts/build-full-i3-rootfs.sh`, keep `ooonana-ai-app` as the package-owned script, and patch the release ISO after tests pass.

**Tech Stack:** POSIX shell, `yad`, xterm fallback, existing Ooonana helper commands, shell tests.

---

### Task 1: Settings Tests

**Files:**
- Modify: `tests/test-full-i3-rootfs.sh`

- [ ] **Step 1: Add assertions for control-center structure**

Add checks near the existing `settings_helper` assertions:

```bash
assert_contains "$settings_helper" "XFCE-style control center"
assert_contains "$settings_helper" "settings sidebar"
assert_contains "$settings_helper" "category screen"
assert_contains "$settings_helper" "System Hardware Network Appearance Apps Ooonana Logs"
assert_contains "$settings_helper" "show_category"
assert_contains "$settings_helper" "show_status_cards"
assert_contains "$settings_helper" "ooonana-wifi-panel"
assert_contains "$settings_helper" "ooonana-bluetooth-panel"
assert_contains "$settings_helper" "ooonana-brightness-panel"
assert_contains "$settings_helper" "ooonana-audio-panel"
assert_contains "$settings_helper" "ooonana-gui-installer"
```

- [ ] **Step 2: Add dry-run assertions**

Extend the existing `settings_dry` block:

```bash
assert_contains "$settings_dry" "XFCE-style control center"
assert_contains "$settings_dry" "settings sidebar: System Hardware Network Appearance Apps Ooonana Logs"
assert_contains "$settings_dry" "category screens: status cards actions details"
```

- [ ] **Step 3: Run failing test**

Run:

```bash
bash tests/test-full-i3-rootfs.sh
```

Expected before implementation: fail on missing new strings.

### Task 2: Settings Implementation

**Files:**
- Modify: `scripts/build-full-i3-rootfs.sh`

- [ ] **Step 1: Update dry-run output**

In the generated `/usr/bin/ooonana-settings` dry-run block, add:

```sh
echo "XFCE-style control center"
echo "settings sidebar: System Hardware Network Appearance Apps Ooonana Logs"
echo "category screens: status cards actions details"
```

- [ ] **Step 2: Add status card helper**

Inside the generated script, add:

```sh
show_status_cards() {
  cards="${TMPDIR:-/tmp}/ooonana-settings-cards.$$"
  {
    printf 'Ooonana Control Center\n'
    printf 'Theme: %s\n' "$(theme_status)"
    printf 'Wallpaper: %s\n' "$(basename "$(wallpaper_status)" 2>/dev/null || echo wallpaper)"
    printf 'Display: %s\n' "$(command -v arandr >/dev/null 2>&1 && echo ready || echo basic)"
    printf 'Audio: %s\n' "$(command -v pavucontrol >/dev/null 2>&1 && echo ready || echo missing)"
    printf 'Wi-Fi: %s\n' "$(command -v nmcli >/dev/null 2>&1 && echo ready || echo missing)"
    printf 'Bluetooth: %s\n' "$(command -v bluetoothctl >/dev/null 2>&1 && echo ready || echo missing)"
    printf 'Repo: https://ooonana.gitlab.io/ooonana-repo\n'
  } >"$cards"
  yad --center --title "Ooonana Control Center" --width=760 --height=460 \
    --text-info --filename="$cards" --button=Settings:0 --button=Close:1 2>/dev/null
  rc="$?"
  rm -f "$cards"
  return "$rc"
}
```

- [ ] **Step 3: Add category screen helper**

Add:

```sh
show_category() {
  section="$1"
  case "$section" in
    System) rows='"" theme "Theme" "Dark/light theme" "" power "Power" "Shutdown, restart, logout"' ;;
    Hardware) rows='"" display "Display" "Monitor layout" "" audio "Audio" "Volume and devices" "" brightness "Brightness" "Backlight slider"' ;;
    Network) rows='"" wifi "Wi-Fi" "NetworkManager panel" "" bluetooth "Bluetooth" "Bluetooth manager"' ;;
    Appearance) rows='"" wallpaper "Wallpaper" "Choose background" "" theme "Theme" "Apply theme"' ;;
    Apps) rows='"" browser "Browser" "Chromium" "" files "Files" "Nemo" "" terminal "Terminal" "Shell"' ;;
    Ooonana) rows='"" packages "Packages" "Package manager" "" ai "AI" "Ooonana AI" "" installer "Installer" "Install Ooonana OS"' ;;
    Logs) rows='"" logs "Logs" "Settings logs" "" about "About" "System info"' ;;
    *) rows='"" overview "Overview" "Status cards"' ;;
  esac
  eval "set -- $rows"
  yad --center --title \"Ooonana Settings - $section\" --width=820 --height=560 \
    --list --print-column=2 --column Icon --column Action --column Name --column Description "$@" 2>/dev/null || true
}
```

- [ ] **Step 4: Use sidebar loop**

Replace the flat `choose_settings_action` first-step loop with:

```sh
while :; do
  show_status_cards || exit 0
  section="$(yad --center --title "Ooonana Settings" --width=360 --height=440 \
    --text "settings sidebar" --list --print-column=1 --column Category \
    System Hardware Network Appearance Apps Ooonana Logs 2>/dev/null || true)"
  [ -n "$section" ] || exit 0
  action="$(show_category "$section")"
  [ -n "$action" ] || continue
  case "$action" in
    overview) show_status_cards || true ;;
    theme) open the existing theme form and call `ooonana-theme-env apply` ;;
    wallpaper) open the existing wallpaper file chooser and call `ooonana-wallpaper "$file"` ;;
    display) run `arandr` or show a missing-tool dialog ;;
    audio) run `pavucontrol` or show a missing-tool dialog ;;
    wifi) run `ooonana-wifi-panel` ;;
    bluetooth) run `ooonana-bluetooth-panel` ;;
    brightness) run `ooonana-brightness-panel` ;;
    packages) run `ooonana-packages-app` ;;
    ai) run `ooonana-ai-app` ;;
    installer) run `ooonana-gui-installer` ;;
    browser) run `ooonana-browser` ;;
    files) run `ooonana-files` ;;
    terminal) run `launch_terminal 'exec sh -l'` ;;
    logs) run `show_settings_logs` ;;
    about) run `show_info` ;;
  esac
done
```

Keep the existing case actions and add `installer) ooonana-gui-installer || true ;;`.

- [ ] **Step 5: Run test**

Run:

```bash
bash tests/test-full-i3-rootfs.sh
```

Expected: pass.

### Task 3: AI App Tests

**Files:**
- Modify: `tests/test-ooonana-ai.sh`
- Modify: `tests/test-full-i3-rootfs.sh`

- [ ] **Step 1: Add AI layout assertions**

Add to `tests/test-ooonana-ai.sh`:

```bash
assert_contains "$(<"$AI_DESKTOP_APP")" "ChatGPT-style desktop chat"
assert_contains "$(<"$AI_DESKTOP_APP")" "ai sidebar"
assert_contains "$(<"$AI_DESKTOP_APP")" "chat transcript"
assert_contains "$(<"$AI_DESKTOP_APP")" "prompt box"
assert_contains "$(<"$AI_DESKTOP_APP")" "provider/model header"
assert_contains "$(<"$AI_DESKTOP_APP")" "show_chat_home"
assert_contains "$(<"$AI_DESKTOP_APP")" "show_chat_prompt"
```

Add to dry-run assertions:

```bash
assert_contains "$app_gui_dry" "ChatGPT-style desktop chat"
assert_contains "$app_gui_dry" "sidebar: New Chat Chat History Tools Tasks Context Provider Permissions Desktop Logs Shell"
assert_contains "$app_gui_dry" "main pane: provider/model header transcript prompt box"
```

- [ ] **Step 2: Run failing AI test**

Run:

```bash
bash tests/test-ooonana-ai.sh
```

Expected before implementation: fail on missing new strings.

### Task 4: AI App Implementation

**Files:**
- Modify: `packages/ooonana/usr/bin/ooonana-ai-app`

- [ ] **Step 1: Update dry-run output**

Add:

```sh
printf 'ChatGPT-style desktop chat\n'
printf 'sidebar: New Chat Chat History Tools Tasks Context Provider Permissions Desktop Logs Shell\n'
printf 'main pane: provider/model header transcript prompt box\n'
```

- [ ] **Step 2: Add chat home helper**

Add:

```sh
show_chat_home() {
  tmp="${TMPDIR:-/tmp}/ooonana-ai-home.$$"
  {
    printf 'Ooonana AI\n'
    printf 'provider/model header\n'
    ooonana ai status 2>/dev/null || true
    printf '\nchat transcript\n'
    [ -f "${OOONANA_AI_CHAT_LOG:-${HOME:-/root}/.local/share/ooonana/ai-chat.log}" ] &&
      tail -80 "${OOONANA_AI_CHAT_LOG:-${HOME:-/root}/.local/share/ooonana/ai-chat.log}" || printf 'No chat yet.\n'
  } >"$tmp"
  yad --center --title "Ooonana AI" --width=920 --height=620 \
    --text-info --filename="$tmp" --button=Prompt:0 --button=Sidebar:2 --button=Close:1 2>/dev/null
  rc="$?"
  rm -f "$tmp"
  return "$rc"
}
```

- [ ] **Step 3: Add prompt helper**

Add:

```sh
show_chat_prompt() {
  prompt="$(yad --center --title "Ooonana AI Prompt" --width=780 --height=260 \
    --form --field "prompt box:TXT" "" 2>/dev/null | cut -d'|' -f1 || true)"
  [ -n "$prompt" ] || return 0
  run_ai_window "Ooonana AI Response" ooonana ai ask "$prompt"
}
```

- [ ] **Step 4: Add sidebar loop**

Use a `yad --list` sidebar with actions:

```sh
sidebar_action() {
  yad --center --title "Ooonana AI" --width=420 --height=560 \
    --text "ai sidebar" --list --print-column=2 \
    --column Icon --column Action --column Name \
    "" new "New Chat" \
    "" chat "Chat" \
    "" history "History" \
    "" tools "Tools" \
    "" tasks "Tasks" \
    "" context "Context" \
    "" provider "Provider" \
    "" permissions "Permissions" \
    "" desktop "Desktop" \
    "" logs "Logs" \
    "" shell "Shell" 2>/dev/null || true
}
```

Wire `chat` to `show_chat_home`, `new` to truncate the chat log, `prompt` to `show_chat_prompt`, and existing actions to their current functions.

- [ ] **Step 5: Run AI test**

Run:

```bash
bash tests/test-ooonana-ai.sh
```

Expected: pass.

### Task 5: Full Verification And Release Patch

**Files:**
- Modify release artifact: `F:\Ooonana\ooonana-os\release-current\ooonana-full-i3.iso`
- Modify release checksums: `F:\Ooonana\ooonana-os\release-current\SHA256SUMS*`

- [ ] **Step 1: Syntax checks**

Run:

```bash
bash -n scripts/*.sh scripts/lib/*.sh tests/*.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/generate-ooonana-pdf.py
find packages -name '*.py' -print0 | xargs -0 -r env PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile
```

Expected: exit 0.

- [ ] **Step 2: Focused tests**

Run:

```bash
bash tests/test-full-i3-rootfs.sh
bash tests/test-ooonana-ai.sh
```

Expected: both pass.

- [ ] **Step 3: Full tests**

Run:

```bash
find tests -maxdepth 1 -type f -name '*.sh' -print0 | sort -z | xargs -0 -n1 bash
```

Expected: each test script prints its `ok` line or existing expected warning, and the command exits 0.

- [ ] **Step 4: Patch release rootfs and ISO**

Use the existing release patch flow after tests pass:

```bash
OOONANA_RELEASE_DIR=/mnt/win_f_actual/Ooonana/ooonana-os/release-current \
OOONANA_PATCH_WORK=/var/tmp/ooonana-release-patch \
OOONANA_OUT_ISO=/mnt/win_f_actual/Ooonana/ooonana-os/release-current/ooonana-full-i3.iso.new \
bash scripts/patch-full-i3-release-ui.sh --resume-after-extract
```

Expected: new ISO produced at `ooonana-full-i3.iso.new`.

- [ ] **Step 5: Verify release ISO**

Run:

```bash
bash scripts/verify-rufus-iso.sh --iso /mnt/win_f_actual/Ooonana/ooonana-os/release-current/ooonana-full-i3.iso
```

Expected: `OOONANA_RUFUS_ISO_OK`.

- [ ] **Step 6: Commit and push**

Run:

```bash
git add scripts/build-full-i3-rootfs.sh packages/ooonana/usr/bin/ooonana-ai-app tests/test-full-i3-rootfs.sh tests/test-ooonana-ai.sh README.md
git commit -m "Polish settings and AI desktop apps"
git push origin main
```

Expected: push succeeds.
