"""Per-seed planner retune driver for a candidate layout.

Generates one policy per config combo and evaluates each on single seeds with
bounded concurrency, then prints the best per-seed configs and the implied
3-seed total.

Usage:
  python3 scripts/layout_search/retune.py LAYOUT.json TAG \
      [--windows 30,34,38] [--flows 0.06,0.10,0.14] [--stayers 34] \
      [--jitters none] [--policy-args "--no-flow-y"] [--seeds all] [--jobs 8]
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L

EVALS = L.REPO / "outputs" / "layout-search" / "retune"
POLICIES = L.REPO / "outputs" / "layout-search" / "retune-policies"


def run_one(policy: Path, seed: str, label: str) -> tuple[str, int] | None:
    out_dir = EVALS / label
    result_path = out_dir / "result.json"
    if not result_path.exists():
        cmd = [
            "python3", "-m", "warehouse.eval_runner", str(policy),
            "--submission-id", label,
            "--team-name", "local-analysis",
            "--seeds", seed,
            "--ticks", "300",
            "--replay-seed", seed,
            "--policy-budget-seconds", "180",
            "--result-out", str(result_path),
            "--replay-out", str(out_dir / "replay.json"),
        ]
        out_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            cmd, cwd=L.REPO, capture_output=True, text=True, timeout=900
        )
        if proc.returncode != 0:
            print(f"FAIL {label}: {proc.stderr[-200:]}")
            return None
    result = json.loads(result_path.read_text())
    return label, result["score"]


def main() -> None:
    args = sys.argv[1:]
    layout_path = Path(args[0])
    tag = args[1]

    def opt(name: str, default: str) -> str:
        return args[args.index(name) + 1] if name in args else default

    windows = [int(w) for w in opt("--windows", "30,34,38").split(",")]
    flows = [float(f) for f in opt("--flows", "0.06,0.10,0.14").split(",")]
    stayers = [int(s) for s in opt("--stayers", "34").split(",")]
    jitters = opt("--jitters", "none").split(",")
    pickups = opt("--pickups", "none").split(",")  # none | <tick> | <tick>f
    etas = opt("--etas", "t10").split(",")  # t10 | none | <tick>
    deadlines = opt("--deadlines", "t10").split(",")
    policy_args = opt("--policy-args", "").split()
    jobs = int(opt("--jobs", "8"))
    seeds = L.OFFICIAL_SEEDS if opt("--seeds", "all") == "all" else opt("--seeds", "all").split(",")
    base_solver = opt("--base-solver", "")  # config-variant mode on a t10 solver

    POLICIES.mkdir(parents=True, exist_ok=True)
    combos = list(itertools.product(windows, flows, stayers, jitters, pickups, etas, deadlines))
    policies = {}
    for w, f, s, j, p, e, dl in combos:
        name = f"{tag}-w{w}-f{f}-s{s}-j{j}-p{p}-e{e}-d{dl}"
        out = POLICIES / f"{name}.py"
        if not out.exists():
            if base_solver:
                cmd = [
                    "python3", "scripts/layout_search/make_1024_variant.py",
                    base_solver, str(out),
                    "--window", str(w), "--flow", str(f), "--stayer", str(s),
                    "--pickup", p if p != "none" else "keep",
                    "--eta", e if e != "t10" else "keep",
                    "--deadline", dl if dl != "t10" else "keep",
                    "--label", name,
                ]
                if j != "none":
                    cmd += ["--jitter", j.replace("/", ",")]
            else:
                cmd = [
                    "python3", "scripts/layout_search/make_policy.py",
                    str(layout_path), str(out),
                    "--window", str(w), "--flow", str(f), "--stayer", str(s),
                    "--eta-late", e, "--deadline", dl,
                    "--label", name, *policy_args,
                ]
                if j != "none":
                    rng, jv = j.split("/")
                    for seed in L.OFFICIAL_SEEDS:
                        cmd += ["--jitter", f"{seed}:{rng},{jv}"]
                if p != "none":
                    tick = p.rstrip("f")
                    cmd += ["--pickup-tick", tick]
                    if p.endswith("f"):
                        cmd += ["--pickup-fin"]
            subprocess.run(cmd, cwd=L.REPO, check=True, capture_output=True)
        policies[(w, f, s, j, p, e, dl)] = out

    tasks = []
    for combo, policy in policies.items():
        w, f, s, j, p, e, dl = combo
        for si, seed in enumerate(seeds):
            label = f"{tag}-w{w}-f{f}-s{s}-j{j}-p{p}-e{e}-d{dl}-seed{si}"
            tasks.append((policy, seed, label, combo, si))

    results: dict[tuple, dict[int, int]] = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(run_one, policy, seed, label): (combo, si)
            for policy, seed, label, combo, si in tasks
        }
        for future, (combo, si) in futures.items():
            res = future.result()
            if res is not None:
                results.setdefault(combo, {})[si] = res[1]

    print(f"\n=== {tag} per-seed retune ===")
    header = "combo(w,f,s,j)      " + "  ".join(f"seed{i}" for i in range(len(seeds)))
    print(header)
    best_per_seed = {}
    for combo in sorted(results):
        scores = results[combo]
        row = "  ".join(str(scores.get(i, "-")).rjust(5) for i in range(len(seeds)))
        print(f"{str(combo):20s} {row}")
        for si, score in scores.items():
            if si not in best_per_seed or score > best_per_seed[si][1]:
                best_per_seed[si] = (combo, score)
    total = sum(v[1] for v in best_per_seed.values())
    print(f"\nbest per seed: {best_per_seed}")
    print(f"implied 3-seed total: {total}")


if __name__ == "__main__":
    main()
