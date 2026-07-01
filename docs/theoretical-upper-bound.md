# Theoretical upper bound analysis

This note documents the strongest upper bound I could certify for the REFUGIO
warehouse challenge using the public simulator rules and the current hidden-seed
research artifacts.

## Result

| Model | Seed 1 | Seed 2 | Seed 3 | Total |
| --- | ---: | ---: | ---: | ---: |
| Solo no-collision cycle bound | 360 | 357 | 355 | 1072 |
| Target-order plus shelf-lock CP-SAT bound | 358 | 353 | 351 | 1062 |
| Best verified solver in the research log | 342 | 342 | 338 | 1022 |

The strongest certified upper bound from this analysis is **1062 deliveries**.
The best verified solver remains **1022 deliveries**, so the exact maximum is
only known to be in the range:

```text
1022 <= exact maximum <= 1062
```

## What the 1062 model includes

The CP-SAT model keeps the constraints that directly affect the sequence and
timing of completed deliveries:

- fixed hidden seeds and deterministic target order for each robot
- the active submitted shelf layout
- 300 simulation ticks
- one action per robot per tick
- travel from the base-entry cell to a walkable pickup cell adjacent to the
  target shelf
- one tick for `PICKUP`
- return from that pickup-adjacent cell to the robot's base-entry drop cell
- one tick for `DROP`
- shelf locks while a robot is carrying the item from that shelf
- same-tick pickup conflicts on the same shelf

Each per-seed CP-SAT solve proved optimal:

```text
bff0fb14575b4676b1f0f01bfc7b0126: 358
dfbf918495ee4fca8d50b53456d59fa8: 353
546a597410b049de82f7ce72fe7fd714: 351
```

## What the model relaxes

The 1062 bound is still optimistic. It does not prove that 1062 is achievable.
The model relaxes the path-level multi-agent constraints:

- robot-to-robot vertex conflicts
- robot-to-robot edge-swap conflicts
- exact corridor and cell capacity over time
- detours needed to make all paths coexist

Those omitted constraints can only reduce the achievable score, so 1062 is a
valid upper bound for the simulator if the abstraction is implemented correctly.

## Full collision-model attempt

I also checked whether the bound could be tightened by accounting for more of
the real collision model.

An exact time-expanded automaton has to track at least position,
carried/not-carried state, delivery count, target order, and action legality for
every robot at every tick. A sampled exact expansion for one robot on one seed
already produced:

```text
time-state records: 1,539,778
transitions: 5,609,791
max states at one tick: 10,746
```

Scaling that direct model to 96 robots and three seeds would require hundreds
of millions of state records before adding collision constraints. A direct
all-robots, all-ticks CP-SAT proof is not practical locally.

I then added 674 valid aggregate separator-capacity cuts per seed. These cuts
bound the number of crossings through coordinate and rectangular graph
separators by the number of separator edges times 300 ticks. They account for
real physical throughput limits, but they are much weaker than exact cell-time
occupancy.

The separator cuts did not tighten the result:

```text
bff0fb14575b4676b1f0f01bfc7b0126: 358
dfbf918495ee4fca8d50b53456d59fa8: 353
546a597410b049de82f7ce72fe7fd714: 351
total: 1062
```

That suggests the remaining gap between 1022 and 1062 is controlled by
path-specific cell-time interactions, not by coarse separator throughput.

## Conclusion

The best certified upper bound is **1062 deliveries**. The exact maximum was not
proved. Proving it would likely require a custom decomposed MAPF/SAT/MILP search
or a matching constructive schedule plus an optimality certificate, rather than
a straightforward one-shot CP-SAT model.
