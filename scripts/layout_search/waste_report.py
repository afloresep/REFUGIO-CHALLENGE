"""Rank near-miss robots by delivery deficit vs recoverable late-game waste.

For every robot that ended an episode carrying (or idling near its entry),
compute: the deficit (extra ticks it needed to convert its final item) and the
per-leg waste of its last few trips (actual ticks minus BFS-optimal distance).
A robot is only fixable if late waste >= deficit, and interventions are
cheapest when the waste is concentrated in a single leg.

Usage:
  python3 scripts/layout_search/waste_report.py REPLAY.json [--max-deficit 10]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L


def analyze(replay: dict, max_deficit: int) -> None:
    shelves = [tuple(c) for c in replay["layout"]["shelf_cells"]]
    blocked = set(shelves)
    entries = L.base_entries_by_robot()
    frames = replay["frames"]

    for rid in range(L.ROBOT_COUNT):
        track = []
        for fr in frames:
            rob = next(r for r in fr["robots"] if r["id"] == rid)
            track.append((fr["tick"], tuple(rob["pos"]), rob["carrying"], rob["deliveries"]))
        final_t, final_pos, final_carry, final_deliv = track[-1]
        entry = entries[rid]
        entry_field = L.bfs([entry], blocked)
        d_end = int(entry_field[final_pos[1], final_pos[0]])
        if not final_carry or d_end <= 0 or d_end > max_deficit:
            continue
        deficit = d_end + 1

        # reconstruct trip boundaries
        events = []  # (kind, tick, pos)
        for i in range(1, len(track)):
            t, pos, carry, deliv = track[i]
            _, ppos, pcarry, pdeliv = track[i - 1]
            if carry and not pcarry:
                events.append(["PICKUP", t, ppos])
            if deliv > pdeliv:
                events.append(["DROP", t, pos])

        legs = []
        prev_drop_t = 0
        pickup = None
        for kind, t, pos in events:
            if kind == "PICKUP":
                pickup = (t, pos)
                d_approach = int(entry_field[pos[1], pos[0]])
                waste = (t - prev_drop_t) - (d_approach + 1)
                legs.append(("approach", prev_drop_t, t, waste))
            else:
                if pickup is not None:
                    d_return = int(entry_field[pickup[1][1], pickup[1][0]])
                    waste = (t - pickup[0]) - (d_return + 1)
                    legs.append(("return", pickup[0], t, waste))
                prev_drop_t = t
                pickup = None
        # unfinished final leg
        if pickup is not None:
            d_return = int(entry_field[pickup[1][1], pickup[1][0]])
            waste = (300 - pickup[0]) - d_return  # ticks used vs needed so far
            legs.append(("final-return(unfinished)", pickup[0], 300, waste))
        else:
            legs.append(("final-approach(unfinished)", prev_drop_t, 300, None))

        late = [leg for leg in legs if leg[2] >= 120]
        late_waste = sum(w for _k, _a, _b, w in late if w is not None and w > 0)
        tag = "FIXABLE" if late_waste >= deficit else "time-bound"
        print(f"rid {rid:2d} deficit {deficit:2d} late_waste {late_waste:2d} {tag}")
        for kind, a, b, w in late:
            print(f"    {kind:28s} t{a:3d}-t{b:3d} waste {w}")


def main() -> None:
    args = sys.argv[1:]
    replay = json.loads(Path(args[0]).read_text())
    max_deficit = int(args[args.index("--max-deficit") + 1]) if "--max-deficit" in args else 10
    analyze(replay, max_deficit)


if __name__ == "__main__":
    main()
