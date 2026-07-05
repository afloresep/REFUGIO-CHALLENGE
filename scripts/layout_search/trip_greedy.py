"""Greedy trip-by-trip replay scheduler.

Unlike full_day_schedule.py, this interleaves robots one trip at a time. Each
robot reserves its idle position until it moves again, so generated matrices are
collision-aware before final exact simulator validation.
"""

from __future__ import annotations

import argparse
import heapq
import json
import random
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from warehouse.targets import target_for

TICKS = 300
DIRS = list(ME.MOVE.items())


@dataclass
class RState:
    pos: tuple[int, int]
    t: int
    deliveries: int


class Reservations:
    def __init__(self, shelves):
        self.blocked = set(tuple(c) for c in shelves)
        self.cell: list[dict[tuple[int, int], set[int]]] = [dict() for _ in range(TICKS + 1)]
        self.edge: list[dict[tuple[tuple[int, int], tuple[int, int]], set[int]]] = [
            dict() for _ in range(TICKS)
        ]
        self.shelf_busy: list[dict[tuple[int, int], set[int]]] = [dict() for _ in range(TICKS)]

    @staticmethod
    def _add(bucket: dict, key, rid: int) -> None:
        bucket.setdefault(key, set()).add(rid)

    @staticmethod
    def _remove(bucket: dict, key, rid: int) -> None:
        owners = bucket.get(key)
        if not owners:
            return
        owners.discard(rid)
        if not owners:
            bucket.pop(key, None)

    def add_idle(self, rid: int, start_t: int, cell: tuple[int, int]) -> None:
        for t in range(start_t, TICKS + 1):
            self._add(self.cell[t], cell, rid)

    def remove_idle(self, rid: int, start_t: int, cell: tuple[int, int]) -> None:
        for t in range(start_t, TICKS + 1):
            self._remove(self.cell[t], cell, rid)

    def transition_free(self, rid: int, t: int, cur: tuple[int, int], nxt: tuple[int, int]) -> bool:
        if t + 1 > TICKS:
            return False
        if nxt in self.blocked:
            return False
        if any(owner != rid for owner in self.cell[t + 1].get(nxt, ())):
            return False
        if cur != nxt and any(owner != rid for owner in self.edge[t].get((nxt, cur), ())):
            return False
        return True

    def shelf_free(self, rid: int, t: int, shelf: tuple[int, int]) -> bool:
        if not (0 <= t < TICKS):
            return False
        return not any(owner != rid for owner in self.shelf_busy[t].get(shelf, ()))

    def add_segment(
        self,
        rid: int,
        start_t: int,
        positions: list[tuple[int, int]],
        actions: list[str],
        pickup_t: int,
        drop_t: int,
        shelf: tuple[int, int],
    ) -> None:
        for i, cell in enumerate(positions):
            t = start_t + i
            if t <= TICKS:
                self._add(self.cell[t], cell, rid)
        for i, ch in enumerate(actions):
            if ch not in ME.MOVE:
                continue
            t = start_t + i
            a = positions[i]
            b = positions[i + 1]
            self._add(self.edge[t], (a, b), rid)
        for t in range(pickup_t, min(drop_t + 1, TICKS)):
            self._add(self.shelf_busy[t], shelf, rid)


def pickup_cells(shelf, blocked):
    sx, sy = shelf
    out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cell = (sx + dx, sy + dy)
        if L.in_walk(*cell) and cell not in blocked:
            out.append(cell)
    return out


def astar(res: Reservations, rid: int, t0: int, start, goals, latest: int):
    if not goals:
        return None

    def h(cell):
        return min(abs(cell[0] - g[0]) + abs(cell[1] - g[1]) for g in goals)

    heap = [(t0 + h(start), t0, start)]
    came = {}
    seen = {(t0, start)}
    while heap:
        _, t, cell = heapq.heappop(heap)
        if cell in goals:
            return t, cell, backtrack(came, (t, cell))
        if t >= latest:
            continue
        for ch, (dx, dy) in DIRS + [("W", (0, 0))]:
            nxt = (cell[0] + dx, cell[1] + dy)
            if ch != "W" and not L.in_walk(*nxt):
                continue
            if not res.transition_free(rid, t, cell, nxt):
                continue
            key = (t + 1, nxt)
            if key in seen:
                continue
            seen.add(key)
            came[key] = (t, cell, ch)
            heapq.heappush(heap, (t + 1 + h(nxt), t + 1, nxt))
    return None


def backtrack(came, state):
    chars = []
    while state in came:
        pt, pc, ch = came[state]
        chars.append(ch)
        state = (pt, pc)
    return list(reversed(chars))


def advance(positions: list[tuple[int, int]], chars: list[str]) -> None:
    cell = positions[-1]
    for ch in chars:
        if ch in ME.MOVE:
            dx, dy = ME.MOVE[ch]
            cell = (cell[0] + dx, cell[1] + dy)
        positions.append(cell)


