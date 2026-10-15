#!/bin/sh
# Console-only stage feedback. No traps, background jobs, terminal input or
# storage writes. Animation consumes existing retry/shutdown waits only.
ooonana_console_begin() {
  ooonana_ui_animated=0
  ooonana_ui_frame=0
  ooonana_ui_label='Starting Ooonana'
  ooonana_ui_device=/dev/tty1
  ooonana_ui_cmdline="$(cat /proc/cmdline 2>/dev/null || true)"
  case " ${ooonana_ui_cmdline} " in
    *' ooonana.motion=off '*|*' console=ttyS'*|*' console=hvc'*|*' console=ttyAMA'*) return 0 ;;
  esac
  [ "${OOONANA_CONSOLE_MOTION:-on}" != off ] || return 0
  [ -c "$ooonana_ui_device" ] && [ -w "$ooonana_ui_device" ] || return 0
  ooonana_ui_dimensions="$(stty size <"$ooonana_ui_device" 2>/dev/null || true)"
  ooonana_ui_rows=${ooonana_ui_dimensions%% *}
  ooonana_ui_cols=${ooonana_ui_dimensions##* }
  case "$ooonana_ui_rows:$ooonana_ui_cols" in *[!0-9:]*|:*|*:) return 0 ;; esac
  [ "$ooonana_ui_rows" -ge 20 ] && [ "$ooonana_ui_cols" -ge 60 ] || return 0
  ooonana_ui_logo=${1:-/usr/share/ooonana/boot-logo.txt}
  ooonana_ui_lines=0
  if [ -r "$ooonana_ui_logo" ]; then
    while IFS= read -r ooonana_ui_line || [ -n "$ooonana_ui_line" ]; do
      ooonana_ui_lines=$((ooonana_ui_lines + 1))
    done <"$ooonana_ui_logo"
  fi
  [ "$ooonana_ui_lines" -gt 0 ] || ooonana_ui_lines=1
  ooonana_ui_row=$(((ooonana_ui_rows - ooonana_ui_lines - 4) / 2))
  {
    printf '\033]P3ffb21a\033[2J\033[%s;1H\033[1;33m' "$ooonana_ui_row"
    if [ -r "$ooonana_ui_logo" ]; then
      while IFS= read -r ooonana_ui_line || [ -n "$ooonana_ui_line" ]; do
        ooonana_console_center "$ooonana_ui_line"
      done <"$ooonana_ui_logo"
    else
      ooonana_console_center 'Ooonana OS'
    fi
    printf '\033[0m'
  } >"$ooonana_ui_device" 2>/dev/null || return 0
  ooonana_ui_row=$((ooonana_ui_row + ooonana_ui_lines + 2))
  ooonana_ui_animated=1
}

ooonana_console_center() {
  ooonana_ui_padding=$(((ooonana_ui_cols - ${#1}) / 2))
  [ "$ooonana_ui_padding" -ge 0 ] || ooonana_ui_padding=0
  printf '%*s%s\n' "$ooonana_ui_padding" '' "$1"
}

ooonana_console_frame() {
  [ "${ooonana_ui_animated:-0}" = 1 ] || return 0
  case "$ooonana_ui_frame" in
    0) ooonana_ui_pulse='o . .' ;;
    1) ooonana_ui_pulse='. o .' ;;
    *) ooonana_ui_pulse='. . o' ;;
  esac
  {
    printf '\033[%s;1H\033[2K\033[1;33m' "$ooonana_ui_row"
    ooonana_console_center "$ooonana_ui_pulse"
    printf '\033[2K\033[0m'
    ooonana_console_center "$ooonana_ui_label"
    # Leave ordinary warnings below the status, not over its text.
    printf '\n'
  } >"$ooonana_ui_device" 2>/dev/null || true
  ooonana_ui_frame=$(((ooonana_ui_frame + 1) % 3))
}

ooonana_console_stage() {
  ooonana_ui_label=$1
  if [ "${ooonana_ui_animated:-0}" = 1 ]; then
    ooonana_console_frame
  else
    printf 'Ooonana: %s\n' "$ooonana_ui_label" || true
  fi
}

ooonana_console_wait() {
  # Whole-second BusyBox sleep works even without fractional-sleep support.
  ooonana_ui_remaining=$1
  while [ "$ooonana_ui_remaining" -gt 0 ]; do
    ooonana_console_frame
    sleep 1 || return "$?"
    ooonana_ui_remaining=$((ooonana_ui_remaining - 1))
  done
}

ooonana_console_end() {
  if [ "${ooonana_ui_animated:-0}" = 1 ]; then
    printf '\033[%s;1H\033[2K\033[0m\033[%s;1H' \
      "$ooonana_ui_row" "$((ooonana_ui_row + 3))" >"$ooonana_ui_device" 2>/dev/null || true
  fi
  ooonana_ui_animated=0
  return 0
}
