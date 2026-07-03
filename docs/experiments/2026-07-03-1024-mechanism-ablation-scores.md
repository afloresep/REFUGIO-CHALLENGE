# Experiment: 1024-mechanism-ablation-scores

Date: 2026-07-03

Code:

- `solutions/ours/2026-07-02-solver-1024.py`
- `solutions/ours/2026-07-02-solver-1024-clean-planner-floor.py`
- `solutions/ours/2026-07-02-solver-1024-no-forced-actions.py`
- `solutions/ours/2026-07-02-solver-1024-no-pickup-side-retarget.py`
- `solutions/ours/2026-07-02-solver-1024-no-robot-boosts.py`
- `solutions/ours/2026-07-02-solver-1024-no-stayer-horizon-tuning.py`
- `scripts/create-1024-ablation-variants.mjs`
- `scripts/run-evaluation.mjs`

Input:

Official seeds:

- `bff0fb14575b4676b1f0f01bfc7b0126`
- `dfbf918495ee4fca8d50b53456d59fa8`
- `546a597410b049de82f7ce72fe7fd714`

Hypothesis:

The 1024 policy should split into a generally stronger planner layer plus small scenario-specific suffix fixes. Removing targeted mechanisms one at a time should show which layer carries the extra deliveries beyond 1008.

Command:

```bash
npm run make:1024-ablations
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024.py --label 2026-07-02-solver-1024-confirm
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-clean-planner-floor.py --label 2026-07-02-solver-1024-clean-planner-floor
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-no-forced-actions.py --label 2026-07-02-solver-1024-no-forced-actions
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-no-pickup-side-retarget.py --label 2026-07-02-solver-1024-no-pickup-side-retarget
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-no-robot-boosts.py --label 2026-07-02-solver-1024-no-robot-boosts
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-no-stayer-horizon-tuning.py --label 2026-07-02-solver-1024-no-stayer-horizon-tuning
```

Result:

| Policy | Score | Seed scores | Delta vs 1024 | Delta vs 1008 | Blocked moves | Remaining distance |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 1024 solver | 1024 | 343, 342, 339 | 0 | +16 | 12 | 6,180 |
| clean planner floor | 1009 | 337, 335, 337 | -15 | +1 | 19 | 6,816 |
| no forced actions | 1021 | 342, 340, 339 | -3 | +13 | 2 | 7,082 |
| no pickup-side retarget | 1018 | 337, 342, 339 | -6 | +10 | 9 | 6,098 |
| no robot boosts | 1020 | 343, 340, 337 | -4 | +12 | 14 | 6,092 |
| no stayer-horizon tuning | 1011 | 336, 336, 339 | -13 | +3 | 26 | 6,102 |

Static differences from the public 1008 baseline:

- Same 960-shelf layout as `solutions/public/c15da13c3eaa.py`.
- Same shared `_BRAIN`, cached distance fields, rolling A*, cell and edge reservations.
- Retuned official-scenario configs: `(14, 42): (34, 0.06)`, `(12, 33): (34, 0.09)`, `(26, 47): (34, 0.06)`.
- `JITTER_CONFIGS = {}`, so the 1024 result is deterministic for these seeds.
- Added scenario-specific stayer reservation horizons.
- Added late pickup-side retargeting.
- Added late per-robot priority boosts.
- Added 366 explicit forced-action keys across the three scenario signatures.

Interpretation:

The hard-coded forced actions are useful but not the main reason the policy clears 1008. Disabling all forced actions still scores 1021. This means the broader retuned planner layer is worth most of the +16.

The combined clean planner floor disables forced actions, robot boosts, pickup-side retargeting, and stayer-horizon tuning together. It scores 1009, only one delivery above the public 1008 baseline. So the retuned `SEED_CONFIGS`/deterministic planner layer alone is just enough to clear the public result, while the helper mechanisms together account for almost all of the final 1024 score.

The largest single tested mechanism is stayer-horizon tuning. Reverting `STAYER_CONFIGS` to the default costs 13 deliveries and raises blocked moves to 26. This suggests the 1024 policy improved throughput partly by not reserving goal/stayer cells too far into the future in the two scenarios where that over-constrains traffic.

Pickup-side retargeting costs 6 deliveries when removed. Robot priority boosts cost 4. Forced actions cost 3 delivery points but also improve the remaining-distance tie-breaker substantially, from 7,082 to 6,180.

Next:

- Isolate retuned `SEED_CONFIGS` versus the public 1008 settings.
- Use the 1021 no-forced-actions variant as the cleaner high-score base for future layout search, but use the 1009 clean planner floor when the point is to avoid all suffix-specific aids.
