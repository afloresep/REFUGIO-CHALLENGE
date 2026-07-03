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
from layout_search import matrix_edit as ME
from layout_search import pair_mask as PM
from layout_search.joint_repair import Ctx, probe
from layout_search.pair_mask import apply_masks, interactors, masked_state, planned_path


def minimal_masks(data, pos, g, trips, cand):
    d_m, pos_m = masked_state(data, pos, cand)
    t_all = probe(d_m, pos_m, g, trips)
    if t_all is None or t_all > 299:
        return None, t_all
    core = list(cand)
    for b in sorted(cand):
        if len(core) <= 1:
            break
        trial = [x for x in core if x != b]
        d_m, pos_m = masked_state(data, pos, trial)
        t = probe(d_m, pos_m, g, trips)
        if t is not None and t <= 299:
            core = trial
    return core, t_all


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
        core, t_all = minimal_masks(data, pos, g, trips, cand)
        if core is None:
            print(f"  g={g}: even all-{len(cand)}-mask lands {t_all}")
            continue
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
        else:
            print(f"  g={g}: sim rejected {sum(d)}")
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
