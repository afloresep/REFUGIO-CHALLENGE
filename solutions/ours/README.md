# Local Variants

Store our policy variants and ablations here.

Suggested naming:

```text
YYYY-MM-DD-short-description.py
```

Pair every meaningful variant with an experiment note under `docs/experiments/`.

Current generated ablations for `c15da13c3eaa.py`:

- `c15da13c3eaa-default-config-only.py`
- `c15da13c3eaa-no-flow-penalty.py`
- `c15da13c3eaa-no-jitter.py`
- `c15da13c3eaa-no-shared-brain.py`
- `c15da13c3eaa-no-shared-brain-cached-world.py`
- `c15da13c3eaa-short-window-16.py`

These parse as Python. Scores for the baseline and first ablations are recorded in `data/evaluation-results.json`.
