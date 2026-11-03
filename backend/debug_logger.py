"""Debug logger — records Percept interactions to debug_sessions/debug_log.md.

OFF by default for privacy: questions, answers and screenshots are only written
to disk when PERCEPT_DEBUG_LOG=1 is set in backend/.env.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "debug_sessions"
LOG_FILE = LOG_DIR / "debug_log.md"
SCREENSHOTS_DIR = LOG_DIR / "screenshots"

_entry_count = 0


def is_enabled() -> bool:
    return os.getenv("PERCEPT_DEBUG_LOG", "0").strip().lower() in ("1", "true", "yes", "on")


def _ensure_dirs():
    LOG_DIR.mkdir(exist_ok=True)
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# Percept Debug Log\n\n"
            "> Auto-generated. Delete `debug_logger.py` and its import in `api/routes.py` when done.\n\n"
            "---\n\n"
        )


def _save_screenshot(b64: str, entry_id: int) -> str | None:
    try:
        # Strip data-URL prefix if present
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        ext = "jpg" if len(img_bytes) > 3 and img_bytes[:2] == b"\xff\xd8" else "png"
        fname = f"screenshot_{entry_id:04d}.{ext}"
        path = SCREENSHOTS_DIR / fname
        path.write_bytes(img_bytes)
        return f"screenshots/{fname}"
    except Exception:
        return None


def log_interaction(
    question: str,
    screenshot_b64: str | None,
    permitted_files: list[str],
    history: list[dict],
    answer: str,
    tools_used: list[str],
    sources: list[str],
    suggested_files: list[str],
    permission_required: list[str],
) -> None:
    global _entry_count
    if not is_enabled():
        return
    _ensure_dirs()
    _entry_count += 1
    entry_id = _entry_count
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    lines.append(f"## Entry #{entry_id} — {ts}\n")

    # Question
    lines.append(f"### Question\n{question}\n")

    # Screenshot
    if screenshot_b64:
        img_path = _save_screenshot(screenshot_b64, entry_id)
        if img_path:
            lines.append(f"### Screenshot\n![screenshot]({img_path})\n")
        else:
            lines.append("### Screenshot\n_(present but could not be saved)_\n")
    else:
        lines.append("### Screenshot\n_(none)_\n")

    # Permitted / loaded files
    if permitted_files:
        lines.append("### Permitted Files (loaded context)")
        for f in permitted_files:
            lines.append(f"- `{f}`")
        lines.append("")
    else:
        lines.append("### Permitted Files\n_(none)_\n")

    # Recent conversation history sent to the model
    if history:
        lines.append("### History Sent to Model")
        for msg in history:
            role_label = "User" if msg.get("role") == "user" else "Percept"
            text = msg.get("text", "").strip()
            # Truncate very long history entries to keep the log readable
            if len(text) > 300:
                text = text[:300] + "…"
            lines.append(f"**{role_label}:** {text}\n")
    else:
        lines.append("### History Sent to Model\n_(none — first message)_\n")

    # Tools Gemini called
    if tools_used:
        lines.append(f"### Tools Used\n{', '.join(tools_used)}\n")

    # Sources referenced
    if sources:
        lines.append("### Sources")
        for s in sources:
            lines.append(f"- `{s}`")
        lines.append("")

    # Suggested files (Gemini spotted on screen but not yet permitted)
    if suggested_files:
        lines.append("### Suggested Files (spotted, not yet permitted)")
        for s in suggested_files:
            lines.append(f"- `{s}`")
        lines.append("")

    # Permission required mid-loop
    if permission_required:
        lines.append("### Permission Required")
        for p in permission_required:
            lines.append(f"- `{p}`")
        lines.append("")

    # Answer
    lines.append(f"### Answer\n{answer}\n")
    lines.append("---\n")

    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
