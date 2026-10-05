#!/usr/bin/env python3
"""Repo-native, opaque SVG application icons; shared 64px geometry/palette."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = {
    "ai": ("#c6b4ff", '<path d="M25 20a8 8 0 0 0-11 8 8 8 0 0 0 1 13 8 8 0 0 0 10 7V20zm14 0a8 8 0 0 1 11 8 8 8 0 0 1-1 13 8 8 0 0 1-10 7V20zM25 29h-6m6 10h-7m21-10h6m-6 10h7"/>'),
    "openvino": ("#c6b4ff", '<rect x="18" y="18" width="28" height="28" rx="7"/><path d="M25 25h14v14H25zm-1-13v6m8-6v6m8-6v6m-16 28v6m8-6v6m8-6v6M12 24h6m-6 8h6m-6 8h6m28-16h6m-6 8h6m-6 8h6"/>'),
    "wifi": ("#8cbcff", '<path d="M12 25a31 31 0 0 1 40 0M19 33a20 20 0 0 1 26 0m-19 8a9 9 0 0 1 12 0"/><circle cx="32" cy="48" r="2" fill="currentColor" stroke="none"/>'),
    "bluetooth": ("#a3baff", '<path d="M31 13v38l13-12-24-16m11-10 13 12-24 16"/>'),
    "settings": ("#c0c8d4", '<circle cx="32" cy="32" r="9"/><path d="m27 13-1 5-5 3-5-1-4 7 4 4v6l-4 4 4 7 5-1 5 3 1 5h10l1-5 5-3 5 1 4-7-4-4v-6l4-4-4-7-5 1-5-3-1-5z" transform="translate(0 -3)"/>'),
    "task-manager": ("#93d5e5", '<rect x="13" y="15" width="38" height="31" rx="6"/><path d="M19 32h7l4-8 5 15 5-8h5M26 52h12m-6-6v6"/>'),
    "health": ("#82d2b2", '<path d="M32 51C8 35 11 18 23 18c4 0 7 2 9 6 2-4 5-6 9-6 12 0 15 17-9 33zM16 33h9l4-7 5 13 4-6h10"/>'),
    "updates": ("#8cbcff", '<path d="M17 26a16 16 0 0 1 28-6l5 6m0-12v12H38M47 38a16 16 0 0 1-28 6l-5-6m0 12V38h12"/>'),
    "music": ("#ff9ab2", '<path d="M27 43V20l22-5v23M27 27l22-5"/><ellipse cx="21" cy="45" rx="6" ry="5"/><ellipse cx="43" cy="40" rx="6" ry="5"/>'),
    "notifications": ("#ffd079", '<path d="M20 28a12 12 0 0 1 24 0v13l5 5H15l5-5zm7 23a6 6 0 0 0 10 0m-5-36v-3"/>'),
    "setup": ("#82d2b2", '<rect x="16" y="13" width="32" height="40" rx="7"/><path d="m23 27 4 4 9-10m-13 20h18m-18 6h10"/>'),
    "installer": ("#ffd079", '<rect x="13" y="37" width="38" height="15" rx="5"/><path d="M32 12v26m-9-9 9 9 9-9m0 16h3"/>'),
    "packages": ("#ffd079", '<path d="m32 13 20 11v23L32 58 12 47V24zm-20 11 20 11 20-11M32 35v23M22 18l20 11v10" transform="translate(0 -4)"/>'),
    "apps": ("#c4a9ff", '<rect x="14" y="14" width="15" height="15" rx="4"/><rect x="35" y="14" width="15" height="15" rx="4"/><rect x="14" y="35" width="15" height="15" rx="4"/><rect x="35" y="35" width="15" height="15" rx="4"/>'),
    "editor": ("#82d2b2", '<path d="m18 41 23-23a5 5 0 0 1 7 7L25 48l-10 3zm19-19 7 7M18 41l7 7"/>'),
    "files": ("#ffd079", '<path d="M12 23v-5h17l5 6h18v25H12zm0 8h40"/>'),
    "terminal": ("#c0c8d4", '<rect x="11" y="15" width="42" height="34" rx="7"/><path d="m20 25 8 7-8 7m14 0h10"/>'),
    "controls": ("#ffd079", '<path d="M14 20h36M14 32h36M14 44h36"/><circle cx="24" cy="20" r="5" fill="#1b1f26"/><circle cx="42" cy="32" r="5" fill="#1b1f26"/><circle cx="27" cy="44" r="5" fill="#1b1f26"/>'),
    "game": ("#ff9ab2", '<path d="M19 23h26c5 0 9 7 9 17 0 7-7 9-11 3l-3-4H24l-3 4c-4 6-11 4-11-3 0-10 4-17 9-17zM22 28v10m-5-5h10"/><circle cx="41" cy="30" r="2" fill="currentColor" stroke="none"/><circle cx="46" cy="35" r="2" fill="currentColor" stroke="none"/>'),
}

if __name__ == "__main__":
    output = ROOT / "packages/ooonana/usr/share/icons/hicolor/scalable/apps"
    output.mkdir(parents=True, exist_ok=True)
    for name, (color, glyph) in ICONS.items():
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect x="2" y="2" width="60" height="60" rx="16" fill="#1b1f26" stroke="#343b46" stroke-width="1.5"/><g color="{color}" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>\n'
        (output / f"ooonana-{name}.svg").write_text(svg, encoding="utf-8")
    print(f"Built {len(ICONS)} native app icons")
