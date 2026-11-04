"""Evaluation harness: screen-only vs. screen-plus-retrieval.

Every test case is answered twice by the same Percept agent (ask_gemini):
  * screen_only  - retrieval tools disabled; the model sees only the screenshot.
                   (Equivalent to the user pressing "Skip".)
  * retrieval    - full toolkit enabled and the project's backend files granted,
                   as if the user had pressed "Grant Access".

The agent runs in-process (not over HTTP) so the harness can switch tools off
and count the tokens sent to Gemini without changing the production API.

Metrics per run (the five proposal metrics + the context decision):
  response_accuracy  fraction of expected keyword groups found in the answer
  task_completion    1 if every keyword group was found
  decision_correct   1 if the agent called tools exactly when the case needs them
                     (retrieval mode only - in screen-only mode no tools exist)
  retrieval_hit      1 if the expected file appeared in the retrieved evidence
  latency_ms         wall-clock time for the whole agent loop
  context_tokens     total prompt tokens sent to Gemini across all rounds
  gemini_calls       number of Gemini round trips

Usage (from repo root, backend server NOT required):
  backend/venv/Scripts/python.exe evaluation/evaluate.py            # all cases, both modes
  backend/venv/Scripts/python.exe evaluation/evaluate.py RT-01 SC-02 # selected cases
"""
from __future__ import annotations

import base64
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # percept.db is resolved relative to the backend folder

from google.genai import chats, types  # noqa: E402

from ai import context_manager as cm  # noqa: E402
from screen.processor import ScreenContext  # noqa: E402

TEST_CASES_PATH = EVAL_DIR / "test_cases.json"
SCREENS_DIR = EVAL_DIR / "screens"
RESULTS_PATH = EVAL_DIR / "results.csv"
SUMMARY_PATH = EVAL_DIR / "results_summary.md"

MODES = ("screen_only", "retrieval")
MAX_ATTEMPTS = 3          # retry a run on Gemini/network errors (503, 429, DNS, ...)
RETRY_WAIT_S = 15
CALL_TIMEOUT_MS = 60_000  # per Gemini call, evaluation only

FIELDS = [
    "id", "category", "mode", "requires_retrieval",
    "response_accuracy", "task_completion", "decision_correct", "retrieval_hit",
    "latency_ms", "context_tokens", "gemini_calls", "tools_used", "attempts", "answer",
]

# Files the user "grants" in retrieval mode: every backend source file.
PERMITTED_FILES = sorted(
    str(p) for p in BACKEND.rglob("*.py")
    if "venv" not in p.parts and "__pycache__" not in p.parts
)


# ---------------------------------------------------------------------------
# Instrumentation: count Gemini calls/tokens and capture tool evidence
# ---------------------------------------------------------------------------
_stats = {"calls": 0, "tokens": 0, "evidence": []}
_orig_send = chats.Chat.send_message
_orig_exec = cm._execute_tool
_orig_tools = cm._build_tools
_orig_prompt = cm.SYSTEM_PROMPT

# Without this note the model still "sees" the tool descriptions in the system
# prompt, tries to call them, and returns an empty answer - an unfair baseline.
SCREEN_ONLY_PROMPT = _orig_prompt + (
    "\n\n## Evaluation mode: screen only\n"
    "No tools are available in this conversation. You cannot search, open or read "
    "project files. Answer using only the screenshot and your general knowledge. "
    "If the screen does not contain the answer, say so plainly instead of guessing."
)


def _counting_send(self, message, *args, **kwargs):
    response = _orig_send(self, message, *args, **kwargs)
    _stats["calls"] += 1
    usage = getattr(response, "usage_metadata", None)
    _stats["tokens"] += (getattr(usage, "prompt_token_count", 0) or 0)
    return response


def _recording_exec(name, args, permitted_files, sources):
    text, perm = _orig_exec(name, args, permitted_files, sources)
    _stats["evidence"].append(text)
    return text, perm


_OrigClient = cm.genai.Client


def _client_with_timeout(*args, **kwargs):
    # A stalled connection (e.g. after the laptop sleeps) otherwise hangs forever;
    # the timeout turns it into an API error that run_case retries.
    kwargs.setdefault("http_options", types.HttpOptions(timeout=CALL_TIMEOUT_MS))
    return _OrigClient(*args, **kwargs)


cm.genai.Client = _client_with_timeout
chats.Chat.send_message = _counting_send
cm._execute_tool = _recording_exec


def _load_screen(name: str | None) -> ScreenContext | None:
    if not name:
        return None
    b64 = base64.b64encode((SCREENS_DIR / name).read_bytes()).decode()
    return ScreenContext(raw_screenshot_b64=b64, media_type="image/png")


def _keyword_score(answer: str, groups: list[list[str]]) -> float:
    if not groups:
        return 1.0
    hits = sum(any(_keyword_found(answer, k) for k in group) for group in groups)
    return hits / len(groups)


def _keyword_found(answer: str, keyword: str) -> bool:
    """Whole-word, case-insensitive match, so "4" does not match "46".
    A trailing "*" marks a prefix keyword ("remov*" matches remove/removes/removing)."""
    prefix = keyword.endswith("*")
    word = re.escape(keyword.rstrip("*"))
    pattern = r"(?<!\w)" + word + ("" if prefix else r"(?!\w)")
    return re.search(pattern, answer, flags=re.IGNORECASE) is not None


