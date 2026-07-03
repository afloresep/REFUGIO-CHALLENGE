"""Global left-compaction of a replay matrix.

Rebuilds every robot's day lock-aware earliest-arrival at its incumbent
delivery count, accepting a rebuild only if the exact simulator confirms the
total is unchanged and the robot's last delivery lands strictly earlier
(monotone progress, no cycles). Interleave with sweep_compress.py: compaction
thins and left-shifts traffic, which opens +1 conversions.

Usage:
  python3 scripts/layout_search/compact_all.py MATRIX.json OUT.json [--passes 3]
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


def last_o(row: str) -> int:
    return max((t for t, ch in enumerate(row) if ch == "O"), default=-1)


def compact(data: dict, passes: int, out: Path):
    best = ME.deliveries(ME.simulate(data))
    total = sum(best)
    print(f"start {data['seed'][:8]}: {total}")
    for p in range(passes):
        moved = 0
        pos = ME.positions_by_tick(ME.simulate(data, record=True))
        for rid in range(L.ROBOT_COUNT):
            if best[rid] == 0:
                continue
            incumbent_end = last_o(data["matrix"][rid])
            cand = build_row(data, pos, rid, best[rid])
            if cand is None or last_o(cand) >= incumbent_end:
                continue
            trial = dict(data)
            trial["matrix"] = list(data["matrix"])
            trial["matrix"][rid] = cand
            d = ME.deliveries(ME.simulate(trial))
            if sum(d) >= total and d[rid] >= best[rid]:
                data = trial
                if sum(d) > total:
                    print(f"  pass {p} rid {rid}: total {total} -> {sum(d)}")
                best, total = d, sum(d)
                moved += 1
                pos = ME.positions_by_tick(ME.simulate(data, record=True))
        print(f"  pass {p}: {moved} rebuilds accepted")
        out.write_text(json.dumps(data))
        if moved == 0:
            break
    print(f"final {data['seed'][:8]}: {total}")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("out")
    ap.add_argument("--passes", type=int, default=3)
    args = ap.parse_args()
    data = ME.load(Path(args.matrix))
    compact(data, args.passes, Path(args.out))


if __name__ == "__main__":
    main()
