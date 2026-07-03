# Experiment: layout-ablation-scores

Date: 2026-07-03

Code:

- `solutions/public/c15da13c3eaa.py`
- `solutions/ours/2026-07-02-solver-1024-no-forced-layout-canonical-racks.py`
- `solutions/ours/2026-07-02-solver-1024-no-forced-layout-wide-avenues.py`
- `solutions/ours/c15da13c3eaa-layout-canonical-racks.py`
- `solutions/ours/c15da13c3eaa-layout-wide-avenues.py`
- `scripts/create-ablation-variants.mjs`
- `scripts/run-evaluation.mjs`

Input:

Official seeds:

- `bff0fb14575b4676b1f0f01bfc7b0126`
- `dfbf918495ee4fca8d50b53456d59fa8`
- `546a597410b049de82f7ce72fe7fd714`

Hypothesis:

Holding the Team 10 planner fixed while swapping only `create_layout()` should separate the value of the submitted layout from the value of shared-state MAPF planning.

Command:

```bash
npm run make:ablations
npm run make:1024-ablations
npm run eval:policy -- solutions/ours/c15da13c3eaa-layout-canonical-racks.py --label c15da13c3eaa-layout-canonical-racks
npm run eval:policy -- solutions/ours/c15da13c3eaa-layout-wide-avenues.py --label c15da13c3eaa-layout-wide-avenues
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-no-forced-layout-canonical-racks.py --label 2026-07-02-solver-1024-no-forced-layout-canonical-racks
npm run eval:policy -- solutions/ours/2026-07-02-solver-1024-no-forced-layout-wide-avenues.py --label 2026-07-02-solver-1024-no-forced-layout-wide-avenues
npm run analyze:layouts
```

Result:

| Policy | Layout | Score | Seed scores | Delta | Blocked moves | Policy time |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| baseline | Team 10 submitted layout | 1008 | 337, 336, 335 | 0 | 4 | 11.92s |
| layout canonical racks | starter-kit canonical rack layout | 890 | 287, 305, 298 | -118 | 34 | 14.88s |
| layout wide avenues | 10 two-column shelf strips with wide vertical avenues | 386 | 123, 120, 143 | -622 | 7,741 | 60.75s |
| 1021 no-forced planner, canonical racks | starter-kit canonical rack layout | 890 | 287, 305, 298 | -118 vs 1008 | 34 | 13.89s |
| 1021 no-forced planner, wide avenues | 10 two-column shelf strips with wide vertical avenues | 386 | 123, 120, 143 | -622 vs 1008 | 7,741 | 59.30s |

Layout feature snapshot:

| Layout | Mean pickup cells per shelf | One-access shelves | Mean nearest base-entry distance | P90 nearest base-entry distance | Full empty columns | Full empty rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Team 10 submitted layout | 1.91 | 256 | 9.79 | 18 | 18 | 11 |
| canonical racks | 1.20 | 768 | 9.94 | 19 | 26 | 10 |
| wide avenues | 1.04 | 920 | 11.76 | 22 | 30 | 2 |

Interpretation:

The Team 10 planner is not sufficient by itself. On the starter-kit canonical layout it scores 890, which is competitive but far below 1008. This quantifies at least 118 deliveries of value from the submitted layout when the planner is held fixed.

The wide-avenue result is worse, not better. It leaves broad vertical corridors, but it breaks the planner/layout pairing and produces 7,741 blocked moves. That rules out the simplistic conclusion that adding aisle width automatically improves throughput. For this policy, the geometry, target distribution, base-entry access, flow-bias assumptions, and reservation planner need to be co-designed.

The first feature metrics explain part of this. Team 10's layout gives shelves more pickup choices on average, with only 256 one-access shelves versus 768 in the canonical rack layout and 920 in the simple wide-avenue layout. The wide-avenue layout also pushes shelf access farther from the nearest base entry. More corridor width did not compensate for lower shelf access multiplicity and worse layout/planner alignment.

Repeating the same layout swaps under the 1021 `no-forced-actions` planner gives exactly the same delivery totals: 890 for canonical racks and 386 for wide avenues. The 1024 planner retuning and removal of forced suffix actions are therefore not enough to overcome these simple layout geometries. The next layout search should perturb the Team 10 topology directly while preserving its short access distances and pickup-cell multiplicity.

Next:

- Search local Team 10 layout perturbations that preserve short access distances while adding explicit return lanes near bases.
- Retune planner flow parameters after layout changes, because the current flow penalty encodes assumptions from the submitted layout.
