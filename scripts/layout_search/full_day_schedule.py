"""Build replay matrices with offline full-day prioritized scheduling.

This is an experimental complement to replay-matrix micro-edits. It plans a
whole per-robot day from known target sequences, reserving cells, reverse edges,
and shelf locks from already planned robots, then validates the matrix with the
real simulator.
"""

from __future__ import annotations

import argparse
import heapq
import json
from collections import defaultdict
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from warehouse.targets import target_for


TICKS = 300
DIRS = list(ME.MOVE.items())


class Reservations:
    def __init__(self, shelves):
        self.blocked = set(tuple(c) for c in shelves)
        self.cell: list[set[tuple[int, int]]] = [set() for _ in range(TICKS + 1)]
        self.edge: list[set[tuple[tuple[int, int], tuple[int, int]]]] = [
            set() for _ in range(TICKS)
        ]
        self.shelf_busy: list[set[tuple[int, int]]] = [
            set() for _ in range(TICKS)
        ]

    def frame_free(self, t: int, cell: tuple[int, int]) -> bool:
        return 0 <= t <= TICKS and cell not in self.cell[t]

    def transition_free(
        self, t: int, cur: tuple[int, int], nxt: tuple[int, int]
    ) -> bool:
        if not self.frame_free(t + 1, nxt):
            return False
        if cur != nxt and (nxt, cur) in self.edge[t]:
            return False
        return True

    def shelf_free(self, t: int, shelf: tuple[int, int]) -> bool:
        return 0 <= t < TICKS and shelf not in self.shelf_busy[t]

    def add_robot(
        self,
        positions: list[tuple[int, int]],
        trips: list[tuple[int, int, tuple[int, int]]],
    ) -> None:
        for t, cell in enumerate(positions):
            self.cell[t].add(cell)
        for t in range(TICKS):
            a, b = positions[t], positions[t + 1]
            if a != b:
                self.edge[t].add((a, b))
        for pickup_tick, drop_tick, shelf in trips:
            for t in range(pickup_tick, min(drop_tick + 1, TICKS)):
                self.shelf_busy[t].add(shelf)


def pickup_cells(shelf, blocked):
    sx, sy = shelf
    out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cell = (sx + dx, sy + dy)
        if L.in_walk(*cell) and cell not in blocked:
            out.append(cell)
    return out


def astar(
    res: Reservations,
    start_t: int,
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    latest_arrival: int,
):
    if start_t > latest_arrival:
        return None

    def h(cell):
        return min(abs(cell[0] - g[0]) + abs(cell[1] - g[1]) for g in goals)

    heap = [(start_t + h(start), start_t, start)]
    came = {}
    seen = {(start_t, start)}
    while heap:
        _, t, cell = heapq.heappop(heap)
        if cell in goals:
            return t, cell, backtrack(came, (t, cell))
        if t >= latest_arrival or t >= TICKS:
            continue
        nt = t + 1
        for ch, (dx, dy) in DIRS + [("W", (0, 0))]:
            nxt = (cell[0] + dx, cell[1] + dy)
            if ch != "W":
                if not L.in_walk(*nxt) or nxt in res.blocked:
                    continue
            if not res.transition_free(t, cell, nxt):
                continue
            key = (nt, nxt)
            if key in seen:
                continue
            seen.add(key)
            came[key] = (t, cell, ch)
            heapq.heappush(heap, (nt + h(nxt), nt, nxt))
    return None


def tail_path(res: Reservations, start_t: int, start: tuple[int, int]):
    """Find any collision-free action suffix from start_t through tick 299."""
    heap = [(0, start_t, start)]
    came = {}
    seen = {(start_t, start)}
    while heap:
        cost, t, cell = heapq.heappop(heap)
        if t == TICKS:
            return backtrack(came, (t, cell))
        for ch, (dx, dy) in [("W", (0, 0))] + DIRS:
            nxt = (cell[0] + dx, cell[1] + dy)
            if ch != "W":
                if not L.in_walk(*nxt) or nxt in res.blocked:
                    continue
            if not res.transition_free(t, cell, nxt):
                continue
            key = (t + 1, nxt)
            if key in seen:
                continue
            seen.add(key)
            came[key] = (t, cell, ch)
            heapq.heappush(heap, (cost + (ch != "W"), t + 1, nxt))
    return None


def backtrack(came, state):
    chars = []
    while state in came:
        pt, pc, ch = came[state]
        chars.append(ch)
        state = (pt, pc)
    return list(reversed(chars))


