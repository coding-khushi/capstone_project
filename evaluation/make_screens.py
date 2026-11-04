"""Generate the benchmark screenshots used by evaluate.py.

Each screen is a 1280x720 editor-style image built from REAL code in this
repository (or a terminal traceback), so the ground truth is known exactly.
Run once from the repo root:  backend/venv/Scripts/python.exe evaluation/make_screens.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).parent / "screens"
FONT_PATH = "C:/Windows/Fonts/consola.ttf"

BG, TITLE_BG, GUTTER, TEXT, DIM = "#1e1e1e", "#323233", "#858585", "#d4d4d4", "#9d9d9d"
W, H, LINE_H = 1280, 720, 22


def _snippet(rel_path: str, start_marker: str, n_lines: int) -> tuple[int, list[str]]:
    """Return (1-based start line, lines) starting at the first line containing start_marker."""
    lines = (ROOT / rel_path).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if start_marker in line:
            return i + 1, lines[i:i + n_lines]
    raise ValueError(f"{start_marker!r} not found in {rel_path}")


def _editor(name: str, title: str, start: int, lines: list[str]) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 16)
    d.rectangle([0, 0, W, 34], fill=TITLE_BG)
    d.text((W // 2, 17), title, font=font, fill=DIM, anchor="mm")
    y = 50
    for i, line in enumerate(lines):
        d.text((14, y), f"{start + i:>4}", font=font, fill=GUTTER)
        d.text((70, y), line, font=font, fill=TEXT)
        y += LINE_H
    img.save(OUT / name)


def _terminal(name: str, title: str, lines: list[str]) -> None:
    img = Image.new("RGB", (W, H), "#0c0c0c")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 16)
    d.rectangle([0, 0, W, 34], fill=TITLE_BG)
    d.text((W // 2, 17), title, font=font, fill=DIM, anchor="mm")
    y = 50
    for line in lines:
        colour = "#f14c4c" if "Error" in line else "#cccccc"
        d.text((14, y), line, font=font, fill=colour)
        y += LINE_H
    img.save(OUT / name)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    vs = " - capstone_project - Visual Studio Code"

    s, l = _snippet("backend/api/routes.py", "def query(", 22)
    _editor("routes_query.png", "routes.py" + vs, s, l)

    s, l = _snippet("backend/retrieval/tools.py", "def search_project(", 31)
    _editor("tools_search_find.png", "tools.py" + vs, s, l)

    s, l = _snippet("backend/ai/context_manager.py", "_INTERNAL_NOTE_RE =", 6)
    _editor("strip_notes.png", "context_manager.py" + vs, s, l)

    s, l = _snippet("backend/debug_logger.py", "def is_enabled", 3)
    _editor("debug_enabled.png", "debug_logger.py" + vs, s, l)

    _terminal("traceback.png", "Windows PowerShell", [
        "PS C:\\shop> python checkout.py",
        "Traceback (most recent call last):",
        '  File "C:\\shop\\checkout.py", line 14, in <module>',
        "    total = subtotal + shipping_cost(order)",
        "            ~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~",
        "TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'",
        "PS C:\\shop> ",
    ])
    print(f"Screens written to {OUT}")


if __name__ == "__main__":
    main()
