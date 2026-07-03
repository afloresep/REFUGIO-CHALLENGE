"""Generate legal 960-shelf candidate layouts from multiple topology families.

Families:
  A  Team 10 isometries (mirror-x/y, rot180, transpose): geometry quality is
     invariant, only the shelf-index -> position demand mapping changes.
  B  Ring / return-lane layouts with door gaps.
  C  Proximity-packed controls: DP with uniform demand (near-base packing
     without seed knowledge).
  E  Demand-tuned DP subsets of legal super-lattices: choose 960 slots in
     row-major order minimizing official-seed demand-weighted round-trip cost.
     The DP is exact for the rank-constrained assignment because sorted shelf
     rank == demand index.

Every subset of a legal super-lattice is legal (removing shelves only adds
walkable cells), so DP outputs need no repair. All outputs are validated with
the evaluator's own validator anyway.

Usage: python3 scripts/layout_search/generate_layouts.py [--only FAMILY,...]
Writes outputs/layout-search/layouts/<name>.json and a summary JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L

OUT_DIR = L.REPO / "outputs" / "layout-search" / "layouts"

DEEP_K_WEIGHTS = (
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.8, 0.6, 0.4, 0.25, 0.12, 0.06, 0.02,
)


# ---------------------------------------------------------------- lattices


def lattice_t10() -> list[tuple[int, int]]:
    """Team 10's underlying lattice: 2-wide column pairs x 4-tall row groups."""
    slots = []
    for gx in range(16):
        for x in (2 + 3 * gx, 3 + 3 * gx):
            for gy in range(10):
                for y in range(2 + 5 * gy, min(2 + 5 * gy + 4, 50)):
                    slots.append((x, y))
    return slots


def lattice_cols23() -> list[tuple[int, int]]:
    """2-wide shelf column pairs, full height, 1-wide vertical aisles."""
    return [
        (x, y)
        for gx in range(16)
        for x in (2 + 3 * gx, 3 + 3 * gx)
        for y in range(2, 50)
    ]


def lattice_comb() -> list[tuple[int, int]]:
    """Single-width columns at even x: every shelf has two pickup sides."""
    return [(x, y) for x in range(2, 49, 2) for y in range(2, 50)]


LATTICES = {
    "t10lat": (lattice_t10, {"bw": 2, "bh": 2, "flow_x": True, "flow_y": True}),
    "cols23": (lattice_cols23, {"bw": 2, "bh": 2, "flow_x": True, "flow_y": False}),
    "comb": (lattice_comb, {"bw": 1, "bh": 1, "flow_x": True, "flow_y": False}),
}


# ---------------------------------------------------------------- DP core


def slot_distance_matrix(slots: list[tuple[int, int]]) -> np.ndarray:
    """D[robot, slot] = dist from robot entry to nearest pickup cell of slot,
    measured on the full lattice (conservative: holes only shorten paths)."""
    blocked = set(slots)
    fields = L.robot_fields(slots)
    M = len(slots)
    D = np.full((L.ROBOT_COUNT, M), 4 * L.GRID, dtype=np.float64)
    for j, slot in enumerate(slots):
        for rid in range(L.ROBOT_COUNT):
            d = L.pickup_distance(fields[rid], slot, blocked)
            if d >= 0:
                D[rid, j] = d
    return D


def dp_select(slots: list[tuple[int, int]], cost: np.ndarray) -> list[tuple[int, int]]:
    """Exact min-cost selection of 960 slots in row-major order.

    cost[i, j] = cost of assigning demand index i to slot j. Slots must be
    sorted row-major so selected rank == demand index.
    """
    M = len(slots)
    K = L.SHELF_COUNT
    INF = np.float64(1e18)
    dps = np.empty((M + 1, K + 1), dtype=np.float64)
    dps[0] = INF
    dps[0, 0] = 0.0
    for j in range(M):
        prev = dps[j]
        cur = prev.copy()
        cand = prev[:-1] + cost[:, j]
        np.minimum(cur[1:], cand, out=cur[1:])
        dps[j + 1] = cur
    if not np.isfinite(dps[M, K]):
        raise RuntimeError("DP infeasible")
    picks: list[tuple[int, int]] = []
    i = K
    for j in range(M, 0, -1):
        if i > 0 and dps[j, i] != dps[j - 1, i]:
            picks.append(slots[j - 1])
            i -= 1
    if i != 0:
        raise RuntimeError("DP backtrack failed")
    picks.reverse()
    return picks


def demand_cost_matrix(
    slots: list[tuple[int, int]], W: np.ndarray, D: np.ndarray
) -> np.ndarray:
    """cost[i, j] = sum_r W[i, r] * (2 * D[r, j] + 2), plus a small uniform
    accessibility floor so zero-demand indices still prefer reachable slots."""
    trip = 2.0 * D + 2.0  # (96, M)
    cost = W @ trip  # (960, M)
    floor = trip.mean(axis=0, keepdims=True)  # (1, M)
    return cost + 0.02 * floor


