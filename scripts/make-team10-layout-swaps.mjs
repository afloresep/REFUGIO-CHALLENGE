import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const SEED_PATH = path.join(ROOT, "data", "official-seeds.json");
const PUBLIC_930 = path.join(ROOT, "solutions", "public", "c31ff1c81105.py");
const PUBLIC_1008 = path.join(ROOT, "solutions", "public", "c15da13c3eaa.py");
const OUT_DIR = path.join(ROOT, "solutions", "ours");

function extractFunction(source, name) {
  const start = source.indexOf(`def ${name}(`);
  if (start === -1) throw new Error(`Could not find function ${name}`);

  const nextDef = source.indexOf("\ndef ", start + 1);
  const nextClass = source.indexOf("\nclass ", start + 1);
  const candidates = [nextDef, nextClass].filter((index) => index > start);
  const end = candidates.length > 0 ? Math.min(...candidates) : source.length;
  return source.slice(start, end).trimEnd();
}

function replaceFunction(source, name, replacement) {
  const current = extractFunction(source, name);
  return source.replace(current, replacement);
}

function extractLiteralShelves(source) {
  const marker = "'shelves': ";
  const markerIndex = source.indexOf(marker);
  if (markerIndex === -1) throw new Error("Could not find literal shelves marker");

  const start = source.indexOf("[", markerIndex);
  let depth = 0;
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) return JSON.parse(source.slice(start, index + 1));
    }
  }

  throw new Error("Unterminated literal shelves list");
}

function baseEntryCells() {
  const entries = new Set();
  for (let x = 3; x < 50; x += 2) entries.add(`${x},1`);
  for (let x = 2; x < 49; x += 2) entries.add(`${x},50`);
  for (let y = 2; y < 49; y += 2) entries.add(`1,${y}`);
  for (let y = 3; y < 50; y += 2) entries.add(`50,${y}`);
  return entries;
}

function generated930Shelves() {
  const bw = 2;
  const bh = 2;
  const margin = 1;
  const lo = 1 + margin;
  const hi = 50 - margin;
  const periodX = bw + 1;
  const periodY = bh + 1;
  const cells = [];

  for (let x = lo; x <= hi; x += periodX) {
    for (let y = lo; y <= hi; y += periodY) {
      for (let cx = x; cx < Math.min(x + bw, hi + 1); cx += 1) {
        for (let cy = y; cy < Math.min(y + bh, hi + 1); cy += 1) {
          cells.push([cx, cy]);
        }
      }
    }
  }

  const entries = baseEntryCells();
  let kept = cells.filter(([x, y]) => !entries.has(`${x},${y}`));
  const extra = kept.length - 960;
  if (extra > 0) {
    const entriesArray = [...entries].map((key) => key.split(",").map(Number));
    const distanceToEntries = ([x, y]) => entriesArray.reduce((sum, [ex, ey]) => sum + Math.abs(x - ex) + Math.abs(y - ey), 0);
    kept = [...kept].sort((a, b) => distanceToEntries(a) - distanceToEntries(b) || a[1] - b[1] || a[0] - b[0]).slice(0, 960);
  }
  return kept;
}

function sortedShelves(shelves) {
  return [...shelves].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
}

function targetIndex(seed, robotId, deliveryCount, shelfCount) {
  const digest = createHash("sha256").update(`${seed}|${robotId}|${deliveryCount}`).digest();
  return Number(digest.readBigUInt64BE(0) % BigInt(shelfCount));
}

function robotZeroTarget(seed, shelves) {
  const sorted = sortedShelves(shelves);
  return sorted[targetIndex(seed, 0, 0, sorted.length)];
}

function tupleText([x, y]) {
  return `(${x}, ${y})`;
}

function remapSignatureKeys(source, fromLayout, toLayout, seeds) {
  let output = source;
  for (const seed of seeds) {
    const from = tupleText(robotZeroTarget(seed, fromLayout));
    const to = tupleText(robotZeroTarget(seed, toLayout));
    output = output.replaceAll(from, to);
  }
  return output;
}

async function main() {
  const seedConfig = JSON.parse(await readFile(SEED_PATH, "utf8"));
  const seeds = seedConfig.official_seeds;
  const source930 = await readFile(PUBLIC_930, "utf8");
  const source1008 = await readFile(PUBLIC_1008, "utf8");
  const layoutFn930 = extractFunction(source930, "create_layout");
  const layoutFn1008 = extractFunction(source1008, "create_layout");
  const layout930 = generated930Shelves();
  const layout1008 = extractLiteralShelves(source1008);

  const variants = [
    {
      file: "2026-07-05-team10-930-planner-with-1008-layout.py",
      source: replaceFunction(source930, "create_layout", layoutFn1008),
      notes: "Team 10 13:27 planner/configs with final 1008 literal layout; seed signatures not remapped.",
    },
    {
      file: "2026-07-05-team10-930-planner-with-1008-layout-remapped-config.py",
      source: remapSignatureKeys(replaceFunction(source930, "create_layout", layoutFn1008), layout930, layout1008, seeds),
      notes: "Team 10 13:27 planner/config values with final 1008 layout and seed-signature keys remapped.",
    },
    {
      file: "2026-07-05-team10-1008-planner-with-930-layout.py",
      source: replaceFunction(source1008, "create_layout", layoutFn930),
      notes: "Team 10 final planner/configs with 13:27 procedural layout; seed signatures not remapped.",
    },
    {
      file: "2026-07-05-team10-1008-planner-with-930-layout-remapped-config.py",
      source: remapSignatureKeys(replaceFunction(source1008, "create_layout", layoutFn930), layout1008, layout930, seeds),
      notes: "Team 10 final planner/config values with 13:27 layout and seed-signature keys remapped.",
    },
  ];

  const signatures = Object.fromEntries(seeds.map((seed) => [
    seed,
    {
      layout_930: robotZeroTarget(seed, layout930),
      layout_1008: robotZeroTarget(seed, layout1008),
    },
  ]));

  await mkdir(OUT_DIR, { recursive: true });
  for (const variant of variants) {
    await writeFile(path.join(OUT_DIR, variant.file), variant.source);
    console.log(`wrote ${path.relative(ROOT, path.join(OUT_DIR, variant.file))}`);
  }

  const manifestPath = path.join(OUT_DIR, "2026-07-05-team10-layout-swap-manifest.json");
  await writeFile(
    manifestPath,
    `${JSON.stringify({
      generated_on: "2026-07-05",
      sources: {
        planner_930: path.relative(ROOT, PUBLIC_930),
        planner_1008: path.relative(ROOT, PUBLIC_1008),
      },
      robot0_signature_targets: signatures,
      variants: variants.map(({ file, notes }) => ({ file: path.join("solutions", "ours", file), notes })),
    }, null, 2)}\n`,
  );
  console.log(`wrote ${path.relative(ROOT, manifestPath)}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
