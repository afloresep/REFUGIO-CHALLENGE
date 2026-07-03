"""Run a set of policies on one seed in parallel and print the score table.

Usage:
  python3 scripts/layout_search/run_policy_evals.py SEED OUT_SUFFIX JOBS POLICY.py [POLICY.py ...]

Results are cached next to each policy as <name>-<OUT_SUFFIX>-result.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run_one(policy: Path, seed: str, suffix: str) -> tuple[str, int | None]:
    result_path = policy.with_name(f"{policy.stem}-{suffix}-result.json")
    if not result_path.exists():
        cmd = [
            "python3", "-m", "warehouse.eval_runner", str(policy),
            "--submission-id", f"{policy.stem}-{suffix}",
            "--team-name", "local-analysis",
            "--seeds", seed, "--ticks", "300", "--replay-seed", seed,
            "--policy-budget-seconds", "180",
            "--result-out", str(result_path),
            "--replay-out", str(policy.with_name(f"{policy.stem}-{suffix}-replay.json")),
        ]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            print(f"FAIL {policy.stem}: {proc.stderr[-160:]}")
            return policy.stem, None
    return policy.stem, json.loads(result_path.read_text())["score"]


def main() -> None:
    seed, suffix, jobs = sys.argv[1], sys.argv[2], int(sys.argv[3])
    policies = [Path(p) for p in sys.argv[4:]]
    results = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_one, p, seed, suffix) for p in policies]
        for future in futures:
            results.append(future.result())
    results.sort(key=lambda t: -(t[1] or 0))
    for name, score in results:
        print(name, score)


if __name__ == "__main__":
    main()
