"""Phase 4: Screenshot preprocessing — strips data-URL prefix and validates format.

PaddleOCR (full OCR) requires Python ≤ 3.11; Gemini vision handles text extraction instead.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field


@dataclass
class OCRResult:
    text: str
    bbox: list[int]  # [x, y, w, h]
    confidence: float


@dataclass
class ScreenContext:
    raw_screenshot_b64: str   # clean base64, no data-URL prefix
    media_type: str           # "image/png" | "image/jpeg" | "image/webp"
    ocr_results: list[OCRResult] = field(default_factory=list)
    visible_text: list[str] = field(default_factory=list)
    active_application: str | None = None
    active_file: str | None = None


def process_screenshot(screenshot_b64: str) -> ScreenContext:
    """Strip data-URL prefix, detect media type, validate base64."""
    media_type = "image/png"

    if screenshot_b64.startswith("data:"):
        header, screenshot_b64 = screenshot_b64.split(",", 1)
        if "jpeg" in header or "jpg" in header:
            media_type = "image/jpeg"
        elif "webp" in header:
            media_type = "image/webp"

    try:
        base64.b64decode(screenshot_b64, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 screenshot: {exc}") from exc

    return ScreenContext(
        raw_screenshot_b64=screenshot_b64,
        media_type=media_type,
    )
