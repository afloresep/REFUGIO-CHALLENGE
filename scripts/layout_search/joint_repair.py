"""General joint repair: traffic-masked ideal + blocker fixes + victim cascade.

The pipeline that converted bff0 robot 69 as a three-robot joint edit:

1. Plan the gain robot's +1 day with selected blockers' TRAFFIC masked but
   their shelf locks live (greedy leave-k-out scored by the extra drop's
   landing tick, like multi_mask but traffic-only, which avoids lock
   surprises when the blockers are later re-timed).
2. Fix each blocker locally around the gain robot's fixed ideal day:
   - conflict segment without a pickup: retime the in-flight return;
   - segment containing its pickup: rebuild the whole final trip;
   both re-parked with wait-or-wander so no lane is left blocked.
3. Victim cascade: simulate; any robot that lost a delivery gets the same
   local fix around all movers; repeat up to 4 rounds.

Every accepted result is validated by the exact simulator (strict total
improvement).

Usage:
  python3 scripts/layout_search/joint_repair.py MATRIX.json OUT.json --gain 41,65
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
from layout_search.pair_repair import with_row
from layout_search.multi_mask import final_o
from warehouse.targets import target_for

OFFGRID = (-99, -99)
EXT = 348


def traffic_mask(pos, b):
    pos2 = [list(f) for f in pos]
    for f in pos2:
        f[b] = OFFGRID
    return pos2


def probe(data, pos, g, trips):
    old = SC.TICKS
    SC.TICKS = EXT
    try:
        pos_ext = pos + [pos[-1]] * (EXT + 1 - len(pos))
        return final_o(SC.build_row(data, pos_ext, g, trips))
    finally:
        SC.TICKS = old


class Ctx:
    def __init__(self, data):
        self.seed = data["seed"]
        self.shelves = L.sorted_shelves([tuple(c) for c in data["shelves"]])
        self.blocked = set(self.shelves)
        self.entries = L.base_entries_by_robot()


def park(ctx, pos_ref, b, head, t, cell):
    if all(SC.stationary_ok(pos_ref, b, cell, tt) for tt in range(t, 301)):
        return head + "W" * (300 - len(head))
    tail = SC.wander_tail(pos_ref, ctx.blocked, b, t, cell)
    if tail is None:
        return None
    return (head + "".join(tail))[:300]


def trips_done(row):
    return sum(1 for ch in row if ch == "O")


def conflicts_with(pos_j, b, movers):
    out = []
    for t in range(301):
        pb = tuple(pos_j[t][b])
        for m in movers:
            if pb == tuple(pos_j[t][m]) or (
                t and pb == tuple(pos_j[t - 1][m]) and tuple(pos_j[t - 1][b]) == tuple(pos_j[t][m])
            ):
                out.append(t)
    return sorted(set(out))


def local_fix(ctx, d_j, pos_j, b, conf, n_trips):
    """Fix robot b around new traffic near `conf` ticks; keep n_trips drops.

    Rebuilds b's whole remaining day from the last drop before the conflict:
    an in-flight return is retimed when nothing else follows, otherwise every
    remaining trip is re-planned (lock-aware) and the robot re-parks with
    wait-or-wander.
    """
    row_b = d_j["matrix"][b]
    t0 = max(0, min(conf) - 2)
    prior = [t for t in range(t0, min(conf)) if row_b[t] in "PO"]
    if prior:
        t0 = prior[-1] + 1
    prev_o = [t for t in range(t0) if row_b[t] == "O"]
    k_start = len(prev_o)
    carrying = any(row_b[t] == "P" for t in range(prev_o[-1] + 1 if prev_o else 0, t0))
    if k_start >= n_trips and not carrying:
        # day complete: retime nothing, just re-park from t0
        return park(ctx, pos_j, b, row_b[:t0], t0, tuple(pos_j[t0][b]))
    if carrying and not any(row_b[t] == "P" for t in range(t0, 300)):
        # in-flight return: retime path to entry + O, then rebuild the rest
        res = SC.earliest_astar(pos_j, ctx.blocked, b, t0, tuple(pos_j[t0][b]), {ctx.entries[b]})
        if res is None:
            return None
        t_e, _, chars = res
        if t_e > 299:
            return None
        head = row_b[:t0] + "".join(chars) + "O"
        t_next, k_next = t_e + 1, k_start + 1
        cell = ctx.entries[b]
    else:
        # rebuild from the trip boundary (redoes any unmatched pickup)
        t_next = prev_o[-1] + 1 if prev_o else 0
        head = row_b[:t_next]
        k_next = k_start
        cell = tuple(pos_j[t_next][b])  # prefix unchanged, so still valid
    locks = SC.LockModel(d_j, ctx.shelves, b)
    for k in range(k_next, n_trips):
        target = target_for(ctx.seed, b, k, ctx.shelves)
        plan = None
        for pc in SC.pickup_cells(target, ctx.blocked):
            got = SC.plan_trip(pos_j, ctx.blocked, locks, b, ctx.entries[b],
                               target, pc, t_next, cell)
            if got and (plan is None or got[1] < plan[1]):
                plan = got
        if plan is None:
            return None
        head += "".join(plan[2])
        if len(head) > 300:
            return None
        t_next = plan[1] + 1
        cell = ctx.entries[b]
    return park(ctx, pos_j, b, head, t_next, cell)


def convert(ctx, data, pos, best, g, max_masks=3):
    trips = best[g] + 1
    t_now = probe(data, pos, g, trips)
    if t_now is None:
        return None, "unplannable"
    masks: list[int] = []
    pos_cur = pos
    while t_now > 299 and len(masks) < max_masks:
        scored = []
        for b in range(L.ROBOT_COUNT):
            if b == g or b in masks:
                continue
            t_b = probe(data, traffic_mask(pos_cur, b), g, trips)
            if t_b is not None and t_b < t_now:
                scored.append((t_b, b))
        if not scored:
            return None, f"stuck at {t_now} (masks {masks})"
        t_now, b = min(scored)
        masks.append(b)
        pos_cur = traffic_mask(pos_cur, b)
    if t_now > 299:
        return None, f"still {t_now} after masks {masks}"

    row_g = SC.build_row(data, pos_cur, g, trips)
    if row_g is None or final_o(row_g) > 299:
        return None, f"real build failed (masks {masks})"
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
            return None, f"victims {losers} unfixable (masks {masks})"
    return None, f"victim cascade did not converge (masks {masks})"


def run(data, gains, out: Path):
    ctx = Ctx(data)
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    pos = ME.positions_by_tick(ME.simulate(data, record=True))
    for g in gains:
        trial, info = convert(ctx, data, pos, best, g)
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
