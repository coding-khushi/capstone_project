"""Phase 5: Gemini API integration. Phase 10 stub for context routing."""
from __future__ import annotations

import base64
import os
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


@dataclass
class ContextDecision:
    screen_sufficient: bool
    missing_symbols: list[str] = field(default_factory=list)
    retrieval_queries: list[str] = field(default_factory=list)
    reasoning: str = ""


def decide(question: str, screen: ScreenContext) -> ContextDecision:
    """Stub — Phase 10 will implement smart context routing."""
    return ContextDecision(screen_sufficient=True, reasoning="Phase 10 not yet implemented")


def ask_gemini(
    question: str,
    screen: ScreenContext | None = None,
    active_file: str | None = None,
) -> tuple[str, list[str]]:
    """Send question (+ optional screenshot) to Gemini. Returns (answer, tools_used)."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return (
            "GOOGLE_API_KEY is not set. "
            "Add GOOGLE_API_KEY=your-key to backend/.env and restart the server.",
            [],
        )

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

    user_text = f"Active file: {active_file}\n\n{question}" if active_file else question
    parts.append(user_text or "What do you see on my screen?")

    response = model.generate_content(parts)

    tools_used = ["screenshot"] if screen and screen.raw_screenshot_b64 else []
    return response.text, tools_used
