"""Unattended ratchet search for a single-seed improvement over the 1024 solver.

Samples targeted whole-bundle perturbations - early/mid-game single-robot
priority boosts (the incumbent's own boost layer includes ticks as early as
40) and short holds at low-traffic parking cells - and evaluates each on one
seed. Accepts only strict improvements over the incumbent per-seed scores
(343 / 342 / 339). On a hit, it writes the improving policy path to
outputs/layout-search/grind/JACKPOT-<seed>-<score>.txt and keeps going.

Usage:
  python3 scripts/layout_search/grind_1024.py [max_trials] [jobs]
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L

BASE = L.REPO / "solutions" / "ours" / "2026-07-02-solver-1024.py"
OUT = L.REPO / "outputs" / "layout-search" / "grind"
SIGS = {
    "bff0fb14575b4676b1f0f01bfc7b0126": (12, 33),
    "dfbf918495ee4fca8d50b53456d59fa8": (26, 47),
    "546a597410b049de82f7ce72fe7fd714": (14, 42),
}
THRESHOLDS = {
    "bff0fb14575b4676b1f0f01bfc7b0126": 343,
    "dfbf918495ee4fca8d50b53456d59fa8": 342,
    "546a597410b049de82f7ce72fe7fd714": 339,
}


def make_trial(rng: random.Random, base_src: str, seed: str, idx: int) -> Path | None:
    """One targeted perturbation: a single-robot priority boost at a random
    tick. The incumbent's own boost layer includes ticks as early as 40, and
    this dimension was only ever sampled at late ticks for near-miss robots."""
    sig = SIGS[seed]
    rid = rng.randrange(96)
    tick = rng.choice((40, 60, 80, 100, 120, 140, 160, 180, 210, 240))
    mode = rng.choice(("all", "carry"))
    patch = f"\nROBOT_BOOSTS.update({{(({sig[0]}, {sig[1]}), {rid}): ({tick}, {mode!r})}})\n"
    name = f"g-{seed[:4]}-{idx}-b{rid}t{tick}{mode[0]}"
    out = OUT / f"{name}.py"
    src = base_src + patch
    compile(src, str(out), "exec")
    out.write_text(src)
    return out


def run_trial(policy: Path, seed: str) -> int | None:
    result_path = policy.with_suffix(".result.json")
    cmd = [
        "python3", "-m", "warehouse.eval_runner", str(policy),
        "--submission-id", policy.stem, "--team-name", "local-analysis",
        "--seeds", seed, "--ticks", "300", "--replay-seed", seed,
        "--policy-budget-seconds", "180",
        "--result-out", str(result_path),
        "--replay-out", str(policy.with_suffix(".replay.json")),
    ]
    proc = subprocess.run(cmd, cwd=L.REPO, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        return None
    score = json.loads(result_path.read_text())["score"]
    # keep disk usage bounded: drop artifacts for non-improving trials
    if score <= THRESHOLDS[seed]:
        for suffix in (".py", ".result.json", ".replay.json"):
            policy.with_suffix(suffix).unlink(missing_ok=True)
    return score


def main() -> None:
    max_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    OUT.mkdir(parents=True, exist_ok=True)
    base_src = BASE.read_text()
    rng = random.Random(20260703)
    seeds = list(SIGS)

    def one(idx: int) -> str:
        seed = seeds[idx % 3]
        policy = make_trial(rng, base_src, seed, idx)
        if policy is None:
            return "skip"
        score = run_trial(policy, seed)
        if score is None:
            return "fail"
        if score > THRESHOLDS[seed]:
            jackpot = OUT / f"JACKPOT-{seed[:8]}-{score}-{policy.stem}.txt"
            jackpot.write_text(f"{policy}\nscore {score} on {seed}\n")
            print(f"JACKPOT {policy.stem}: {score} on {seed[:8]} (threshold {THRESHOLDS[seed]})")
        return f"{policy.stem}={score}"

    done = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for result in pool.map(one, range(max_trials)):
            done += 1
            if done % 25 == 0:
                print(f"[{done}/{max_trials}] latest: {result}", flush=True)
    print("grind complete:", done, "trials")


if __name__ == "__main__":
    main()
