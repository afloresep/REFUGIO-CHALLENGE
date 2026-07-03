"""Leave-one-out pair repair for near-miss +1 conversions.

For a gain robot g whose extra trip misses tick 299 by a hair, identify the
critical blocker: re-plan g's +1 day with each other robot b hypothetically
removed (its traffic and shelf locks masked). If removing b converts g, fix
g's ideal plan as frozen traffic and rebuild b's day around it at unchanged
delivery count. The exact simulator validates the joint edit.

Usage:
  python3 scripts/layout_search/pair_repair.py MATRIX.json OUT.json --gain 41,38
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search.sweep_compress import build_row

OFFGRID = (-99, -99)


def masked(data: dict, pos, b: int):
    """Copy of (data, pos) with robot b's traffic and locks removed."""
    d2 = dict(data)
    d2["matrix"] = list(data["matrix"])
    d2["matrix"][b] = "W" * len(data["matrix"][b])
    pos2 = [list(frame) for frame in pos]
    for frame in pos2:
        frame[b] = OFFGRID
    return d2, pos2


def with_row(data: dict, pos, rid: int, row: str):
    """Copy of (data, pos) with rid's row replaced and positions replayed."""
    d2 = dict(data)
    d2["matrix"] = list(data["matrix"])
    d2["matrix"][rid] = row
    pos2 = [list(frame) for frame in pos]
    cell = tuple(pos[0][rid])
    for t, ch in enumerate(row):
        if ch in ME.MOVE:
            dx, dy = ME.MOVE[ch]
            cell = (cell[0] + dx, cell[1] + dy)
        pos2[t + 1][rid] = cell
    return d2, pos2


def repair(data: dict, gains: list[int], out: Path):
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    for g in gains:
        if build_row(data, pos, g, best[g] + 1) is not None:
            continue  # single-robot sweep already handles this
        converted = False
        for b in range(L.ROBOT_COUNT):
            if b == g:
                continue
            d_masked, pos_masked = masked(data, pos, b)
            row_g = build_row(d_masked, pos_masked, g, best[g] + 1)
            if row_g is None:
                continue
            # b is critical: rebuild b around g's ideal plan
            d_g, pos_g = with_row(data, pos, g, row_g)
            row_b = build_row(d_g, pos_g, b, best[b])
            if row_b is None:
                print(f"  g={g}: blocker b={b} found but b unrebuildable")
                continue
            trial = dict(d_g)
            trial["matrix"] = list(d_g["matrix"])
            trial["matrix"][b] = row_b
            d = ME.deliveries(ME.simulate(trial))
            if sum(d) > total:
                print(f"  g={g} b={b}: {total} -> {sum(d)}")
                data = trial
                best, total = d, sum(d)
                pos = ME.positions_by_tick(ME.simulate(data, record=True))
                out.write_text(json.dumps(data))
                converted = True
                break
            print(f"  g={g} b={b}: joint rejected ({sum(d)})")
        if not converted:
            print(f"  g={g}: no single-blocker conversion")
    print(f"final {data['seed'][:8]}: {total}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--gain", required=True)
    args = ap.parse_args()
    data = ME.load(Path(args.matrix))
    gains = [int(x) for x in args.gain.split(",")]
    repair(data, gains, Path(args.out))


if __name__ == "__main__":
    main()
