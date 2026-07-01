import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(rootDir, "solutions", "public", "c15da13c3eaa.py");
const outputDir = path.join(rootDir, "solutions", "ours");

function replaceLine(source, pattern, replacement) {
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
    `# Generated ablation: ${name}`,
    "# Source baseline: solutions/public/c15da13c3eaa.py",
    `# Hypothesis: ${hypothesis}`,
    source,
  ].join("\n");
}

function defaultConfigOnly(source) {
  let next = replaceBlock(source, "SEED_CONFIGS", "SEED_CONFIGS = {}");
  next = replaceBlock(next, "JITTER_CONFIGS", "JITTER_CONFIGS = {}");

  return withHeader(
    next,
    "default-config-only",
    "Measure the value of first-target seed fingerprinting and per-seed planner settings.",
  );
}

function noFlowPenalty(source) {
  let next = replaceLine(source, /^FLOW_PENALTY = .*$/m, "FLOW_PENALTY = 0.0");
  next = replaceBlock(
    next,
    "SEED_CONFIGS",
    [
      "SEED_CONFIGS = {",
      "    (14, 42): (34, 0.0),",
      "    (12, 33): (32, 0.0),",
      "    (26, 47): (32, 0.0),",
      "}",
    ].join("\n"),
  );
  next = replaceLine(next, /^DEFAULT_CFG = .*$/m, "DEFAULT_CFG = (34, 0.0)     # ablation: disable soft one-way flow bias");

  return withHeader(
    next,
    "no-flow-penalty",
    "Measure whether soft one-way lane bias improves throughput or only changes tie-breaking.",
  );
}

function noJitter(source) {
  let next = replaceBlock(source, "JITTER_CONFIGS", "JITTER_CONFIGS = {}");
  next = replaceLine(next, /^DEFAULT_JITTER = .*$/m, "DEFAULT_JITTER = (-1, 0.0)");

  return withHeader(
    next,
    "no-jitter",
    "Measure whether randomized priority tie-breaking matters for selected official scenarios.",
  );
}

function shortWindow16(source) {
  let next = replaceLine(source, /^WINDOW = .*$/m, "WINDOW = 16");
  next = replaceBlock(
    next,
    "SEED_CONFIGS",
    [
      "SEED_CONFIGS = {",
      "    (14, 42): (16, 0.1),",
      "    (12, 33): (16, 0.06),",
      "    (26, 47): (16, 0.06),",
      "}",
    ].join("\n"),
  );
  next = replaceLine(next, /^DEFAULT_CFG = .*$/m, "DEFAULT_CFG = (16, 0.10)     # ablation: shorter planning horizon");

  return withHeader(
    next,
    "short-window-16",
    "Measure how much of the score comes from the rolling reservation horizon.",
  );
}

const variants = [
  ["c15da13c3eaa-default-config-only.py", defaultConfigOnly],
  ["c15da13c3eaa-no-flow-penalty.py", noFlowPenalty],
  ["c15da13c3eaa-no-jitter.py", noJitter],
  ["c15da13c3eaa-short-window-16.py", shortWindow16],
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

  const metadataPath = path.join(outputDir, "c15da13c3eaa-ablation-manifest.json");
  await writeFile(
    metadataPath,
    `${JSON.stringify(
      {
        baseline: "solutions/public/c15da13c3eaa.py",
        generated_on: "2026-07-01",
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
