# Experiment: public-layout-diffusion-and-swap

Date: 2026-07-05

Code:

- `scripts/analyze-public-jobs.mjs`
- `scripts/make-team10-layout-swaps.mjs`
- `scripts/run-evaluation.mjs`
- `solutions/public/c31ff1c81105.py`
- `solutions/public/c15da13c3eaa.py`
- `solutions/ours/2026-07-05-team10-930-planner-with-1008-layout.py`
- `solutions/ours/2026-07-05-team10-930-planner-with-1008-layout-remapped-config.py`
- `solutions/ours/2026-07-05-team10-1008-planner-with-930-layout.py`
- `solutions/ours/2026-07-05-team10-1008-planner-with-930-layout-remapped-config.py`

Input:

- Public `/jobs` page from `https://refugio-hackathon-nine.vercel.app/jobs`
- Public `/replays/<job>` pages for all successful jobs
- Public `/code/<job>` pages for all successful jobs
- Official seeds from `data/official-seeds.json`

Hypothesis:

The speedrun mechanism did not simply fail. Shared artifacts should leave a
visible trace in the public data, but the final discontinuity should come from
information that was not legible in the artifact alone: the demand-index mapping
from hidden seeds to sorted shelf cells.

Command:

```bash
curl -L -sS https://refugio-hackathon-nine.vercel.app/jobs -o /tmp/refugio-jobs.html
# Then download public replay/code pages for succeeded jobs into:
# /tmp/refugio-analysis/replay-html/<job>.html
# /tmp/refugio-analysis/code-py/<job>.py

npm run analyze:public-jobs -- \
  --jobs-html /tmp/refugio-jobs.html \
  --replay-html-dir /tmp/refugio-analysis/replay-html \
  --code-dir /tmp/refugio-analysis/code-py \
  --summary-out data/public-job-layout-analysis.json \
  --figure-dir public/figures

node scripts/make-team10-layout-swaps.mjs

npm run eval:policy -- solutions/public/c31ff1c81105.py \
  --label team10-930-public \
  --out-dir outputs/experiments/team10-layout-swaps/team10-930-public
npm run eval:policy -- solutions/public/c15da13c3eaa.py \
  --label team10-1008-public \
  --out-dir outputs/experiments/team10-layout-swaps/team10-1008-public
npm run eval:policy -- solutions/ours/2026-07-05-team10-930-planner-with-1008-layout.py \
  --label team10-930-planner-1008-layout \
  --out-dir outputs/experiments/team10-layout-swaps/team10-930-planner-1008-layout
npm run eval:policy -- solutions/ours/2026-07-05-team10-930-planner-with-1008-layout-remapped-config.py \
  --label team10-930-planner-1008-layout-remap \
  --out-dir outputs/experiments/team10-layout-swaps/team10-930-planner-1008-layout-remap
npm run eval:policy -- solutions/ours/2026-07-05-team10-1008-planner-with-930-layout.py \
  --label team10-1008-planner-930-layout \
  --out-dir outputs/experiments/team10-layout-swaps/team10-1008-planner-930-layout
npm run eval:policy -- solutions/ours/2026-07-05-team10-1008-planner-with-930-layout-remapped-config.py \
  --label team10-1008-planner-930-layout-remap \
  --out-dir outputs/experiments/team10-layout-swaps/team10-1008-planner-930-layout-remap
```

Result:

Public-site analysis:

| Quantity | Value |
| --- | ---: |
| Jobs | 93 |
| Succeeded | 86 |
| Safety rejected | 7 |
| Exact replay layouts among successful jobs | 20 |
| Exact code files among successful jobs | 83 |

Top layout diffusion facts:

| Layout group | Jobs | Teams | First seen | Best score |
| --- | ---: | ---: | --- | ---: |
| Largest common floor layout | 33 | 14 | Team 3, 11:07, 888 | 904 |
| Older common layout | 19 | 13 | Team 16, 10:06, 24 | 884 |
| Team 4 907 layout family | 7 | 6 | Team 4, 12:23, 907 | 924 |
| Team 10 930 shared layout | 6 | 6 | Team 10, 13:27, 930 | 931 |
| Team 10 1008 final layout | 1 | 1 | Team 10, 13:57, 1008 | 1008 |

The Team 10 930 layout spread after it appeared:

| Time UTC | Team | Job | Deliveries | Points |
| --- | --- | --- | ---: | ---: |
| 13:27:11 | Team 10 | `c31ff1c81105` | 930 | 4,965 |
| 13:38:37 | Team 13 | `d3f597c7ceaa` | 918 | 0 |
| 13:48:38 | Team 3 | `3905ff4f9ead` | 931 | 831 |
| 13:55:10 | Team 12 | `9b2617f16f38` | 930 | 0 |
| 13:55:10 | Team 8 | `d9d5e50cbd41` | 930 | 0 |
| 13:57:29 | Team 5 | `9f6e36d64061` | 925 | 0 |

Team 10 layout-swap counterfactuals:

| Policy | Score | Seed scores | Blocked moves | Interpretation |
| --- | ---: | --- | ---: | --- |
| Team 10 13:27 public | 930 | 306, 318, 306 | 16 | shared 930 layout + older planner |
| Team 10 final public | 1008 | 337, 336, 335 | 4 | final public best |
| 13:27 planner + final layout | 1000 | 336, 333, 331 | 3 | drop-in final layout clears 1000 without final planner |
| 13:27 planner + final layout, remapped configs | 999 | 334, 333, 332 | 2 | same result; not a signature-miss artifact |
| final planner + 13:27 layout | 922 | 302, 315, 305 | 12 | final planner cannot recover old layout |
| final planner + 13:27 layout, remapped configs | 924 | 304, 317, 303 | 10 | remap helps only +2 |

Generated figures:

- `public/figures/event-frontier.svg`
- `public/figures/layout-diffusion.svg`

Interpretation:

The public data contradicts the strongest version of "sharing did nothing."
Layouts did travel. Exact code almost never copied, but exact replay layouts
clustered heavily: only 20 exact layouts among 86 successful jobs, and the 930
layout was reused by six teams within the final half hour.

What sharing bought was a floor and convergence. The 930 layout let multiple
teams land in the 918-931 range, but it only moved the frontier by +1 after
Team 10 posted it. The final 1008 layout arrived too late to diffuse, and it was
unique in the public record.

The swap experiment isolates the discontinuity. Replacing the 13:27 layout with
the final layout raises the older planner from 930 to 999-1000. Replacing the
final layout with the 13:27 layout drops the final planner to 922-924. Therefore
the +78 public jump was mostly a layout/demand-map jump, not a late planner
rewrite.

The article framing should be:

- Shared public code pushed the room into a narrow family of stateful traffic planners.
- Public artifacts transmitted copyable structure, especially layouts.
- The final advantage was the hidden explanation of the structure: targets are
  deterministic row-major shelf indices under the known seeds.
- The map traveled. The reason for the map did not.

Next:

- Add a clean-room "mechanism disclosure" arm: hand the agent not only the seeds
  but the explicit instruction that layout design is a rank-constrained
  index-to-position assignment over sorted shelves.
