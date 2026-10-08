"""Phase 5: Gemini API. Phase 10: context routing + retrieval injection."""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field

import google.generativeai as genai

from screen.processor import ScreenContext

GEMINI_MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = (
    "You are Percept, an AI assistant embedded in the user's desktop. "
    "You can see the user's screen and help them understand what's on it, "
    "answer questions about their code, and provide context-aware assistance. "
    "Be concise and direct. When analysing code, focus on what the user is asking."
)

# Keywords that signal the user is asking about their codebase
_RETRIEVAL_TRIGGERS = {
    "function", "class", "method", "file", "module", "import",
    "how does", "where is", "what does", "implementation", "defined",
    "definition", "reference", "called", "returns", "parameter",
    "variable", "interface", "type", "error", "bug", "why is",
}


# ---------------------------------------------------------------------------
# Phase 10: Context decision
# ---------------------------------------------------------------------------

@dataclass
class ContextDecision:
    screen_sufficient: bool
    missing_symbols: list[str] = field(default_factory=list)
    retrieval_queries: list[str] = field(default_factory=list)
    reasoning: str = ""


def decide(question: str, screen: ScreenContext | None) -> ContextDecision:
    """Decide whether the screenshot alone is enough or retrieval is needed."""
    q_lower = question.lower()

    # Backtick-quoted symbols are an explicit code reference
    symbols = re.findall(r'`(\w+)`', question)

    needs_retrieval = (
        bool(symbols)
        or any(trigger in q_lower for trigger in _RETRIEVAL_TRIGGERS)
    )

    if needs_retrieval:
        return ContextDecision(
            screen_sufficient=False,
            missing_symbols=symbols,
            retrieval_queries=[question],
            reasoning="Question references code constructs — adding project context.",
        )

    return ContextDecision(
        screen_sufficient=True,
        reasoning="Visual context appears sufficient.",
    )


# ---------------------------------------------------------------------------
# Phase 5 + 9 + 10: Ask Gemini with optional retrieval context
# ---------------------------------------------------------------------------

def ask_gemini(
    question: str,
    screen: ScreenContext | None = None,
    active_file: str | None = None,
) -> tuple[str, list[str], list[str]]:
    """Send question to Gemini, injecting retrieval context when needed.

    Returns (answer, tools_used, sources).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return (
            "GOOGLE_API_KEY is not set. "
            "Add it to backend/.env and restart the server.",
            [], [],
        )

    # Phase 10: routing decision
    decision = decide(question, screen)

    # Phase 9: retrieve project context if needed
    retrieval_text = ""
    sources: list[str] = []
    tools_used: list[str] = []

    if screen and screen.raw_screenshot_b64:
        tools_used.append("screenshot")

    if not decision.screen_sufficient:
        from retrieval.tools import search_project, find_definition

        # Semantic search
        results = search_project(question, top_k=4)
        if results:
            tools_used.append("project_search")
            snippets = []
            for r in results:
                sources.append(r["file"])
                snippets.append(
                    f"// {r['file']} (lines {r.get('line_start', '?')}-{r.get('line_end', '?')})\n"
                    f"{r['text']}"
                )
            retrieval_text = "\n\n".join(snippets)

        # Symbol lookup for backtick-quoted names
        for sym in decision.missing_symbols:
            defn = find_definition(sym)
            if defn and defn["file"] not in sources:
                sources.append(defn["file"])
                retrieval_text += (
                    f"\n\nDefinition of `{sym}`: "
                    f"{defn['file']} line {defn['line_start']} ({defn['kind']})"
                )

    # Build Gemini request
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    parts: list = []

    if screen and screen.raw_screenshot_b64:
        parts.append({
            "mime_type": screen.media_type,
            "data": base64.b64decode(screen.raw_screenshot_b64),
        })

    text_parts: list[str] = []
    if active_file:
        text_parts.append(f"Active file: {active_file}")
    if retrieval_text:
        text_parts.append(f"Relevant code from project:\n{retrieval_text}")
    text_parts.append(question or "What do you see on my screen?")

    parts.append("\n\n".join(text_parts))

    response = model.generate_content(parts)
    return response.text, tools_used, list(dict.fromkeys(sources))  # deduplicated
