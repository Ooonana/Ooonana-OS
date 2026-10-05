# shellcheck shell=sh
# Ooonana shell helpers.

export PATH="/sbin:/bin:/usr/sbin:/usr/bin${PATH:+:$PATH}"

bunana() {
  case "${1:-}" in
    --shutdown)
      /usr/bin/bunana --shutdown
      ;;
    --restart|--reboot)
      /usr/bin/bunana --restart
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
