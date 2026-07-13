from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChartPoint:
    label: str
    value: float


FONT = {
    "A": (" AAA ", "A   A", "AAAAA", "A   A", "A   A"),
    "B": ("BBBB ", "B   B", "BBBB ", "B   B", "BBBB "),
    "C": (" CCCC", "C    ", "C    ", "C    ", " CCCC"),
    "D": ("DDDD ", "D   D", "D   D", "D   D", "DDDD "),
    "E": ("EEEEE", "E    ", "EEEE ", "E    ", "EEEEE"),
    "F": ("FFFFF", "F    ", "FFFF ", "F    ", "F    "),
    "G": (" GGGG", "G    ", "G GGG", "G   G", " GGG "),
    "H": ("H   H", "H   H", "HHHHH", "H   H", "H   H"),
    "I": ("IIIII", "  I  ", "  I  ", "  I  ", "IIIII"),
    "J": ("JJJJJ", "   J ", "   J ", "J  J ", " JJ  "),
    "K": ("K   K", "K  K ", "KKK  ", "K  K ", "K   K"),
    "L": ("L    ", "L    ", "L    ", "L    ", "LLLLL"),
    "M": ("M   M", "MM MM", "M M M", "M   M", "M   M"),
    "N": ("N   N", "NN  N", "N N N", "N  NN", "N   N"),
    "O": (" OOO ", "O   O", "O   O", "O   O", " OOO "),
    "P": ("PPPP ", "P   P", "PPPP ", "P    ", "P    "),
    "Q": (" QQQ ", "Q   Q", "Q   Q", "Q  Q ", " QQ Q"),
    "R": ("RRRR ", "R   R", "RRRR ", "R  R ", "R   R"),
    "S": (" SSSS", "S    ", " SSS ", "    S", "SSSS "),
    "T": ("TTTTT", "  T  ", "  T  ", "  T  ", "  T  "),
    "U": ("U   U", "U   U", "U   U", "U   U", " UUU "),
    "V": ("V   V", "V   V", "V   V", " V V ", "  V  "),
    "W": ("W   W", "W   W", "W W W", "WW WW", "W   W"),
    "X": ("X   X", " X X ", "  X  ", " X X ", "X   X"),
    "Y": ("Y   Y", " Y Y ", "  Y  ", "  Y  ", "  Y  "),
    "Z": ("ZZZZZ", "   Z ", "  Z  ", " Z   ", "ZZZZZ"),
    "0": (" 000 ", "0   0", "0   0", "0   0", " 000 "),
    "1": ("  1  ", " 11  ", "  1  ", "  1  ", "11111"),
    "2": ("2222 ", "    2", " 222 ", "2    ", "22222"),
    "3": ("3333 ", "    3", " 333 ", "    3", "3333 "),
    "4": ("4  4 ", "4  4 ", "44444", "   4 ", "   4 "),
    "5": ("55555", "5    ", "5555 ", "    5", "5555 "),
    "6": (" 666 ", "6    ", "6666 ", "6   6", " 666 "),
    "7": ("77777", "   7 ", "  7  ", " 7   ", "7    "),
    "8": (" 888 ", "8   8", " 888 ", "8   8", " 888 "),
    "9": (" 999 ", "9   9", " 9999", "    9", " 999 "),
    " ": ("     ", "     ", "     ", "     ", "     "),
}


def parse_chart_values(text: str) -> list[ChartPoint]:
    tokens = [token for token in re.split(r"[\s,]+", text.strip()) if token]
    points: list[ChartPoint] = []
    for index, token in enumerate(tokens, start=1):
        label = str(index)
        raw_value = token
        if "=" in token:
            label, raw_value = token.split("=", 1)
        elif ":" in token:
            label, raw_value = token.split(":", 1)
        value = float(raw_value)
        points.append(ChartPoint(label.strip() or str(index), value))
    if not points:
        raise ValueError("chart needs values")
    return points


def render_chart(text: str, width: int = 28) -> str:
    points = parse_chart_values(text)
    max_value = max(abs(point.value) for point in points) or 1
    label_width = max(len(point.label) for point in points)
    lines = []
    for point in points:
        bar_size = max(1, round(abs(point.value) / max_value * width)) if point.value else 0
        bar = "#" * bar_size
        lines.append(f"{point.label:<{label_width}} | {bar} {point.value:g}")
    return "\n".join(lines)


def render_big_text(text: str) -> str:
    rows = ["", "", "", "", ""]
    for char in text.upper():
        glyph = FONT.get(char, _fallback_glyph(char))
        for index, line in enumerate(glyph):
            rows[index] += line + "  "
    return "\n".join(row.rstrip() for row in rows)


def render_tilt_text(text: str) -> str:
    rows = render_big_text(text).splitlines()
    max_indent = len(rows) - 1
    return "\n".join((" " * (max_indent - index)) + row for index, row in enumerate(rows))


def _fallback_glyph(char: str) -> tuple[str, str, str, str, str]:
    letter = (char or "?")[0].upper()
    return (letter * 5, letter + "   " + letter, letter * 5, letter + "   " + letter, letter * 5)
