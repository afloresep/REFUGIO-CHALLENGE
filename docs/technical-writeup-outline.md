# Technical Writeup Outline

Working title: `Why 920 Was Not the Ceiling`

## Thesis

The apparent 920-ish ceiling came from analyzing a different problem than the one the evaluator actually rewarded. A memoryless, decentralized, generic warehouse policy may plateau around that region, but the public best result used a custom layout, shared module state, time-expanded cooperative planning, and seed-specific tuning to reach 1008 raw deliveries.

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

Evidence:

- `data/public-leaderboard-snapshot.json`
- `npm run analyze:replays`

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
| no-globals ablation drops below 1008 | simulator experiment | pending |
| custom layout matters quantitatively | simulator experiment | pending |
