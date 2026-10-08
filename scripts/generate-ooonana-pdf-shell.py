#!/usr/bin/env python3
"""Opaque native-PDF shell UI. Keep TinyEMU field names/actions and AcroForm data."""
import json
import os
from pathlib import Path
import sys

from pdfrw import PdfArray, PdfDict, PdfName, PdfObject, PdfString, PdfWriter

BG = (0.055, 0.063, 0.078)
CARD = (0.090, 0.102, 0.122)
KEY = (0.145, 0.165, 0.192)
INK = (0.91, 0.93, 0.96)
MUTED = (0.58, 0.64, 0.71)
ACCENT = (1.0, 0.64, 0.27)
FONT = PdfDict(Type=PdfName.Font, Subtype=PdfName.Type1, BaseFont=PdfName.Helvetica)
MONO = PdfDict(Type=PdfName.Font, Subtype=PdfName.Type1, BaseFont=PdfName.Courier)
FONTS = PdfDict(F1=FONT, FUI=FONT, FMono=MONO)


def rgb(color):
    return " ".join(str(value) for value in color)


def literal(value):
    return PdfString.encode(str(value))


def rounded(x, y, width, height, radius, color):
    radius = min(radius, width / 2, height / 2)
    bend = radius * 0.55228475
    right, top = x + width, y + height
    return f"""{rgb(color)} rg
{x + radius} {y} m {right - radius} {y} l
{right - radius + bend} {y} {right} {y + radius - bend} {right} {y + radius} c
{right} {top - radius} l
{right} {top - radius + bend} {right - radius + bend} {top} {right - radius} {top} c
{x + radius} {top} l
{x + radius - bend} {top} {x} {top - radius + bend} {x} {top - radius} c
{x} {y + radius} l
{x} {y + radius - bend} {x + radius - bend} {y} {x + radius} {y} c h f
"""


def text(x, y, size, value, color=INK, font="FUI"):
    return f"BT /{font} {size} Tf {rgb(color)} rg 1 0 0 1 {x} {y} Tm {literal(value)} Tj ET\n"


def create_script(js):
    return PdfDict(S=PdfName.JavaScript,
                   JS=literal("try {" + js + "} catch (e) {app.alert(e.stack || e)}"))


def create_page(width, height):
    return PdfDict(Type=PdfName.Page, MediaBox=PdfArray([0, 0, width, height]),
                   Resources=PdfDict(Font=FONTS))


def appearance(width, height, value, background, color, font, size, centered=False, radius=0):
    # Initial AP and canonical V agree; JavaScript keeps widgets interactive.
    x = max(4, (width - len(str(value)) * size * 0.52) / 2) if centered else 4
    baseline = max(1, (height - size) / 2 + size * 0.22)
    stream = "q\n" + rounded(0, 0, width, height, radius, background)
    stream += f"0 0 {width} {height} re W n\n" + text(x, baseline, size, value, color, font) + "Q\n"
    return PdfDict(indirect=True, Type=PdfName.XObject, Subtype=PdfName.Form,
                   FormType=1, BBox=PdfArray([0, 0, width, height]),
                   Resources=PdfDict(Font=FONTS), stream=stream)


def create_field(name, x, y, width, height, value="", f_type=PdfName.Tx, display=False):
    # OOONANA_INDIRECT_WIDGETS / OOONANA_MONO_FRAMEBUFFER
    font, size, color = ("FMono", 10.5, ACCENT) if display else ("FUI", 9, MUTED)
    field = PdfDict(indirect=True, Type=PdfName.Annot, Subtype=PdfName.Widget,
                    FT=f_type, F=4, Ff=1 if display else 0,
                    Rect=PdfArray([x, y, x + width, y + height]),
                    T=literal(name), V=literal(value),
                    BS=PdfDict(W=0), MK=PdfDict(BG=PdfArray(CARD)),
                    DA=literal(f"/{font} {size} Tf {rgb(color)} rg"), Q=0)
    field.AP = PdfDict(N=appearance(width, height, value, CARD, color, font, size))
    return field


def create_button(name, x, y, width, height, value, accent=False):
    button = create_field(name, x, y, width, height, f_type=PdfName.Btn)
    background, color = (ACCENT, BG) if accent else (KEY, INK)
    button.Ff = 65536
    button.MK = PdfDict(BG=PdfArray(background), CA=literal(value))
    button.DA = literal(f"/FUI 9 Tf {rgb(color)} rg")
    button.AP = PdfDict(N=appearance(width, height, value, background, color, "FUI", 9, True, 5))
    return button


def keyboard_button(key, x, y, width, height, value=None, toggle=False):
    button = create_button("button_" + key, 28 + (x - 220) * 1.5,
                           56 + (y - 68) * 1.4, width * 1.5, height * 1.4,
                           value or key.upper())
    encoded = json.dumps(key)
    button.AA = PdfDict(D=create_script(f"button_toggle({encoded})")) if toggle else PdfDict(
        D=create_script(f"button_down({encoded})"), U=create_script(f"button_up({encoded})"))
    return button


