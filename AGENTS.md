# AGENTS.md

This repo is a working bench for understanding and improving the REFUGIO warehouse hackathon result, and for turning that work into a technical article.

The main goal is not to polish the local Next app. The main goal is to explain why "1000 deliveries is impossible" was a false conclusion, reproduce the public 1008 result, dissect the mechanisms that made it possible, and search for a stronger policy/layout.

## Start Here

Read these files before making claims or changes:

- `docs/challenge-brief.md` - challenge rules, robot cycle, scoring terms.
- `docs/research-plan.md` - current workstreams and checklist.
- `docs/technical-writeup-outline.md` - intended article structure.
- `docs/experiments/2026-07-01-official-seed-ablation-scores.md` - key ablation results.
- `docs/limit-argument-review.md` - why the external "1000 impossible" proof is wrong.
- `data/evaluation-results.json` - machine-readable official-seed scores.

If you need one sentence of context: the public best policy reached 1008 because the evaluator allowed Python module-global state, turning nominally decentralized `act()` calls into a centralized cooperative MAPF planner with shared robot state and rolling reservations.

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

Important measured ablations:

| Policy | Score | Seed scores | Main lesson |
| --- | ---: | --- | --- |
| baseline | 1008 | 337, 336, 335 | public result reproduced |
| default config only | 1000 | 336, 333, 331 | seed tuning is useful but not the whole jump |
| no flow penalty | 992 | 334, 330, 328 | soft lane bias matters |
| no jitter | 1001 | 334, 336, 331 | jitter helps but is not essential |
| short window 16 | 997 | 334, 336, 327 | reservation horizon matters |
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

Analyze a policy statically:

```bash
npm run analyze:policy -- solutions/public/c15da13c3eaa.py
```

Regenerate ablations from the public baseline:

```bash
npm run make:ablations
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

1. Add a no-edge-reservation ablation.
   Keep shared `_BRAIN`, cell reservations, and layout. Remove only edge-swap reservations. Score it on official seeds and record whether head-on swap prevention is a major part of the 1008.

2. Add layout ablations.
   Run the Team 10 planner on canonical rack blocks and wide avenues. This separates custom layout value from planner value.

3. Add a layout feature analysis script.
   Compute shelf access counts, average base-entry distances, aisle widths/connectivity, and congestion proxies for public layouts and ablations.

4. Extract more public policies if useful.
   Start with jobs around 930 and 925. Use `npm run fetch:public-code -- <job-id>`.

5. Draft the article from evidence, not vibes.
   The article should open with the contradiction: an agent claimed 1000 was impossible, but the public best code reproduces 1008 locally on the same seeds.

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

- How much does edge-reservation logic contribute independent of cell reservations?
- How much of 1008 is layout versus planner when the planner is held fixed?
- Can a layout with explicit return lanes and base-side balancing beat 1008?
- Can we create a tighter, correct upper-bound argument that explains why 1008 is possible but still constrains the search?
- Which part of the external `limit.md` proof first breaks when evaluated against the public best layout and target sequence?
