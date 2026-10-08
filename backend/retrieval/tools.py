"""Retrieval tools exposed to the agent. Phases 6 and 9."""
from __future__ import annotations

import platform
import re
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from database import get_engine
from database.models import Symbol, ProjectFile, Project


# ---------------------------------------------------------------------------
# Phase 6: Active file detection
# ---------------------------------------------------------------------------

def get_active_file() -> dict:
    """Detect the file currently open in VS Code (macOS only via AppleScript)."""
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


# ---------------------------------------------------------------------------
# Phase 9: Code retrieval
# ---------------------------------------------------------------------------

def get_file(path: str) -> dict:
    """Return the full content of a file."""
    try:
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
        return {"path": path, "content": content, "lines": len(content.splitlines())}
    except OSError as e:
        return {"path": path, "error": str(e)}


def search_project(query: str, top_k: int = 5) -> list[dict]:
    """Semantic search over the indexed project using embeddings."""
    try:
        from indexing.embeddings import search_embeddings
        with Session(get_engine()) as session:
            return search_embeddings(query, session, top_k=top_k)
    except Exception:
        return []


def find_definition(symbol: str) -> dict | None:
    """Return the definition location of a symbol from the tree-sitter index."""
    try:
        with Session(get_engine()) as session:
            sym = (
                session.query(Symbol)
                .filter(Symbol.name == symbol)
                .first()
            )
            if not sym:
                return None
            return {
                "name": sym.name,
                "kind": sym.kind,
                "file": sym.file.path,
                "line_start": sym.line_start,
                "line_end": sym.line_end,
            }
    except Exception:
        return None


def find_references(symbol: str) -> list[dict]:
    """Find all references to a symbol using regex across indexed files."""
    try:
        with Session(get_engine()) as session:
            # Get the project root from any indexed project
            project = session.query(Project).first()
            if not project:
                return []

            root = Path(project.root_path)
            pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
            results = []

            for pf in project.files:
                filepath = root / pf.path
                try:
                    lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
                except OSError:
                    continue

                for i, line in enumerate(lines, start=1):
                    if pattern.search(line):
                        results.append({
                            "file": pf.path,
                            "line": i,
                            "text": line.strip(),
                        })

            return results
    except Exception:
        return []


def get_screen() -> dict:
    raise NotImplementedError("Phase 4 — use screen.processor directly")


def get_project_structure() -> dict:
    raise NotImplementedError("Use /api/v1/project/structure endpoint")
