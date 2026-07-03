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

function noEdgeReservations(source) {
  let next = replaceLine(source, /    cell_res=\{\}; edge_res=\{\}/, "    cell_res={}");
  next = replaceLine(
    next,
    /        path=_astar\(world,start,goal_field\[rid\],cell_res,edge_res\)/,
    "        path=_astar(world,start,goal_field[rid],cell_res)",
  );
  next = replaceLine(
    next,
    /        for i in range\(min\(last,WINDOW\)\): edge_res\[\(i,path\[i\],path\[i\+1\]\)\]=rid\n/,
    "",
  );
  next = replaceLine(
    next,
    /def _astar\(world, start, field, cell_res, edge_res\):/,
    "def _astar(world, start, field, cell_res):",
  );
  next = replaceLine(
    next,
    /            if within and \(\(nt,m\) in cell_res or \(t,m,n\) in edge_res\): continue/,
    "            if within and (nt,m) in cell_res: continue",
  );

  return withHeader(
    next,
    "no-edge-reservations",
    "Measure whether rolling edge-swap reservations add throughput beyond shared state, cell reservations, flow bias, seed config, and first-step conflict resolution.",
  );
}

function noSharedBrain(source) {
  const pattern = /^_BRAIN=_Brain\(\)\n\n[\s\S]*?^def _plan/m;
  const replacement = [
    "# Ablation: do not keep a module-global _BRAIN.",
    "# Each act() call builds a fresh local brain. Other robots are visible only",
    "# as current positions from observation.all_robot_positions, with no remembered",
    "# targets, carrying state, wait streaks, or future plan from previous calls.",
    "def act(observation):",
    "    try: return _act_memoryless(observation)",
    "    except Exception: return Action.WAIT",
    "",
    "def _act_memoryless(obs):",
    "    brain=_Brain()",
    "    global WINDOW, FLOW_PENALTY, RNG_SEED, JITTER, _RNG",
    "    WINDOW, FLOW_PENALTY = DEFAULT_CFG",
    "    RNG_SEED, JITTER = DEFAULT_JITTER",
    "    _RNG = None",
    "    brain.world = _World(obs.grid)",
    "    brain.cur_tick = obs.tick",
    "    try: _plan(brain,obs)",
    "    except Exception: brain.moves={}",
    "    return _action_for(brain,obs)",
    "",
    "def _plan",
  ].join("\n");

  if (!pattern.test(source)) {
    throw new Error("Could not find _BRAIN/act/_act block");
  }

  return withHeader(
    source.replace(pattern, replacement),
    "no-shared-brain",
    "Measure how much score remains when act() cannot retain cross-robot or cross-tick module-global planner state.",
  );
}

function noSharedBrainCachedWorld(source) {
  const pattern = /^_BRAIN=_Brain\(\)\n\n[\s\S]*?^def _plan/m;
  const replacement = [
    "# Ablation: do not keep module-global robot-planner state.",
    "# This keeps only a static world/distance cache so the run measures loss of",
    "# cross-robot/cross-tick coordination rather than repeated grid preprocessing.",
    "_WORLD_CACHE = None",
    "_WORLD_CACHE_FLOW = None",
    "",
    "def _memoryless_world(grid):",
    "    global _WORLD_CACHE, _WORLD_CACHE_FLOW",
    "    flow_key = FLOW_PENALTY",
    "    if _WORLD_CACHE is None or _WORLD_CACHE_FLOW != flow_key:",
    "        _WORLD_CACHE = _World(grid)",
    "        _WORLD_CACHE_FLOW = flow_key",
    "    return _WORLD_CACHE",
    "",
    "def act(observation):",
    "    try: return _act_memoryless_cached_world(observation)",
    "    except Exception: return Action.WAIT",
    "",
    "def _act_memoryless_cached_world(obs):",
    "    brain=_Brain()",
    "    global WINDOW, FLOW_PENALTY, RNG_SEED, JITTER, _RNG",
    "    WINDOW, FLOW_PENALTY = DEFAULT_CFG",
    "    RNG_SEED, JITTER = DEFAULT_JITTER",
    "    _RNG = None",
    "    brain.world = _memoryless_world(obs.grid)",
    "    brain.cur_tick = obs.tick",
    "    try: _plan(brain,obs)",
    "    except Exception: brain.moves={}",
    "    return _action_for(brain,obs)",
    "",
    "def _plan",
  ].join("\n");

  if (!pattern.test(source)) {
    throw new Error("Could not find _BRAIN/act/_act block");
  }

  return withHeader(
    source.replace(pattern, replacement),
    "no-shared-brain-cached-world",
    "Measure loss from removing persistent robot-planner state while keeping static map and distance caching.",
  );
}

const variants = [
  ["c15da13c3eaa-default-config-only.py", defaultConfigOnly],
  ["c15da13c3eaa-no-edge-reservations.py", noEdgeReservations],
  ["c15da13c3eaa-no-flow-penalty.py", noFlowPenalty],
  ["c15da13c3eaa-no-jitter.py", noJitter],
  ["c15da13c3eaa-no-shared-brain.py", noSharedBrain],
  ["c15da13c3eaa-no-shared-brain-cached-world.py", noSharedBrainCachedWorld],
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
