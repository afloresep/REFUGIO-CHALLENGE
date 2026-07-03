"""Lock-aware iterative day-compression sweep over a replay matrix.

Generalizes compress_day.py: each robot's whole day is rebuilt earliest-arrival
against the other 95 frozen trajectories, but the planner also respects the
exact simulator's shelf-lock semantics computed offline from the matrix rows:

- a shelf is locked while any robot carries an item drawn from it
  (ticks pickup+1 .. drop, inclusive);
- a pickup on a locked shelf is blocked; same-tick pickups on one shelf go to
  the lowest robot id;
- therefore the rebuilt robot must neither pick while another lock covers the
  tick (it would be blocked and desync itself) nor hold a lock across a frozen
  robot's recorded pickup tick (it would steal the lock and desync them).

Every accepted candidate is validated by the exact simulator; the sweep is
greedy (accept iff total deliveries strictly increase) and iterates passes
until a full pass yields nothing.

Usage:
  python3 scripts/layout_search/sweep_compress.py MATRIX.json OUT.json \
      [--passes 4] [--robots 0,17,37]
"""

from __future__ import annotations

import argparse
import heapq
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from warehouse.targets import target_for

TICKS = 300


def trips_from_row(row: str, seed: str, rid: int, shelves) -> list[tuple[int, int, tuple[int, int]]]:
    """(pickup_tick, drop_tick, shelf) per completed or in-flight trip."""
    out = []
    k = 0
    t_p = None
    for t, ch in enumerate(row):
        if ch == "P":
            t_p = t
        elif ch == "O" and t_p is not None:
            out.append((t_p, t, target_for(seed, rid, k, shelves)))
            k += 1
            t_p = None
    if t_p is not None:  # picked but never delivered
        out.append((t_p, TICKS, target_for(seed, rid, k, shelves)))
    return out


class LockModel:
    """Frozen shelf-lock intervals and pickup events, excluding one robot."""

    def __init__(self, data: dict, shelves, rid: int):
        self.locked: dict[tuple[int, int], list[tuple[int, int]]] = {}
        self.pick_events: dict[tuple[int, int], list[int]] = {}
        seed = data["seed"]
        for r, row in enumerate(data["matrix"]):
            if r == rid:
                continue
            for t_p, t_d, shelf in trips_from_row(row, seed, r, shelves):
                self.locked.setdefault(shelf, []).append((t_p + 1, min(t_d, TICKS)))
                self.pick_events.setdefault(shelf, []).append(t_p)

    def pick_ok(self, shelf, t_p: int) -> bool:
        """Our P at t_p is neither lock-blocked nor a same-tick contest."""
        for a, b in self.locked.get(shelf, ()):
            if a <= t_p <= b:
                return False
        return t_p not in self.pick_events.get(shelf, ())

    def steal_conflict(self, shelf, t_p: int, t_d: int) -> int | None:
        """Frozen pickup tick our lock [t_p+1, t_d] would cover, if any."""
        for t in sorted(self.pick_events.get(shelf, ())):
            if t_p + 1 <= t <= t_d:
                return t
        return None


def earliest_astar(pos, blocked, rid, t_a, start, goals, floor=0):
    """Earliest arrival at a goal cell (arrival >= floor), frozen obstacles."""
    def h(c):
        return min(abs(c[0] - g[0]) + abs(c[1] - g[1]) for g in goals)

    heap = [(t_a + h(start), t_a, start)]
    came, seen = {}, {(t_a, start)}
    while heap:
        _, t, cell = heapq.heappop(heap)
        if cell in goals and t >= floor:
            chars = []
            state = (t, cell)
            while state in came:
                pt, pc, ch = came[state]
                chars.append(ch)
                state = (pt, pc)
            return t, cell, list(reversed(chars))
        if t >= TICKS - 1:
            continue
        nt = t + 1
        occ_next = {pos[nt][r] for r in range(L.ROBOT_COUNT) if r != rid}
        for ch, (dx, dy) in list(ME.MOVE.items()) + [("W", (0, 0))]:
            nc = (cell[0] + dx, cell[1] + dy)
            if ch != "W":
                if not L.in_walk(*nc) or nc in blocked:
                    continue
                if any(
                    r != rid and pos[t][r] == nc and pos[nt][r] == cell
                    for r in range(L.ROBOT_COUNT)
                ):
                    continue
            if nc in occ_next:
                continue
            key = (nt, nc)
            if key in seen:
                continue
            seen.add(key)
            came[key] = (t, cell, ch)
            heapq.heappush(heap, (nt + h(nc), nt, nc))
    return None


def stationary_ok(pos, rid, cell, t) -> bool:
    """No frozen robot occupies `cell` at tick t (we stand there)."""
    if t >= len(pos):
        return True
    return all(pos[t][r] != cell for r in range(L.ROBOT_COUNT) if r != rid)


