# AGENTS.md

This repo is a working bench for understanding and improving the REFUGIO warehouse hackathon result, and for turning that work into a technical article.

The main goal is not to polish the local Next app. The main goal is to explain why "1000 deliveries is impossible" was a false conclusion, reproduce the public 1008 result, dissect the mechanisms that made it possible, and search for a stronger policy/layout.

## Start Here

Read these files before making claims or changes:

- `docs/challenge-brief.md` - challenge rules, robot cycle, scoring terms.
- `docs/research-plan.md` - current workstreams and checklist.
- `docs/technical-writeup-outline.md` - intended article structure.
- `docs/experiments/2026-07-01-official-seed-ablation-scores.md` - key ablation results.
- `docs/experiments/2026-07-03-layout-search-scores.md` - layout-search results, demand-model exploit, and why 1024 is a sharp local optimum.
- `docs/limit-argument-review.md` - why the external "1000 impossible" proof is wrong.
- `data/evaluation-results.json` - machine-readable official-seed scores.

If you need one sentence of context: the public best policy reached 1008 because the evaluator allowed Python module-global state, turning nominally decentralized `act()` calls into a centralized cooperative MAPF planner with shared robot state and rolling reservations; the current local closed-gate best is 1024 by retuning that planner and adding audited hidden-seed suffix fixes.

## Hard Facts

Official seeds:

```text
bff0fb14575b4676b1f0f01bfc7b0126
dfbf918495ee4fca8d50b53456d59fa8
546a597410b049de82f7ce72fe7fd714
```

Baseline:

- `solutions/public/c15da13c3eaa.py`
- Public leaderboard raw score: 1008.
- Local reproduction: 337, 336, 335 = 1008.
- Bundled replay for the first seed: 337 deliveries.

Current local best:

- `solutions/ours/2026-07-02-solver-1024.py`
- Local official-seed reproduction: 343, 342, 339 = 1024.
- Same shelf layout as the public 1008 baseline.
- `no-forced-actions` ablation still scores 1021, so most of the +16 comes from the retuned planner layer rather than explicit action overrides.

Important measured ablations:

| Policy | Score | Seed scores | Main lesson |
| --- | ---: | --- | --- |
| 1024 solver | 1024 | 343, 342, 339 | current local closed-gate best |
| 1024 clean planner floor | 1009 | 337, 335, 337 | retuned config alone barely clears public 1008 |
| 1024 clean floor, no late priority | 1007 | 338, 334, 335 | late ETA/deadline priority is a small clean-floor effect |
| 1024 clean floor, public configs | 1005 | 334, 337, 334 | old seed configs and jitter interact rather than adding independently |
| 1024 clean floor, public jitter | 999 | 333, 335, 331 | deterministic ordering helps only with the retuned configs |
| 1024 no forced actions | 1021 | 342, 340, 339 | hard suffix overrides are useful but not the main lift |
| 1024 no stayer-horizon tuning | 1011 | 336, 336, 339 | shorter stayer reservations are a major 1024 mechanism |
| 1024 no pickup-side retarget | 1018 | 337, 342, 339 | late pickup-side choice adds deliveries |
| 1024 no robot boosts | 1020 | 343, 340, 337 | late per-robot priority boosts add deliveries |
| baseline | 1008 | 337, 336, 335 | public result reproduced |
| layout canonical racks | 890 | 287, 305, 298 | Team 10 planner alone does not explain 1008 |
| layout wide avenues | 386 | 123, 120, 143 | naive wide corridors break planner/layout fit |
| default config only | 1000 | 336, 333, 331 | seed tuning is useful but not the whole jump |
| no flow penalty | 992 | 334, 330, 328 | soft lane bias matters |
| no jitter | 1001 | 334, 336, 331 | jitter helps but is not essential |
| short window 16 | 997 | 334, 336, 327 | reservation horizon matters |
| no edge reservations | 451 | 137, 128, 186 | head-on swap prevention is decisive |
| no shared brain, cached world | 492 | 172, 153, 167 | shared robot-planner state is decisive |
| no shared brain, fresh world | timed out | 172, -, - | no state plus no cache is too slow |

Do not repeat the claim that 1000 is impossible. The evaluator locally falsifies it.

## Commands

Run app:

```bash
npm run dev -- --hostname 0.0.0.0 --port 3002
```

Validate project:

```bash
npm run lint
npm run typecheck
node -e "for (const f of ['data/official-seeds.json','data/evaluation-results.json','data/public-leaderboard-snapshot.json']) JSON.parse(require('fs').readFileSync(f,'utf8'))"
python3 -c "import ast, pathlib; files=sorted(pathlib.Path('solutions').glob('**/*.py')); [ast.parse(p.read_text()) for p in files]; print('python ast ok for', len(files), 'policy files')"
```

Analyze replays:

```bash
npm run analyze:replays
npm run analyze:replays -- --json
```

Analyze generated and public layouts:

