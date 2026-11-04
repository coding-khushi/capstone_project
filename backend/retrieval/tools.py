"""Retrieval tools exposed to the agent. Phases 6 and 9."""
from __future__ import annotations

import io
import os
import platform
import re
import subprocess
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from database import get_engine
from database.models import Symbol, ProjectFile, Project

# Optional document-reading libraries — checked once at import time
try:
    from pptx import Presentation as _PptxPresentation  # type: ignore
    _HAS_PPTX = True
except ImportError:
    _HAS_PPTX = False

try:
    import pypdf as _pypdf  # type: ignore
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

try:
    from docx import Document as _DocxDocument  # type: ignore
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False


# ---------------------------------------------------------------------------
# Phase 6: Active file detection
# ---------------------------------------------------------------------------

def get_active_file() -> dict:
    """Detect the file currently open in VS Code (macOS via AppleScript, Windows via Win32 API)."""
    system = platform.system()
    if system == "Windows":
        return _get_active_file_windows()
    if system != "Darwin":
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


def _parse_vscode_title(title: str) -> str | None:
    """Extract the file name from a VS Code window title.

    VS Code titles look like "● main.py - capstone_project - Visual Studio Code"
    (the dot marks unsaved changes). Returns None for non-file views like "Welcome".
    """
    if not title.endswith("Visual Studio Code"):
        return None
    first = title.split(" - ")[0].lstrip("●○ ").strip()
    if not first or first == "Visual Studio Code" or "." not in first:
        return None
    return first


def _get_active_file_windows() -> dict:
    """Find the most recently used VS Code window on Windows and parse its title.

    EnumWindows walks windows in z-order (front to back), so the first VS Code
    window found is the one the user used last — even when Percept itself is in front.
    """
    try:
        import ctypes

        user32 = ctypes.windll.user32
        found: list[str] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _visit(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value.endswith("Visual Studio Code"):
                found.append(buf.value)
                return False  # stop at the frontmost VS Code window
            return True

        user32.EnumWindows(_visit, 0)
        name = _parse_vscode_title(found[0]) if found else None
        if name is None:
            return {"path": None, "app": None}
        return {"path": name, "app": "Visual Studio Code"}
    except Exception:
        return {"path": None, "app": None}


# ---------------------------------------------------------------------------
# Phase 9: Code retrieval
# ---------------------------------------------------------------------------

def get_file(path: str) -> dict:
    """Return the full content of a file."""
    return read_document(path)


def _read_bytes(path: str) -> bytes:
    """Read a file's bytes, even when another app (e.g. PowerPoint) has it open.

    Office apps on Windows open documents in a way that makes a normal open()
    fail with a sharing violation. In that case, retry with full Win32 sharing
    (read + write + delete), which only reads and never blocks the other app.
    """
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except PermissionError:
        if platform.system() != "Windows":
            raise
    import ctypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = ctypes.c_void_p
    GENERIC_READ, SHARE_ALL, OPEN_EXISTING = 0x80000000, 0x7, 3
    handle = kernel32.CreateFileW(path, GENERIC_READ, SHARE_ALL, None, OPEN_EXISTING, 0, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise PermissionError(f"Could not open {path} (Windows error {kernel32.GetLastError()})")
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    with os.fdopen(fd, "rb") as fh:  # closes the handle too
        return fh.read()


def read_document(path: str) -> dict:
    """Read a file for context. Handles .pptx, .pdf, .docx, .zip, and plain text."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        data = _read_bytes(path)
    except OSError as e:
        return {"path": path, "error": str(e)}

    if ext == '.pptx':
        if not _HAS_PPTX:
            return {"path": path, "error": "python-pptx not available (pip install python-pptx)"}
        try:
            prs = _PptxPresentation(io.BytesIO(data))
            slide_texts = []
            for i, slide in enumerate(prs.slides, 1):
                texts = [
                    shape.text.strip()
                    for shape in slide.shapes
                    if hasattr(shape, 'text') and shape.text.strip()
                ]
                if texts:
                    slide_texts.append(f"[Slide {i}]\n" + "\n".join(texts))
            content = "\n\n".join(slide_texts) or "(No text found in presentation)"
            return {"path": path, "content": content, "lines": len(slide_texts)}
        except Exception as e:
            return {"path": path, "error": str(e)}

    if ext == '.pdf':
        if not _HAS_PYPDF:
            return {"path": path, "error": "pypdf not available (pip install pypdf)"}
        try:
            reader = _pypdf.PdfReader(io.BytesIO(data))
            pages = []
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Page {i}]\n{text.strip()}")
            content = "\n\n".join(pages) or "(No text found in PDF)"
            return {"path": path, "content": content, "lines": len(pages)}
        except Exception as e:
            return {"path": path, "error": str(e)}

    if ext in ('.docx', '.doc'):
        if not _HAS_DOCX:
            return {"path": path, "error": "python-docx not available (pip install python-docx)"}
        try:
            doc = _DocxDocument(io.BytesIO(data))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            content = "\n".join(paragraphs) or "(No text found in document)"
            return {"path": path, "content": content, "lines": len(paragraphs)}
        except Exception as e:
            return {"path": path, "error": str(e)}

    if ext == '.zip':
        try:
            parts = []
            with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
                for name in zf.namelist():
                    if any(name.endswith(ext) for ext in ('.txt', '.md', '.py', '.js', '.ts', '.json', '.csv')):
                        try:
                            text = zf.read(name).decode('utf-8', errors='ignore').strip()
                            if text:
                                parts.append(f"[{name}]\n{text[:3000]}")
                        except Exception:
                            continue
            content = "\n\n".join(parts) or "(No readable text files found in zip)"
            return {"path": path, "content": content, "lines": len(parts)}
        except Exception as e:
            return {"path": path, "error": str(e)}

    # Plain text fallback (.txt, .md, .py, .js, .ts, .csv, etc.)
    content = data.decode("utf-8", errors="ignore")
    return {"path": path, "content": content, "lines": len(content.splitlines())}


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
