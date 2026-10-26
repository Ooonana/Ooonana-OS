#!/usr/bin/env bash
# Attach only to the GTK chooser descended from this private QA run.
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID == 0 && $# == 2 ]] || exit 2
rootfs="$(realpath "$1")"; output="$(realpath "$2")"
[[ "$rootfs" == /var/tmp/*/full-i3-rootfs && "$output" == /var/tmp/ooonana-firefox-warning-* && ! -L "$2" ]] || exit 2
command -v gdb >/dev/null
probe_pid=; debug_pid=
cleanup() {
  if [[ -n "$debug_pid" ]]; then kill -INT "$debug_pid" 2>/dev/null || true; wait "$debug_pid" 2>/dev/null || true; fi
  if [[ -n "$probe_pid" ]]; then kill -TERM "$probe_pid" 2>/dev/null || true; wait "$probe_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
OOONANA_FIREFOX_QA_WARNING_TRACE=1 bash "$SOURCE/tests/run-candidate-gui.sh" "$rootfs" "$output" >"$output/driver.log" 2>&1 &
probe_pid=$!
ready=0
for _ in {1..300}; do
  if grep -q CHOOSER_CANCEL_TRACE_READY "$output/firefox-frame.log" 2>/dev/null; then ready=1; break; fi
  kill -0 "$probe_pid" 2>/dev/null || { cat "$output/driver.log"; exit 1; }
  sleep .1
done
[[ "$ready" == 1 ]] || { echo 'Private picker trace gate missing' >&2; exit 1; }
# Traverse only this owned process tree, never search arbitrary user processes.
queue=("$probe_pid"); target=
for ((index=0; index<${#queue[@]} && index<512; index++)); do
  pid="${queue[index]}"
  [[ -r "/proc/$pid/task/$pid/children" ]] || continue
  read -ra children <"/proc/$pid/task/$pid/children" || true
  queue+=("${children[@]}")
  cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$cmd" == '/usr/libexec/xdg-desktop-portal-gtk '* || "$cmd" == '/usr/libexec/xdg-desktop-portal-gtk' ]]; then target="$pid"; break; fi
done
[[ "$target" =~ ^[0-9]+$ && "$(stat -c %u "/proc/$target")" == 1000 ]]
[[ "$(readlink "/proc/$target/ns/mnt")" != "$(readlink /proc/self/ns/mnt)" ]]
printf 'OWNED_GTK_TRACE_PID=%s\n' "$target"
# No inferior calls, fatal masks or GTK settings changed. Break on the real
# assertion helper, record its stack/constant arguments, detach and resume.
inner_pid="$(awk '/^NSpid:/ {print $NF}' "/proc/$target/status")"
[[ "$inner_pid" =~ ^[0-9]+$ ]]
timeout --signal=INT --kill-after=5 45 unshare --mount --propagation private \
  nsenter --target "$target" --pid /bin/sh -c '
    mount -t proc proc /proc
    exec gdb -nx -nh -batch -ex "set pagination off" -ex "set confirm off" -ex "set auto-load off" \
      -ex "set sysroot /proc/$1/root" \
      -ex "set solib-search-path /proc/$1/root/usr/lib:/proc/$1/root/lib" \
      -ex "attach $1" -ex "break g_return_if_fail_warning" -ex continue -ex "bt 30" \
      -ex '\''x/s $rsi'\'' -ex '\''x/s $rdx'\'' -ex detach
  ' fixture "$inner_pid" >"$output/gtk-warning-stack.log" 2>&1 &
debug_pid=$!
ready=0
for _ in {1..150}; do
  if grep -q '^Breakpoint [0-9]' "$output/gtk-warning-stack.log"; then ready=1; break; fi
  kill -0 "$debug_pid" 2>/dev/null || break
  sleep .1
done
[[ "$ready" == 1 ]] || { tail -35 "$output/gtk-warning-stack.log"; exit 1; }
mkdir "$output/trace-ready"
wait "$debug_pid"; debug_pid=
wait "$probe_pid"; probe_pid=
grep -q gtk_widget_event "$output/gtk-warning-stack.log"
grep -q WIDGET_REALIZED_FOR_EVENT "$output/gtk-warning-stack.log"
echo 'GTK_WARNING_STACK_OK actual chooser assertion captured; no suppression or production mutation'
