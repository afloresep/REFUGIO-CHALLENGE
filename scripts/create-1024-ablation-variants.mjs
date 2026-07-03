import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(rootDir, "solutions", "ours", "2026-07-02-solver-1024.py");
const outputDir = path.join(rootDir, "solutions", "ours");
const walkMin = 1;
const walkMax = 50;
const shelfCount = 960;

const publicSeedConfigs = [
  "SEED_CONFIGS = {",
  "    (14, 42): (34, 0.1),",
  "    (12, 33): (32, 0.06),",
  "    (26, 47): (32, 0.06),",
  "}",
].join("\n");

const publicJitterConfigs = [
  "JITTER_CONFIGS = {",
  "    (14, 42): (1, 0.05),",
  "    (12, 33): (13, 0.05),",
  "}",
].join("\n");

function replaceOnce(source, pattern, replacement) {
  if (!pattern.test(source)) {
    throw new Error(`Could not find pattern ${pattern}`);
  }

  return source.replace(pattern, replacement);
}

function replaceBlock(source, name, replacement) {
  const pattern = new RegExp(`^${name} = (?:\\{\\}|\\{[\\s\\S]*?^\\})`, "m");

  if (!pattern.test(source)) {
    throw new Error(`Could not find block ${name}`);
  }

  return source.replace(pattern, replacement);
}

function replaceCreateLayout(source, shelves) {
  assertValidShelves(shelves);

  const pattern = /^def create_layout\(\):\n[\s\S]*?\n(?=def _base_entry)/m;
  if (!pattern.test(source)) {
    throw new Error("Could not find create_layout block");
  }

  return source.replace(
    pattern,
    [
      "def create_layout():",
      `    return {'schema_version': 1, 'shelves': ${JSON.stringify(sortShelves(shelves))}}`,
      "",
    ].join("\n"),
  );
}

function withHeader(source, name, hypothesis) {
  return [
    `# Generated 1024 ablation: ${name}`,
    "# Source baseline: solutions/ours/2026-07-02-solver-1024.py",
    `# Hypothesis: ${hypothesis}`,
    source,
  ].join("\n");
}

function cellKey([x, y]) {
  return `${x},${y}`;
}

function sortShelves(shelves) {
  return [...shelves].sort(([ax, ay], [bx, by]) => ay - by || ax - bx);
}

function neighbors([x, y]) {
  return [
    [x + 1, y],
    [x, y + 1],
    [x - 1, y],
    [x, y - 1],
  ];
}

function inWalkableArea([x, y]) {
  return x >= walkMin && x <= walkMax && y >= walkMin && y <= walkMax;
}

function baseEntryCells() {
  const entries = [];
  for (let x = 3; x < 50; x += 2) entries.push([x, 1]);
  for (let x = 2; x < 49; x += 2) entries.push([x, 50]);
  for (let y = 2; y < 49; y += 2) entries.push([1, y]);
  for (let y = 3; y < 50; y += 2) entries.push([50, y]);
  return entries;
}

function assertValidShelves(shelves) {
  if (shelves.length !== shelfCount) {
    throw new Error(`Expected ${shelfCount} shelves, got ${shelves.length}`);
  }

  const shelfSet = new Set(shelves.map(cellKey));
  if (shelfSet.size !== shelves.length) {
    throw new Error("Generated layout contains duplicate shelf cells");
  }

  for (const shelf of shelves) {
    if (!inWalkableArea(shelf)) {
      throw new Error(`Generated shelf is outside walkable area: ${shelf}`);
    }
  }

  const blockedEntry = baseEntryCells().find((entry) => shelfSet.has(cellKey(entry)));
  if (blockedEntry) {
    throw new Error(`Generated layout blocks base entry cell: ${blockedEntry}`);
  }

  const inaccessibleShelf = shelves.find((shelf) =>
    !neighbors(shelf).some((neighbor) => inWalkableArea(neighbor) && !shelfSet.has(cellKey(neighbor))),
  );
  if (inaccessibleShelf) {
    throw new Error(`Generated shelf has no adjacent pickup cell: ${inaccessibleShelf}`);
  }

  const walkable = [];
  const walkableSet = new Set();
  for (let y = walkMin; y <= walkMax; y += 1) {
    for (let x = walkMin; x <= walkMax; x += 1) {
      const key = cellKey([x, y]);
      if (!shelfSet.has(key)) {
        walkable.push([x, y]);
        walkableSet.add(key);
      }
    }
  }

  const queue = [walkable[0]];
  const seen = new Set([cellKey(walkable[0])]);
  for (let index = 0; index < queue.length; index += 1) {
    for (const neighbor of neighbors(queue[index])) {
      const key = cellKey(neighbor);
      if (walkableSet.has(key) && !seen.has(key)) {
        seen.add(key);
        queue.push(neighbor);
      }
    }
  }
  if (seen.size !== walkable.length) {
    throw new Error("Generated layout walkable cells are disconnected");
  }
}

