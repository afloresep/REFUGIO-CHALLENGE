"""Sweep single-robot suffix replans over replay matrices.

For each robot and selected start tick, preserve the replay prefix, replan that
robot alone to one additional delivery against frozen outside traffic, then
validate the whole matrix with the exact simulator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import matrix_edit as ME
from layout_search import suffix_replan as SR


def parse_ticks(raw: str) -> list[int]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            bits = [int(x) for x in part.split(":")]
            if len(bits) == 2:
                start, stop = bits
                step = 1
            elif len(bits) == 3:
                start, stop, step = bits
            else:
                raise ValueError(f"bad tick range: {part}")
            out.extend(range(start, stop + 1, step))
        else:
            out.append(int(part))
    return sorted(set(out))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix")
    parser.add_argument("out")
    parser.add_argument("--ticks", default="0:260:20,270,280")
    parser.add_argument("--rids", default="")
    args = parser.parse_args()

    data = ME.load(Path(args.matrix))
    base = ME.simulate(data)
    base_d = ME.deliveries(base)
    base_total = sum(base_d)
    ticks = parse_ticks(args.ticks)
    rids = (
        [int(x) for x in args.rids.split(",") if x.strip()]
        if args.rids
        else list(range(len(base_d)))
    )

    records = []
    best = None
    for rid in rids:
        target = {rid: base_d[rid] + 1}
        for t0 in ticks:
            candidate, diagnostics = SR.replan(data, [rid], t0, target, (rid,))
            if candidate is None:
                continue
            result = ME.simulate(candidate)
            d = ME.deliveries(result)
            total = sum(d)
            gains = [i for i, (a, b) in enumerate(zip(base_d, d)) if b > a]
            losses = [i for i, (a, b) in enumerate(zip(base_d, d)) if b < a]
            rec = {
                "rid": rid,
                "t0": t0,
                "score": total,
                "delta": total - base_total,
                "self": [base_d[rid], d[rid]],
                "gains": gains,
                "losses": losses,
                "diagnostics": diagnostics,
            }
            records.append(rec)
            if best is None or (total, d[rid], -len(losses)) > (
                best["score"],
                best["self"][1],
                -len(best["losses"]),
            ):
                best = rec
                print(json.dumps({"best": best}, indent=2), flush=True)

    payload = {
        "seed": data["seed"],
        "matrix": str(args.matrix),
        "base_score": base_total,
        "base_counts": dict(sorted((str(k), base_d.count(k)) for k in set(base_d))),
        "ticks": ticks,
        "records": records,
        "best": best,
        "net_wins": [r for r in records if r["delta"] > 0],
        "self_gains": [r for r in records if r["self"][1] > r["self"][0]],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({
        "base_score": base_total,
        "records": len(records),
        "net_wins": len(payload["net_wins"]),
        "self_gains": len(payload["self_gains"]),
        "best": best,
    }, indent=2))


if __name__ == "__main__":
    main()
