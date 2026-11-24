# Xephyr needs full repaint and continuous redirection.
BEGIN { print "# Ooonana WSL compositor adapter." }
/^[[:space:]]*use-damage[[:space:]]*=[[:space:]]*(true|false);[[:space:]]*$/ {
    print "use-damage = false;"
    damage++
    next
}
/^[[:space:]]*unredir-if-possible[[:space:]]*=[[:space:]]*(true|false);[[:space:]]*$/ {
    print "unredir-if-possible = false;"
    redirect++
    next
}
{ print }
END { if (damage != 1 || redirect != 1) exit 1 }
