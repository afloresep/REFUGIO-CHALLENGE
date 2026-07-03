"""Merge layout-search eval results into data/evaluation-results.json.

Idempotent by label: existing entries with the same label are replaced.

Usage: python3 scripts/layout_search/record_results.py LABEL=EVAL_DIR[:NOTES] ...
Each EVAL_DIR must contain a result.json from warehouse.eval_runner.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "evaluation-results.json"
BASELINE = 1008
BEST_1024 = 1024


def entry_from_result(label: str, eval_dir: Path, notes: str | None) -> dict:
    result = json.loads((eval_dir / "result.json").read_text())
    seed_scores = [s["score"] for s in result["seed_results"]]
    entry = {
        "policy": f"generated: scripts/layout_search (label {label})",
        "label": label,
        "score": result["score"],
        "seed_scores": seed_scores,
        "delta_vs_baseline": result["score"] - BASELINE,
        "delta_vs_1024": result["score"] - BEST_1024,
        "blocked_moves": result["score_breakdown"]["blocked_moves"],
        "remaining_distance": result["score_breakdown"]["remaining_distance"],
        "policy_time_seconds": result["policy_time_seconds"],
    }
    if notes:
        entry["notes"] = notes
    return entry


def main() -> None:
    data = json.loads(DATA.read_text())
    by_label = {e["label"]: i for i, e in enumerate(data["results"])}
    for spec in sys.argv[1:]:
        label, rest = spec.split("=", 1)
        parts = rest.split("::", 1)
        eval_dir = REPO / parts[0]
        notes = parts[1] if len(parts) > 1 else None
        entry = entry_from_result(label, eval_dir, notes)
        if label in by_label:
            data["results"][by_label[label]] = entry
        else:
            data["results"].append(entry)
            by_label[label] = len(data["results"]) - 1
        print(f"recorded {label}: {entry['score']} {entry['seed_scores']}")
    data["updated_on"] = "2026-07-03"
    DATA.write_text(json.dumps(data, indent=1) + "\n")


if __name__ == "__main__":
    main()
