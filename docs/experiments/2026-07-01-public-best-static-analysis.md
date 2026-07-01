# Experiment: public-best-static-analysis

Date: 2026-07-01

Code:

- `solutions/public/c15da13c3eaa.py`
- `scripts/analyze-policy.mjs`
- `scripts/create-ablation-variants.mjs`

Input:

- Public best raw-score policy from `https://refugio-hackathon-nine.vercel.app/code/c15da13c3eaa`

Hypothesis:

The 1008-delivery public result is not a memoryless decentralized policy. It should show centralized state, multi-robot planning, seed-specific tuning, and custom layout structure.

Command:

```bash
npm run fetch:public-code -- c15da13c3eaa
npm run analyze:policy -- solutions/public/c15da13c3eaa.py
npm run make:ablations
python3 -c "import ast, pathlib; files=sorted(pathlib.Path('solutions').glob('**/*.py')); [ast.parse(p.read_text()) for p in files]; print('python ast ok for', len(files), 'policy files')"
```

Result:

- Extracted baseline: 339 lines, 23,334 bytes.
- SHA-256: `224053d644afc2fef31e97ec93c11930794aec579c21c4da95390cab1080fb84`.
- `create_layout()` contains 960 shelf coordinates.
- Syntax validation passed for 5 policy files: the public baseline plus 4 generated ablations.
- Static features detected:
  - module-global `_BRAIN`
  - use of `all_robot_positions`
  - per-robot state maps
  - `SEED_CONFIGS` / `JITTER_CONFIGS`
  - rolling `WINDOW`
  - A* planner
  - cell and edge reservations
  - BFS distance-field cache
  - `FLOW_PENALTY`
  - priority jitter
  - greedy fallback
  - target locking
  - exception-to-wait fallback

Generated ablation inputs:

- `solutions/ours/c15da13c3eaa-default-config-only.py`
- `solutions/ours/c15da13c3eaa-no-flow-penalty.py`
- `solutions/ours/c15da13c3eaa-no-jitter.py`
- `solutions/ours/c15da13c3eaa-short-window-16.py`

Interpretation:

This supports the central claim that the public best policy used a stateful centralized cooperative MAPF-style controller, not the literal memoryless decentralized policy described in the challenge prose. The first obvious false ceiling is therefore any analysis that assumes each robot can only act from its own current observation without shared module-level memory.

The code also makes the 922/1008 gap more concrete: the baseline itself comments that `DEFAULT_CFG` is a robust fallback near 922, while the public submission adds seed-specific window, flow, and jitter configuration.

Next:

- Add or recover an evaluator so the generated ablations can be scored.
- Prioritize `default-config-only` first, because it directly tests whether the 1008 result depends on seed fingerprinting.
- Then test `no-flow-penalty`, `no-jitter`, and `short-window-16`.

Evaluator note:

`warehouse` and `warehouse_api` are available through the original starter kit in this Python environment. See `docs/evaluator-status.md`.
