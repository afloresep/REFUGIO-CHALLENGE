import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const replayDir = path.join(rootDir, "public", "replays");

const SIDES = ["top", "bottom", "left", "right"];

function sideForRobotId(id) {
  if (id < 24) return "top";
  if (id < 48) return "bottom";
  if (id < 72) return "left";
  return "right";
}

function baseEntry([x, y]) {
  if (x === 0) return [1, y];
  if (x === 51) return [50, y];
  if (y === 0) return [x, 1];
  return [x, 50];
}

function key([x, y]) {
  return `${x},${y}`;
}

function percentile(values, p) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index];
}

function mean(values) {
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function round(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return Number(value.toFixed(digits));
}

function passable(layout, x, y) {
  return layout.grid[y]?.[x] === layout.cell_encoding.empty;
}

function neighbors([x, y]) {
  return [
    [x + 1, y],
    [x - 1, y],
    [x, y + 1],
    [x, y - 1],
  ];
}

function multiSourceBfs(layout, sources) {
  const queue = [];
  const distance = new Map();

  for (const source of sources) {
    if (!passable(layout, source[0], source[1])) continue;
    const sourceKey = key(source);
    if (distance.has(sourceKey)) continue;
    distance.set(sourceKey, 0);
    queue.push(source);
  }

  for (let head = 0; head < queue.length; head += 1) {
    const cell = queue[head];
    const current = distance.get(key(cell));

    for (const next of neighbors(cell)) {
      const [x, y] = next;
      if (x < 1 || x > 50 || y < 1 || y > 50) continue;
      if (!passable(layout, x, y)) continue;
      const nextKey = key(next);
      if (distance.has(nextKey)) continue;
      distance.set(nextKey, current + 1);
      queue.push(next);
    }
  }

  return distance;
}

function layoutMetrics(layout) {
  const baseEntries = layout.bases.map((base) => baseEntry(base.position));
  const distanceFromBaseEntry = multiSourceBfs(layout, baseEntries);
  const shelfCells = layout.shelf_cells ?? [];
  const shelfAccessDistances = [];
  const accessCounts = [];

  for (const shelf of shelfCells) {
    const access = neighbors(shelf).filter(([x, y]) => passable(layout, x, y));
    accessCounts.push(access.length);

    const distances = access
      .map((cell) => distanceFromBaseEntry.get(key(cell)))
      .filter((value) => value !== undefined);

    if (distances.length > 0) {
      shelfAccessDistances.push(Math.min(...distances));
    }
  }

  let interiorEmpty = 0;
  for (let y = 1; y <= 50; y += 1) {
    for (let x = 1; x <= 50; x += 1) {
      if (passable(layout, x, y)) interiorEmpty += 1;
    }
  }

  return {
    base_entry_count: baseEntries.length,
    interior_empty: interiorEmpty,
    mean_access_cells_per_shelf: round(mean(accessCounts)),
    mean_shelf_access_distance_to_base_entry: round(mean(shelfAccessDistances)),
    p90_shelf_access_distance_to_base_entry: percentile(shelfAccessDistances, 90),
    reachable_empty_from_base_entries: distanceFromBaseEntry.size,
    shelf_count: shelfCells.length,
  };
}

function deliveryEvents(frames) {
  const events = [];

  for (let index = 1; index < frames.length; index += 1) {
    const previous = new Map(frames[index - 1].robots.map((robot) => [robot.id, robot.deliveries]));
    let deliveries = 0;

    for (const robot of frames[index].robots) {
      deliveries += Math.max(0, robot.deliveries - (previous.get(robot.id) ?? 0));
    }

    if (deliveries > 0) {
      events.push({ tick: frames[index].tick, deliveries });
    }
  }

  return events;
}

function robotDeliveryStats(frame) {
  const deliveries = frame.robots.map((robot) => robot.deliveries);
  const bySide = Object.fromEntries(SIDES.map((side) => [side, 0]));

  for (const robot of frame.robots) {
    bySide[sideForRobotId(robot.id)] += robot.deliveries;
  }

  const sorted = [...frame.robots].sort((a, b) => b.deliveries - a.deliveries || a.id - b.id);

  return {
    by_side: bySide,
    max_robot_deliveries: sorted[0]?.deliveries ?? 0,
    mean_robot_deliveries: round(mean(deliveries)),
    min_robot_deliveries: Math.min(...deliveries),
    top_robots: sorted.slice(0, 5).map((robot) => ({
      id: robot.id,
      side: sideForRobotId(robot.id),
      deliveries: robot.deliveries,
    })),
  };
}

function summarizeReplay(jobId, replay) {
  const finalFrame = replay.frames.at(-1);
  const events = deliveryEvents(replay.frames);
  const eventCounts = events.map((event) => event.deliveries);
  const finalStats = robotDeliveryStats(finalFrame);
  const carryingAtEnd = finalFrame.robots.filter((robot) => robot.carrying).length;

  return {
    job_id: jobId,
    name: replay.name ?? null,
    replay_deliveries: replay.total_deliveries,
    ticks: replay.ticks,
    frames: replay.frames.length,
    first_delivery_tick: events[0]?.tick ?? null,
    last_delivery_tick: events.at(-1)?.tick ?? null,
    peak_deliveries_in_one_tick: eventCounts.length > 0 ? Math.max(...eventCounts) : 0,
    delivery_ticks: events.length,
    carrying_at_end: carryingAtEnd,
    ...finalStats,
    layout: layoutMetrics(replay.layout),
  };
}

async function main() {
  const files = (await readdir(replayDir)).filter((file) => file.endsWith(".json")).sort();
  const summaries = [];

  for (const file of files) {
    const jobId = file.replace(/\.json$/, "");
    const replay = JSON.parse(await readFile(path.join(replayDir, file), "utf8"));
    summaries.push(summarizeReplay(jobId, replay));
  }

  if (process.argv.includes("--json")) {
    console.log(JSON.stringify(summaries, null, 2));
    return;
  }

  console.table(
    summaries.map((summary) => ({
      job: summary.job_id,
      replay_deliveries: summary.replay_deliveries,
      first_drop: summary.first_delivery_tick,
      last_drop: summary.last_delivery_tick,
      active_drop_ticks: summary.delivery_ticks,
      peak_drop_tick: summary.peak_deliveries_in_one_tick,
      carrying_at_end: summary.carrying_at_end,
      mean_robot: summary.mean_robot_deliveries,
      min_robot: summary.min_robot_deliveries,
      max_robot: summary.max_robot_deliveries,
      mean_access_dist: summary.layout.mean_shelf_access_distance_to_base_entry,
      p90_access_dist: summary.layout.p90_shelf_access_distance_to_base_entry,
    })),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
