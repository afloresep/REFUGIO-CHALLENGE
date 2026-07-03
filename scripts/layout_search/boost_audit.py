"""Audit one seed's replay for near-miss deliveries and test per-robot boosts.

A boost entry ((scenario_sig, robot_id): (tick, mode)) gives that robot top
planner priority from `tick` onward. This finds robots that ended the episode
carrying an item close to their base entry (or idling short of a final
pickup), injects one-boost trial policies, evaluates each on that seed, and
reports which boosts add deliveries.

Usage:
  python3 scripts/layout_search/boost_audit.py POLICY.py SEED REPLAY.json \
      --tag NAME [--top 8] [--jobs 6]
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search.make_1024_variant import replace_dict

OUT_ROOT = L.REPO / "outputs" / "layout-search" / "boosts"


def load_replay(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def near_miss_candidates(replay: dict, top: int) -> list[dict]:
    shelves = [tuple(c) for c in replay["layout"]["shelf_cells"]]
    blocked = set(shelves)
    entries = L.base_entries_by_robot()
    final = {r["id"]: r for r in replay["frames"][-1]["robots"]}
    candidates = []
    for rid, rob in final.items():
        entry = entries[rid]
        field = L.bfs([entry], blocked)
        x, y = rob["pos"]
        dist = int(field[y, x]) if L.in_walk(x, y) else -1
        if rob["carrying"] and 0 < dist <= 14:
            candidates.append(
                {"rid": rid, "dist": dist, "mode": "carry", "carrying": True}
            )
        elif not rob["carrying"] and 0 < dist <= 8:
            candidates.append(
                {"rid": rid, "dist": dist, "mode": "all", "carrying": False}
            )
    candidates.sort(key=lambda c: (not c["carrying"], c["dist"]))
    return candidates[:top]


def make_trial(policy_src: str, sig: tuple, rid: int, tick: int, mode: str, out: Path) -> None:
    marker = "ROBOT_BOOSTS = {"
    start = policy_src.index(marker)
    i = policy_src.index("{", start)
    depth = 0
    for j in range(i, len(policy_src)):
        if policy_src[j] == "{":
            depth += 1
        elif policy_src[j] == "}":
            depth -= 1
            if depth == 0:
                existing = policy_src[i : j + 1]
                break
    addition = f"ROBOT_BOOSTS.update({{(({sig[0]}, {sig[1]}), {rid}): ({tick}, {mode!r})}})\n"
    insert_at = policy_src.index("\n", policy_src.index(existing) + len(existing)) + 1
    src = policy_src[:insert_at] + addition + policy_src[insert_at:]
    compile(src, str(out), "exec")
    out.write_text(src)


def run_eval(policy: Path, seed: str, out_dir: Path) -> int | None:
    result_path = out_dir / "result.json"
    if not result_path.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "python3", "-m", "warehouse.eval_runner", str(policy),
            "--submission-id", out_dir.name, "--team-name", "local-analysis",
            "--seeds", seed, "--ticks", "300", "--replay-seed", seed,
            "--policy-budget-seconds", "180",
            "--result-out", str(result_path),
            "--replay-out", str(out_dir / "replay.json"),
        ]
        proc = subprocess.run(cmd, cwd=L.REPO, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            print(f"FAIL {out_dir.name}: {proc.stderr[-160:]}")
            return None
    return json.loads(result_path.read_text())["score"]


def main() -> None:
    args = sys.argv[1:]
    policy_path, seed, replay_path = Path(args[0]), args[1], Path(args[2])

    def opt(name: str, default: str) -> str:
        return args[args.index(name) + 1] if name in args else default

    tag = opt("--tag", "boost")
    top = int(opt("--top", "8"))
    jobs = int(opt("--jobs", "6"))

    replay = load_replay(replay_path)
    shelves = [tuple(c) for c in replay["layout"]["shelf_cells"]]
    sig = L.first_target_signatures(shelves, seeds=[seed])[seed]
    policy_src = policy_path.read_text()

    base_score = run_eval(policy_path, seed, OUT_ROOT / f"{tag}-base")
    print(f"base score on {seed[:8]}: {base_score}")

    candidates = near_miss_candidates(replay, top)
    print(f"candidates: {candidates}")

    trials = []
    for c in candidates:
        for tick in (max(120, 299 - 6 * c["dist"] - 60), max(150, 299 - 6 * c["dist"])):
            name = f"{tag}-r{c['rid']}-t{tick}-{c['mode']}"
            out = OUT_ROOT / f"{name}.py"
            make_trial(policy_src, sig, c["rid"], tick, c["mode"], out)
            trials.append((out, name))

    results = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(run_eval, policy, seed, OUT_ROOT / name): name
            for policy, name in trials
        }
        for future, name in futures.items():
            results[name] = future.result()

    improved = {n: s for n, s in results.items() if s is not None and s > base_score}
    print("\nall trials:")
    for name in sorted(results):
        print(f"  {name}: {results[name]}")
    print(f"\nimproving boosts (> {base_score}): {improved}")


if __name__ == "__main__":
    main()
