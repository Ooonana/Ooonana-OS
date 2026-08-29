# shellcheck shell=sh
# Ooonana shell helpers.

export PATH="/sbin:/bin:/usr/sbin:/usr/bin${PATH:+:$PATH}"

bunana() {
  case "${1:-}" in
    --shutdown)
      sync 2>/dev/null || true
      poweroff -f 2>/dev/null || halt -f 2>/dev/null || shutdown -h now 2>/dev/null || exit 0
      ;;
    --restart|--reboot)
      sync 2>/dev/null || true
      reboot -f 2>/dev/null || shutdown -r now 2>/dev/null || exit 0
      ;;
    --help|-h)
      printf 'bunana              exit shell\n'
      printf 'bunana --shutdown   power off\n'
      printf 'bunana --restart    reboot\n'
      ;;
    *)
      exit 0
      ;;
  esac
}
