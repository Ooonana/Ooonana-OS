#!/bin/sh
# PDF-only front door: cheap help; real package operations use unchanged CLI.
set -eu
version='@CORE_VERSION@'
case "${1:-}" in
  version|--version|-v) printf 'ooonana %s\n' "$version"; exit 0 ;;
  ''|help|usage|--help|-h)
    case "${2:-}" in
      '')
        printf '%s\n' "ooonana $version | PDF terminal" \
          'Usage: ooonana COMMAND' \
          '  version  me  list  search QUERY  show PACKAGE' \
          '  update  get PACKAGE  verify PACKAGE  check' \
          '  help packages  help repo  ai status'
        exit 0 ;;
      packages|get|install|upgrade|remove|repo|ai)
        topic="${2:-}"
        [ "$topic" != install ] || topic=get
        help_file="/run/ooonana/help/$topic"
        [ -f "$help_file" ] || help_file="/usr/share/ooonana/pdf-help/$topic"
        if [ -f "$help_file" ]; then cat "$help_file"; exit 0; fi ;;
    esac ;;
esac
backend=/run/ooonana/usr/bin/ooonana-pkg
[ -f "$backend" ] || backend=/usr/bin/ooonana-pkg
if [ -x /run/ooonana/bin/sh ]; then
  exec /run/ooonana/bin/sh "$backend" "$@"
fi
exec /bin/sh "$backend" "$@"
