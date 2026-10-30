#!/bin/sh
set -eu
[ "$(id -u)" = 1000 ]
case "$1" in /qa/input-method/qt.txt) ;; *) exit 2 ;; esac
IFS= read -r text
printf '%s' "$text" >"$1"
