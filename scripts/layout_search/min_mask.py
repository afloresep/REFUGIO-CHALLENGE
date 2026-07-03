"""Minimal-mask search: mask all interactors, then greedily eliminate.

For deep knots where pairs/triples fail but the free-space floor allows the
conversion: masking every robot that interacts with the gain robot's corridor
must reproduce (approximately) the floor. Greedy elimination then finds an
irreducible mask core; if it is small, joint_repair's blocker-fix + victim
cascade can rebuild everyone around the gain robot's ideal day.

Usage:
  python3 scripts/layout_search/min_mask.py MATRIX.json OUT.json --gain 20,42 [--full]
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
from layout_search import sweep_compress as SC
from layout_search.joint_repair import Ctx, probe
from layout_search.pair_mask import apply_masks, interactors, masked_state, planned_path
from layout_search.pair_repair import masked
from layout_search.sweep_compress import trips_from_row


def ideal_candidates(data, pos, g, trips, pad=2):
    """Interactors + lock owners along g's FREE-SPACE ideal corridor.

    The corridor-interactor set misses distant lock owners: a robot whose
    shelf lock (not body) delays the gain robot. Plan the ideal day with
    everyone masked, then collect (a) robots whose incumbent positions touch
    that corridor, (b) robots whose trips lock a shelf adjacent to it during
    the corridor's time window.
    """
    d_all, pos_all = data, pos
    for b in range(L.ROBOT_COUNT):
        if b != g:
            d_all, pos_all = masked(d_all, pos_all, b)
    cells = planned_path(d_all, pos_all, g, trips)
    if cells is None:
        return None
    cand = set(interactors(pos, g, cells, pad=pad))
    corridor = {}
    for t, c in enumerate(cells):
        corridor.setdefault(c, []).append(t)
    seed = data["seed"]
    shelves = L.sorted_shelves([tuple(c) for c in data["shelves"]])
    for r, row in enumerate(data["matrix"]):
        if r == g:
            continue
        for t_p, t_d, shelf in trips_from_row(row, seed, r, shelves):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pc = (shelf[0] + dx, shelf[1] + dy)
                ts = corridor.get(pc)
                if ts and any(t_p - 4 <= t <= t_d + 4 for t in ts):
                    cand.add(r)
                    break
    return sorted(cand)


def minimal_masks(data, pos, g, trips, cand, orders=2):
    """Irreducible mask cores; several greedy elimination orders when asked."""
    d_m, pos_m = masked_state(data, pos, cand)
    t_all = probe(d_m, pos_m, g, trips)
    if t_all is None or t_all > 299:
        return None, t_all
    cores = []
    for order in ([sorted(cand), sorted(cand, reverse=True)])[:orders]:
        core = list(cand)
        for b in order:
            if len(core) <= 1:
                break
            trial = [x for x in core if x != b]
            d_m, pos_m = masked_state(data, pos, trial)
            t = probe(d_m, pos_m, g, trips)
            if t is not None and t <= 299:
                core = trial
        if sorted(core) not in [sorted(c) for c in cores]:
            cores.append(core)
    return cores, t_all


def run(data, gains, out: Path):
    ctx = Ctx(data)
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    for g in gains:
        trips = best[g] + 1
        cand = ideal_candidates(data, pos, g, trips)
        if cand is None:
            print(f"  g={g}: unplannable")
            continue
        cores, t_all = minimal_masks(data, pos, g, trips, cand)
        if cores is None:
            print(f"  g={g}: even all-{len(cand)}-mask lands {t_all}")
            continue
        converted = False
        for core in cores:
            print(f"  g={g}: core {core} (all-mask lands {t_all})")
            trial, info = apply_masks(ctx, data, pos, best, g, core)
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
                converted = True
                break
            print(f"  g={g}: sim rejected {sum(d)}")
        if converted:
            continue
    print(f"final {data['seed'][:8]}: {total}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--gain", required=True)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    PM.FULL = args.full
    data = ME.load(Path(args.matrix))
    run(data, [int(x) for x in args.gain.split(",")], Path(args.out))


if __name__ == "__main__":
    main()
