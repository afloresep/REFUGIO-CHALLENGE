"""Trace one robot's trajectory in a replay and quantify wasted ticks.

For each trip segment (pickup -> drop, or the unfinished tail), compares the
ticks actually used against the BFS-optimal distance on the layout, and marks
WAITs and revisited cells. Use it to find planner wobbles worth forcing.

Usage:
  python3 scripts/layout_search/trace_robot.py REPLAY.json RID [--from-tick T]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L


def main() -> None:
    args = sys.argv[1:]
    replay = json.loads(Path(args[0]).read_text())
    rid = int(args[1])
    from_tick = int(args[args.index("--from-tick") + 1]) if "--from-tick" in args else 0

    shelves = [tuple(c) for c in replay["layout"]["shelf_cells"]]
    blocked = set(shelves)
    entry = L.base_entries_by_robot()[rid]
    entry_field = L.bfs([entry], blocked)

    frames = replay["frames"]
    track = []
    for fr in frames:
        rob = next(r for r in fr["robots"] if r["id"] == rid)
        track.append((fr["tick"], tuple(rob["pos"]), rob["carrying"], rob["deliveries"]))

    print(f"rid {rid}, entry {entry}, final deliveries {track[-1][3]}, "
          f"final pos {track[-1][1]} carrying={track[-1][2]} "
          f"dist_to_entry={int(entry_field[track[-1][1][1], track[-1][1][0]])}")

    # segment boundaries: pickup = carrying False->True, drop = deliveries +1
    events = []
    for i in range(1, len(track)):
        t, pos, carry, deliv = track[i]
        pt, ppos, pcarry, pdeliv = track[i - 1]
        if carry and not pcarry:
            events.append(("PICKUP", t, pos))
        if deliv > pdeliv:
            events.append(("DROP", t, pos))
    for e in events:
        print("  event:", e)

    print(f"\ntrace from tick {from_tick}:")
    seen_at = {}
    for i, (t, pos, carry, deliv) in enumerate(track):
        if t < from_tick:
            continue
        prev = track[i - 1][1] if i > 0 else None
        move = "WAIT" if prev == pos else ""
        revisit = f"(revisit from t{seen_at[pos]})" if pos in seen_at and move != "WAIT" else ""
        seen_at[pos] = t
        d = int(entry_field[pos[1], pos[0]]) if L.in_walk(*pos) else -1
        print(f"  t{t:3d} {pos} carry={int(carry)} deliv={deliv} d_entry={d:2d} {move}{revisit}")


if __name__ == "__main__":
    main()
