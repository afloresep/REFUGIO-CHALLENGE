"""Trip-by-trip suffix scheduler from an incumbent replay prefix.

The incumbent matrix is kept through t0. From the exact simulator state at t0,
all robots reserve their current idle cells. A greedy priority queue then plans
one additional delivery at a time, updating reservations after each committed
trip. The final matrix is validated by the exact simulator.
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
    carrying: bool
    deliveries: int
    target: tuple[int, int]


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

    def add_shelf_lock(self, rid: int, start_t: int, shelf: tuple[int, int]) -> None:
        for t in range(start_t, TICKS):
            self._add(self.shelf_busy[t], shelf, rid)

    def remove_shelf_lock(self, rid: int, start_t: int, shelf: tuple[int, int]) -> None:
        for t in range(start_t, TICKS):
            self._remove(self.shelf_busy[t], shelf, rid)

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
        locks: list[tuple[int, int, tuple[int, int]]],
    ) -> None:
        for i, cell in enumerate(positions):
            t = start_t + i
            if t <= TICKS:
                self._add(self.cell[t], cell, rid)
        for i, ch in enumerate(actions):
            if ch not in ME.MOVE:
                continue
            t = start_t + i
            self._add(self.edge[t], (positions[i], positions[i + 1]), rid)
        for pickup_t, drop_t, shelf in locks:
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


def append_action(actions: list[str], positions: list[tuple[int, int]], ch: str) -> None:
    actions.append(ch)
    positions.append(positions[-1])


def plan_one_delivery(data, res: Reservations, state: RState, rid: int):
    entry = L.base_entries_by_robot()[rid]
    seed = data["seed"]
    shelves = L.sorted_shelves(data["shelves"])
    actions: list[str] = []
    positions = [state.pos]
    locks: list[tuple[int, int, tuple[int, int]]] = []
    t = state.t
    target = state.target
    carrying = state.carrying
    pickup_t = state.t if carrying else None

    if not carrying:
        goals = set(pickup_cells(target, res.blocked))
        got = astar(res, rid, t, positions[-1], goals, TICKS - 2)
        if got is None:
            return None
        t, _, chars = got
        actions.extend(chars)
        advance(positions, chars)
        if not res.shelf_free(rid, t, target):
            return None
        if not res.transition_free(rid, t, positions[-1], positions[-1]):
            return None
        append_action(actions, positions, "P")
        pickup_t = t
        t += 1

    got = astar(res, rid, t, positions[-1], {entry}, TICKS - 1)
    if got is None:
        return None
    t, _, chars = got
    actions.extend(chars)
    advance(positions, chars)
    if not res.transition_free(rid, t, positions[-1], positions[-1]):
        return None
    append_action(actions, positions, "O")
    drop_t = t
    end_t = state.t + len(actions)
    if end_t > TICKS:
        return None
    locks.append((pickup_t if pickup_t is not None else state.t, drop_t, target))
    new_deliveries = state.deliveries + 1
    next_target = target_for(seed, rid, new_deliveries, shelves)
    new_state = RState(
        pos=positions[-1],
        t=end_t,
        carrying=False,
        deliveries=new_deliveries,
        target=next_target,
    )
    return actions, positions, locks, new_state


def state_at(result, rid: int, t0: int) -> RState:
    if t0 == 0:
        robot = sorted(result.initial_robots, key=lambda r: r.robot_id)[rid]
    else:
        robot = sorted(result.tick_results[t0 - 1].robots_after, key=lambda r: r.robot_id)[rid]
    return RState(
        pos=tuple(robot.position),
        t=t0,
        carrying=robot.carrying_item,
        deliveries=robot.deliveries,
        target=tuple(robot.target_item_position),
    )


def trip_estimate(data, fields, rid: int, deliveries: int) -> int:
    shelves = L.sorted_shelves(data["shelves"])
    blocked = set(tuple(c) for c in data["shelves"])
    target = target_for(data["seed"], rid, deliveries, shelves)
    d = L.pickup_distance(fields[rid], target, blocked)
    return 10_000 if d < 0 else 2 * d + 2


def heap_key(mode: str, state: RState, est: int, jitter: float, rid: int):
    if mode == "earliest":
        return (state.t, est, jitter, rid)
    if mode == "shortest":
        return (est, state.t, jitter, rid)
    if mode == "fewest":
        return (state.deliveries, state.t + est, jitter, rid)
    if mode == "random":
        return (jitter, state.t + est, rid)
    raise ValueError(mode)


def build(data: dict, t0: int, mode: str, seed: int, max_deliveries: int):
    rng = random.Random(seed)
    base = ME.simulate(data, record=True)
    states = [state_at(base, rid, t0) for rid in range(L.ROBOT_COUNT)]
    res = Reservations(data["shelves"])
    rows = [list(row[:t0]) for row in data["matrix"]]
    for rid, state in enumerate(states):
        res.add_idle(rid, t0, state.pos)
        if state.carrying:
            res.add_shelf_lock(rid, t0, state.target)

    fields = L.robot_fields(data["shelves"])
    heap = []
    for rid, state in enumerate(states):
        if state.deliveries >= max_deliveries:
            continue
        est = trip_estimate(data, fields, rid, state.deliveries)
        heapq.heappush(heap, (*heap_key(mode, state, est, rng.random(), rid), rid))

    diagnostics = []
    while heap:
        *_, rid = heapq.heappop(heap)
        state = states[rid]
        if state.t >= TICKS - 1 or state.deliveries >= max_deliveries:
            continue
        planned = plan_one_delivery(data, res, state, rid)
        if planned is None:
            diagnostics.append({
                "robot": rid,
                "t": state.t,
                "deliveries": state.deliveries,
                "planned": False,
            })
            continue
        trip_actions, positions, locks, new_state = planned
        res.remove_idle(rid, state.t, state.pos)
        if state.carrying:
            res.remove_shelf_lock(rid, state.t, state.target)
        res.add_segment(rid, state.t, positions, trip_actions, locks)
        res.add_idle(rid, new_state.t, new_state.pos)
        rows[rid].extend(trip_actions)
        states[rid] = new_state
        diagnostics.append({
            "robot": rid,
            "t0": state.t,
            "t1": new_state.t,
            "deliveries": new_state.deliveries,
            "planned": True,
        })
        est = trip_estimate(data, fields, rid, new_state.deliveries)
        heapq.heappush(heap, (*heap_key(mode, new_state, est, rng.random(), rid), rid))

    matrix = [("".join(row) + "W" * TICKS)[:TICKS] for row in rows]
    out = dict(data)
    out["matrix"] = matrix
    return out, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix")
    parser.add_argument("out")
    parser.add_argument("--t0", type=int, required=True)
    parser.add_argument("--mode", choices=["earliest", "shortest", "fewest", "random"], default="earliest")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-deliveries", type=int, default=8)
    args = parser.parse_args()

    data = ME.load(Path(args.matrix))
    candidate, diagnostics = build(data, args.t0, args.mode, args.seed, args.max_deliveries)
    result = ME.simulate(candidate)
    deliveries = ME.deliveries(result)
    payload = {
        "seed": data["seed"],
        "matrix": str(args.matrix),
        "t0": args.t0,
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
    print(json.dumps({k: payload[k] for k in ("score", "delivery_counts", "t0", "mode", "random_seed")}, indent=2))


if __name__ == "__main__":
    main()
