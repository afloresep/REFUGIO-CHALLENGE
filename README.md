# Refugio 2026

Self-hosted implementation of the public REFUGIO hackathon surfaces:

- replay viewer backed by bundled `public/replays/*.json` payloads
- extracted Python templates from the instructions page
- deterministic safety checker with LLM-style review text

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