```bash
npm run analyze:layouts
npm run analyze:layouts -- --json
```

Analyze a policy statically:

```bash
npm run analyze:policy -- solutions/public/c15da13c3eaa.py
```

Regenerate ablations from the public baseline:

```bash
npm run make:ablations
```

Regenerate ablations from the 1024 local solver:

```bash
npm run make:1024-ablations
```

Evaluate a policy on the official seeds:

```bash
npm run eval:policy -- solutions/public/c15da13c3eaa.py --label c15da13c3eaa
```

Evaluation outputs go under `outputs/`, which is gitignored. Record durable results in `data/evaluation-results.json` and `docs/experiments/*.md`.

## Evaluator

The `warehouse` evaluator is available in this environment through the original starter kit, but it is not vendored in this repo:

```text
warehouse /Users/afloresep/Downloads/refugio-starter-kit/warehouse/__init__.py
warehouse_api /Users/afloresep/Downloads/refugio-starter-kit/warehouse_api/__init__.py
```

If imports fail in a future environment, do not guess scores. Document the missing evaluator and stop scoring work until it is restored.

## File Map

- `solutions/public/` - extracted public submissions. Do not edit these in place.
- `solutions/ours/` - generated or hand-written variants and ablations.
- `scripts/create-ablation-variants.mjs` - source of generated ablations.
- `scripts/run-evaluation.mjs` - wrapper around `warehouse.eval_runner`.
- `data/official-seeds.json` - official seed values.
- `data/evaluation-results.json` - committed score summaries.
- `docs/experiments/` - reproducible experiment notes.
- `public/replays/` - vendored public replay payloads used by the local viewer.

## Next Priorities

1. The layout search is done (see `docs/experiments/2026-07-03-layout-search-scores.md`).
   Key mechanism: targets are drawn as `sorted_shelves[sha256(seed|robot|deliveries) mod 960]`, so official-seed demand is computable offline and layouts are index-to-position maps. The best alternative layout (`solutions/ours/2026-07-03-layout-dp-t10lat-composite-1016.py`, demand-DP subset of Team 10's own lattice) scores 1016 and beats the Team 10 layout +12 at equal planner config, but the layout family ceiling under this planner is ~1016-1023. Team 10's layout is demand-co-optimal (868/960 cells identical with the exact DP optimum). Tooling: `scripts/layout_search/`.

2. Toward >1024, the config and layout dimensions are exhausted (~350 evaluator runs; W/F/S fine grid, stayer/eta/deadline/pickup/jitter/WAIT_CAP/NODE_CAP micro-sweeps, 48 single-boost trials all saturate at 343/342/339). Remaining paths are heavy: hand-crafted forced-action trajectory chains, multi-boost combinatorics, or a structurally better planner (windowed PBS/CBS).

3. Extract more public policies if useful.
   Start with jobs around 930 and 925. Use `npm run fetch:public-code -- <job-id>`.

4. Draft the article from evidence, not vibes.
   The article should open with the contradiction: an agent claimed 1000 was impossible, but the public best code reproduces 1008 locally on the same seeds. The demand-co-optimality of Team 10's layout (and the offline demand model behind it) is a headline finding.

## Article Angle

Working title: `Why 920 Was Not the Ceiling`.

Core thesis:

The false ceiling came from analyzing a stricter problem than the one the evaluator actually ran. Agents treated the policy as memoryless and decentralized, then converted one solution family's plateau into a universal bound. The public best result exploited the actual execution model: module globals, shared robot state, cached distance fields, rolling time-windowed A*, cell/edge reservations, soft lane bias, and light seed tuning.

Make these distinctions explicit:

- raw score vs hackathon points
- three-seed leaderboard score vs one replay payload
- legal layout constraints vs one searched layout family
- theoretical lower/upper bounds vs measured evaluator results
- "memoryless" prose vs Python module-global reality

## Experiment Discipline

- Every numeric claim should point to a command, `data/*.json`, or `docs/experiments/*.md`.
- Prefer small ablations that isolate one mechanism.
- Keep public baselines immutable; copy into `solutions/ours/` for variants.
- Regenerate generated ablations by editing `scripts/create-ablation-variants.mjs`, not by hand-editing generated files first.
- If an evaluation times out, record status, completed seed scores, policy time, and blocked moves.
- Do not commit `outputs/` or `__pycache__/`.

## Engineering Notes

- Use `rg` for search.
- Use `apply_patch` for edits.
- Keep generated policy files ASCII and syntactically valid Python.
- After changes, run relevant validation commands before committing.
- Avoid unrelated frontend changes unless the task is specifically about the local viewer.

## Current Open Questions

- Can a layout with explicit return lanes and base-side balancing beat 1008?
- Can a cleaner layout/planner search beat 1024 without hand-written suffix actions?
- Can we create a tighter, correct upper-bound argument that explains why 1008 is possible but still constrains the search?
- Which part of the external `limit.md` proof first breaks when evaluated against the public best layout and target sequence?
