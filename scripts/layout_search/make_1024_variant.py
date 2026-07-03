"""Generate a config variant of the Team 10-layout 1024-family solvers.

Unlike make_policy.py (which rebuilds the whole config block and drops robot
boosts / forced actions), this substitutes individual config dict literals in
an existing solver file, preserving every other layer. Keys are the known
official-seed signatures for the Team 10 layout.

Usage:
  python3 scripts/layout_search/make_1024_variant.py BASE.py OUT.py \
      --window W --flow F [--stayer S] [--pickup TICK[f]|keep|none] \
      [--eta T|keep|none] [--deadline T|keep|none] [--jitter RNG,J] [--label X]

--window/--flow/--stayer apply to all three seed signatures (per-seed bests
are assembled later from single-seed evaluations).
"""

from __future__ import annotations

import sys
from pathlib import Path

SIGS = [(12, 33), (26, 47), (14, 42)]  # bff0..., dfbf..., 546a...


def replace_dict(source: str, name: str, new_literal: str) -> str:
    marker = f"{name} = {{"
    start = source.index(marker)
    i = source.index("{", start)
    depth = 0
    for j in range(i, len(source)):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                return source[:start] + f"{name} = " + new_literal + source[j + 1 :]
    raise ValueError(f"unterminated dict for {name}")


def main() -> None:
    argv = sys.argv[1:]
    positional = []
    opts = {
        "window": None, "flow": None, "stayer": None,
        "pickup": "keep", "eta": "keep", "deadline": "keep",
        "jitter": None, "label": "1024 config variant",
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        key = a.lstrip("-").replace("-", "_")
        if a.startswith("--"):
            opts[key] = argv[i + 1]
            i += 2
        else:
            positional.append(a)
            i += 1
    base, out = Path(positional[0]), Path(positional[1])
    source = base.read_text()

    if opts["window"] is not None:
        w, f = int(opts["window"]), float(opts["flow"])
        cfg = {sig: (w, f) for sig in SIGS}
        source = replace_dict(source, "SEED_CONFIGS", repr(cfg))
    if opts["stayer"] is not None:
        s = int(opts["stayer"])
        source = replace_dict(source, "STAYER_CONFIGS", repr({sig: s for sig in SIGS}))
    if opts["pickup"] != "keep":
        if opts["pickup"] == "none":
            source = replace_dict(source, "PICKUP_SIDE_CONFIGS", "{}")
            source = replace_dict(source, "PICKUP_SIDE_FINISHABLE_CONFIGS", "{}")
        else:
            tick = int(opts["pickup"].rstrip("f"))
            source = replace_dict(
                source, "PICKUP_SIDE_CONFIGS", repr({sig: tick for sig in SIGS})
            )
            fin = {sig: True for sig in SIGS} if opts["pickup"].endswith("f") else {}
            source = replace_dict(source, "PICKUP_SIDE_FINISHABLE_CONFIGS", repr(fin))
    if opts["eta"] != "keep":
        val = {} if opts["eta"] == "none" else {sig: int(opts["eta"]) for sig in SIGS}
        source = replace_dict(source, "ETA_LATE_CONFIGS", repr(val))
    if opts["deadline"] != "keep":
        val = {} if opts["deadline"] == "none" else {sig: int(opts["deadline"]) for sig in SIGS}
        source = replace_dict(source, "DEADLINE_TIGHT_CONFIGS", repr(val))
    if opts["jitter"] is not None:
        rng, j = opts["jitter"].split(",")
        cfg = {sig: (int(rng), float(j)) for sig in SIGS}
        source = replace_dict(source, "JITTER_CONFIGS", repr(cfg))
    if opts.get("wait_cap") is not None:
        source = source.replace(
            "WAIT_CAP = 30", f"WAIT_CAP = {int(opts['wait_cap'])}", 1
        )
    if opts.get("node_cap") is not None:
        source = source.replace(
            "NODE_CAP = 2500", f"NODE_CAP = {int(opts['node_cap'])}", 1
        )

    header = f"# Generated 1024 config variant: {opts['label']}\n# Base: {base}\n"
    source = header + source
    compile(source, str(out), "exec")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(source)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
