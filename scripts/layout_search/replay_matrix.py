"""Extract per-seed action matrices from replays and build replay policies.

A replay policy embeds the full 300x96 action matrix for each official seed
(fingerprinted at tick 0 from (robot_id, first target)), replaying the
recorded bundle verbatim. Nobody reacts to anything, so local matrix edits
have no cascade surface: the evaluator's own dynamics validate each edit.

Usage:
  python3 scripts/layout_search/replay_matrix.py extract REPLAY.json OUT.npz
  python3 scripts/layout_search/replay_matrix.py build OUT.py MATRIX.npz ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L

# Action encoding: single chars for compact embedding
# U/D/L/R = moves, W = wait, P = pickup, O = drop
DELTA_TO_ACT = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}


def extract_matrix(replay: dict) -> list[str]:
    """Return per-robot action strings of length = ticks (outcome-faithful)."""
    frames = replay["frames"]
    ticks = len(frames) - 1
    tracks: dict[int, list] = {r["id"]: [] for r in frames[0]["robots"]}
    for fr in frames:
        for r in fr["robots"]:
            tracks[r["id"]].append((tuple(r["pos"]), r["carrying"], r["deliveries"]))
    matrix = []
    for rid in range(L.ROBOT_COUNT):
        tr = tracks[rid]
        acts = []
        for i in range(ticks):
            (p0, c0, d0), (p1, c1, d1) = tr[i], tr[i + 1]
            if p1 != p0:
                acts.append(DELTA_TO_ACT[(p1[0] - p0[0], p1[1] - p0[1])])
            elif c1 and not c0:
                acts.append("P")
            elif d1 > d0:
                acts.append("O")
            else:
                acts.append("W")
        matrix.append("".join(acts))
    return matrix


POLICY_TEMPLATE = '''"""REFUGIO replay policy: verbatim per-seed action matrices."""
from warehouse_api import Action

_ACT = {{"U": Action.UP, "D": Action.DOWN, "L": Action.LEFT, "R": Action.RIGHT,
        "W": Action.WAIT, "P": Action.PICKUP, "O": Action.DROP}}

_MATRICES = {matrices!r}

# (robot_id, first target position) -> seed key, computed offline.
_FINGERPRINT = {fingerprint!r}

_ACTIVE = {{"key": None, "tick0_seen": False}}


def create_layout():
    return {{'schema_version': 1, 'shelves': {shelves!r}}}


def act(observation):
    if observation.tick == 0:
        key = _FINGERPRINT.get(
            (observation.robot_id, tuple(observation.target_item_position))
        )
        if key is not None:
            _ACTIVE["key"] = key
    key = _ACTIVE["key"]
    if key is None:
        return Action.WAIT
    row = _MATRICES[key][observation.robot_id]
    if observation.tick >= len(row):
        return Action.WAIT
    return _ACT[row[observation.tick]]
'''


def build_policy(out: Path, matrix_files: list[Path]) -> None:
    matrices = {}
    fingerprint = {}
    shelves = None
    for mf in matrix_files:
        data = json.loads(mf.read_text())
        seed = data["seed"]
        matrices[seed[:8]] = data["matrix"]
        shelves = data["shelves"]
        ss = L.sorted_shelves(shelves)
        from warehouse.targets import target_index
        for rid in range(L.ROBOT_COUNT):
            idx = target_index(seed, rid, 0, L.SHELF_COUNT)
            fingerprint[(rid, tuple(ss[idx]))] = seed[:8]
    src = POLICY_TEMPLATE.format(
        matrices=matrices, fingerprint=fingerprint, shelves=[list(c) for c in shelves]
    )
    compile(src, str(out), "exec")
    out.write_text(src)
    print(f"wrote {out}")


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "extract":
        replay = json.loads(Path(sys.argv[2]).read_text())
        matrix = extract_matrix(replay)
        payload = {
            "seed": replay["global_seed"],
            "matrix": matrix,
            "shelves": replay["layout"]["shelf_cells"],
            "total_deliveries": replay["total_deliveries"],
        }
        Path(sys.argv[3]).write_text(json.dumps(payload))
        print(f"extracted {replay['global_seed'][:8]}: {replay['total_deliveries']} deliveries")
    elif cmd == "build":
        build_policy(Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])


if __name__ == "__main__":
    main()
