# Default prompt for Ooonana's interactive ash and bash sessions.
case $- in *i*) ;; *) return 0 ;; esac
[ -t 2 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ] || return 0

if [ -z "${ENV:-}" ]; then
  ENV=/etc/profile.d/ooonana-terminal.sh
  export ENV
fi

case "${PS1:-}" in
  ''|'$ '|'# '|'\u@\h:\w\$ '|'\h:\w\$ '|'\w \$ '|'\w\$ '|'\w # '|'\w $ ')
    case "$TERM" in
      *256color*|*direct*) PS1='\[\033[38;5;214m\]\u@\h\[\033[0m\] \w\$ ' ;;
      *) PS1='\[\033[33m\]\u@\h\[\033[0m\] \w\$ ' ;;
    esac
    ;;
esac
