"""Greedy leave-k-out repair for near-miss +1 conversions.

Where pair_repair.py needs a single critical blocker, this searches greedily
for a small set (k <= 3): each candidate mask is scored by how much it lowers
the landing tick of the gain robot's extra drop on an extended horizon. Once
the projected tick reaches <= 299, the gain robot's day is rebuilt for real
and every masked robot is rebuilt around it in sequence at unchanged delivery
count; the exact simulator validates the joint edit.

Usage:
  python3 scripts/layout_search/multi_mask.py MATRIX.json OUT.json --gain 69,65
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search import sweep_compress as SC
from layout_search.pair_repair import masked, with_row

EXT = 348  # extended planning horizon for shortfall scoring


def final_o(row: str | None) -> int | None:
    if row is None:
        return None
    t = row.rfind("O")
    return t if t >= 0 else None


def probe(data, pos, g, trips):
    """Landing tick of g's last drop on the extended horizon (None if unplannable)."""
    old = SC.TICKS
    SC.TICKS = EXT
    try:
        pos_ext = pos + [pos[-1]] * (EXT + 1 - len(pos))
        return final_o(SC.build_row(data, pos_ext, g, trips))
    finally:
        SC.TICKS = old


def convert(data, pos, best, g, out_masks=3):
    trips = best[g] + 1
    t_now = probe(data, pos, g, trips)
    if t_now is None:
        return None, "unplannable"
    masks: list[int] = []
    d_cur, pos_cur = data, pos
    while t_now > 299 and len(masks) < out_masks:
        scored = []
        for b in range(L.ROBOT_COUNT):
            if b == g or b in masks:
                continue
            d_m, pos_m = masked(d_cur, pos_cur, b)
            t_b = probe(d_m, pos_m, g, trips)
            if t_b is not None and t_b < t_now:
                scored.append((t_b, b))
        if not scored:
            return None, f"stuck at {t_now}"
        t_now, b = min(scored)
        masks.append(b)
        d_cur, pos_cur = masked(d_cur, pos_cur, b)
    if t_now > 299:
        return None, f"still {t_now} after masks {masks}"

    row_g = SC.build_row(d_cur, pos_cur, g, trips)
    if row_g is None or final_o(row_g) is None or final_o(row_g) > 299:
        return None, f"real build failed after masks {masks}"
    # rebuild masked robots around g, in both orders if needed
    for order in (masks, masks[::-1]):
        d_try, pos_try = with_row(data, pos, g, row_g)
        ok = True
        for b in order:
            row_b = SC.build_row(d_try, pos_try, b, best[b])
            if row_b is None:
                ok = False
                break
            d_try, pos_try = with_row(d_try, pos_try, b, row_b)
        if ok:
            return d_try, f"masks {order}"
    return None, f"blockers {masks} unrebuildable"


def run(data, gains, out: Path):
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    for g in gains:
        trial, info = convert(data, pos, best, g)
        if trial is None:
            print(f"  g={g}: {info}")
            continue
        d = ME.deliveries(ME.simulate(trial))
        if sum(d) > total:
            print(f"  g={g}: {total} -> {sum(d)} ({info})")
            data = trial
            best, total = d, sum(d)
            pos = ME.positions_by_tick(ME.simulate(data, record=True))
            out.write_text(json.dumps(data))
        else:
            print(f"  g={g}: sim rejected {sum(d)} ({info})")
    print(f"final {data['seed'][:8]}: {total}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--gain", required=True)
    args = ap.parse_args()
    data = ME.load(Path(args.matrix))
    run(data, [int(x) for x in args.gain.split(",")], Path(args.out))


if __name__ == "__main__":
    main()