def wander_tail(pos, blocked, rid, t_start, cell) -> list[str] | None:
    """Collision-free filler for ticks t_start..299, preferring waits."""
    heap = [(0, t_start, cell)]
    came, seen = {}, {(t_start, cell)}
    while heap:
        cost, t, c = heapq.heappop(heap)
        if t == TICKS:
            chars = []
            state = (t, c)
            while state in came:
                pt, pc, ch = came[state]
                chars.append(ch)
                state = (pt, pc)
            return list(reversed(chars))
        nt = t + 1
        occ_next = {pos[nt][r] for r in range(L.ROBOT_COUNT) if r != rid} if nt < len(pos) else set()
        for ch, (dx, dy) in [("W", (0, 0))] + list(ME.MOVE.items()):
            nc = (c[0] + dx, c[1] + dy)
            if ch != "W":
                if not L.in_walk(*nc) or nc in blocked:
                    continue
                if any(
                    r != rid and pos[t][r] == nc and nt < len(pos) and pos[nt][r] == c
                    for r in range(L.ROBOT_COUNT)
                ):
                    continue
            if nc in occ_next:
                continue
            key = (nt, nc)
            if key in seen:
                continue
            seen.add(key)
            came[key] = (t, c, ch)
            heapq.heappush(heap, (cost + (ch != "W"), nt, nc))
    return None


def pickup_cells(shelf, blocked):
    return {
        (shelf[0] + dx, shelf[1] + dy)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if L.in_walk(shelf[0] + dx, shelf[1] + dy)
        and (shelf[0] + dx, shelf[1] + dy) not in blocked
    }


def build_row(data, pos, rid, trips_target) -> str | None:
    seed = data["seed"]
    shelves = L.sorted_shelves([tuple(c) for c in data["shelves"]])
    blocked = set(shelves)
    entry = L.base_entries_by_robot()[rid]
    locks = LockModel(data, shelves, rid)

    row: list[str] = []
    t, cell = 0, entry
    for k in range(trips_target):
        target = target_for(seed, rid, k, shelves)
        goals = pickup_cells(target, blocked)
        if not goals:
            return None
        floor = 0
        for _attempt in range(24):
            res = earliest_astar(pos, blocked, rid, t, cell, goals, floor=floor)
            if res is None:
                return None
            t_p, p_cell, chars = res
            # P at t_p: lock-legal and physically unobstructed next tick
            if not locks.pick_ok(target, t_p) or not stationary_ok(pos, rid, p_cell, t_p + 1):
                floor = t_p + 1
                continue
            back = earliest_astar(pos, blocked, rid, t_p + 1, p_cell, {entry})
            if back is None:
                return None
            t_d, _, back_chars = back
            if t_d > TICKS - 1:
                return None
            stolen = locks.steal_conflict(target, t_p, t_d)
            if stolen is not None:
                floor = stolen + 1  # pick after the frozen robot instead
                continue
            if not stationary_ok(pos, rid, entry, t_d + 1):
                floor = t_p + 1
                continue
            row += chars + ["P"] + back_chars + ["O"]
            t, cell = t_d + 1, entry
            break
        else:
            return None
    # park: W if the entry stays clear, else wander
    if all(stationary_ok(pos, rid, cell, tt) for tt in range(t, TICKS + 1)):
        row += ["W"] * (TICKS - t)
    else:
        tail = wander_tail(pos, blocked, rid, t, cell)
        if tail is None:
            return None
        row += tail
    return "".join(row[:TICKS])


def sweep(data: dict, robots: list[int], passes: int, out: Path):
    base = ME.simulate(data)
    best = ME.deliveries(base)
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    for p in range(passes):
        improved = False
        pos = ME.positions_by_tick(ME.simulate(data, record=True))
        for rid in robots:
            cand_row = build_row(data, pos, rid, best[rid] + 1)
            if cand_row is None:
                continue
            trial = dict(data)
            trial["matrix"] = list(data["matrix"])
            trial["matrix"][rid] = cand_row
            d = ME.deliveries(ME.simulate(trial))
            if sum(d) > total:
                print(f"  pass {p} rid {rid}: {total} -> {sum(d)} "
                      f"(rid {best[rid]} -> {d[rid]})")
                data = trial
                best, total = d, sum(d)
                out.write_text(json.dumps(data))
                pos = ME.positions_by_tick(ME.simulate(data, record=True))
                improved = True
            elif sum(d) != total or d[rid] != best[rid]:
                print(f"  pass {p} rid {rid}: rejected {sum(d)} (rid {d[rid]})")
        if not improved:
            break
    print(f"final {data['seed'][:8]}: {total}")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--passes", type=int, default=4)
    ap.add_argument("--robots", default=None)
    args = ap.parse_args()
    data = ME.load(Path(args.matrix))
    robots = (
        [int(x) for x in args.robots.split(",")]
        if args.robots
        else list(range(L.ROBOT_COUNT))
    )
    sweep(data, robots, args.passes, Path(args.out))


if __name__ == "__main__":
    main()
