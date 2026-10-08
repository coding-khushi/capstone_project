"""Phase 7: Tree-sitter project indexer — walks a directory and stores symbols in SQLite."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.orm import Session

from database.models import Project, ProjectFile, Symbol, init_db
from indexing.embeddings import embed_and_store

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "release", ".mypy_cache",
}

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = init_db()
    return _engine


# ---------------------------------------------------------------------------
# Tree-sitter language loading (graceful degradation if not installed)
# ---------------------------------------------------------------------------

_LANGUAGES: dict[str, object] = {}

try:
    from tree_sitter import Language, Parser as TSParser

    try:
        import tree_sitter_python as _tspy
        _LANGUAGES[".py"] = Language(_tspy.language())
    except Exception:
        pass

    try:
        import tree_sitter_javascript as _tsjs
        _LANGUAGES[".js"] = Language(_tsjs.language())
        _LANGUAGES[".jsx"] = _LANGUAGES[".js"]
    except Exception:
        pass

    try:
        import tree_sitter_typescript as _tsts
        _LANGUAGES[".ts"] = Language(_tsts.language_typescript())
        _LANGUAGES[".tsx"] = Language(_tsts.language_tsx())
    except Exception:
        pass

    TREE_SITTER_OK = bool(_LANGUAGES)
except ImportError:
    TREE_SITTER_OK = False
    TSParser = None  # type: ignore


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------

_KIND_MAP = {
    "function_definition": "function",
    "function_declaration": "function",
    "class_definition": "class",
    "class_declaration": "class",
    "method_definition": "method",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "decorated_definition": "function",
}

_DEF_TYPES = set(_KIND_MAP)


def _extract_symbols(root_node) -> list[dict]:
    results: list[dict] = []

    def walk(node):
        if node.type in _DEF_TYPES:
            name_node = node.child_by_field_name("name")
            if name_node:
                results.append({
                    "name": name_node.text.decode("utf8"),
                    "kind": _KIND_MAP[node.type],
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                })
        for child in node.children:
            walk(child)

    walk(root_node)
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_project_path(root_path: str) -> dict:
    """Walk root_path, parse supported files with tree-sitter, persist to SQLite."""
    root = Path(root_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root_path}")

    engine = _get_engine()
    stats = {"files_indexed": 0, "symbols_found": 0, "tree_sitter": TREE_SITTER_OK}

    with Session(engine) as session:
        project = session.query(Project).filter_by(root_path=str(root)).first()
        if project:
            for f in list(project.files):
                session.delete(f)
            session.flush()
        else:
            project = Project(name=root.name, root_path=str(root))
            session.add(project)
            session.flush()

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            for filename in filenames:
                filepath = Path(dirpath) / filename
                ext = filepath.suffix.lower()
                if ext not in _LANGUAGES:
                    continue

                try:
                    source = filepath.read_bytes()
                except OSError:
                    continue

                rel_path = str(filepath.relative_to(root))
                lang = ext.lstrip(".")
                pf = ProjectFile(project_id=project.id, path=rel_path, language=lang)
                session.add(pf)
                session.flush()

                if TREE_SITTER_OK and ext in _LANGUAGES:
                    parser = TSParser(_LANGUAGES[ext])
                    tree = parser.parse(source)
                    symbols = _extract_symbols(tree.root_node)
                    for sym in symbols:
                        session.add(Symbol(
                            file_id=pf.id,
                            name=sym["name"],
                            kind=sym["kind"],
                            line_start=sym["line_start"],
                            line_end=sym["line_end"],
                        ))
                    stats["symbols_found"] += len(symbols)

                stats["files_indexed"] += 1

        # Phase 8: generate and store embeddings
        try:
            stats["embeddings"] = embed_and_store(project.id, session)
        except Exception:
            stats["embeddings"] = 0  # sentence-transformers not installed yet

        session.commit()

    return stats


def get_project_structure(root_path: str) -> dict:
    """Return the symbol index for an already-indexed project."""
    root = Path(root_path).resolve()
    engine = _get_engine()

    with Session(engine) as session:
        project = session.query(Project).filter_by(root_path=str(root)).first()
        if not project:
            return {"error": "Project not indexed yet. POST /api/v1/index?project_path=... first."}

        return {
            pf.path: [
                {"name": s.name, "kind": s.kind, "line": s.line_start}
                for s in pf.symbols
            ]
            for pf in project.files
        }
