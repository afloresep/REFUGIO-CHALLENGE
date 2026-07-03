"""Joint two-robot lock-chain edits over a replay matrix.

For a gain robot b whose single-robot compression to +1 deliveries fails or
regresses, the blocker is often a frozen shelf lock or pickup event owned by
another robot a. This tool rebuilds a's day first (same delivery count,
lock-aware earliest-arrival, releasing its locks as early as possible), then
rebuilds b to +1 against the updated state, and validates with the exact
simulator.

Pair selection: for each robot b, every robot a that owns a lock interval or
pickup event on any of b's first (d_b + 1) target shelves.

Usage:
  python3 scripts/layout_search/sweep_pairs.py MATRIX.json OUT.json [--gain 83]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search.sweep_compress import build_row, trips_from_row
from warehouse.targets import target_for


def candidate_pairs(data: dict, gains: list[int], best: list[int]):
    """Yield (a, b): a owns lock/pickup events on b's needed target shelves."""
    seed = data["seed"]
    shelves = L.sorted_shelves([tuple(c) for c in data["shelves"]])
    owners: dict[tuple[int, int], set[int]] = {}
    for r, row in enumerate(data["matrix"]):
        for _tp, _td, shelf in trips_from_row(row, seed, r, shelves):
            owners.setdefault(shelf, set()).add(r)
    for b in gains:
        needed = [target_for(seed, b, k, shelves) for k in range(best[b] + 1)]
        blockers: set[int] = set()
        for s in needed:
            blockers |= owners.get(s, set())
        blockers.discard(b)
        for a in sorted(blockers):
            yield a, b


def sweep_pairs(data: dict, gains: list[int], out: Path):
    base = ME.simulate(data)
    best = ME.deliveries(base)
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    tried = 0
    for a, b in candidate_pairs(data, gains, best):
        row_a = build_row(data, pos, a, best[a])
        if row_a is None:
            continue
        step = dict(data)
        step["matrix"] = list(data["matrix"])
        step["matrix"][a] = row_a
        sim_a = ME.simulate(step, record=True)
        d_a = ME.deliveries(sim_a)
        if sum(d_a) < total:
            continue  # a's rebuild alone already loses deliveries
        pos_a = ME.positions_by_tick(sim_a)
        row_b = build_row(step, pos_a, b, best[b] + 1)
        tried += 1
        if row_b is None:
            continue
        step["matrix"][b] = row_b
        d = ME.deliveries(ME.simulate(step))
        if sum(d) > total:
            print(f"  pair ({a},{b}): {total} -> {sum(d)} (b {best[b]} -> {d[b]})")
            data = step
            best, total = d, sum(d)
            out.write_text(json.dumps(data))
            pos = ME.positions_by_tick(ME.simulate(data, record=True))
        else:
            print(f"  pair ({a},{b}): no gain ({sum(d)})")
    print(f"final {data['seed'][:8]}: {total} ({tried} joint attempts)")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--gain", default=None, help="csv of gain robots; default all")
    args = ap.parse_args()
    data = ME.load(Path(args.matrix))
    gains = (
        [int(x) for x in args.gain.split(",")]
        if args.gain
        else list(range(L.ROBOT_COUNT))
    )
    sweep_pairs(data, gains, Path(args.out))


if __name__ == "__main__":
    main()
