# Portable natural-version ordering for BusyBox builds without strverscmp.
# Numeric runs compare as strings, avoiding overflow/rounding for long versions.
function order(character) {
    if (character == "~") return -1
    if (character == "" || character ~ /^[0-9]$/) return 0
    if (character ~ /^[A-Za-z]$/) return ascii[character]
    return ascii[character] + 256
}
function version_compare(left, right, i, j, a, b, difference, first_difference) {
    i = j = 1
    while (i <= length(left) || j <= length(right)) {
        a = substr(left, i, 1); b = substr(right, j, 1)
        while ((a != "" && a !~ /^[0-9]$/) || (b != "" && b !~ /^[0-9]$/)) {
            difference = order(a) - order(b)
            if (difference) return difference < 0 ? -1 : 1
            if (a != "") i++
            if (b != "") j++
            a = substr(left, i, 1); b = substr(right, j, 1)
        }
        while (substr(left, i, 1) == "0") i++
        while (substr(right, j, 1) == "0") j++
        first_difference = 0
        a = substr(left, i, 1); b = substr(right, j, 1)
        while (a ~ /^[0-9]$/ && b ~ /^[0-9]$/) {
            if (!first_difference) first_difference = (a + 0) - (b + 0)
            i++; j++
            a = substr(left, i, 1); b = substr(right, j, 1)
        }
        if (a ~ /^[0-9]$/) return 1
        if (b ~ /^[0-9]$/) return -1
        if (first_difference) return first_difference < 0 ? -1 : 1
    }
    return 0
}
BEGIN {
    FS = "\t"
    for (code = 1; code < 128; code++) ascii[sprintf("%c", code)] = code
    if (mode == "compare") {
        result = version_compare(left, right)
        print (result < 0 ? "<" : result > 0 ? ">" : "=")
        exit
    }
}
NF >= 5 && $2 != "" {
    id = $2
    # Strict comparison keeps first source for equal versions.
    if (!(id in best) || version_compare(versions[id], $3) < 0) {
        versions[id] = $3
        best[id] = $0
    }
}
END {
    if (mode != "compare") for (id in best) print best[id]
}
