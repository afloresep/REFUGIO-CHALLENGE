# Technical Writeup Outline

Working title: `Why 920 Was Not the Ceiling`

## Thesis

The apparent 920-ish ceiling came from analyzing a different problem than the one the evaluator actually rewarded. A memoryless, decentralized, generic warehouse policy may plateau around that region, but the public best result used a custom layout, shared module state, time-expanded cooperative planning, and seed-specific tuning to reach 1008 raw deliveries. The public data shows that sharing did transmit copyable artifacts, especially layouts, but the final discontinuity came from an unspoken explanation of the artifact: the hidden-seed demand stream is a row-major shelf-index assignment problem. A local closed-gate continuation of the same family reaches 1024 by retuning the planner and adding audited late-game fixes, and replay-matrix policies reach 1042.

## Structure

### 1. The Challenge

- One Python file.
- Two functions: `create_layout()` and `act(observation)`.
- 96 robots, 960 shelves, 52 x 52 grid, 300 ticks, three hidden seeds.
- Robot loop: target, pickup, return, drop, repeat.
- Scoring: raw deliveries vs progressive-frontier points.

Evidence:

- instructions page
- leaderboard snapshot
- local replay summary

### 2. The Scoreboard Trap

- The point winner was not the raw-score winner.
- 931 deliveries won the points table.
- 1008 deliveries was the highest public raw score.
- Local replay files show one run, not the three-seed aggregate.
- Public sharing was not inert: exact layouts diffused heavily, while exact code copying was rare.
- The Team 10 930 layout spread to six teams and produced the winning 931-point submission, but Team 10's 1008 layout arrived too late and stayed unique.

Evidence:

- `data/public-leaderboard-snapshot.json`
- `data/public-job-layout-analysis.json`
- `npm run analyze:replays`
- `npm run analyze:public-jobs`

### 3. What We Did Wrong

- We spent time asking broad LLMs for "maximum possible" reasoning before pinning down the exact evaluator behavior.
- We accepted the memoryless/decentralized phrasing too literally.
- We treated layout and policy as separable instead of co-designed.
- We underestimated the value of being first under progressive-frontier scoring.

### 4. The Missing Capability: Shared State

- The instructions claim no shared memory.
- The best public code has a shared `_BRAIN`.
- `act()` is called once per robot per tick in one Python module, so globals can coordinate all robots.
- That turns the problem from independent local routing into centralized cooperative MAPF.

Evidence:

- best-code page
- extracted best solution once committed locally

### 5. Anatomy of the 1008 Solution

Explain the public best result:

- custom shelf topology
- base-entry handling
- BFS fields to shelves and bases
- prioritized reservation planning over a rolling time window
- edge reservations to prevent swaps
- soft directional lane penalties
- stuck-robot fallback
- per-seed window and flow settings

### 6. Why the LLM Ceiling Failed

Likely failure modes:

- bounded by average shortest-path round trip
- assumed independent robots
- ignored action timing details
- ignored global-memory implementation possibility
- ignored hidden-seed fingerprinting
- reasoned from starter layouts instead of layout-policy co-design
- conflated public points with raw deliveries

### 7. Toward a Better Solver

Candidate improvements:

- design layout as a traffic network first, storage second
- reserve base-entry return lanes explicitly
- use assignment-like target pressure metrics, even without seeing other targets
- search layouts with congestion metrics, not only average shelf distance
- tune by seed only where allowed by observable initial state
- add stronger deadlock recovery than one-step fallback
- separate robust planner changes from hand-written hidden-seed suffix actions

### 8. What We Can Prove

Separate:

- measured public facts
- reproduced simulator facts
- inferred evaluator behavior
- hypotheses still needing ablation

### 9. Final Takeaway

The lesson is not that LLMs are useless for optimization. The lesson is that they are bad at discovering hidden degrees of freedom unless the evaluator contract is treated as executable evidence.

## Evidence Table To Fill

| Claim | Evidence | Status |
| --- | --- | --- |
| 1008 was public best raw score | leaderboard snapshot | done |
| bundled `c15da13c3eaa` replay has 337 deliveries | replay script | done |
| best policy uses module-global shared state | public code extraction + static analyzer | done |
| best policy uses seed-specific config | public code extraction + static analyzer | done |
| extracted baseline reproduces 1008 | official-seed evaluator run | done |
| seed-specific config matters quantitatively | official-seed ablation | done |
| flow penalty matters quantitatively | official-seed ablation | done |
| edge reservations are decisive for throughput | official-seed ablation | done |
| no-globals ablation drops below 1008 | official-seed ablation | done |
| `limit.md` impossibility proof is contradicted | official-seed evaluator run | done |
| custom layout matters quantitatively | official-seed layout ablation | done |
| Team 10 layout has stronger shelf access than simple alternatives | layout feature analysis | done |
| local closed-gate solver reaches 1024 | official-seed evaluator run | done |
| 1024 mostly comes from retuned planner layer, not forced actions alone | official-seed ablation | done |
| removing all 1024 helper mechanisms leaves a 1009 clean planner floor | official-seed ablation | done |
| 1024 clean floor depends on seed-config and jitter interactions | official-seed ablation | done |
| 1021 no-forced planner does not rescue simple alternate layouts | official-seed layout ablation | done |
| exact public layouts diffused far more than exact code | public job/replay/code analysis | done |
| Team 10's 930 layout propagated to six teams, but 1008 stayed unique | public layout diffusion analysis | done |
| Team 10 13:27 planner plus final layout scores 999-1000 | layout-swap counterfactual | done |
| Team 10 final planner plus 13:27 layout scores 922-924 | layout-swap counterfactual | done |
