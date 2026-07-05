"""Randomized multi-robot suffix LNS over replay matrices.

This wraps suffix_replan with cached incumbent simulation state. For a chosen
start tick, a moving robot set is replanned against frozen outside traffic.
Selected gain robots target one more delivery; all other moving robots target
their incumbent delivery count. Each candidate is validated by the exact
warehouse simulator.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L
from layout_search import matrix_edit as ME
from layout_search import suffix_replan as SR


def parse_ints(raw: str) -> list[int]:
    if not raw.strip():
        return []
    return [int(x) for x in raw.split(",") if x.strip()]


def replan_cached(
    data: dict,
    result,
    rids: list[int],
    t0: int,
    targets: dict[int, int],
    order: tuple[int, ...],
):
    res = SR.Res(data["shelves"])
    moving = set(rids)
    res.add_outside(result, moving, t0)
    matrix = list(data["matrix"])
    diagnostics = []
    for rid in order:
        state = SR.robot_state_at(result, rid, t0)
        target_deliveries = targets.get(rid, state.deliveries)
        planned = SR.plan_one(data, res, state, rid, t0, target_deliveries)
        if planned is None:
            return None, diagnostics + [{"robot": rid, "planned": False}]
        row_suffix, positions, trips = planned
        matrix[rid] = matrix[rid][:t0] + row_suffix
        res.add_path(positions, trips, t0)
        diagnostics.append({
            "robot": rid,
            "planned": True,
            "target_deliveries": target_deliveries,
            "trips": len(trips),
        })
    out = dict(data)
    out["matrix"] = matrix
    return out, diagnostics


def candidate_orders(
    rids: list[int],
    base_d: list[int],
    gain_rids: set[int],
    samples: int,
    rng: random.Random,
):
    seen: set[tuple[int, ...]] = set()
    heuristics = [
        tuple(rids),
        tuple(sorted(rids)),
        tuple(sorted(rids, key=lambda r: (r not in gain_rids, -base_d[r], r))),
        tuple(sorted(rids, key=lambda r: (r in gain_rids, -base_d[r], r))),
        tuple(sorted(rids, key=lambda r: (-base_d[r], r))),
        tuple(sorted(rids, key=lambda r: (base_d[r], r))),
    ]
    for order in heuristics:
        if order not in seen:
            seen.add(order)
            yield order
    for _ in range(samples):
        order = list(rids)
        rng.shuffle(order)
        order_t = tuple(order)
        if order_t in seen:
            continue
        seen.add(order_t)
        yield order_t


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix")
    parser.add_argument("out")
    parser.add_argument("--rids", required=True)
    parser.add_argument("--gain-rids", required=True)
    parser.add_argument("--t0", type=int, required=True)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    data = ME.load(Path(args.matrix))
    base_result = ME.simulate(data, record=True)
    base_d = ME.deliveries(base_result)
    base_total = sum(base_d)
    rids = parse_ints(args.rids)
    gain_rids = set(parse_ints(args.gain_rids))
    if not gain_rids <= set(rids):
        raise SystemExit("--gain-rids must be a subset of --rids")
    targets = {rid: base_d[rid] for rid in rids}
    for rid in gain_rids:
        targets[rid] = base_d[rid] + 1

    rng = random.Random(args.seed)
    best = None
    records = []
    tried = 0
    feasible = 0
    for order in candidate_orders(rids, base_d, gain_rids, args.samples, rng):
        tried += 1
        candidate, diagnostics = replan_cached(data, base_result, rids, args.t0, targets, order)
        if candidate is None:
            continue
        feasible += 1
        result = ME.simulate(candidate)
        d = ME.deliveries(result)
        total = sum(d)
        gains = [i for i, (a, b) in enumerate(zip(base_d, d)) if b > a]
        losses = [i for i, (a, b) in enumerate(zip(base_d, d)) if b < a]
        rec = {
            "score": total,
            "delta": total - base_total,
            "order": list(order),
            "gains": gains,
            "losses": losses,
            "gain_counts": {str(r): [base_d[r], d[r]] for r in sorted(gain_rids)},
            "diagnostics": diagnostics,
        }
        records.append(rec)
        key = (total, sum(d[r] - base_d[r] for r in gain_rids), -len(losses))
        if best is None or key > best[0]:
            best = (key, rec, candidate)
            print(json.dumps({"best": rec, "tried": tried, "feasible": feasible}, indent=2), flush=True)

    payload = {
        "seed": data["seed"],
        "matrix": str(args.matrix),
        "base_score": base_total,
        "base_counts": dict(sorted((str(k), base_d.count(k)) for k in set(base_d))),
        "rids": rids,
        "gain_rids": sorted(gain_rids),
        "t0": args.t0,
        "samples": args.samples,
        "random_seed": args.seed,
        "tried": tried,
        "feasible": feasible,
        "best": best[1] if best else None,
        "records": records,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    if best is not None:
        out.write_text(json.dumps(best[2]) + "\n")
    print(json.dumps({
        "base_score": base_total,
        "tried": tried,
        "feasible": feasible,
        "best": best[1] if best else None,
    }, indent=2))


if __name__ == "__main__":
    main()
