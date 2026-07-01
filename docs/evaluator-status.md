# Evaluator Status

As of 2026-07-01, the executable REFUGIO evaluator is available to this Python
environment through the original starter kit, but it is not vendored in this
repo.

Current import resolution:

```text
warehouse /Users/afloresep/Downloads/refugio-starter-kit/warehouse/__init__.py
warehouse_api /Users/afloresep/Downloads/refugio-starter-kit/warehouse_api/__init__.py
```

Confirmed locally:

```bash
python3 -c "import warehouse, warehouse_api"
python3 -m warehouse.eval_runner --help
```

Official seeds:

```text
bff0fb14575b4676b1f0f01bfc7b0126
dfbf918495ee4fca8d50b53456d59fa8
546a597410b049de82f7ce72fe7fd714
```

Use the npm wrapper:

```bash
npm run eval:policy -- solutions/public/c15da13c3eaa.py --label c15da13c3eaa
```

Evaluation outputs are written to `outputs/evals/` and gitignored.

The first local score summary is committed in `data/evaluation-results.json`.
