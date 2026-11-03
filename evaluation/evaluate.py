"""Phase 16: Evaluation harness.

Runs each test case against both screen-only and retrieval-augmented
Percept and records metrics to results.csv.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000/api/v1"
TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_PATH = Path(__file__).parent / "results.csv"

METRICS_FIELDS = [
    "id",
    "phase",
    "description",
    "requires_retrieval",
    "response_accuracy",   # 0.0–1.0 manual annotation
    "retrieval_accuracy",  # 0.0–1.0 — did it fetch the right context?
    "task_completion",     # 0 or 1
    "latency_ms",
    "context_tokens",
    "tools_used",
    "notes",
]


def run_query(question: str, screenshot_b64: str | None = None) -> tuple[dict, float]:
    start = time.monotonic()
    resp = httpx.post(
        f"{API_BASE}/query",
        json={"question": question, "screenshot_b64": screenshot_b64},
        timeout=120.0,
    )
    latency_ms = (time.monotonic() - start) * 1000
    return resp.json(), latency_ms


def main():
    cases = json.loads(TEST_CASES_PATH.read_text())

    with RESULTS_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METRICS_FIELDS)
        writer.writeheader()

        for case in cases:
            print(f"Running {case['id']}: {case['description']} ...")
            try:
                result, latency = run_query(case["question"])
                row = {
                    "id": case["id"],
                    "phase": case["phase"],
                    "description": case["description"],
                    "requires_retrieval": case["requires_retrieval"],
                    "response_accuracy": "",   # fill manually
                    "retrieval_accuracy": "",
                    "task_completion": "",
                    "latency_ms": round(latency, 1),
                    "context_tokens": "",
                    "tools_used": ",".join(result.get("tools_used", [])),
                    "notes": result.get("answer", "")[:120],
                }
            except Exception as exc:
                row = {f: "" for f in METRICS_FIELDS}
                row.update({"id": case["id"], "notes": str(exc)})

            writer.writerow(row)
            print(f"  done ({row['latency_ms']} ms)")

    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
