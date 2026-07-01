import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

function lineForIndex(source, index) {
  return source.slice(0, index).split("\n").length;
}

function collectMatches(source, pattern, group = 1) {
  return Array.from(source.matchAll(pattern), (match) => match[group]).filter(Boolean);
}

function evidence(source, pattern) {
  const match = pattern.exec(source);

  if (!match) {
    return null;
  }

  return {
    line: lineForIndex(source, match.index ?? 0),
    text: match[0].split("\n")[0].trim(),
  };
}

function feature(source, label, pattern, whyItMatters) {
  const found = evidence(source, pattern);

  return {
    evidence: found,
    label,
    present: Boolean(found),
    why_it_matters: whyItMatters,
  };
}

function createLayoutSlice(source) {
  const start = source.indexOf("def create_layout");

  if (start === -1) {
    return "";
  }

  const nextDef = source.indexOf("\ndef ", start + 1);
  const nextClass = source.indexOf("\nclass ", start + 1);
  const candidates = [nextDef, nextClass].filter((index) => index > start);
  const end = candidates.length > 0 ? Math.min(...candidates) : source.length;

  return source.slice(start, end);
}

function topLevelAssignments(source) {
  const assignments = [];

  for (const match of source.matchAll(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$/gm)) {
    assignments.push({
      line: lineForIndex(source, match.index ?? 0),
      name: match[1],
      value: match[2].trim(),
    });
  }

  return assignments;
}

function mutableGlobalNames(assignments) {
  return assignments
    .filter((assignment) => {
      return /^_/.test(assignment.name)
        || /^[a-z]/.test(assignment.name)
        || /\{\}|\[\]|set\(|dict\(|_Brain\(|random\.Random/.test(assignment.value);
    })
    .map((assignment) => assignment.name);
}

function analyze(source, filePath) {
  const layoutSource = createLayoutSlice(source);
  const assignments = topLevelAssignments(source);
  const features = [
    feature(
      source,
      "module-global shared brain",
      /^_BRAIN\s*=\s*_Brain\(/m,
      "Turns repeated act() calls into one stateful controller instead of independent memoryless robots.",
    ),
    feature(
      source,
      "uses all robot positions",
      /\ball_robot_positions\b/,
      "Allows every call to plan around the full fleet occupancy.",
    ),
    feature(
      source,
      "per-robot state maps",
      /\bbrain\.(?:pos|base|entry|target|carrying|wait_streak)\b/,
      "Keeps hidden state for robots whose current call is not being processed.",
    ),
    feature(
      source,
      "seed fingerprint configuration",
      /\b(?:SEED_CONFIGS|JITTER_CONFIGS|_select_config)\b/,
      "Uses early observable demand as a scenario signature and changes planner parameters.",
    ),
    feature(
      source,
      "rolling planning window",
      /\bWINDOW\s*=/,
      "Plans multiple future ticks rather than choosing only the next shortest-path move.",
    ),
    feature(
      source,
      "A* path planner",
      /^def _astar\b/m,
      "Searches time-expanded paths against reservations.",
    ),
    feature(
      source,
      "cell reservations",
      /\bcell_res\b/,
      "Prevents two robots from occupying the same future cell.",
    ),
    feature(
      source,
      "edge reservations",
      /\bedge_res\b/,
      "Prevents head-on swaps, a common multi-agent pathfinding failure.",
    ),
    feature(
      source,
      "BFS distance fields",
      /\b(?:dist_cache|def _bfs|shelf_field|base_field)\b/,
      "Caches distance-to-goal heuristics for many repeated robot planning calls.",
    ),
    feature(
      source,
      "soft traffic flow penalty",
      /\bFLOW_PENALTY\b|^def _flow\b/m,
      "Biases movement into lane-like patterns without making paths impossible.",
    ),
    feature(
      source,
      "priority jitter",
      /\bJITTER\b|random\.Random|\.uniform\(/,
      "Breaks deterministic priority ties differently for selected scenarios.",
    ),
    feature(
      source,
      "greedy fallback step",
      /^def _coordinated_step\b/m,
      "Keeps robots moving when the main reservation planner cannot provide a move.",
    ),
    feature(
      source,
      "target locking",
      /\blocked\b|target not in brain\.locked/,
      "Avoids multiple robots trying to pick a shelf already being carried.",
    ),
    feature(
      source,
      "exception fallback to wait",
      /except Exception:\s*return Action\.WAIT/,
      "Keeps the submission valid under unexpected local errors.",
    ),
  ];

  return {
    assignments: assignments.slice(0, 40),
    bytes: Buffer.byteLength(source),
    classes: collectMatches(source, /^class\s+([A-Za-z_][A-Za-z0-9_]*)/gm),
    features,
    file: filePath,
    functions: collectMatches(source, /^def\s+([A-Za-z_][A-Za-z0-9_]*)/gm),
    global_statements: collectMatches(source, /^\s+global\s+(.+)$/gm),
    imports: collectMatches(source, /^(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))/gm, 1)
      .concat(collectMatches(source, /^import\s+([A-Za-z0-9_.]+)/gm)),
    lines: source.split("\n").length - 1,
    mutable_global_names: mutableGlobalNames(assignments),
    sha256: createHash("sha256").update(source).digest("hex"),
    shelf_coordinate_pairs_in_create_layout: collectMatches(layoutSource, /\[\s*(\d+)\s*,\s*\d+\s*\]/g).length,
    suggested_ablation_targets: [
      "replace module-global _BRAIN with per-call memoryless routing",
      "force DEFAULT_CFG and DEFAULT_JITTER for every seed signature",
      "set FLOW_PENALTY = 0.0",
      "remove edge_res checks while keeping cell reservations",
      "shorten WINDOW and NODE_CAP to quantify planner depth",
      "run the same planner on canonical rack-block layout",
    ],
  };
}

function printHuman(report) {
  console.log(`${report.file}`);
  console.log(`sha256: ${report.sha256}`);
  console.log(`size: ${report.lines} lines, ${report.bytes} bytes`);
  console.log(`imports: ${report.imports.join(", ")}`);
  console.log(`classes: ${report.classes.join(", ")}`);
  console.log(`functions: ${report.functions.length}`);
  console.log(`create_layout coordinate pairs: ${report.shelf_coordinate_pairs_in_create_layout}`);
  console.log(`mutable globals: ${report.mutable_global_names.join(", ")}`);
  console.log("");
  console.table(
    report.features.map((item) => ({
      feature: item.label,
      present: item.present,
      evidence: item.evidence ? `line ${item.evidence.line}: ${item.evidence.text}` : "",
    })),
  );
  console.log("Suggested ablations:");

  for (const target of report.suggested_ablation_targets) {
    console.log(`- ${target}`);
  }
}

async function main() {
  const filePath = process.argv.find((arg) => arg.endsWith(".py"));

  if (!filePath) {
    console.error("Usage: npm run analyze:policy -- <policy.py> [--json]");
    process.exitCode = 1;
    return;
  }

  const source = await readFile(filePath, "utf8");
  const report = analyze(source, path.normalize(filePath));

  if (process.argv.includes("--json")) {
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  printHuman(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
