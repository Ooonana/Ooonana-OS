#!/bin/sh
# Browser request from isolated OpenVINO userspace to user's Ooonana desktop.
set -eu
url="${1:-}"
fifo="${OOONANA_OPENVINO_BROWSER_FIFO:-}"
case "$url" in
  http://127.0.0.1:*'/openvino.html#token='*|http://127.0.0.1:*'/duck.html#token='*) ;;
  *) exit 1 ;;
esac
[ -n "$fifo" ] && [ -p "$fifo" ] || exit 1
printf '%s\n' "$url" > "$fifo"
