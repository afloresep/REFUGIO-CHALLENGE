"""Left-compress one robot's full day in a replay matrix.

Re-plans every leg (approach -> PICKUP -> return -> DROP) earliest-arrival
with a time-expanded A* against all other robots' frozen trajectories. The
robot's target sequence is computed offline from the counter-based generator,
so the whole day can shift earlier wherever the recorded bundle wasted ticks.
Validity (locks, pickup conflicts, collisions) is confirmed by the evaluator's
own simulator afterwards.
"""

from __future__ import annotations

import heapq
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from warehouse.targets import target_for


def earliest_astar(pos, blocked, rid, t_a, start, goals, t_max):
    """Earliest arrival at any goal cell from start@t_a, frozen obstacles."""
    def h(c):
        return min(abs(c[0] - g[0]) + abs(c[1] - g[1]) for g in goals)

    heap = [(t_a + h(start), t_a, start)]
    came, seen = {}, {(t_a, start)}
    while heap:
        f, t, cell = heapq.heappop(heap)
        if cell in goals:
            chars = []
            state = (t, cell)
            while state in came:
                pt, pc, ch = came[state]
                chars.append(ch)
                state = (pt, pc)
            return t, cell, list(reversed(chars))
        if t >= t_max:
            continue
        nt = t + 1
        occ_next = {pos[nt][r] for r in range(96) if r != rid} if nt < len(pos) else set()
        for ch, (dx, dy) in list(ME.MOVE.items()) + [("W", (0, 0))]:
            nc = (cell[0] + dx, cell[1] + dy)
            if ch != "W":
                if not L.in_walk(*nc) or nc in blocked:
                    continue
                if any(
                    r != rid and pos[t][r] == nc and nt < len(pos) and pos[nt][r] == cell
                    for r in range(96)
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


def pickup_cells(shelf, blocked):
    return {
        (shelf[0] + dx, shelf[1] + dy)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if L.in_walk(shelf[0] + dx, shelf[1] + dy)
        and (shelf[0] + dx, shelf[1] + dy) not in blocked
    }


def compress(data: dict, rid: int, trips: int, lock_floors: dict[int, int] | None = None):
    """Rebuild rid's first `trips` trips earliest-arrival; then park.

    lock_floors: optional {trip_index: earliest_pickup_frame} to respect shelf
    locks discovered via simulation.
    """
    seed = data["seed"]
    shelves = L.sorted_shelves([tuple(c) for c in data["shelves"]])
    blocked = set(shelves)
    entry = L.base_entries_by_robot()[rid]

    base = ME.simulate(data, record=True)
    pos = ME.positions_by_tick(base)

    row = []
    t = 0
    cell = entry
    for k in range(trips):
        target = target_for(seed, rid, k, shelves)
        goals = pickup_cells(target, blocked)
        res = earliest_astar(pos, blocked, rid, t, cell, goals, 299)
        if res is None:
            return None, f"trip {k}: no approach"
        t, cell, chars = res
        row += chars
        if lock_floors and k in lock_floors:
            while t < lock_floors[k]:
                row.append("W")
                t += 1
        row.append("P")
        t += 1
        res = earliest_astar(pos, blocked, rid, t, cell, {entry}, 299)
        if res is None:
            return None, f"trip {k}: no return"
        t, cell, chars = res
        row += chars
        if t > 299:
            return None, f"trip {k}: return too late ({t})"
        row.append("O")
        t += 1
    action_str = ("".join(row) + "W" * 300)[:300]
    return action_str, t - 1  # frame index of final O


if __name__ == "__main__":
    path, rid, trips = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    data = ME.load(path)
    row, info = compress(data, rid, trips)
    print(rid, "->", info)
