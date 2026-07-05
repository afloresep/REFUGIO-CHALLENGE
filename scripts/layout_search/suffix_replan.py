"""Experimental suffix replanner for replay matrices.

Keep the incumbent replay prefix through a chosen tick, then rebuild a small
set of robots' remaining actions against frozen outside traffic. This is a
middle ground between one-row compression and full-day scheduling.
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from warehouse.targets import target_for

TICKS = 300
DIRS = list(ME.MOVE.items())


@dataclass(frozen=True)
class RState:
    pos: tuple[int, int]
    carrying: bool
    deliveries: int
    target: tuple[int, int]


class Res:
    def __init__(self, shelves):
        self.blocked = set(tuple(c) for c in shelves)
        self.cell = [set() for _ in range(TICKS + 1)]
        self.edge = [set() for _ in range(TICKS)]
        self.shelf_busy = [set() for _ in range(TICKS)]

    def add_outside(self, result, moving: set[int], t0: int) -> None:
        tracks = ME.positions_by_tick(result)
        for t in range(t0, TICKS + 1):
            for rid in range(L.ROBOT_COUNT):
                if rid not in moving:
                    self.cell[t].add(tracks[t][rid])
        for t in range(t0, TICKS):
            robots_before = {r.robot_id: r for r in result.tick_results[t].robots_before}
            for rid in range(L.ROBOT_COUNT):
                if rid in moving:
                    continue
                a, b = tracks[t][rid], tracks[t + 1][rid]
                if a != b:
                    self.edge[t].add((a, b))
                r = robots_before[rid]
                if r.carrying_item:
                    self.shelf_busy[t].add(tuple(r.target_item_position))

    def add_path(
        self,
        positions: list[tuple[int, int]],
        trips: list[tuple[int, int, tuple[int, int]]],
        t0: int,
    ) -> None:
        for i, cell in enumerate(positions):
            t = t0 + i
            if t <= TICKS:
                self.cell[t].add(cell)
        for i in range(min(len(positions) - 1, TICKS - t0)):
            a, b = positions[i], positions[i + 1]
            if a != b:
                self.edge[t0 + i].add((a, b))
        for pickup_t, drop_t, shelf in trips:
            for t in range(pickup_t, min(drop_t + 1, TICKS)):
                self.shelf_busy[t].add(shelf)

    def free_transition(self, t: int, cur: tuple[int, int], nxt: tuple[int, int]) -> bool:
        if t + 1 > TICKS or nxt in self.cell[t + 1]:
            return False
        if cur != nxt and (nxt, cur) in self.edge[t]:
            return False
        return True


def pickup_cells(shelf, blocked):
    sx, sy = shelf
    out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        c = (sx + dx, sy + dy)
        if L.in_walk(*c) and c not in blocked:
            out.append(c)
    return out


def astar(res: Res, rid: int, t0: int, start, goals, latest: int):
    if not goals:
        return None

    def h(c):
        return min(abs(c[0] - g[0]) + abs(c[1] - g[1]) for g in goals)

    heap = [(t0 + h(start), t0, start)]
    seen = {(t0, start)}
    came = {}
    while heap:
        _, t, cell = heapq.heappop(heap)
        if cell in goals:
            return t, cell, backtrack(came, (t, cell))
        if t >= latest or t >= TICKS:
            continue
        for ch, (dx, dy) in DIRS + [("W", (0, 0))]:
            nxt = (cell[0] + dx, cell[1] + dy)
            if ch != "W" and (not L.in_walk(*nxt) or nxt in res.blocked):
                continue
            if not res.free_transition(t, cell, nxt):
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


def advance(actions, positions, chars):
    cell = positions[-1]
    for ch in chars:
        actions.append(ch)
        if ch in ME.MOVE:
            dx, dy = ME.MOVE[ch]
            cell = (cell[0] + dx, cell[1] + dy)
        positions.append(cell)


def append_static(actions, positions, ch):
    actions.append(ch)
    positions.append(positions[-1])


def robot_state_at(result, rid: int, t0: int) -> RState:
    if t0 == 0:
        r = sorted(result.initial_robots, key=lambda x: x.robot_id)[rid]
    else:
        r = sorted(result.tick_results[t0 - 1].robots_after, key=lambda x: x.robot_id)[rid]
    return RState(tuple(r.position), r.carrying_item, r.deliveries, tuple(r.target_item_position))


def plan_one(data, res: Res, state: RState, rid: int, t0: int, target_deliveries: int):
    seed = data["seed"]
    shelves = L.sorted_shelves(data["shelves"])
    entry = L.base_entries_by_robot()[rid]
    actions = []
    positions = [state.pos]
    trips = []
    t = t0
    carrying = state.carrying
    deliveries = state.deliveries
    target = state.target
    locked_since = t0 if carrying else None

    while deliveries < target_deliveries and t < TICKS:
        if not carrying:
            goals = set(pickup_cells(target, res.blocked))
            got = astar(res, rid, t, positions[-1], goals, TICKS - 2)
            if got is None:
                break
            t, _, chars = got
            advance(actions, positions, chars)
            if t >= TICKS or target in res.shelf_busy[t]:
                break
            append_static(actions, positions, "P")
            carrying = True
            locked_since = t
            t += 1
        got = astar(res, rid, t, positions[-1], {entry}, TICKS - 1)
        if got is None:
            break
        t, _, chars = got
        advance(actions, positions, chars)
        if t >= TICKS:
            break
        append_static(actions, positions, "O")
        trips.append((locked_since if locked_since is not None else t, t, target))
        deliveries += 1
        carrying = False
        locked_since = None
        target = target_for(seed, rid, deliveries, shelves)
        t += 1

    # Park safely through the horizon.
    while len(actions) < TICKS - t0:
        cur_t = t0 + len(actions)
        if res.free_transition(cur_t, positions[-1], positions[-1]):
            append_static(actions, positions, "W")
        else:
            moved = False
            for ch, (dx, dy) in DIRS:
                nxt = (positions[-1][0] + dx, positions[-1][1] + dy)
                if L.in_walk(*nxt) and nxt not in res.blocked and res.free_transition(cur_t, positions[-1], nxt):
                    advance(actions, positions, [ch])
                    moved = True
                    break
            if not moved:
                return None
    return "".join(actions[: TICKS - t0]), positions[: TICKS - t0 + 1], trips


def replan(data, rids: list[int], t0: int, targets: dict[int, int], order: tuple[int, ...]):
    result = ME.simulate(data, record=True)
    res = Res(data["shelves"])
    moving = set(rids)
    res.add_outside(result, moving, t0)
    matrix = list(data["matrix"])
    diagnostics = []
    for rid in order:
        state = robot_state_at(result, rid, t0)
        target_deliveries = targets.get(rid, state.deliveries)
        planned = plan_one(data, res, state, rid, t0, target_deliveries)
        if planned is None:
            return None, diagnostics + [{"robot": rid, "planned": False}]
        row_suffix, positions, trips = planned
        matrix[rid] = matrix[rid][:t0] + row_suffix
        res.add_path(positions, trips, t0)
        diagnostics.append({"robot": rid, "planned": True, "target_deliveries": target_deliveries, "trips": len(trips)})
    out = dict(data)
    out["matrix"] = matrix
    return out, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix")
    parser.add_argument("out")
    parser.add_argument("--rids", required=True, help="comma-separated robot ids")
    parser.add_argument("--t0", type=int, required=True)
    parser.add_argument("--target", action="append", default=[], help="rid:deliveries")
    parser.add_argument("--max-orders", type=int, default=120)
    args = parser.parse_args()

    data = ME.load(Path(args.matrix))
    base = ME.simulate(data)
    base_d = ME.deliveries(base)
    rids = [int(x) for x in args.rids.split(",") if x]
    targets = {rid: base_d[rid] for rid in rids}
    for item in args.target:
        rid_s, val_s = item.split(":", 1)
        targets[int(rid_s)] = int(val_s)
    best = None
    tried = 0
    for order in itertools.permutations(rids):
        tried += 1
        candidate, diagnostics = replan(data, rids, args.t0, targets, order)
        if candidate is None:
            continue
        res = ME.simulate(candidate)
        d = ME.deliveries(res)
        total = sum(d)
        if best is None or total > best[0]:
            best = (total, order, candidate, diagnostics, d)
            print(json.dumps({
                "best": total,
                "order": order,
                "delivery_counts": dict(sorted((str(k), d.count(k)) for k in set(d))),
                "diagnostics": diagnostics,
            }, indent=2))
        if tried >= args.max_orders:
            break
    if best is None:
        raise SystemExit("no feasible candidate")
    total, order, candidate, diagnostics, d = best
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate))
    out.with_suffix(".summary.json").write_text(json.dumps({
        "score": total,
        "order": list(order),
        "delivery_counts": dict(sorted((str(k), d.count(k)) for k in set(d))),
        "diagnostics": diagnostics,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
