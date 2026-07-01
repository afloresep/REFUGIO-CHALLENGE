# Evaluator Status

As of 2026-07-01, this repo does not contain the executable REFUGIO evaluator.

Checked locally:

```bash
rg --files | rg '(^|/)(warehouse|eval|runner|sim|simulation|local_runner|eval_runner)'
rg -n "warehouse_api|local_runner|eval_runner|validate_layout|class Observation|enum Action" .
```

Result:

- No local `warehouse` package.
- No local `warehouse_api` implementation.
- No `warehouse.local_runner`, `warehouse.eval_runner`, or `warehouse.validate_layout` source.
- The only evaluator references are in the instruction page, templates, and extracted policies.

Implication:

The ablation inputs under `solutions/ours/` are ready, but they cannot be scored inside this repo until we recover, rebuild, or reimplement the evaluator.

Next evaluator options:

- Find the original starter kit or package distributed during the hackathon.
- Reconstruct a compatible simulator from the public rules and replay schema.
- Use public replay data only for descriptive analysis, not policy scoring.
