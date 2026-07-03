"""Pair-mask lookahead for non-submodular near-miss conversions.

When no single traffic mask lowers the gain robot's extra-drop landing tick
(joint_repair's greedy gets 'stuck'), pairs can still work: two robots share
the same corridor window, and removing either alone leaves the other blocking.
This tool finds interactor robots along the gain robot's planned path, probes
all pairs (and triples seeded by the best pair), then hands any winning mask
set to joint_repair's blocker-fix + victim-cascade pipeline.

Usage:
  python3 scripts/layout_search/pair_mask.py MATRIX.json OUT.json --gain 41,65
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search import sweep_compress as SC
from layout_search.pair_repair import with_row
from layout_search.multi_mask import final_o
from layout_search.joint_repair import (
    Ctx, conflicts_with, local_fix, park, probe, traffic_mask,
)


def planned_path(data, pos, g, trips):
    """Cells-by-tick of g's extended-horizon plan (with current traffic)."""
    old = SC.TICKS
    SC.TICKS = 348
    try:
        pos_ext = pos + [pos[-1]] * (349 - len(pos))
        row = SC.build_row(data, pos_ext, g, trips)
    finally:
        SC.TICKS = old
    if row is None:
        return None
    cells = [tuple(pos[0][g])]
    c = cells[0]
    for ch in row:
        if ch in ME.MOVE:
            dx, dy = ME.MOVE[ch]
            c = (c[0] + dx, c[1] + dy)
        cells.append(c)
    return cells


def interactors(pos, g, cells, pad=2):
    out = set()
    for t, c in enumerate(cells):
        for dt in range(-pad, pad + 1):
            tt = t + dt
            if 0 <= tt < len(pos):
                for r in range(L.ROBOT_COUNT):
                    if r != g and abs(pos[tt][r][0] - c[0]) + abs(pos[tt][r][1] - c[1]) <= 1:
                        out.add(r)
    return sorted(out)


def masked_pos(pos, masks):
    p = pos
    for b in masks:
        p = traffic_mask(p, b)
    return p


def apply_masks(ctx, data, pos, best, g, masks):
    """joint_repair pipeline with a preset mask list."""
    trips = best[g] + 1
    row_g = SC.build_row(data, masked_pos(pos, masks), g, trips)
    if row_g is None or final_o(row_g) is None or final_o(row_g) > 299:
        return None, "real build failed"
    d_j, pos_j = with_row(data, pos, g, row_g)
    movers = [g]
    for b in masks:
        conf = conflicts_with(pos_j, b, movers)
        if conf:
            new_b = local_fix(ctx, d_j, pos_j, b, conf, best[b])
            if new_b is None:
                return None, f"blocker {b} unfixable"
            d_j, pos_j = with_row(d_j, pos_j, b, new_b)
        movers.append(b)
    for _round in range(6):
        d_fin = ME.deliveries(ME.simulate(d_j))
        losers = [r for r in range(L.ROBOT_COUNT) if d_fin[r] < best[r]]
        if not losers:
            return d_j, f"masks {masks}"
        progressed = False
        for v in losers:
            conf = conflicts_with(pos_j, v, [m for m in movers if m != v])
            if not conf:
                continue
            new_v = local_fix(ctx, d_j, pos_j, v, conf, best[v])
            if new_v is None:
                continue
            d_j, pos_j = with_row(d_j, pos_j, v, new_v)
            if v not in movers:
                movers.append(v)
            progressed = True
        if not progressed:
            return None, f"victims {losers} unfixable"
    return None, "cascade did not converge"


def run(data, gains, out: Path):
    ctx = Ctx(data)
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    for g in gains:
        trips = best[g] + 1
        cells = planned_path(data, pos, g, trips)
        if cells is None:
            print(f"  g={g}: unplannable")
            continue
        cand = interactors(pos, g, cells)
        print(f"  g={g}: {len(cand)} interactors")
        t_base = probe(data, pos, g, trips)
        winners = []
        for b1, b2 in itertools.combinations(cand, 2):
            t = probe(data, masked_pos(pos, [b1, b2]), g, trips)
            if t is not None and t <= 299:
                winners.append((t, [b1, b2]))
        if not winners:
            # triples seeded by best-scoring pairs
            pair_scores = []
            for b1, b2 in itertools.combinations(cand, 2):
                t = probe(data, masked_pos(pos, [b1, b2]), g, trips)
                if t is not None and t < (t_base or 999):
                    pair_scores.append((t, [b1, b2]))
            pair_scores.sort()
            for t2, pair in pair_scores[:5]:
                for b3 in cand:
                    if b3 in pair:
                        continue
                    t = probe(data, masked_pos(pos, pair + [b3]), g, trips)
                    if t is not None and t <= 299:
                        winners.append((t, pair + [b3]))
                if winners:
                    break
        if not winners:
            print(f"  g={g}: no pair/triple mask reaches 299")
            continue
        winners.sort(key=lambda w: (w[0], len(w[1])))
        converted = False
        for t, masks in winners[:8]:
            trial, info = apply_masks(ctx, data, pos, best, g, masks)
            if trial is None:
                print(f"  g={g} masks {masks}: {info}")
                continue
            d = ME.deliveries(ME.simulate(trial))
            if sum(d) > total:
                print(f"  g={g}: {total} -> {sum(d)} ({info})")
                data = trial
                best, total = d, sum(d)
                pos = ME.positions_by_tick(ME.simulate(data, record=True))
                out.write_text(json.dumps(data))
                converted = True
                break
        if not converted:
            print(f"  g={g}: all winning masks failed to apply")
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
