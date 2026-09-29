"""Phase 10: Decides whether screen context is sufficient or retrieval is needed."""
from __future__ import annotations

from dataclasses import dataclass, field
from screen.processor import ScreenContext


@dataclass
class ContextDecision:
    screen_sufficient: bool
    missing_symbols: list[str] = field(default_factory=list)
    retrieval_queries: list[str] = field(default_factory=list)
    reasoning: str = ""


def decide(question: str, screen: ScreenContext) -> ContextDecision:
    """Analyse question + screen and decide what extra context is needed.

    Implemented in Phase 10. Stub returns 'screen sufficient' for now.
    """
    return ContextDecision(screen_sufficient=True, reasoning="Phase 10 not yet implemented")