def build(compiled, output):
    page = create_page(760, 820)
    page.AA = PdfDict(O=create_script(Path(compiled).read_text()))
    fields = []
    terminal_rows = 30  # OOONANA_SERIAL_TERMINAL_LAYOUT
    for index in range(terminal_rows):
        initial = "Ooonana OS PDF 0.6" if index == 29 else "Starting JavaScript..." if index == 28 else ""
        fields.append(create_field(f"field_{index}", 28, 350 + index * 12.3,
                                   704, 12.3, initial, display=True))
    speed = create_field("speed_indicator", 555, 774, 177, 22, "Loading kernel...")
    speed.Ff = 1
    fields.append(speed)
    status = create_field("key_status", 452, 315, 280, 14, "Booting Linux; keep PDF tab visible")
    status.Ff = 1
    fields.append(status)
    command = create_field("key_input", 28, 282, 608, 26)
    command.DA = literal(f"/FMono 11 Tf {rgb(INK)} rg")
    command.AA = PdfDict(K=create_script("pdf_key_input(event)"))
    fields.append(command)
    enter = create_button("command_enter", 646, 282, 86, 26, "Run / Enter", accent=True)
    enter.AA = PdfDict(U=create_script("queue_console_text('\\r'); globalThis.getField('key_input').value = ''"))
    fields.append(enter)

    special = [
        ("Esc", 220, 170, 20, 12, "Esc", False),
        ("`", 220, 148, 12, 16, "`", False),
        ("Backspace", 550, 148, 50, 16, "Backspace", False),
        ("Tab", 220, 128, 24, 16, "Tab", False),
        ("\\", 562, 128, 38, 16, "\\", False),
        ("CapsLock", 220, 108, 30, 16, "Caps", False),
        ("Enter", 542, 108, 58, 16, "Enter", False),
        ("Shift", 220, 88, 44, 16, "Shift", True),
        ("RShift", 530, 88, 70, 16, "RShift", False),
        ("Ctrl", 220, 68, 36, 16, "Ctrl", True),
        ("Alt", 260, 68, 36, 16, "Alt", True),
        ("Space", 300, 68, 174, 16, "Space", False),
        ("RAlt", 480, 68, 36, 16, "Alt", True),
        ("ContextMenu", 522, 68, 36, 16, "Menu", False),
        ("RCtrl", 564, 68, 36, 16, "Ctrl", True),
        ("Home", 608, 148, 32, 16, "Home", False),
        ("Insert", 608, 128, 32, 16, "Ins", False),
        ("Delete", 608, 108, 32, 16, "Del", False),
        ("End", 646, 148, 32, 16, "End", False),
        ("PgUp", 646, 128, 32, 16, "PgUp", False),
        ("PgDn", 646, 108, 32, 16, "PgDn", False),
        ("ArrowUp", 633, 88, 20, 16, "^", False),
        ("ArrowLeft", 608, 68, 20, 16, "<", False),
        ("ArrowDown", 633, 68, 20, 16, "v", False),
        ("ArrowRight", 658, 68, 20, 16, ">", False),
    ]
    fields.extend(keyboard_button(*info) for info in special)
    for keys, x, y, width, height in (([f"F{i}" for i in range(1, 13)], 246, 170, 22, 12),
                                    ("1234567890-=", 238, 148, 20, 16),
                                    ("qwertyuiop[]", 250, 128, 20, 16),
                                    ("asdfghjkl;'", 256, 108, 20, 16),
                                    ("zxcvbnm,./", 270, 88, 20, 16)):
        fields.extend(keyboard_button(key, x + index * (width + 6), y, width, height)
                      for index, key in enumerate(keys))

    architecture = "RISC-V64" if os.environ.get("OOONANA_PDF_BITS") == "64" else "RISC-V32"
    page.Contents = PdfDict(stream="".join([
        f"{rgb(BG)} rg 0 0 760 820 re f\n",
        text(28, 784, 24, "OoonanaPDF"),
        text(28, 766, 9, f"Ooonana OS in PDF  /  {architecture}  /  local, disposable session", MUTED),
        rounded(20, 342, 720, 414, 14, CARD),
        text(32, 737, 9, "TERMINAL", MUTED),
        text(535, 737, 9, "80 columns  /  30 rows", MUTED),
        f"{rgb(KEY)} RG 1 w 28 725 m 732 725 l S\n",
        text(28, 319, 9, "COMMAND INPUT", MUTED),
        rounded(20, 44, 720, 204, 14, CARD),
        text(32, 232, 9, "VIRTUAL KEYBOARD", MUTED),
        text(461, 232, 9, "Click modifier once to toggle; again to release.", MUTED),
        text(28, 22, 8, "Based on linuxpdf  /  Chromium PDF JavaScript required", MUTED),
        text(445, 22, 8, "Boot speed varies; keep PDF tab visible", MUTED),
    ]))
    page.Annots = PdfArray(fields)
    writer = PdfWriter()
    writer.addpage(page)
    writer.trailer.Info = PdfDict(Title=literal("OoonanaPDF"), Author=literal("Ooonana"),
                                  Subject=literal("Interactive native Linux shell"))
    writer.trailer.Root.AcroForm = PdfDict(Fields=PdfArray(fields), NeedAppearances=PdfObject("false"),
                                          DA=literal("/FUI 9 Tf 0.91 0.93 0.96 rg"),
                                          DR=PdfDict(Font=FONTS))
    writer.write(str(output))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate-ooonana-pdf.py COMPILED_JS OUTPUT_PDF")
    build(sys.argv[1], sys.argv[2])
