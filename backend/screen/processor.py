"""Phase 4: OpenCV preprocessing + PaddleOCR text extraction."""
from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass
class OCRResult:
    text: str
    bbox: list[int]  # [x, y, w, h]
    confidence: float


@dataclass
class ScreenContext:
    raw_screenshot_b64: str
    ocr_results: list[OCRResult]
    visible_text: list[str]
    active_application: str | None = None
    active_file: str | None = None


def process_screenshot(screenshot_b64: str) -> ScreenContext:
    """Decode screenshot, run OpenCV preprocessing, run OCR.

    Implemented in Phase 4. Currently returns a stub.
    """
    return ScreenContext(
        raw_screenshot_b64=screenshot_b64,
        ocr_results=[],
        visible_text=[],
        active_application=None,
        active_file=None,
    )
