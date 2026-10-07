"""Retrieval tools exposed to the agent. Phases 6, 9."""
from __future__ import annotations

import platform
import subprocess


def get_screen() -> dict:
    """Return current screen OCR + screenshot."""
    raise NotImplementedError("Phase 4")


def get_active_file() -> dict:
    """Phase 6: Detect the file currently open in VS Code (macOS only via AppleScript)."""
    if platform.system() != "Darwin":
        return {"path": None, "app": None}

    script = """
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell
    if frontApp is "Code" then
        tell application "Visual Studio Code"
            set w to front window
            set doc to name of w
        end tell
        return doc
    else
        return ""
    end if
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        )
        path = result.stdout.strip()
        return {"path": path if path else None, "app": "Visual Studio Code"}
    except Exception:
        return {"path": None, "app": None}


def get_file(path: str) -> dict:
    """Return content of a specific project file."""
    raise NotImplementedError("Phase 9")


def search_project(query: str, top_k: int = 5) -> list[dict]:
    """Semantic + keyword search over the indexed project."""
    raise NotImplementedError("Phase 9")


def find_definition(symbol: str) -> dict | None:
    """Return the definition location of a symbol via Tree-sitter index."""
    raise NotImplementedError("Phase 9")


def find_references(symbol: str) -> list[dict]:
    """Return all reference locations of a symbol."""
    raise NotImplementedError("Phase 9")


def get_project_structure() -> dict:
    """Return the project file/symbol tree."""
    raise NotImplementedError("Phase 7")
