"""One-shot iteration driver: sweep -> probe -> floors -> min-mask.

Runs the whole conversion-discovery loop on a replay matrix:
1. single-robot lock-aware sweep (cheap conversions first);
2. extended-horizon shortfall probe over all 96 robots;
3. free-space floor triage (drop physically dead candidates);
4. minimal-mask core search + suffix cascade on the viable ones;
repeating until a full cycle adds nothing.

Usage:
  python3 scripts/layout_search/iterate.py MATRIX.json OUT.json [--exclude 93]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search import pair_mask as PM
from layout_search import sweep_compress as SW
from layout_search.joint_repair import Ctx, probe
from layout_search.pair_mask import apply_masks, interactors, masked_state, planned_path
from layout_search.min_mask import ideal_candidates, minimal_masks
from layout_search.pair_repair import masked

MAX_SHORTFALL = 10


def shortfalls(data, pos, best):
    out = []
    for rid in range(L.ROBOT_COUNT):
        t = probe(data, pos, rid, best[rid] + 1)
        if t is not None and 299 < t <= 299 + MAX_SHORTFALL:
            out.append((t - 299, rid))
    out.sort()
    return out


def floor_of(data, pos, g, trips):
    d_all, pos_all = data, pos
    for b in range(L.ROBOT_COUNT):
        if b != g:
            d_all, pos_all = masked(d_all, pos_all, b)
    return probe(d_all, pos_all, g, trips)


def cycle(data, out: Path, exclude: set[int]):
    ctx = Ctx(data)
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    improved = False

    # 1. sweep
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    for rid in range(L.ROBOT_COUNT):
        cand_row = SW.build_row(data, pos, rid, best[rid] + 1)
        if cand_row is None:
            continue
        trial = dict(data)
        trial["matrix"] = list(data["matrix"])
        trial["matrix"][rid] = cand_row
        d = ME.deliveries(ME.simulate(trial))
        if sum(d) > total:
            print(f"  sweep rid {rid}: {total} -> {sum(d)}", flush=True)
            data, best, total, improved = trial, d, sum(d), True
            pos = ME.positions_by_tick(ME.simulate(data, record=True))
            out.write_text(json.dumps(data))

    # 2-4. probe -> floors -> min-mask
    near = shortfalls(data, pos, best)
    print(f"  near-misses: {near}", flush=True)
    for shortfall, g in near:
        if g in exclude:
            continue
        trips = best[g] + 1
        fl = floor_of(data, pos, g, trips)
        if fl is None or fl > 299:
            print(f"  g={g}: floor {fl}, dead", flush=True)
            continue
        cand = [b for b in (ideal_candidates(data, pos, g, trips) or []) if b not in exclude]
        if not cand:
            continue
        cores, t_all = minimal_masks(data, pos, g, trips, cand)
        if cores is None:
            print(f"  g={g}: all-mask lands {t_all}, skip", flush=True)
            continue
        for core in cores:
            print(f"  g={g}: floor {fl}, core {core}", flush=True)
            trial, info = apply_masks(ctx, data, pos, best, g, core)
            if trial is None:
                print(f"  g={g}: {info}", flush=True)
                continue
            d = ME.deliveries(ME.simulate(trial))
            if sum(d) > total:
                print(f"  g={g}: {total} -> {sum(d)} ({info})", flush=True)
                data, best, total, improved = trial, d, sum(d), True
                pos = ME.positions_by_tick(ME.simulate(data, record=True))
                out.write_text(json.dumps(data))
                break
            print(f"  g={g}: sim rejected {sum(d)}", flush=True)
    return data, total, improved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--cycles", type=int, default=4)
    args = ap.parse_args()
    PM.FULL = True
    exclude = {int(x) for x in args.exclude.split(",") if x}
    data = ME.load(Path(args.matrix))
    print(f"start {data['seed'][:8]}: {sum(ME.deliveries(ME.simulate(data)))}", flush=True)
    for c in range(args.cycles):
        print(f"cycle {c}", flush=True)
        data, total, improved = cycle(data, Path(args.out), exclude)
        if not improved:
            break
    print(f"final {data['seed'][:8]}: {total}", flush=True)


if __name__ == "__main__":
    main()
