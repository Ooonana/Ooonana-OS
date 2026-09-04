from __future__ import annotations

import re
from dataclasses import dataclass
from textwrap import dedent, wrap


QUACK_PORTRAIT = dedent(
    r"""
                            ....::::....
                         .--            :-.
                       ::                  -:
                     .-                      =.
                    -                         :.
                   :                           :.
                  ..      =+.          .+=.     =
                  =.     .%%=    ...   =%%.      :
                  :          .--====--.          =
                 :         .-=========--.         .
         :..:.:. =.        .:==========:.         - .:.::::
        ..     .:-            .:----:.            =:.     .
         ..                                              .:
         ..                                              ..
          ::.                                          .::
           .:.                                        .:.
             .:.                                     :.
              -.                                    .-
              -.                                    .=
              -.                                    .=
              -.                                    .-
              :.                                     .
               -.                                  .-
               ..                                  :.
                .:                                :.
                 .:                              :.
                   :.                          .:
                     .-..                  ..-.
                        +++:............:+++.
                        +==              ==+.
                       .=-                -=.
                      +===.              :===+
                   .======-:            -=======.
                  =========-           .-=========
                 ===========+          -===========
                 ..:-=-==++=:          :===+===-:..
                      ..                    ..
    """
).strip("\n")

QUACK_PORTRAIT_SMALL = dedent(
    r"""
                .::::.
            .:         .:
           -.            .:
          :                :
         .    %#      #%   ..
         .      -====-      -
    =:-. :    .-=======     . .:=-
   .    ..        ::.       ..   :.
    -.                          .:
     :.                        .:
       -                      :
       =                      -
       =                      -
       :                      .
        .                    ..
         .                  .
          :.              .:
             ++.      .++
             =.        :=
           :==:        :==:
         :=====.      .=====:
         +=====#      +=====+
           ..            ..
    """
).strip("\n")

QUACK_PORTRAIT_TINY = dedent(
    r"""
          .::::.
      .:         .:
     :  %#      #%  :
    .     -====-     .
=:-.:   .-=======.   :.:=-
.   ..      ::       ..   .
 -.                    .-
   :.                .:
     :.            .:
        ++.    .++
       :=:      :=
     +====#    +====+
       ..        ..
    """
).strip("\n")

# Backward-compatible name for callers that still refer to the shortest portrait.
QUACK_PORTRAIT_MINI = QUACK_PORTRAIT_TINY


def animate_quack_portrait(portrait: str, frame: int, speaking: bool = False) -> str:
    """Animate supplied Quack art without changing its outer dimensions."""
    phase = int(frame) % 8
    text = str(portrait)
    blink = phase == 7 or (speaking and phase in {2, 5})
    if blink:
        text = text.replace(".%%=", ".--=").replace("=%%.", "=--.")
        text = text.replace("%#", "--").replace("#%", "--")
    return text


def render_speech_bubble(
    text: str,
    label: str = "Quack",
    width: int = 54,
    max_lines: int = 4,
) -> str:
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(text or ""))
    clean = " ".join(clean.replace("```", "").split()) or "..."
    inner = max(12, min(84, int(width) - 6))
    prefix = f"{label}: "
    payload_width = max(4, inner - len(prefix))
    lines = wrap(
        clean,
        width=payload_width,
        break_long_words=True,
        break_on_hyphens=False,
    ) or ["..."]
    limit = max(1, int(max_lines))
    if len(lines) > limit:
        lines = lines[-limit:]
        lines[0] = "... " + lines[0].lstrip(". ")
    lines[0] = (prefix + lines[0])[:inner]
    content_width = max(18, max(len(line) for line in lines))
    top = " ." + "-" * (content_width + 2) + "."
    body = []
    for index, line in enumerate(lines):
        left, right = ("/", "\\") if index == 0 else ("|", "|")
        body.append(f"{left} {line:<{content_width}} {right}")
    tail_at = max(4, min(content_width - 2, content_width // 2))
    bottom = " \\" + "_" * tail_at + "  " + "_" * (content_width - tail_at) + "/"
    tail = " " * (tail_at + 3) + "\\/"
    return "\n".join([top, *body, bottom, tail])


@dataclass(frozen=True)
class ChartPoint:
    label: str
    value: float


_VISUAL_FENCE = re.compile(r"```\s*([^\n`]*)\n(.*?)```", re.DOTALL)
_BAR_RUN = re.compile(r"[#=█▓▒░▇▆▅▄▃▂▁]{2,}")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")


def extract_visual_panel(text: str) -> tuple[str, str] | None:
    """Extract a terminal-friendly chart, diagram, or table from model output."""
    value = str(text or "")
    for match in _VISUAL_FENCE.finditer(value):
        language = match.group(1).strip().lower().split(maxsplit=1)[0]
        body = match.group(2).strip("\n")
        if not body:
            continue
        if language in {"chart", "graph", "plot"}:
            return "chart", body
        if language in {"mermaid", "diagram", "ascii"}:
            return "diagram", body
        if language in {"table", "markdown"} and _looks_like_table(body):
            return "table", body
        if language in {"", "text", "txt"}:
            kind = _visual_kind(body)
            if kind is not None:
                return kind, body

    lines = value.splitlines()
    chart_lines = [line.rstrip() for line in lines if "|" in line and _BAR_RUN.search(line)]
    if len(chart_lines) >= 2:
        return "chart", "\n".join(chart_lines)
    for index in range(len(lines) - 1):
        if "|" in lines[index] and _TABLE_RULE.match(lines[index + 1]):
            table: list[str] = []
            cursor = index
            while cursor < len(lines) and "|" in lines[cursor]:
                table.append(lines[cursor].rstrip())
                cursor += 1
            if len(table) >= 3:
                return "table", "\n".join(table)
    return None


def _visual_kind(text: str) -> str | None:
    if _looks_like_table(text):
        return "table"
    lines = [line for line in text.splitlines() if line.strip()]
    if sum(bool(_BAR_RUN.search(line)) and "|" in line for line in lines) >= 2:
        return "chart"
    diagram_chars = sum(any(token in line for token in ("->", "-->", "+--", "┌", "└", "│")) for line in lines)
    return "diagram" if len(lines) >= 3 and diagram_chars >= 2 else None


def _looks_like_table(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return len(lines) >= 3 and "|" in lines[0] and bool(_TABLE_RULE.match(lines[1]))


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