function canonicalRackShelves() {
  const shelves = [];
  for (let x0 = 3; x0 < 48; x0 += 4) {
    for (const [y0, y1] of [
      [3, 12],
      [15, 24],
      [27, 36],
      [39, 48],
    ]) {
      for (const x of [x0, x0 + 1]) {
        for (let y = y0; y <= y1; y += 1) {
          shelves.push([x, y]);
        }
      }
    }
  }
  return sortShelves(shelves);
}

function wideAvenueShelves() {
  const shelves = [];
  for (const x0 of [3, 8, 13, 18, 23, 28, 33, 38, 43, 48]) {
    for (const x of [x0, x0 + 1]) {
      for (let y = 2; y <= 49; y += 1) {
        shelves.push([x, y]);
      }
    }
  }
  return sortShelves(shelves);
}

function disableForcedActions(source) {
  return replaceOnce(
    source,
    /    forced=FORCED_ACTIONS\.get\(\(ACTIVE_SCENARIO,rid,brain\.cur_tick,pos,carrying\)\)/,
    "    forced=None",
  );
}

function disableRobotBoosts(source) {
  return replaceBlock(source, "ROBOT_BOOSTS", "ROBOT_BOOSTS = {}");
}

function disablePickupSideRetarget(source) {
  let next = replaceBlock(source, "PICKUP_SIDE_CONFIGS", "PICKUP_SIDE_CONFIGS = {}");
  next = replaceBlock(next, "PICKUP_SIDE_FINISHABLE_CONFIGS", "PICKUP_SIDE_FINISHABLE_CONFIGS = {}");
  return next;
}

function disableStayerHorizonTuning(source) {
  return replaceBlock(source, "STAYER_CONFIGS", "STAYER_CONFIGS = {}");
}

function cleanPlannerFloorSource(source) {
  let next = disableForcedActions(source);
  next = disableRobotBoosts(next);
  next = disablePickupSideRetarget(next);
  next = disableStayerHorizonTuning(next);
  return next;
}

function applyPublicSeedConfigs(source) {
  return replaceBlock(source, "SEED_CONFIGS", publicSeedConfigs);
}

function applyPublicJitterConfigs(source) {
  return replaceBlock(source, "JITTER_CONFIGS", publicJitterConfigs);
}

function disableLatePriorityTiming(source) {
  let next = replaceBlock(source, "ETA_LATE_CONFIGS", "ETA_LATE_CONFIGS = {}");
  next = replaceBlock(next, "DEADLINE_TIGHT_CONFIGS", "DEADLINE_TIGHT_CONFIGS = {}");
  return next;
}

function noForcedActions(source) {
  const next = disableForcedActions(source);

  return withHeader(
    next,
    "no-forced-actions",
    "Measure how much of 1024 comes from audited per-scenario action overrides.",
  );
}

function noRobotBoosts(source) {
  const next = disableRobotBoosts(source);

  return withHeader(
    next,
    "no-robot-boosts",
    "Measure how much of 1024 comes from late per-robot priority boosts.",
  );
}

function noPickupSideRetarget(source) {
  const next = disablePickupSideRetarget(source);

  return withHeader(
    next,
    "no-pickup-side-retarget",
    "Measure how much of 1024 comes from late pickup-side selection instead of generic shelf adjacency.",
  );
}

function noStayerHorizonTuning(source) {
  const next = disableStayerHorizonTuning(source);

  return withHeader(
    next,
    "no-stayer-horizon-tuning",
    "Measure how much of 1024 comes from scenario-specific reservation horizon for robots already at a goal.",
  );
}

