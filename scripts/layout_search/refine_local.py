"""Refine a lattice-subset layout by directly optimizing the serving model.

Phase 1: geometry fixed-point. The DP's distance matrix is computed on the
full lattice, but the chosen layout opens 288 holes that shorten real paths.
Recompute distances on the current layout's geometry, re-run the DP, and keep
iterating while the serving-model prediction improves.

Phase 2: rank-local swap search. Swapping a selected slot with a nearby hole
only shifts demand indices between the two ranks, so nearby-rank swaps are
small perturbations. Greedy accept on serving-model improvement.

Usage:
  python3 scripts/layout_search/refine_local.py LATTICE START.json OUT.json \
      [--swap-seconds N]
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search.generate_layouts import demand_cost_matrix, dp_select
from layout_search.optimize_deliveries import ALL_LATTICES


def subset_distance_matrix(
    slots: list[tuple[int, int]], selected: set[tuple[int, int]]
) -> np.ndarray:
    """D[robot, slot] measured on the current layout (holes walkable)."""
    fields = L.robot_fields(selected)
    M = len(slots)
    D = np.full((L.ROBOT_COUNT, M), 4 * L.GRID, dtype=np.float64)
    for j, (sx, sy) in enumerate(slots):
        for rid in range(L.ROBOT_COUNT):
            best = -1
            f = fields[rid]
            if (sx, sy) not in selected:
                # Hole: if selected later, its neighbors become pickup cells.
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = sx + dx, sy + dy
                    if L.in_walk(nx, ny) and (nx, ny) not in selected:
                        d = int(f[ny, nx])
                        if d >= 0 and (best < 0 or d < best):
                            best = d
            else:
                best = L.pickup_distance(f, (sx, sy), selected)
            if best >= 0:
                D[rid, j] = best
    return D


def refine(lattice_name: str, start_path: Path, out_path: Path, swap_seconds: int) -> None:
    build, _cfg = ALL_LATTICES[lattice_name]
    slots = sorted(build(), key=lambda c: (c[1], c[0]))
    slot_rank = {slot: j for j, slot in enumerate(slots)}
    W = L.demand_weight_matrix(weights=L.DEFAULT_K_WEIGHTS)

    layout = L.load_layout(start_path)
    assert all(tuple(c) in slot_rank for c in layout), "start layout not in lattice"
    pred = L.predicted_scores(layout)
    best_total = pred["total_uncongested"]
    print(f"start: pred={best_total} {pred['per_seed_uncongested']}")

    # Phase 1: geometry fixed-point on the DP.
    for rnd in range(5):
        D = subset_distance_matrix(slots, L.shelf_set(layout))
        cost = demand_cost_matrix(slots, W, D)
        cand = dp_select(slots, cost)
        cand_pred = L.predicted_scores(cand)
        total = cand_pred["total_uncongested"]
        print(f"fixed-point round {rnd}: pred={total} {cand_pred['per_seed_uncongested']}")
        if total > best_total:
            layout, best_total = cand, total
        else:
            break

    # Phase 2: rank-local swap search.
    rng = random.Random(12345)
    selected = set(L.shelf_set(layout))
    deadline = time.time() + swap_seconds
    tried = accepted = 0
    while time.time() < deadline:
        tried += 1
        shelf = rng.choice(tuple(selected))
        r = slot_rank[shelf]
        lo, hi = max(0, r - 40), min(len(slots), r + 41)
        holes = [s for s in slots[lo:hi] if s not in selected]
        if not holes:
            continue
        hole = rng.choice(holes)
        trial = (selected - {shelf}) | {hole}
        if L.validate(trial) is not None:
            continue
        p = L.predicted_scores(trial)
        if p["total_uncongested"] > best_total:
            selected = trial
            best_total = p["total_uncongested"]
            accepted += 1
            print(f"swap {tried}: {shelf}->{hole} pred={best_total}")
    layout = sorted(selected, key=lambda c: (c[1], c[0]))

    error = L.validate(layout)
    assert error is None, error
    final = L.predicted_scores(layout)
    print(
        f"final: pred={final['total_uncongested']} {final['per_seed_uncongested']} "
        f"(swaps tried={tried} accepted={accepted})"
    )
    L.save_layout(out_path, layout, {"name": out_path.stem, "pred": final})


def main() -> None:
    args = sys.argv[1:]
    swap_seconds = 300
    if "--swap-seconds" in args:
        i = args.index("--swap-seconds")
        swap_seconds = int(args[i + 1])
        args = args[:i] + args[i + 2 :]
    lattice_name, start, out = args
    refine(lattice_name, Path(start), Path(out), swap_seconds)


if __name__ == "__main__":
    main()
