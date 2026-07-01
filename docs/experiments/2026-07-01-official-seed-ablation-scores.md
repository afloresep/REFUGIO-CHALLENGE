# Experiment: official-seed-ablation-scores

Date: 2026-07-01

Code:

- `solutions/public/c15da13c3eaa.py`
- `solutions/ours/c15da13c3eaa-default-config-only.py`
- `solutions/ours/c15da13c3eaa-no-flow-penalty.py`
- `solutions/ours/c15da13c3eaa-no-jitter.py`
- `solutions/ours/c15da13c3eaa-short-window-16.py`
- `scripts/run-evaluation.mjs`

Input:

Official seeds:

- `bff0fb14575b4676b1f0f01bfc7b0126`
- `dfbf918495ee4fca8d50b53456d59fa8`
- `546a597410b049de82f7ce72fe7fd714`

Hypothesis:

The extracted public best policy should reproduce the public 1008 raw score locally. The first ablations should show which small mechanisms account for the last deliveries above the fallback near 1000.

Command:

```bash
npm run eval:policy -- solutions/public/c15da13c3eaa.py --label c15da13c3eaa
npm run eval:policy -- solutions/ours/c15da13c3eaa-default-config-only.py --label c15da13c3eaa-default-config-only
npm run eval:policy -- solutions/ours/c15da13c3eaa-no-flow-penalty.py --label c15da13c3eaa-no-flow-penalty
npm run eval:policy -- solutions/ours/c15da13c3eaa-no-jitter.py --label c15da13c3eaa-no-jitter
npm run eval:policy -- solutions/ours/c15da13c3eaa-short-window-16.py --label c15da13c3eaa-short-window-16
```

Result:

| Policy | Score | Seed scores | Delta | Blocked moves | Policy time |
| --- | ---: | --- | ---: | ---: | ---: |
| baseline | 1008 | 337, 336, 335 | 0 | 4 | 11.92s |
| default config only | 1000 | 336, 333, 331 | -8 | 3 | 12.70s |
| no flow penalty | 992 | 334, 330, 328 | -16 | 13 | 13.18s |
| no jitter | 1001 | 334, 336, 331 | -7 | 8 | 12.19s |
| short window 16 | 997 | 334, 336, 327 | -11 | 2 | 9.78s |

Interpretation:

The extracted public policy reproduces the public 1008 score exactly. The first replay seed gives 337 deliveries, matching the bundled replay for `c15da13c3eaa`.

The seed-specific config is useful but is not the full story: removing it still scores 1000. That means the main >920 jump is already present in the shared-state planner plus custom layout.

The soft flow penalty is the largest of these first ablations at -16 deliveries and raises blocked moves from 4 to 13, so the lane-like movement bias is doing real congestion work.

Shortening the reservation horizon to 16 costs 11 deliveries while reducing runtime, which gives a useful speed/score knob for future search.

Next:

- Add ablations for no edge reservations and no shared `_BRAIN`.
- Compare the same planner against canonical and wide-avenue layouts.
- Run repeated local variants only when the policy contains jitter; otherwise deterministic runs should be stable for these seeds.