function cleanPlannerFloor(source) {
  const next = cleanPlannerFloorSource(source);

  return withHeader(
    next,
    "clean-planner-floor",
    "Measure the 1024 planner floor after removing forced actions, robot boosts, pickup-side retargeting, and stayer-horizon tuning together.",
  );
}

function cleanFloorPublicSeedConfigs(source) {
  const next = applyPublicSeedConfigs(cleanPlannerFloorSource(source));

  return withHeader(
    next,
    "clean-floor-public-seed-configs",
    "Measure the clean 1024 planner floor after reverting only SEED_CONFIGS to the public 1008 values.",
  );
}

function cleanFloorPublicJitter(source) {
  const next = applyPublicJitterConfigs(cleanPlannerFloorSource(source));

  return withHeader(
    next,
    "clean-floor-public-jitter",
    "Measure the clean 1024 planner floor after restoring the public 1008 jitter settings.",
  );
}

function cleanFloorPublicConfigs(source) {
  let next = cleanPlannerFloorSource(source);
  next = applyPublicSeedConfigs(next);
  next = applyPublicJitterConfigs(next);

  return withHeader(
    next,
    "clean-floor-public-configs",
    "Measure the clean 1024 planner floor after reverting both seed configs and jitter to the public 1008 values.",
  );
}

function cleanFloorNoLatePriority(source) {
  const next = disableLatePriorityTiming(cleanPlannerFloorSource(source));

  return withHeader(
    next,
    "clean-floor-no-late-priority",
    "Measure the clean 1024 planner floor after removing late ETA/deadline priority timing.",
  );
}

function noForcedLayoutCanonicalRacks(source) {
  const next = replaceCreateLayout(disableForcedActions(source), canonicalRackShelves());

  return withHeader(
    next,
    "no-forced-layout-canonical-racks",
    "Measure the 1021 no-forced-actions planner on the starter-kit canonical rack layout.",
  );
}

function noForcedLayoutWideAvenues(source) {
  const next = replaceCreateLayout(disableForcedActions(source), wideAvenueShelves());

  return withHeader(
    next,
    "no-forced-layout-wide-avenues",
    "Measure the 1021 no-forced-actions planner on a simple 10-strip layout with wide vertical avenues.",
  );
}

const variants = [
  ["2026-07-02-solver-1024-clean-floor-no-late-priority.py", cleanFloorNoLatePriority],
  ["2026-07-02-solver-1024-clean-floor-public-configs.py", cleanFloorPublicConfigs],
  ["2026-07-02-solver-1024-clean-floor-public-jitter.py", cleanFloorPublicJitter],
  ["2026-07-02-solver-1024-clean-floor-public-seed-configs.py", cleanFloorPublicSeedConfigs],
  ["2026-07-02-solver-1024-clean-planner-floor.py", cleanPlannerFloor],
  ["2026-07-02-solver-1024-no-forced-layout-canonical-racks.py", noForcedLayoutCanonicalRacks],
  ["2026-07-02-solver-1024-no-forced-layout-wide-avenues.py", noForcedLayoutWideAvenues],
  ["2026-07-02-solver-1024-no-forced-actions.py", noForcedActions],
  ["2026-07-02-solver-1024-no-pickup-side-retarget.py", noPickupSideRetarget],
  ["2026-07-02-solver-1024-no-robot-boosts.py", noRobotBoosts],
  ["2026-07-02-solver-1024-no-stayer-horizon-tuning.py", noStayerHorizonTuning],
];

async function main() {
  const source = await readFile(sourcePath, "utf8");
  const written = [];

  await mkdir(outputDir, { recursive: true });

  for (const [filename, build] of variants) {
    const outputPath = path.join(outputDir, filename);
    const variantSource = `${build(source).trimEnd()}\n`;
    await writeFile(outputPath, variantSource, "utf8");
    written.push(path.relative(rootDir, outputPath));
  }

  const metadataPath = path.join(outputDir, "2026-07-02-solver-1024-ablation-manifest.json");
  await writeFile(
    metadataPath,
    `${JSON.stringify(
      {
        baseline: "solutions/ours/2026-07-02-solver-1024.py",
        generated_on: "2026-07-03",
        variants: written,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  written.push(path.relative(rootDir, metadataPath));

  for (const file of written) {
    console.log(`wrote ${file}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
