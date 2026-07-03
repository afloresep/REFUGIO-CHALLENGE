"""Strip dead post-final-delivery tails from a replay matrix.

Everything a robot does after its last successful drop delivers nothing: it
is residual traffic from the reactive planner chasing targets it never
completed. Frozen robots' recorded actions never depend on being blocked
(blocked actions were recorded as waits), so removing this traffic cannot
desync anyone; each stripped robot parks at its post-drop cell, wandering
only if another robot's frozen path passes through. The exact simulator
validates that per-robot deliveries are unchanged.

Thinner traffic makes subsequent day-compression sweeps strictly easier.

Usage:
  python3 scripts/layout_search/strip_tails.py MATRIX.json OUT.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search.sweep_compress import TICKS, wander_tail


def strip(data: dict) -> tuple[dict, int]:
    base = ME.simulate(data, record=True)
    baseline = ME.deliveries(base)
    pos = [list(frame) for frame in ME.positions_by_tick(base)]
    blocked = set(map(tuple, data["shelves"]))
    matrix = list(data["matrix"])
    stripped = 0

    for rid in range(L.ROBOT_COUNT):
        row = matrix[rid]
        t_o = max((t for t, ch in enumerate(row) if ch == "O"), default=-1)
        tail_start = t_o + 1
        if all(ch == "W" for ch in row[tail_start:]):
            continue
        cell = tuple(pos[tail_start][rid]) if tail_start < len(pos) else tuple(pos[-1][rid])

        def clear(c, t0):
            return all(
                tuple(pos[t][r]) != c
                for t in range(t0, TICKS + 1)
                for r in range(L.ROBOT_COUNT)
                if r != rid
            )

        if clear(cell, tail_start):
            new_positions = [cell] * (TICKS + 1 - tail_start)
            new_tail = "W" * (TICKS - tail_start)
        else:
            chars = wander_tail(pos, blocked, rid, tail_start, cell)
            if chars is None:
                continue
            new_positions, c = [cell], cell
            for ch in chars:
                if ch in ME.MOVE:
                    dx, dy = ME.MOVE[ch]
                    c = (c[0] + dx, c[1] + dy)
                new_positions.append(c)
            new_tail = "".join(chars)
        matrix[rid] = row[:tail_start] + new_tail
        for i, c in enumerate(new_positions):
            pos[tail_start + i][rid] = c
        stripped += 1

    out = dict(data)
    out["matrix"] = matrix
    check = ME.deliveries(ME.simulate(out))
    if check != baseline:
        diffs = [(r, baseline[r], check[r]) for r in range(L.ROBOT_COUNT) if baseline[r] != check[r]]
        raise RuntimeError(f"strip changed deliveries: {diffs}")
    return out, stripped


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    data = ME.load(src)
    out, n = strip(data)
    dst.write_text(json.dumps(out))
    d = ME.deliveries(ME.simulate(out))
    print(f"{data['seed'][:8]}: stripped {n} tails, total {sum(d)} (unchanged)")


if __name__ == "__main__":
    main()
