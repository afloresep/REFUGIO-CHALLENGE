# Refugio 2026

This repo is the working bench for a technical postmortem and follow-up solver
work on the REFUGIO warehouse challenge.

It currently includes a self-hosted implementation of the public hackathon
surfaces:

- replay viewer backed by bundled `public/replays/*.json` payloads
- extracted Python templates from the instructions page
- deterministic safety checker with LLM-style review text

It also contains the beginning of the analysis track:

- `docs/challenge-brief.md` captures the challenge contract and the 921 vs 1008
  scoring distinction.
- `docs/research-plan.md` lays out the experiments needed for the technical
  postmortem.
- `docs/technical-writeup-outline.md` is the draft structure for the blog-style
  technical article.
- `docs/evaluator-status.md` records the current simulator/evaluator gap.
- `data/public-leaderboard-snapshot.json` preserves the public leaderboard facts
  used by the analysis.
- `data/evaluation-results.json` records local official-seed scores for the
  extracted baseline and first ablations.
- `scripts/analyze-replays.mjs` summarizes vendored replay payloads.

## Run

```bash
npm install
npm run dev -- --hostname 0.0.0.0 --port 3002
```

Open `http://127.0.0.1:3002`.

## Routes

- `/instructions` summarizes the public challenge contract.
- `/templates` renders the extracted Python templates.
- `/review` checks a Python policy against local safety rules.
- `/replays/bf4184ae5b49` loads and renders a public replay.

## Analysis

Summarize the bundled public replays:

```bash
npm run analyze:replays
npm run analyze:replays -- --json
```

Extract and inspect a public policy:

```bash
npm run fetch:public-code -- c15da13c3eaa
npm run analyze:policy -- solutions/public/c15da13c3eaa.py
npm run make:ablations
npm run eval:policy -- solutions/public/c15da13c3eaa.py --label c15da13c3eaa
```

The leaderboard raw score is a three-seed aggregate. The bundled replay JSON for
each job is one 300-tick payload, so its `total_deliveries` is expected to be
roughly one third of the public raw score for high-scoring jobs.

Official seed values are recorded in `data/official-seeds.json`. Evaluation
outputs are written under `outputs/`, which is intentionally gitignored.

## Replay extraction

Runtime replay pages do not depend on the public Vercel app. The known replay
payloads are vendored under `public/replays/` and read from disk by the app.

The public site originally embedded replay data in Next Flight script chunks. The
parser in `src/lib/refugio-replay.ts` is kept so additional public payloads can be
ingested deliberately, but normal app routes use local data only.

## Research notes

- [Theoretical upper bound analysis](docs/theoretical-upper-bound.md) documents
  the strongest certified delivery ceiling found for the hidden-seed warehouse
  runs and explains why the exact maximum remains unproved.
