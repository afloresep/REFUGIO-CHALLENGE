"""Delivery-maximizing layout optimization via DP + marginal reweighting.

The linear DP minimizes total demand-weighted travel, which is not the true
objective (deliveries under a per-robot 300-tick budget). This script closes
the loop: run the DP, score the result with the uncongested serving model,
then reweight each (robot, k) demand by its marginal delivery value
(~(n_r + 1) / 300 for trips the robot can actually reach) and repeat. Keeps
the best serving-model layout per lattice.

Usage: python3 scripts/layout_search/optimize_deliveries.py [rounds]
Writes outputs/layout-search/layouts/rw-<lattice>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search.generate_layouts import (
    LATTICES,
    demand_cost_matrix,
    dp_select,
    slot_distance_matrix,
)
from warehouse.targets import target_index

OUT_DIR = L.REPO / "outputs" / "layout-search" / "layouts"

MAX_K = 20


def lattice_hyb() -> list[tuple[int, int]]:
    """x-pairs full height with three cross-aisle rows kept open."""
    return [
        (x, y)
        for gx in range(16)
        for x in (2 + 3 * gx, 3 + 3 * gx)
        for y in range(2, 50)
        if y not in (13, 25, 37)
    ]


def lattice_rows23() -> list[tuple[int, int]]:
    """2-tall shelf row pairs, full width, 1-wide horizontal aisles."""
    return [
        (x, y)
        for gy in range(16)
        for y in (2 + 3 * gy, 3 + 3 * gy)
        for x in range(2, 50)
    ]


ALL_LATTICES = dict(LATTICES)
ALL_LATTICES["hyb"] = (lattice_hyb, {"bw": 2, "bh": 2, "flow_x": True, "flow_y": False})
ALL_LATTICES["rows23"] = (
    lattice_rows23,
    {"bw": 2, "bh": 2, "flow_x": False, "flow_y": True},
)


def serving_trace(shelves) -> dict[str, list[int]]:
    """Per-seed, per-robot delivery counts under the uncongested model."""
    ss = L.sorted_shelves(shelves)
    blocked = L.shelf_set(shelves)
    fields = L.robot_fields(shelves)
    trace: dict[str, list[int]] = {}
    for seed in L.OFFICIAL_SEEDS:
        counts = []
        for rid in range(L.ROBOT_COUNT):
            t = 0
            n = 0
            for k in range(MAX_K + 4):
                idx = target_index(seed, rid, k, L.SHELF_COUNT)
                d = L.pickup_distance(fields[rid], ss[idx], blocked)
                if d < 0:
                    break
                trip = 2 * d + 2
                if t + trip > L.TICKS:
                    break
                t += trip
                n += 1
            counts.append(n)
        trace[seed] = counts
    return trace


def marginal_weight_matrix(trace: dict[str, list[int]]) -> np.ndarray:
    """W[idx, r] = marginal delivery value of shortening that demand's trip."""
    W = np.zeros((L.SHELF_COUNT, L.ROBOT_COUNT), dtype=np.float64)
    for seed, counts in trace.items():
        for rid in range(L.ROBOT_COUNT):
            n = counts[rid]
            rate = (n + 1) / L.TICKS
            for k in range(MAX_K):
                if k <= n + 1:
                    w = rate
                else:
                    w = rate * (0.25 ** (k - n - 1))
                if w < 1e-4:
                    break
                idx = target_index(seed, rid, k, L.SHELF_COUNT)
                W[idx, rid] += w
    return W


def optimize(lattice_name: str, rounds: int) -> None:
    build, _cfg = ALL_LATTICES[lattice_name]
    slots = sorted(build(), key=lambda c: (c[1], c[0]))
    D = slot_distance_matrix(slots)

    W0 = L.demand_weight_matrix(weights=L.DEFAULT_K_WEIGHTS)
    W0 = W0 / W0.sum()
    W = W0.copy()
    best_layout = None
    best_pred = None
    history = []
    for rnd in range(rounds):
        cost = demand_cost_matrix(slots, W, D)
        layout = dp_select(slots, cost)
        pred = L.predicted_scores(layout)
        history.append(pred["total_uncongested"])
        if best_pred is None or pred["total_uncongested"] > best_pred["total_uncongested"]:
            best_layout, best_pred = layout, pred
        Wm = marginal_weight_matrix(serving_trace(layout))
        Wm = Wm / Wm.sum()
        W = 0.5 * W + 0.5 * Wm

    assert best_layout is not None and best_pred is not None
    name = f"rw-{lattice_name}"
    L.save_layout(
        OUT_DIR / f"{name}.json",
        best_layout,
        {"name": name, "history": history, "pred": best_pred},
    )
    m = L.metrics(best_layout)
    print(
        f"{name}: history={history} best_pred={best_pred['total_uncongested']} "
        f"per_seed={best_pred['per_seed_uncongested']} trip={best_pred['mean_trip']} "
        f"access={m['mean_access_cells']} one_access={m['one_access_shelves']}"
    )


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    for lattice_name in ALL_LATTICES:
        optimize(lattice_name, rounds)


if __name__ == "__main__":
    main()
