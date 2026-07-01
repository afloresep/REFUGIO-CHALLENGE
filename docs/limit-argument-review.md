# Review: `limit.md` 1000-Impossible Argument

Source read on 2026-07-01:

```text
/Users/afloresep/refugio-2/refugio/limit.md
```

## Core Claims In The Note

- Current solution scores 894 on the three official seeds.
- A perfect planner on the best legal layout is capped near 960.
- 1000 is unreachable.
- The absolute 1033 idealization is physically impossible because it assumes travel through shelves, an illegal solid central blob, and no congestion or shelf locks.
- Realistic reachable scores are in the low 900s.

## Direct Contradictions From This Repo

Measured with `python3 -m warehouse.eval_runner` on the official seeds:

| Policy | Score | Seed scores |
| --- | ---: | --- |
| `solutions/public/c15da13c3eaa.py` | 1008 | 337, 336, 335 |
| `default-config-only` ablation | 1000 | 336, 333, 331 |
| `no-jitter` ablation | 1001 | 334, 336, 331 |
| `short-window-16` ablation | 997 | 334, 336, 327 |

So the claim "1000 is unreachable" is false under the actual evaluator. It is false even without seed-specific config and false without jitter.

## Likely Failure Points

1. The note analyzes the author's `solve.py` and layout search, not the public best layout and planner.
2. The "best legal layout, perfect planner = 960" bound is empirically invalid because a legal submitted layout plus real planner scores 1008.
3. The distance/throughput model treats average trip cost as a tight global ceiling, but the public best result shows the assumed average distance or cycle accounting is not tight for the actual target sequence/layout.
4. The congestion argument assumes 1-wide-aisle conflicts are mostly irreducible. The baseline's 4 blocked moves versus the no-shared-brain cached variant's 14,305 blocked moves shows coordination removes almost all observed move conflicts in this evaluator.
5. The note misses the effective power of module-global planner state: shared per-robot state, rolling reservations, target locks, and cached fields across calls.

## Useful Evidence From Our No-Brain Ablation

| Policy | Score | Blocked moves | Status |
| --- | ---: | ---: | --- |
| baseline | 1008 | 4 | succeeded |
| no shared brain, cached world | 492 | 14,305 | succeeded |
| no shared brain, fresh world | 0 official / 172 first seed | 4,813 on completed seed | timed out |

This is a clean postmortem point: the public best score is not just a better geometry. It depends on turning the nominally decentralized `act()` calls into a stateful centralized planner.

## How To Use This In The Writeup

Treat `limit.md` as the representative failed proof:

- It starts from plausible physical accounting.
- It over-trusts a "best legal layout" search result.
- It converts a measured plateau of one solution family into a universal upper bound.
- It does not validate the bound against the actual public best code.

The writeup should show the contradiction early: `limit.md` says 1000 is impossible, while `c15da13c3eaa.py` reproduces 1008 locally on the same seeds.
