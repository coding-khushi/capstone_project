<<<<<<< ours
"""Phase 5: Gemini API. Phase 10: context routing + retrieval injection."""
=======
"""Gemini vision integration for Percept."""
>>>>>>> theirs
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv
from google import genai
from google.genai import types

from screen.processor import ScreenContext

load_dotenv()

# Use the Flash model configured for fast screen-aware responses.
GEMINI_MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """
You are Percept, an AI assistant embedded in the user's desktop.

You can see the user's screen through screenshots and help them understand
what is currently visible.

Your responsibilities:
- Understand the screenshot visually.
- Answer questions about applications, UI, errors, text, websites, and code
  visible on the screen.
- Use the active file information when provided.
- If the screenshot contains code, explain or debug the visible code.
- If the screenshot contains an error, identify the likely cause and suggest
  a practical fix.
- Do not pretend to see information that is not visible.
- Be concise and direct.
"""

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


<<<<<<< ours
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

=======
def decide(question: str, screen: ScreenContext) -> ContextDecision:
    """Phase 10 placeholder for smarter context routing."""
    return ContextDecision(
        screen_sufficient=True,
        reasoning="Current implementation uses the supplied screen context.",
    )
>>>>>>> theirs

# ---------------------------------------------------------------------------
# Phase 5 + 9 + 10: Ask Gemini with optional retrieval context
# ---------------------------------------------------------------------------

def ask_gemini(
    question: str,
    screen: ScreenContext | None = None,
    active_file: str | None = None,
<<<<<<< ours
) -> tuple[str, list[str], list[str]]:
    """Send question to Gemini, injecting retrieval context when needed.

    Returns (answer, tools_used, sources).
    """
=======
) -> tuple[str, list[str]]:
    """Send a question and optional screenshot to Gemini."""

>>>>>>> theirs
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return (
            "GOOGLE_API_KEY is not set. "
<<<<<<< ours
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
=======
            "Add GOOGLE_API_KEY to backend/.env and restart the server.",
            [],
        )

    client = genai.Client(api_key=api_key)
>>>>>>> theirs

    contents = []

    # Add screenshot when available.
    if screen and screen.raw_screenshot_b64:
        try:
            image_bytes = base64.b64decode(screen.raw_screenshot_b64)

            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=screen.media_type,
                )
            )
        except Exception as exc:
            return (
                f"I couldn't process the screenshot: {exc}",
                [],
            )

    # Build the user's context.
    context_parts = []

    if active_file:
        context_parts.append(f"Active file: {active_file}")

    if question:
        context_parts.append(f"User question: {question}")
    else:
        context_parts.append(
            "Describe what is currently visible on the screen."
        )

    contents.append("\n\n".join(context_parts))

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )

<<<<<<< ours
    text_parts: list[str] = []
    if active_file:
        text_parts.append(f"Active file: {active_file}")
    if retrieval_text:
        text_parts.append(f"Relevant code from project:\n{retrieval_text}")
    text_parts.append(question or "What do you see on my screen?")

    parts.append("\n\n".join(text_parts))

    response = model.generate_content(parts)
    return response.text, tools_used, list(dict.fromkeys(sources))  # deduplicated
=======
        answer = response.text or "I couldn't generate a response."

        tools_used = []
        if screen and screen.raw_screenshot_b64:
            tools_used.append("screenshot")

        return answer, tools_used

    except Exception as exc:
        return (
            f"Gemini request failed: {exc}",
            [],
        )
>>>>>>> theirs
