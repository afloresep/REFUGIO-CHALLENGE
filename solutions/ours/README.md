# Local Variants

Store our policy variants and ablations here.

Suggested naming:

```text
YYYY-MM-DD-short-description.py
```

Pair every meaningful variant with an experiment note under `docs/experiments/`.

Current generated ablations for `c15da13c3eaa.py`:

- `2026-07-02-solver-1024.py`: local closed-gate 1024-delivery policy.
- `2026-07-02-solver-1024-clean-planner-floor.py`
- `2026-07-02-solver-1024-no-forced-actions.py`
- `2026-07-02-solver-1024-no-pickup-side-retarget.py`
- `2026-07-02-solver-1024-no-robot-boosts.py`
- `2026-07-02-solver-1024-no-stayer-horizon-tuning.py`
- `c15da13c3eaa-default-config-only.py`
- `c15da13c3eaa-layout-canonical-racks.py`
- `c15da13c3eaa-layout-wide-avenues.py`
- `c15da13c3eaa-no-edge-reservations.py`
- `c15da13c3eaa-no-flow-penalty.py`
- `c15da13c3eaa-no-jitter.py`
- `c15da13c3eaa-no-shared-brain.py`
- `c15da13c3eaa-no-shared-brain-cached-world.py`
- `c15da13c3eaa-short-window-16.py`

These parse as Python. Scores for the baseline and first ablations are recorded in `data/evaluation-results.json`.
