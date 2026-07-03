# Research Plan

The goal is to produce a technical postmortem and a better solution path, not just a prettier replay viewer.

## Questions

1. Why did several LLM analyses conclude that roughly 921 deliveries was a ceiling?
2. Which assumption broke when Team 10 reached 1008 deliveries?
3. How much of the lift came from layout geometry, stateful coordination, seed tuning, and planner details?
4. Can we find a stronger strategy than the public best solution and the current 1024 local solver?
5. What evidence should the final technical writeup show so the explanation is convincing?

## Workstreams

### 1. Public Data Baseline

- Preserve the public leaderboard snapshot.
- Summarize bundled replays with repeatable scripts.
- Compare single-replay totals with public three-seed raw scores.
- Extract visible public code for high-value jobs.

### 2. Rule and Evaluator Model

- Record the exact layout constraints.
- Model the robot lifecycle and action semantics.
- Reconstruct the scoring formula.
- Identify which prose constraints were actually enforced by public results.

### 3. Best-Solution Anatomy

Analyze `c15da13c3eaa` as a case study:

- custom shelf layout
- global `_BRAIN` state
- cached BFS distance fields
- time-windowed A* reservation planning
- first-move conflict resolution
- soft one-way flow penalties
- per-seed parameter selection from robot 0's first target

### 4. Ceiling Analysis

Build upper-bound estimates in layers:

- optimistic no-collision lower travel distance
- base-entry throughput constraints
- shelf-access bottlenecks
- aisle traffic and swap conflicts
- pickup/drop action overhead
- per-seed target distribution

The target is not a formal proof at first. The target is to locate which bound was falsely tight.

### 5. New Search

Once the evaluator is available or reconstructed:

- run ablations of Team 10's policy
- search layouts with lane structure and base-side balancing
- tune reservation-window parameters by seed
- compare deterministic and jittered priority rules
- test whether cleaner planner/layout search can beat the 1024 three-seed local result

## Experiment Log Format

Use one markdown file per experiment under `docs/experiments/`:

```md
# Experiment: short-title

Date:
Code:
Input:
Hypothesis:
Command:
Result:
Interpretation:
Next:
```

When the simulator is available, every numeric claim in the writeup should point to one of these experiment notes or to a script output.

## Near-Term Checklist

- [x] Add challenge brief.
- [x] Add public leaderboard snapshot.
- [x] Add replay analysis script.
- [x] Extract public best code to a local solution file.
- [x] Add static analyzer for policy features.
- [x] Generate first ablation input files.
- [x] Document current evaluator gap.
- [x] Confirm local evaluator availability.
- [x] Score first ablation variants.
- [x] Add no-shared-brain ablations.
- [x] Review external `limit.md` 1000-impossible argument.
- [x] Add no-edge-reservation ablation.
- [x] Add layout ablations.
- [x] Add layout feature analysis script.
- [x] Add first 1024 mechanism ablations.
- [ ] Add combined 1024 mechanism ablations.
- [ ] Search layout variants around the 1021 no-forced-actions planner.
