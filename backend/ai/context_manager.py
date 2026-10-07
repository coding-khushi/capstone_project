"""Phase 5: Claude API integration. Phase 10 stub for context routing."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic

from screen.processor import ScreenContext

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


def ask_claude(
    question: str,
    screen: ScreenContext | None = None,
    active_file: str | None = None,
) -> tuple[str, list[str]]:
    """Send question (+ optional screenshot) to Claude. Returns (answer, tools_used)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "ANTHROPIC_API_KEY is not set. "
            "Create backend/.env with ANTHROPIC_API_KEY=sk-ant-... and restart the server.",
            [],
        )

    client = anthropic.Anthropic(api_key=api_key)

    content: list[dict] = []

    if screen and screen.raw_screenshot_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": screen.media_type,
                "data": screen.raw_screenshot_b64,
            },
        })

    user_text = f"Active file: {active_file}\n\n{question}" if active_file else question
    content.append({"type": "text", "text": user_text or "What do you see on my screen?"})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    tools_used = ["screenshot"] if screen and screen.raw_screenshot_b64 else []
    return response.content[0].text, tools_used