def _is_api_error(answer: str) -> bool:
    """Gemini/network failure (overload, timeout, no internet) rather than a real answer."""
    return answer.startswith("Gemini API error")


def run_case(case: dict, mode: str) -> dict:
    cm._build_tools = (lambda: None) if mode == "screen_only" else _orig_tools
    cm.SYSTEM_PROMPT = SCREEN_ONLY_PROMPT if mode == "screen_only" else _orig_prompt
    permitted = [] if mode == "screen_only" else PERMITTED_FILES
    screen = _load_screen(case.get("screen"))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        _stats.update(calls=0, tokens=0, evidence=[])
        start = time.monotonic()
        answer, tools_used, sources, _ = cm.ask_gemini(
            question=case["question"], screen=screen, permitted_files=permitted,
        )
        latency_ms = (time.monotonic() - start) * 1000
        if not _is_api_error(answer) or attempt == MAX_ATTEMPTS:
            break
        print(f"    Gemini/network error, retrying in {RETRY_WAIT_S}s ...")
        time.sleep(RETRY_WAIT_S)

    tools_used = [t for t in tools_used if t != "screenshot"]  # input, not a retrieval tool
    acc = _keyword_score(answer, case["expected_keywords"])
    evidence = " ".join(_stats["evidence"] + list(sources))
    expected_file = case.get("expected_file")

    if mode == "retrieval":
        decision = int(bool(tools_used) == case["requires_retrieval"])
    else:
        decision = ""
    retrieval_hit = int(expected_file in evidence) if (expected_file and mode == "retrieval") else ""

    return {
        "id": case["id"],
        "category": case["category"],
        "mode": mode,
        "requires_retrieval": case["requires_retrieval"],
        "response_accuracy": round(acc, 2),
        "task_completion": int(acc == 1.0),
        "decision_correct": decision,
        "retrieval_hit": retrieval_hit,
        "latency_ms": round(latency_ms),
        "context_tokens": _stats["tokens"],
        "gemini_calls": _stats["calls"],
        "tools_used": ",".join(tools_used),
        "attempts": attempt,
        "answer": " ".join(answer.split()),
    }


def _mean(rows: list[dict], key: str) -> str:
    vals = [float(r[key]) for r in rows if r[key] != ""]
    return f"{sum(vals) / len(vals):.2f}" if vals else "-"


def write_summary(rows: list[dict]) -> str:
    ok = [r for r in rows if not _is_api_error(r["answer"])]
    lines = [
        "# Percept evaluation summary",
        "",
        f"Runs: {len(rows)} ({len(rows) - len(ok)} failed with Gemini/network errors and are excluded below).",
        "",
        "| Case type | Mode | Runs | Response accuracy | Task completion | Decision correct "
        "| Retrieval hit | Mean latency (s) | Mean context tokens | Mean Gemini calls |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for category in ("screen_sufficient", "needs_retrieval"):
        for mode in MODES:
            sub = [r for r in ok if r["category"] == category and r["mode"] == mode]
            if not sub:
                continue
            latency = _mean(sub, "latency_ms")
            latency = f"{float(latency) / 1000:.1f}" if latency != "-" else "-"
            lines.append(
                f"| {category} | {mode} | {len(sub)} | {_mean(sub, 'response_accuracy')} "
                f"| {_mean(sub, 'task_completion')} | {_mean(sub, 'decision_correct')} "
                f"| {_mean(sub, 'retrieval_hit')} | {latency} "
                f"| {_mean(sub, 'context_tokens')} | {_mean(sub, 'gemini_calls')} |"
            )
    text = "\n".join(lines) + "\n"
    SUMMARY_PATH.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    cases = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    wanted = set(sys.argv[1:])
    if wanted:
        cases = [c for c in cases if c["id"] in wanted]

    # Re-running selected cases replaces only their rows and keeps the rest.
    previous: list[dict] = []
    if wanted and RESULTS_PATH.exists():
        with RESULTS_PATH.open(encoding="utf-8") as f:
            previous = [r for r in csv.DictReader(f) if r["id"] not in wanted]

    order = {c["id"]: i for i, c in enumerate(json.loads(TEST_CASES_PATH.read_text(encoding="utf-8")))}

    def save(rows_to_save: list[dict]) -> list[dict]:
        ordered = sorted(rows_to_save, key=lambda r: (order.get(r["id"], 99), MODES.index(r["mode"])))
        with RESULTS_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(ordered)
        return ordered

    new_rows: list[dict] = []
    for case in cases:
        for mode in MODES:
            print(f"Running {case['id']} [{mode}] ...", flush=True)
            row = run_case(case, mode)
            new_rows.append(row)
            save(previous + new_rows)  # saved after every run, so an interrupted run keeps its progress
            print(f"    acc={row['response_accuracy']} tools={row['tools_used'] or '-'} "
                  f"{row['latency_ms']} ms, {row['context_tokens']} tokens", flush=True)

    rows = save(previous + new_rows)
    print("\n" + write_summary(rows))
    print(f"Per-run results: {RESULTS_PATH}\nSummary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