def make_dp_layout(lattice_name: str, W: np.ndarray) -> list[tuple[int, int]]:
    build, _cfg = LATTICES[lattice_name]
    slots = sorted(build(), key=lambda c: (c[1], c[0]))
    D = slot_distance_matrix(slots)
    cost = demand_cost_matrix(slots, W, D)
    return dp_select(slots, cost)


# ---------------------------------------------------------------- families


def family_a() -> dict[str, list[tuple[int, int]]]:
    t10 = L.team10_shelves()
    out = {
        "t10-mirror-x": [(51 - x, y) for x, y in t10],
        "t10-mirror-y": [(x, 51 - y) for x, y in t10],
        "t10-rot180": [(51 - x, 51 - y) for x, y in t10],
        "t10-transpose": [(y, x) for x, y in t10],
    }
    return out


def family_b() -> dict[str, list[tuple[int, int]]]:
    """Concentric 2-thick shelf rings, 2-wide lanes, cardinal door cuts."""
    cells = set()
    for x in range(2, 50):
        for y in range(2, 50):
            d = min(x - 2, y - 2, 49 - x, 49 - y)
            if d % 4 in (1, 2):
                cells.add((x, y))
    doors = {13, 26, 39}
    cells = {
        (x, y)
        for x, y in cells
        if x not in doors
        and y not in doors
        and abs(x - y) > 1
        and abs(x + y - 51) > 1
    }
    entries = set(L.base_entries_by_robot())
    dist = L.bfs(entries, set())  # open-floor distance to nearest entry
    ranked = sorted(cells, key=lambda c: (int(dist[c[1], c[0]]), c[1], c[0]))
    if len(ranked) >= L.SHELF_COUNT:
        return {"rings-v1": ranked[: L.SHELF_COUNT]}

    from warehouse.layout import _shelves_without_pickup, _walkable_cells_connected

    chosen = set(cells)
    pool = [
        (x, y)
        for x in range(2, 50)
        for y in range(2, 50)
        if (x, y) not in chosen and (x, y) not in entries
    ]
    pool.sort(key=lambda c: (int(dist[c[1], c[0]]), c[1], c[0]))
    for cand in pool:
        if len(chosen) == L.SHELF_COUNT:
            break
        trial = chosen | {cand}
        if _shelves_without_pickup(trial):
            continue
        if not _walkable_cells_connected(trial):
            continue
        chosen = trial
    return {"rings-v1": list(chosen)}


def family_c(profiles: dict[str, np.ndarray]) -> dict[str, list[tuple[int, int]]]:
    total = float(profiles["cons"].sum())
    W_uni = np.full((L.SHELF_COUNT, L.ROBOT_COUNT), total / (960 * 96))
    return {
        "uni-t10lat": make_dp_layout("t10lat", W_uni),
        "uni-cols23": make_dp_layout("cols23", W_uni),
        "uni-comb": make_dp_layout("comb", W_uni),
    }


def family_e(profiles: dict[str, np.ndarray]) -> dict[str, list[tuple[int, int]]]:
    out = {}
    for lat in ("t10lat", "cols23", "comb"):
        for pname, W in profiles.items():
            out[f"dp-{lat}-{pname}"] = make_dp_layout(lat, W)
    return out


# ---------------------------------------------------------------- driver


def main() -> None:
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))

    profiles = {
        "cons": L.demand_weight_matrix(weights=L.DEFAULT_K_WEIGHTS),
        "deep": L.demand_weight_matrix(weights=DEEP_K_WEIGHTS),
    }

    candidates: dict[str, list[tuple[int, int]]] = {}
    fams = {
        "a": lambda: family_a(),
        "b": lambda: family_b(),
        "c": lambda: family_c(profiles),
        "e": lambda: family_e(profiles),
    }
    for fam, fn in fams.items():
        if only and fam not in only:
            continue
        candidates.update(fn())

    summary = []
    for name, shelves in candidates.items():
        error = L.validate(shelves)
        entry = {"name": name, "legal": error is None}
        if error is not None:
            entry["error"] = error
            print(f"ILLEGAL {name}: {error}")
        else:
            L.save_layout(OUT_DIR / f"{name}.json", shelves, {"name": name})
            entry.update(L.metrics(shelves))
            entry.update(L.predicted_scores(shelves))
            print(
                f"ok {name}: pred={entry['total_uncongested']} "
                f"trip={entry['mean_trip']} access={entry['mean_access_cells']} "
                f"one_access={entry['one_access_shelves']}"
            )
        summary.append(entry)

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {len(summary)} candidates to {OUT_DIR}")


if __name__ == "__main__":
    main()
