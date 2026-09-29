"""Phase 9: Retrieval tools exposed to the agent.

Each function matches a named tool in the agent's tool schema.
Implementations are filled in per phase.
"""
from __future__ import annotations


def get_screen() -> dict:
    """Return current screen OCR + screenshot."""
    raise NotImplementedError("Phase 4")


def get_active_file() -> dict:
    """Return the file currently open/focused."""
    raise NotImplementedError("Phase 6")


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
