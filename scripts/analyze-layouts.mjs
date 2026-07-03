import { readFile } from "node:fs/promises";

const GRID = 52;
const WALK_MIN = 1;
const WALK_MAX = 50;

const defaultFiles = [
  "solutions/public/c15da13c3eaa.py",
  "solutions/ours/c15da13c3eaa-layout-canonical-racks.py",
  "solutions/ours/c15da13c3eaa-layout-wide-avenues.py",
];

function cellKey([x, y]) {
  return `${x},${y}`;
}

function node([x, y]) {
  return y * GRID + x;
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
  return x >= WALK_MIN && x <= WALK_MAX && y >= WALK_MIN && y <= WALK_MAX;
}

function baseEntries() {
  const entries = [];
  for (let x = 3; x < 50; x += 2) entries.push([x, 1]);
  for (let x = 2; x < 49; x += 2) entries.push([x, 50]);
  for (let y = 2; y < 49; y += 2) entries.push([1, y]);
  for (let y = 3; y < 50; y += 2) entries.push([50, y]);
  return entries;
}

function extractShelves(source, file) {
  const marker = "'shelves': ";
  const markerIndex = source.indexOf(marker);
  if (markerIndex === -1) {
    throw new Error(`${file}: could not find create_layout shelves`);
  }

  const start = source.indexOf("[", markerIndex);
  let depth = 0;
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) {
        return JSON.parse(source.slice(start, index + 1));
      }
    }
  }

  throw new Error(`${file}: unterminated shelves list`);
}

function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[index];
}

function round(value, digits = 2) {
  return Number(value.toFixed(digits));
}

function bfsFromBaseEntries(shelfSet) {
  const dist = new Int32Array(GRID * GRID).fill(-1);
  const queue = [];

  for (const entry of baseEntries()) {
    if (shelfSet.has(cellKey(entry))) continue;
    dist[node(entry)] = 0;
    queue.push(entry);
  }

  for (let index = 0; index < queue.length; index += 1) {
    const current = queue[index];
    const nextDistance = dist[node(current)] + 1;
    for (const neighbor of neighbors(current)) {
      if (!inWalkableArea(neighbor)) continue;
      if (shelfSet.has(cellKey(neighbor))) continue;
      const neighborNode = node(neighbor);
      if (dist[neighborNode] !== -1) continue;
      dist[neighborNode] = nextDistance;
      queue.push(neighbor);
    }
  }

  return dist;
}

function maxEmptyRun(shelfSet, fixed, axis) {
  let best = 0;
  let current = 0;
  for (let moving = WALK_MIN; moving <= WALK_MAX; moving += 1) {
    const cell = axis === "x" ? [moving, fixed] : [fixed, moving];
    if (shelfSet.has(cellKey(cell))) {
      current = 0;
    } else {
      current += 1;
      best = Math.max(best, current);
    }
  }
  return best;
}

function analyzeShelves(file, shelves) {
  const shelfSet = new Set(shelves.map(cellKey));
  const dist = bfsFromBaseEntries(shelfSet);
  const accessCounts = [];
  const nearestAccessDistances = [];
  const allAccessDistances = [];
  const walkableDegrees = [];
  let adjacentShelfPairs = 0;

  for (const shelf of shelves) {
    const access = neighbors(shelf).filter((neighbor) => inWalkableArea(neighbor) && !shelfSet.has(cellKey(neighbor)));
    accessCounts.push(access.length);
    for (const neighbor of neighbors(shelf)) {
      if (inWalkableArea(neighbor) && shelfSet.has(cellKey(neighbor)) && node(neighbor) > node(shelf)) {
        adjacentShelfPairs += 1;
      }
    }

    const distances = access.map((cell) => dist[node(cell)]).filter((distance) => distance >= 0);
    if (distances.length === 0) {
      throw new Error(`${file}: shelf has no reachable pickup access: ${shelf}`);
    }
    nearestAccessDistances.push(Math.min(...distances));
    allAccessDistances.push(...distances);
  }

  for (let y = WALK_MIN; y <= WALK_MAX; y += 1) {
    for (let x = WALK_MIN; x <= WALK_MAX; x += 1) {
      const cell = [x, y];
      if (shelfSet.has(cellKey(cell))) continue;
      walkableDegrees.push(
        neighbors(cell).filter((neighbor) => inWalkableArea(neighbor) && !shelfSet.has(cellKey(neighbor))).length,
      );
    }
  }

  const verticalRuns = [];
  const horizontalRuns = [];
  for (let i = WALK_MIN; i <= WALK_MAX; i += 1) {
    verticalRuns.push(maxEmptyRun(shelfSet, i, "y"));
    horizontalRuns.push(maxEmptyRun(shelfSet, i, "x"));
  }

  return {
    file,
    shelves: shelves.length,
    walkable: walkableDegrees.length,
    mean_access_cells: round(mean(accessCounts)),
    min_access_cells: Math.min(...accessCounts),
    one_access_shelves: accessCounts.filter((count) => count === 1).length,
    mean_nearest_base_dist: round(mean(nearestAccessDistances)),
    p90_nearest_base_dist: percentile(nearestAccessDistances, 90),
    mean_access_base_dist: round(mean(allAccessDistances)),
    p90_access_base_dist: percentile(allAccessDistances, 90),
    adjacent_shelf_pairs: adjacentShelfPairs,
    mean_walkable_degree: round(mean(walkableDegrees)),
    dead_ends: walkableDegrees.filter((degree) => degree <= 1).length,
    junctions: walkableDegrees.filter((degree) => degree >= 3).length,
    full_empty_cols: verticalRuns.filter((run) => run === 50).length,
    full_empty_rows: horizontalRuns.filter((run) => run === 50).length,
    long_empty_cols: verticalRuns.filter((run) => run >= 40).length,
    long_empty_rows: horizontalRuns.filter((run) => run >= 40).length,
  };
}

async function main() {
  const json = process.argv.includes("--json");
  const files = process.argv.filter((arg) => !arg.startsWith("--")).slice(2);
  const targets = files.length > 0 ? files : defaultFiles;
  const summaries = [];

  for (const file of targets) {
    const source = await readFile(file, "utf8");
    summaries.push(analyzeShelves(file, extractShelves(source, file)));
  }

  if (json) {
    console.log(JSON.stringify(summaries, null, 2));
  } else {
    console.table(
      summaries.map((summary) => ({
        file: summary.file,
        shelves: summary.shelves,
        mean_access: summary.mean_access_cells,
        one_access: summary.one_access_shelves,
        mean_nearest_base_dist: summary.mean_nearest_base_dist,
        p90_nearest_base_dist: summary.p90_nearest_base_dist,
        dead_ends: summary.dead_ends,
        junctions: summary.junctions,
        full_empty_cols: summary.full_empty_cols,
        full_empty_rows: summary.full_empty_rows,
      })),
    );
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