def plan_trip(data, res: Reservations, state: RState, rid: int):
    seed = data["seed"]
    shelves = L.sorted_shelves(data["shelves"])
    entry = L.base_entries_by_robot()[rid]
    target = target_for(seed, rid, state.deliveries, shelves)
    goals = set(pickup_cells(target, res.blocked))
    approach = astar(res, rid, state.t, state.pos, goals, TICKS - 2)
    if approach is None:
        return None
    t_pick, _, chars1 = approach
    if not res.shelf_free(rid, t_pick, target):
        return None
    positions = [state.pos]
    actions = list(chars1)
    advance(positions, chars1)
    actions.append("P")
    positions.append(positions[-1])
    back = astar(res, rid, t_pick + 1, positions[-1], {entry}, TICKS - 1)
    if back is None:
        return None
    t_drop, _, chars2 = back
    actions.extend(chars2)
    advance(positions, chars2)
    actions.append("O")
    positions.append(positions[-1])
    end_t = state.t + len(actions)
    if end_t > TICKS:
        return None
    return actions, positions, t_pick, t_drop, target, end_t


def trip_estimate(data, fields, rid: int, deliveries: int) -> int:
    shelves = L.sorted_shelves(data["shelves"])
    blocked = set(tuple(c) for c in data["shelves"])
    target = target_for(data["seed"], rid, deliveries, shelves)
    d = L.pickup_distance(fields[rid], target, blocked)
    return 10_000 if d < 0 else 2 * d + 2


def build(data: dict, mode: str, seed: int, max_trips: int):
    rng = random.Random(seed)
    entries = L.base_entries_by_robot()
    res = Reservations(data["shelves"])
    states = [RState(pos=entries[rid], t=0, deliveries=0) for rid in range(L.ROBOT_COUNT)]
    actions: list[list[str]] = [[] for _ in range(L.ROBOT_COUNT)]
    for rid, entry in enumerate(entries):
        res.add_idle(rid, 0, entry)

    fields = L.robot_fields(data["shelves"])
    heap = []
    for rid in range(L.ROBOT_COUNT):
        est = trip_estimate(data, fields, rid, 0)
        jitter = rng.random()
        if mode == "shortest":
            key = (est, jitter, rid)
        elif mode == "earliest":
            key = (0, est, jitter, rid)
        elif mode == "fewest":
            key = (0, est, jitter, rid)
        elif mode == "random":
            key = (jitter, est, rid)
        else:
            raise ValueError(f"unknown mode {mode}")
        heapq.heappush(heap, (*key, rid))

    diagnostics = []
    while heap:
        *_, rid = heapq.heappop(heap)
        state = states[rid]
        if state.deliveries >= max_trips or state.t >= TICKS - 2:
            continue
        planned = plan_trip(data, res, state, rid)
        if planned is None:
            diagnostics.append({"robot": rid, "t": state.t, "deliveries": state.deliveries, "planned": False})
            continue
        trip_actions, positions, pickup_t, drop_t, shelf, end_t = planned
        res.remove_idle(rid, state.t, state.pos)
        res.add_segment(rid, state.t, positions, trip_actions, pickup_t, drop_t, shelf)
        res.add_idle(rid, end_t, positions[-1])
        actions[rid].extend(trip_actions)
        states[rid] = RState(pos=positions[-1], t=end_t, deliveries=state.deliveries + 1)
        diagnostics.append({
            "robot": rid,
            "t0": state.t,
            "t1": end_t,
            "deliveries": state.deliveries + 1,
            "planned": True,
        })
        if states[rid].deliveries < max_trips:
            est = trip_estimate(data, fields, rid, states[rid].deliveries)
            jitter = rng.random()
            if mode == "shortest":
                key = (est, states[rid].t, jitter, rid)
            elif mode == "earliest":
                key = (states[rid].t, est, jitter, rid)
            elif mode == "fewest":
                key = (states[rid].deliveries, states[rid].t + est, jitter, rid)
            else:
                key = (jitter, states[rid].t + est, rid)
            heapq.heappush(heap, (*key, rid))

    matrix = [("".join(row) + "W" * TICKS)[:TICKS] for row in actions]
    out = dict(data)
    out["matrix"] = matrix
    return out, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix")
    parser.add_argument("out")
    parser.add_argument("--mode", choices=["shortest", "earliest", "fewest", "random"], default="earliest")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-trips", type=int, default=8)
    args = parser.parse_args()

    data = ME.load(Path(args.matrix))
    candidate, diagnostics = build(data, args.mode, args.seed, args.max_trips)
    result = ME.simulate(candidate)
    deliveries = ME.deliveries(result)
    payload = {
        "seed": data["seed"],
        "matrix": str(args.matrix),
        "mode": args.mode,
        "random_seed": args.seed,
        "score": sum(deliveries),
        "delivery_counts": dict(sorted((str(k), deliveries.count(k)) for k in set(deliveries))),
        "diagnostics": diagnostics,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate) + "\n")
    out.with_suffix(".summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({k: payload[k] for k in ("score", "delivery_counts", "mode", "random_seed")}, indent=2))


if __name__ == "__main__":
    main()
