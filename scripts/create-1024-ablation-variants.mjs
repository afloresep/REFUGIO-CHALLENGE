import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(rootDir, "solutions", "ours", "2026-07-02-solver-1024.py");
const outputDir = path.join(rootDir, "solutions", "ours");

function replaceOnce(source, pattern, replacement) {
  if (!pattern.test(source)) {
    throw new Error(`Could not find pattern ${pattern}`);
  }

  return source.replace(pattern, replacement);
}

function replaceBlock(source, name, replacement) {
  const pattern = new RegExp(`^${name} = \\{[\\s\\S]*?\\n\\}`, "m");

  if (!pattern.test(source)) {
    throw new Error(`Could not find block ${name}`);
  }

  return source.replace(pattern, replacement);
}

function withHeader(source, name, hypothesis) {
  return [
    `# Generated 1024 ablation: ${name}`,
    "# Source baseline: solutions/ours/2026-07-02-solver-1024.py",
    `# Hypothesis: ${hypothesis}`,
    source,
  ].join("\n");
}

function noForcedActions(source) {
  const next = replaceOnce(
    source,
    /    forced=FORCED_ACTIONS\.get\(\(ACTIVE_SCENARIO,rid,brain\.cur_tick,pos,carrying\)\)/,
    "    forced=None",
  );

  return withHeader(
    next,
    "no-forced-actions",
    "Measure how much of 1024 comes from audited per-scenario action overrides.",
  );
}

function noRobotBoosts(source) {
  const next = replaceBlock(source, "ROBOT_BOOSTS", "ROBOT_BOOSTS = {}");

  return withHeader(
    next,
    "no-robot-boosts",
    "Measure how much of 1024 comes from late per-robot priority boosts.",
  );
}

function noPickupSideRetarget(source) {
  let next = replaceBlock(source, "PICKUP_SIDE_CONFIGS", "PICKUP_SIDE_CONFIGS = {}");
  next = replaceBlock(next, "PICKUP_SIDE_FINISHABLE_CONFIGS", "PICKUP_SIDE_FINISHABLE_CONFIGS = {}");

  return withHeader(
    next,
    "no-pickup-side-retarget",
    "Measure how much of 1024 comes from late pickup-side selection instead of generic shelf adjacency.",
  );
}

function noStayerHorizonTuning(source) {
  const next = replaceBlock(source, "STAYER_CONFIGS", "STAYER_CONFIGS = {}");

  return withHeader(
    next,
    "no-stayer-horizon-tuning",
    "Measure how much of 1024 comes from scenario-specific reservation horizon for robots already at a goal.",
  );
}

const variants = [
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