def advance(
    positions: list[tuple[int, int]], actions: list[str], chars: list[str]
) -> None:
    cell = positions[-1]
    for ch in chars:
        actions.append(ch)
        if ch in ME.MOVE:
            dx, dy = ME.MOVE[ch]
            cell = (cell[0] + dx, cell[1] + dy)
        positions.append(cell)


def append_stationary(
    positions: list[tuple[int, int]], actions: list[str], ch: str
) -> None:
    actions.append(ch)
    positions.append(positions[-1])


def plan_robot(data: dict, res: Reservations, rid: int, max_trips: int = 8):
    seed = data["seed"]
    shelves = L.sorted_shelves(data["shelves"])
    entry = L.base_entries_by_robot()[rid]
    actions: list[str] = []
    positions = [entry]
    trips: list[tuple[int, int, tuple[int, int]]] = []

    for k in range(max_trips):
        now = len(actions)
        target = target_for(seed, rid, k, shelves)
        goals = set(pickup_cells(target, res.blocked))
        if not goals:
            break
        approach = astar(res, now, positions[-1], goals, TICKS - 2)
        if approach is None:
            break
        t_pick, _, chars = approach
        advance(positions, actions, chars)
        if len(actions) >= TICKS - 1:
            break
        if not res.frame_free(t_pick + 1, positions[-1]):
            break
        if not res.shelf_free(t_pick, target):
            break
        append_stationary(positions, actions, "P")

        back = astar(res, len(actions), positions[-1], {entry}, TICKS - 1)
        if back is None:
            actions.pop()
            positions.pop()
            break
        t_drop, _, chars = back
        advance(positions, actions, chars)
        if len(actions) >= TICKS:
            break
        if not res.frame_free(t_drop + 1, positions[-1]):
            break
        append_stationary(positions, actions, "O")
        trips.append((t_pick, t_drop, target))

    if len(actions) < TICKS:
        tail = tail_path(res, len(actions), positions[-1])
        if tail is None:
            return None
        advance(positions, actions, tail)

    return "".join(actions[:TICKS]), positions[: TICKS + 1], trips


def order_for(data: dict, mode: str) -> list[int]:
    base_result = ME.simulate(data)
    deliveries = ME.deliveries(base_result)
    entries = L.base_entries_by_robot()
    if mode == "id":
        return list(range(L.ROBOT_COUNT))
    if mode == "deliveries_desc":
        return sorted(range(L.ROBOT_COUNT), key=lambda r: (-deliveries[r], r))
    if mode == "deliveries_asc":
        return sorted(range(L.ROBOT_COUNT), key=lambda r: (deliveries[r], r))
    if mode == "center_first":
        return sorted(
            range(L.ROBOT_COUNT),
            key=lambda r: (abs(entries[r][0] - 26) + abs(entries[r][1] - 26), r),
        )
    if mode == "edge_first":
        return sorted(
            range(L.ROBOT_COUNT),
            key=lambda r: (-(abs(entries[r][0] - 26) + abs(entries[r][1] - 26)), r),
        )
    raise ValueError(f"unknown order mode: {mode}")


def build(data: dict, mode: str, max_trips: int):
    res = Reservations(data["shelves"])
    matrix = ["W" * TICKS for _ in range(L.ROBOT_COUNT)]
    diagnostics = []
    for rid in order_for(data, mode):
        planned = plan_robot(data, res, rid, max_trips=max_trips)
        if planned is None:
            diagnostics.append({"robot": rid, "planned": False})
            continue
        row, positions, trips = planned
        matrix[rid] = row
        res.add_robot(positions, trips)
        diagnostics.append({"robot": rid, "planned": True, "trips": len(trips)})
    out = dict(data)
    out["matrix"] = matrix
    return out, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix")
    parser.add_argument("out")
    parser.add_argument("--order", default="deliveries_desc")
    parser.add_argument("--max-trips", type=int, default=8)
    args = parser.parse_args()

    data = ME.load(Path(args.matrix))
    candidate, diagnostics = build(data, args.order, args.max_trips)
    result = ME.simulate(candidate)
    deliveries = ME.deliveries(result)
    payload = {
        "seed": candidate["seed"],
        "score": sum(deliveries),
        "delivery_counts": dict(sorted((str(k), deliveries.count(k)) for k in set(deliveries))),
        "diagnostics": diagnostics,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate))
    out.with_suffix(".summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
