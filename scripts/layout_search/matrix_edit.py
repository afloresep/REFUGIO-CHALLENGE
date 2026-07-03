"""Edit replay action matrices: exact internal sim + time-expanded re-routing.

The replay reframe: with every robot's actions frozen in a matrix, edits have
no cascade surface. Re-route one robot around the other 95 frozen trajectories
with a time-expanded A*, verify with the evaluator's own simulator.

Library + CLI: `sim` scores a matrix file; editing is scripted per case.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L

from warehouse.simulation import run_simulation
from warehouse_api import Action

ACT = {
    "U": Action.UP, "D": Action.DOWN, "L": Action.LEFT, "R": Action.RIGHT,
    "W": Action.WAIT, "P": Action.PICKUP, "O": Action.DROP,
}
MOVE = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
DELTA_TO_CH = {v: k for k, v in MOVE.items()}


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def simulate(data: dict, record: bool = False):
    matrix = data["matrix"]

    def policy(obs):
        row = matrix[obs.robot_id]
        if obs.tick >= len(row):
            return Action.WAIT
        return ACT[row[obs.tick]]

    return run_simulation(
        data["seed"], policy, ticks=len(matrix[0]),
        shelf_cells=[tuple(c) for c in data["shelves"]],
        record_ticks=record,
    )


def deliveries(result) -> list[int]:
    return [r.deliveries for r in sorted(result.final_robots, key=lambda r: r.robot_id)]


def positions_by_tick(result) -> list[list[tuple[int, int]]]:
    """pos[tick][rid], including tick 0 (initial) .. ticks (final)."""
    out = [[tuple(r.position) for r in sorted(result.initial_robots, key=lambda r: r.robot_id)]]
    for tr in result.tick_results:
        out.append([tuple(r.position) for r in sorted(tr.robots_after, key=lambda r: r.robot_id)])
    return out


def reroute(
    data: dict,
    pos: list[list[tuple[int, int]]],
    rid: int,
    t_start: int,
    goal: tuple[int, int],
    t_deadline: int,
) -> list[str] | None:
    """Time-expanded A*: path for rid from its pos at t_start to goal by
    t_deadline, avoiding all other robots' frozen (tick, cell) and swaps.
    Returns action chars covering ticks t_start .. arrival-1, or None."""
    import heapq

    blocked = L.shelf_set([tuple(c) for c in data["shelves"]])
    start = pos[t_start][rid]
    occupied = {}
    for t in range(t_start, min(t_deadline + 2, len(pos))):
        occupied[t] = {pos[t][r] for r in range(L.ROBOT_COUNT) if r != rid}

    def h(c):
        return abs(c[0] - goal[0]) + abs(c[1] - goal[1])

    heap = [(h(start), t_start, start)]
    came: dict[tuple, tuple] = {}
    seen = {(t_start, start)}
    while heap:
        f, t, cell = heapq.heappop(heap)
        if cell == goal:
            # backtrack
            chars = []
            state = (t, cell)
            while state in came:
                pt, pc, ch = came[state]
                chars.append(ch)
                state = (pt, pc)
            return list(reversed(chars))
        if t >= t_deadline:
            continue
        nt = t + 1
        occ_next = occupied.get(nt, set())
        occ_now = occupied.get(t, set())
        for ch, (dx, dy) in list(MOVE.items()) + [("W", (0, 0))]:
            nc = (cell[0] + dx, cell[1] + dy)
            if ch != "W":
                if not L.in_walk(*nc) or nc in blocked:
                    continue
                # swap conflict: someone at nc now moving to our cell
                if nc in occ_now:
                    others_next = {
                        r for r in range(L.ROBOT_COUNT)
                        if r != rid and pos[t][r] == nc and nt < len(pos) and pos[nt][r] == cell
                    }
                    if others_next:
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


def splice(row: str, t_start: int, chars: list[str], then: str, resume_at: int | None) -> str:
    """Replace row[t_start:] with chars + then + (waits | recorded tail)."""
    n = len(row)
    prefix = row[:t_start]
    body = "".join(chars) + then
    end = t_start + len(body)
    if resume_at is None:
        return (prefix + body + "W" * n)[:n]
    assert end <= resume_at, f"edit overruns resume point: {end} > {resume_at}"
    return prefix + body + "W" * (resume_at - end) + row[resume_at:]


if __name__ == "__main__":
    data = load(Path(sys.argv[2]))
    result = simulate(data)
    d = deliveries(result)
    print(f"{data['seed'][:8]}: total {sum(d)}")
