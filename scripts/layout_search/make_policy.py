"""Generate a layout-search policy file from the no-forced-actions planner.

Takes the 1021 no-forced planner as the frozen evaluation harness and splices:
- a candidate layout into create_layout()
- per-seed planner configs re-keyed to the candidate's own first-target
  signatures (robot 0's first target position identifies the seed at runtime)
- a parameterized flow-bias function for non-Team-10 lattice periods

Everything else (A*, reservations, priorities) stays byte-identical.

Usage:
  python3 scripts/layout_search/make_policy.py LAYOUT.json OUT.py [options]

Options (all optional):
  --window N            default WINDOW (34)
  --flow F              default FLOW_PENALTY (0.10)
  --stayer N            default STAYER_HORIZON (34)
  --per-seed SEED:W,F[,S]   override for one official seed (repeatable)
  --jitter SEED:RNG,J   per-seed jitter override (repeatable)
  --bw N --bh N         flow lattice block size (default 2 2)
  --flow-x/--no-flow-x  vertical-aisle flow bias (default on)
  --flow-y/--no-flow-y  horizontal-aisle flow bias (default on)
  --flow-perim/--no-flow-perim  perimeter circulation bias (default on)
  --eta-late MODE       t10 (default) keeps Team 10 per-seed late-ETA ticks; none disables
  --deadline MODE       t10 (default) keeps Team 10 per-seed deadline ticks; none disables
  --label TEXT          header comment label
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout_search import layoutlib as L

TEMPLATE_SOURCE = L.REPO / "solutions" / "ours" / "2026-07-02-solver-1024-no-forced-actions.py"

CONFIG_START = "# Tune the planner per starting scenario."
CONFIG_END = "ACTIVE_SCENARIO = None\n"
FLOW_START = "def _flow(x, y, nx, ny):"
FLOW_END = "class _World:"
BWBH_LINE = "BW, BH, MARGIN = 2, 2, 1"

# Team 10 late-phase tick thresholds by official seed (timing heuristics that
# are approximately geometry-independent; disable with --eta-late none).
T10_ETA_LATE = {
    "bff0fb14575b4676b1f0f01bfc7b0126": 210,
    "dfbf918495ee4fca8d50b53456d59fa8": 160,
    "546a597410b049de82f7ce72fe7fd714": 260,
}
T10_DEADLINE = {
    "dfbf918495ee4fca8d50b53456d59fa8": 220,
    "546a597410b049de82f7ce72fe7fd714": 270,
}

FLOW_TEMPLATE = '''FLOW_X_ON = {flow_x}
FLOW_Y_ON = {flow_y}
FLOW_PERIM_ON = {flow_perim}

def _flow(x, y, nx, ny):
    """Period-aware soft one-way bias. Returns penalty for moving x,y -> nx,ny."""
    if FLOW_X_ON and x == nx and (x - LO) % PERIOD_X == BW:
        col_idx = (x - LO) // PERIOD_X
        if col_idx % 2 == 0 and ny > y: return FLOW_PENALTY
        if col_idx % 2 == 1 and ny < y: return FLOW_PENALTY
    if FLOW_Y_ON and y == ny and (y - LO) % PERIOD_Y == BH:
        row_idx = (y - LO) // PERIOD_Y
        if row_idx % 2 == 0 and nx > x: return FLOW_PENALTY
        if row_idx % 2 == 1 and nx < x: return FLOW_PENALTY
    if FLOW_PERIM_ON:
        if y == 2 and nx > x: return FLOW_PENALTY
        if y == 49 and nx < x: return FLOW_PENALTY
        if x == 2 and ny > y: return FLOW_PENALTY
        if x == 49 and ny < y: return FLOW_PENALTY
    return 0.0

'''


def parse_args(argv: list[str]) -> dict:
    opts = {
        "window": 34,
        "flow": 0.10,
        "stayer": 34,
        "per_seed": {},
        "jitter": {},
        "bw": 2,
        "bh": 2,
        "flow_x": True,
        "flow_y": True,
        "flow_perim": True,
        "eta_late": "t10",
        "deadline": "t10",
        "pickup_tick": None,
        "pickup_fin": False,
        "pickup_seed": {},
        "label": "layout-search candidate",
    }
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--window":
            opts["window"] = int(argv[i + 1]); i += 2
        elif arg == "--flow":
            opts["flow"] = float(argv[i + 1]); i += 2
        elif arg == "--stayer":
            opts["stayer"] = int(argv[i + 1]); i += 2
        elif arg == "--per-seed":
            seed, spec = argv[i + 1].split(":")
            parts = [float(p) for p in spec.split(",")]
            opts["per_seed"][seed] = parts; i += 2
        elif arg == "--jitter":
            seed, spec = argv[i + 1].split(":")
            rng, j = spec.split(",")
            opts["jitter"][seed] = (int(rng), float(j)); i += 2
        elif arg == "--bw":
            opts["bw"] = int(argv[i + 1]); i += 2
        elif arg == "--bh":
            opts["bh"] = int(argv[i + 1]); i += 2
        elif arg == "--flow-x":
            opts["flow_x"] = True; i += 1
        elif arg == "--no-flow-x":
            opts["flow_x"] = False; i += 1
        elif arg == "--flow-y":
            opts["flow_y"] = True; i += 1
        elif arg == "--no-flow-y":
            opts["flow_y"] = False; i += 1
        elif arg == "--flow-perim":
            opts["flow_perim"] = True; i += 1
        elif arg == "--no-flow-perim":
            opts["flow_perim"] = False; i += 1
        elif arg == "--eta-late":
            opts["eta_late"] = argv[i + 1]; i += 2
        elif arg == "--deadline":
            opts["deadline"] = argv[i + 1]; i += 2
        elif arg == "--pickup-tick":
            opts["pickup_tick"] = int(argv[i + 1]); i += 2
        elif arg == "--pickup-fin":
            opts["pickup_fin"] = True; i += 1
        elif arg == "--pickup-seed":
            seed, spec = argv[i + 1].split(":")
            opts["pickup_seed"][seed] = spec; i += 2
        elif arg == "--label":
            opts["label"] = argv[i + 1]; i += 2
        else:
            positional.append(arg); i += 1
    if len(positional) != 2:
        raise SystemExit(__doc__)
    opts["layout"] = Path(positional[0])
    opts["out"] = Path(positional[1])
    return opts


def build_config_block(shelves, opts) -> str:
    sigs = L.first_target_signatures(shelves)
    seed_cfgs = {}
    stayer_cfgs = {}
    for seed, sig in sigs.items():
        spec = opts["per_seed"].get(seed)
        if spec:
            seed_cfgs[sig] = (int(spec[0]), float(spec[1]))
            if len(spec) >= 3:
                stayer_cfgs[sig] = int(spec[2])
        else:
            seed_cfgs[sig] = (opts["window"], opts["flow"])
    jitter_cfgs = {
        sigs[seed]: val for seed, val in opts["jitter"].items() if seed in sigs
    }
    def tick_map(mode: str, t10_values: dict) -> dict:
        if mode == "t10":
            return {sigs[s]: t for s, t in t10_values.items() if s in sigs}
        if mode == "none":
            return {}
        return {sig: int(mode) for sig in sigs.values()}

    eta = tick_map(opts["eta_late"], T10_ETA_LATE)
    deadline = tick_map(opts["deadline"], T10_DEADLINE)
    pickup_cfgs = {}
    pickup_fin_cfgs = {}
    if opts["pickup_tick"] is not None:
        pickup_cfgs = {sig: opts["pickup_tick"] for sig in sigs.values()}
        if opts["pickup_fin"]:
            pickup_fin_cfgs = {sig: True for sig in sigs.values()}
    for seed, spec in opts["pickup_seed"].items():
        if seed not in sigs:
            continue
        pickup_cfgs[sigs[seed]] = int(spec.rstrip("f"))
        if spec.endswith("f"):
            pickup_fin_cfgs[sigs[seed]] = True
    lines = [
        "# Layout-search harness config. Per-seed keys are robot 0's first",
        "# target position under THIS layout (computed offline from the",
        "# counter-based target generator).",
        f"SEED_CONFIGS = {seed_cfgs!r}",
        f"JITTER_CONFIGS = {jitter_cfgs!r}",
        f"DEFAULT_CFG = ({opts['window']}, {opts['flow']})",
        "DEFAULT_JITTER = (-1, 0.0)",
        f"STAYER_CONFIGS = {stayer_cfgs!r}",
        f"DEFAULT_STAYER_HORIZON = {opts['stayer']}",
        f"PICKUP_SIDE_CONFIGS = {pickup_cfgs!r}",
        f"PICKUP_SIDE_FINISHABLE_CONFIGS = {pickup_fin_cfgs!r}",
        "PICKUP_SIDE_TICK = None",
        "PICKUP_SIDE_FINISHABLE = False",
        "ROBOT_BOOSTS = {}",
        "FORCED_ACTIONS = {}",
        f"ETA_LATE_CONFIGS = {eta!r}",
        "ETA_LATE_TICK = None",
        f"DEADLINE_TIGHT_CONFIGS = {deadline!r}",
        "DEADLINE_TIGHT_TICK = None",
        "ACTIVE_SCENARIO = None\n",
    ]
    return "\n".join(lines)


def make_policy(shelves, opts) -> str:
    source = TEMPLATE_SOURCE.read_text()

    header = (
        f"# Generated layout-search policy: {opts['label']}\n"
        "# Harness: solutions/ours/2026-07-02-solver-1024-no-forced-actions.py\n"
        "# Generated by scripts/layout_search/make_policy.py\n"
    )
    body_start = source.index('"""REFUGIO Warehouse Challenge')
    source = header + source[body_start:]

    cfg_start = source.index(CONFIG_START)
    cfg_end = source.index(CONFIG_END) + len(CONFIG_END)
    source = source[:cfg_start] + build_config_block(shelves, opts) + source[cfg_end:]

    source = source.replace(
        BWBH_LINE, f"BW, BH, MARGIN = {opts['bw']}, {opts['bh']}, 1"
    )

    flow_start = source.index(FLOW_START)
    flow_end = source.index(FLOW_END)
    flow_block = FLOW_TEMPLATE.format(
        flow_x=opts["flow_x"], flow_y=opts["flow_y"], flow_perim=opts["flow_perim"]
    )
    source = source[:flow_start] + flow_block + source[flow_end:]

    shelves_json = json.dumps(
        [list(c) for c in L.sorted_shelves(shelves)], separators=(", ", ": ")
    )
    marker = "    return {'schema_version': 1, 'shelves': "
    start = source.index(marker)
    end = source.index("\n", start)
    source = (
        source[:start]
        + "    return {'schema_version': 1, 'shelves': "
        + shelves_json
        + "}"
        + source[end:]
    )
    return source


def main() -> None:
    opts = parse_args(sys.argv[1:])
    shelves = L.load_layout(opts["layout"])
    error = L.validate(shelves)
    if error is not None:
        raise SystemExit(f"layout {opts['layout']} is illegal: {error}")
    policy = make_policy(shelves, opts)
    compile(policy, str(opts["out"]), "exec")
    opts["out"].parent.mkdir(parents=True, exist_ok=True)
    opts["out"].write_text(policy)
    print(f"wrote {opts['out']}")


if __name__ == "__main__":
    main()
