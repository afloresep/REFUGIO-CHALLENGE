# REFUGIO Challenge Brief

This is the working technical brief for the REFUGIO warehouse challenge. It is based on the public challenge site, the public best-code page, the public leaderboard, the postmortem blog, and the replay payloads vendored in this repo.

## Sources

- Challenge site: https://refugio-hackathon-nine.vercel.app
- Instructions: https://refugio-hackathon-nine.vercel.app/instructions
- Best public raw-score code: https://refugio-hackathon-nine.vercel.app/code/c15da13c3eaa
- Personal event recap: https://blog.micr.dev/blog/my-first-hackathon-experience
- Local replay payloads: `public/replays/*.json`

## Core Contract

- Submit one Python file.
- Define `create_layout()` and `act(observation)`.
- The warehouse is a 52 x 52 grid with a 50 x 50 interior.
- There are 96 fixed bases on the outer border.
- There must be exactly 960 unique shelf cells inside the interior.
- Base-entry cells must remain empty.
- Every shelf must have at least one cardinal adjacent walkable pickup cell.
- All empty interior cells must form one connected floor component.
- The evaluator runs 300 ticks over three hidden official seeds.
- Raw score is total deliveries across the three official seeds.
- The public replay bundled for a job is a single 300-tick run, not the three-seed aggregate.

Official seeds used for local reproduction:

- `bff0fb14575b4676b1f0f01bfc7b0126`
- `dfbf918495ee4fca8d50b53456d59fa8`
- `546a597410b049de82f7ce72fe7fd714`

## Robot Cycle

1. A robot starts empty at its base-entry cell with a target shelf.
2. It moves to any walkable cell cardinally adjacent to the target shelf.
3. It emits `Action.PICKUP`; there is no shelf direction requirement.
4. It carries the package back to its own base-entry cell.
5. It emits `Action.DROP`; the evaluator gives +1 delivery and assigns a new target.
6. The loop repeats until tick 300 ends.

## Observation Model

The instructions describe the policy as decentralized and memoryless. Each `act()` call receives:

- `tick`
- `robot_id`
- `position`
- `base_position`
- `target_item_position`
- `carrying_item`
- `grid`
- `all_robot_positions`

The robot sees every current robot position, but only its own target and carrying state.

Important caveat for analysis: the public best raw-score code uses Python module globals for a shared `_BRAIN`, cached world state, per-robot maps, and coordinated planning. So the effective environment allowed cross-call memory, even though the prose says "memoryless." That gap is central to the 920-ceiling question.

## Scoring Terms

Keep these separate:

- `replay deliveries`: deliveries shown in one bundled replay JSON.
- `raw score`: sum of deliveries over the three hidden official seeds.
- `hackathon points`: progressive-frontier points, not raw deliveries.

The progressive frontier starts at baseline `C = 100`. A submission earns points only for newly claimed raw-score slices above the previous public frontier. Later submissions with the same raw score earn 0 frontier points.

Public contradiction to explain:

- Team table winner by points: Equipo 03, 92,172 points, best deliveries 931.
- Highest raw-score job: `c15da13c3eaa`, Equipo 10, 1008 deliveries, 66,990 points.
- Local replay for `c15da13c3eaa`: 337 deliveries in one seed-like replay payload.

This is not a contradiction: 1008 is the three-seed raw score, while 337 is one replay payload, and hackathon points depend on when the frontier was crossed.

## Public Snapshot

The public leaderboard snapshot used by this repo is in `data/public-leaderboard-snapshot.json`.

The important public jobs for first-pass analysis are:

- `c15da13c3eaa`: 1008 raw deliveries, 66,990 points, Team 10.
- `3905ff4f9ead`: 931 raw deliveries, 831 points, Team 03.
- `9b2617f16f38`: 930 raw deliveries, 0 points, Team 12.
- `d9d5e50cbd41`: 930 raw deliveries, 0 points, Team 08.
- `9f6e36d64061`: 925 raw deliveries, 0 points, Team 05.

## Initial Explanation Hypotheses

1. The "maximum 921" estimate probably assumed a truly memoryless decentralized policy. The best public code uses stateful centralized coordination through module globals.
2. A simple throughput estimate undercounts if it treats robots as independent round trips instead of a traffic-flow problem with cooperative collision avoidance.
3. The layout is not passive. It shapes the queueing network, aisle contention, pickup accessibility, and return lanes.
4. Hidden official seeds were partially fingerprintable. The best public code selects planner parameters from the first target of robot 0.
5. LLMs likely over-indexed on shortest-path distance and shelf density, and under-indexed on time-expanded reservation planning and per-seed specialization.
6. The public replay total and the three-seed raw score are easy to confuse, producing false ceiling arguments.

## What We Still Need

- Score the generated ablation variants under the local evaluator.
- Re-run the public best code under controlled variants: no globals, no seed fingerprinting, no custom layout, no flow penalty, lower planning window.
- Build upper-bound calculations that account for traffic conflicts, base-entry throughput, and pickup access, not just robot round-trip lengths.
