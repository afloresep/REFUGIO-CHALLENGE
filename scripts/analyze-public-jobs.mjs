import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

function usage() {
  console.error([
    "Usage: node scripts/analyze-public-jobs.mjs --jobs-html <file> --replay-html-dir <dir> [options]",
    "",
    "Options:",
    "  --code-dir <dir>          Directory with <job-id>.py files for optional code-copy stats.",
    "  --summary-out <file>      Defaults to outputs/public-site-analysis/summary.json.",
    "  --figure-dir <dir>        Defaults to public/figures.",
  ].join("\n"));
}

function argValue(args, name) {
  const index = args.indexOf(name);
  return index === -1 ? undefined : args[index + 1];
}

function cleanHtml(value) {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function parseJobsHtml(html) {
  const body = html.match(/<tbody>([\s\S]*?)<\/tbody>/)?.[1];
  if (!body) {
    throw new Error("Could not find jobs table <tbody>.");
  }

  return [...body.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map((rowMatch) => {
    const cells = [...rowMatch[1].matchAll(/<td>([\s\S]*?)<\/td>/g)].map((cellMatch) => cleanHtml(cellMatch[1]));
    return {
      job: cells[0],
      team: cells[1],
      status: cells[2],
      points: cells[3] === "-" ? null : Number(cells[3].replace(/,/g, "")),
      deliveries: cells[4] === "-" ? null : Number(cells[4]),
      runtime_seconds: cells[5] === "-" ? null : Number(cells[5].replace(/s$/, "")),
      submitted: cells[6],
      committed: cells[7],
    };
  });
}

function teamNumber(team) {
  const match = String(team).match(/(\d+)$/);
  return match ? Number(match[1]) : null;
}

function shortTeamLabel(team) {
  const number = teamNumber(team);
  return number === null ? String(team) : `T${number}`;
}

function extractArrayAfter(source, marker) {
  const markerIndex = source.indexOf(marker);
  if (markerIndex === -1) {
    throw new Error(`Marker not found: ${marker}`);
  }

  const start = source.indexOf("[", markerIndex + marker.length);
  let depth = 0;
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start, index + 1);
      }
    }
  }

  throw new Error(`Unterminated array after ${marker}`);
}

function layoutHash(shelves) {
  const sorted = [...shelves].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  return createHash("sha256").update(JSON.stringify(sorted)).digest("hex");
}

function groupBy(values, keyFn) {
  const groups = new Map();
  for (const value of values) {
    const key = keyFn(value);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(value);
  }
  return groups;
}

function frontierChanges(rows) {
  const successful = rows
    .filter((row) => row.status === "succeeded")
    .sort((a, b) => Date.parse(a.submitted) - Date.parse(b.submitted));
  let frontier = 0;
  const changes = [];

  for (const row of successful) {
    if (row.deliveries > frontier) {
      changes.push({ ...row, previous_frontier: frontier, frontier_delta: row.deliveries - frontier });
      frontier = row.deliveries;
    }
  }

  return changes;
}

function teamSummaries(rows) {
  return [...groupBy(rows.filter((row) => row.status === "succeeded"), (row) => row.team)]
    .map(([team, teamRows]) => {
      const ordered = [...teamRows].sort((a, b) => Date.parse(a.submitted) - Date.parse(b.submitted));
      const best = ordered.reduce((winner, row) => (row.deliveries > winner.deliveries ? row : winner), ordered[0]);
      return {
        team,
        submissions: ordered.length,
        first_submitted: ordered[0].submitted,
        last_submitted: ordered.at(-1).submitted,
        best_deliveries: best.deliveries,
        best_job: best.job,
        final_deliveries: ordered.at(-1).deliveries,
        points: ordered.reduce((sum, row) => sum + (row.points ?? 0), 0),
        scores: ordered.map((row) => row.deliveries),
      };
    })
    .sort((a, b) => b.best_deliveries - a.best_deliveries || a.team.localeCompare(b.team));
}

async function addReplayLayouts(rows, replayHtmlDir) {
  const successful = rows.filter((row) => row.status === "succeeded");

  for (const row of successful) {
    const replayPath = path.join(replayHtmlDir, `${row.job}.html`);
    const html = await readFile(replayPath, "utf8");
    const raw = extractArrayAfter(html, "shelf_cells\\\":");
    const shelves = JSON.parse(raw);
    row.replay_layout_hash = layoutHash(shelves);
    row.replay_shelf_count = shelves.length;
  }
}

async function addCodeAnalysis(rows, codeDir) {
  if (!codeDir) return;

  const files = new Set(await readdir(codeDir));
  for (const row of rows.filter((item) => item.status === "succeeded")) {
    const file = `${row.job}.py`;
    if (!files.has(file)) continue;
    const source = await readFile(path.join(codeDir, file), "utf8");
    row.code_sha = createHash("sha256").update(source).digest("hex");
    row.code_lines = source.split("\n").length - 1;
    row.has_brain = /_BRAIN|class\s+.*Brain|brain\./.test(source);
    row.has_astar = /def\s+_?astar|heapq/.test(source);
    row.has_edge_reservations = /edge_res|edge_reserv|reserved_edges/.test(source);
    row.has_seed_config = /SEED_CONFIGS|JITTER_CONFIGS|_select_config|first target|starting scenario/.test(source);
    row.has_literal_layout = source.includes("'shelves': [[") || source.includes('"shelves": [[');
  }
}

function summarizeLayouts(rows) {
  const groups = [...groupBy(rows.filter((row) => row.replay_layout_hash), (row) => row.replay_layout_hash)]
    .map(([hash, groupRows]) => {
      const ordered = [...groupRows].sort((a, b) => Date.parse(a.submitted) - Date.parse(b.submitted));
      const best = ordered.reduce((winner, row) => (row.deliveries > winner.deliveries ? row : winner), ordered[0]);
      return {
        hash,
        jobs: ordered.length,
        teams: [...new Set(ordered.map((row) => row.team))].sort(),
        first_job: ordered[0].job,
        first_team: ordered[0].team,
        first_submitted: ordered[0].submitted,
        first_deliveries: ordered[0].deliveries,
        best_job: best.job,
        best_team: best.team,
        best_deliveries: best.deliveries,
      };
    })
    .sort((a, b) => b.jobs - a.jobs || b.best_deliveries - a.best_deliveries);

  const byHash = new Map(groups.map((group) => [group.hash, group]));
  for (const row of rows) {
    if (row.replay_layout_hash) row.layout_group = classifyLayoutGroup(byHash.get(row.replay_layout_hash));
  }

  return groups;
}

function summarizeTransitions(rows) {
  const transitions = [];
  for (const [team, teamRows] of groupBy(rows.filter((row) => row.status === "succeeded"), (row) => row.team)) {
    const ordered = [...teamRows].sort((a, b) => Date.parse(a.submitted) - Date.parse(b.submitted));
    for (let index = 1; index < ordered.length; index += 1) {
      transitions.push({
        team,
        from_job: ordered[index - 1].job,
        to_job: ordered[index].job,
        submitted: ordered[index].submitted,
        layout_changed: ordered[index - 1].replay_layout_hash !== ordered[index].replay_layout_hash,
        delivery_delta: ordered[index].deliveries - ordered[index - 1].deliveries,
        deliveries: ordered[index].deliveries,
      });
    }
  }
  return transitions;
}

function summarizeCode(rows) {
  const successful = rows.filter((row) => row.status === "succeeded" && row.code_sha);
  if (successful.length === 0) return null;
  const codeGroups = [...groupBy(successful, (row) => row.code_sha).values()]
    .map((groupRows) => ({
      jobs: groupRows.length,
      teams: [...new Set(groupRows.map((row) => row.team))].sort(),
      best_deliveries: Math.max(...groupRows.map((row) => row.deliveries)),
      first_job: [...groupRows].sort((a, b) => Date.parse(a.submitted) - Date.parse(b.submitted))[0].job,
    }))
    .sort((a, b) => b.jobs - a.jobs || b.best_deliveries - a.best_deliveries);

  const bands = [
    [">=920", (row) => row.deliveries >= 920],
    ["895-919", (row) => row.deliveries >= 895 && row.deliveries < 920],
    ["850-894", (row) => row.deliveries >= 850 && row.deliveries < 895],
    ["<850", (row) => row.deliveries < 850],
  ].map(([label, predicate]) => {
    const bandRows = successful.filter(predicate);
    return {
      label,
      jobs: bandRows.length,
      has_brain: bandRows.filter((row) => row.has_brain).length,
      has_astar: bandRows.filter((row) => row.has_astar).length,
      has_edge_reservations: bandRows.filter((row) => row.has_edge_reservations).length,
      has_seed_config: bandRows.filter((row) => row.has_seed_config).length,
      has_literal_layout: bandRows.filter((row) => row.has_literal_layout).length,
    };
  });

  return {
    analyzed_jobs: successful.length,
    unique_code_files: codeGroups.length,
    exact_code_copy_groups: codeGroups.filter((group) => group.jobs > 1),
    feature_bands: bands,
  };
}

function classifyLayoutGroup(group) {
  if (!group) return "other";
  if (group.best_deliveries >= 1000) return "1008 unique layout";
  if (group.best_deliveries >= 925) return "930 shared layout";
  if (teamNumber(group.first_team) === 4 && group.best_deliveries >= 907) return "907 shared layout";
  if (group.jobs >= 20) return "common floor layout";
  if (group.jobs >= 5) return "reused layout";
  return "other";
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function makeSvg(width, height, content) {
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    '<rect width="100%" height="100%" fill="#fbfaf7"/>',
    '<style>text{font-family:Inter,Arial,sans-serif;fill:#1f2933}.small{font-size:11px;fill:#65707c}.axis{stroke:#aab3bd;stroke-width:1}.grid{stroke:#e6e1d8;stroke-width:1}.title{font-size:18px;font-weight:700}.label{font-size:12px;font-weight:600}.tick{font-size:10px;fill:#65707c}</style>',
    content,
    "</svg>",
  ].join("\n");
}

function xScale(value, min, max, left, right) {
  return left + ((value - min) / (max - min || 1)) * (right - left);
}

function yScale(value, min, max, top, bottom) {
  return bottom - ((value - min) / (max - min || 1)) * (bottom - top);
}

function timeLabel(ms) {
  return new Date(ms).toISOString().slice(11, 16);
}

function makeFrontierFigure(rows, teams, changes) {
  const successful = rows.filter((row) => row.status === "succeeded");
  const minTime = Math.min(...successful.map((row) => Date.parse(row.submitted)));
  const maxTime = Math.max(...successful.map((row) => Date.parse(row.submitted)));
  const left = { x0: 70, x1: 690, y0: 70, y1: 420 };
  const right = { x0: 790, x1: 1060, y0: 70, y1: 420 };
  const maxScore = 1020;
  const parts = [];

  parts.push('<text x="70" y="35" class="title">REFUGIO frontier and final team spread</text>');
  parts.push('<text x="70" y="55" class="small">86 successful submissions; frontier jumps from 931 to 1008 in the final minute.</text>');

  for (const score of [0, 250, 500, 750, 1000]) {
    const y = yScale(score, 0, maxScore, left.y0, left.y1);
    parts.push(`<line x1="${left.x0}" x2="${left.x1}" y1="${y}" y2="${y}" class="grid"/>`);
    parts.push(`<text x="${left.x0 - 12}" y="${y + 4}" text-anchor="end" class="tick">${score}</text>`);
  }

  parts.push(`<line x1="${left.x0}" x2="${left.x0}" y1="${left.y0}" y2="${left.y1}" class="axis"/>`);
  parts.push(`<line x1="${left.x0}" x2="${left.x1}" y1="${left.y1}" y2="${left.y1}" class="axis"/>`);

  for (const row of successful) {
    const x = xScale(Date.parse(row.submitted), minTime, maxTime, left.x0, left.x1);
    const y = yScale(row.deliveries, 0, maxScore, left.y0, left.y1);
    const fill = row.deliveries >= 1000 ? "#d1495b" : row.deliveries >= 920 ? "#2a6fbb" : "#9aa5b1";
    parts.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.2" fill="${fill}" opacity="0.78"/>`);
  }

  let path = "";
  let current = 0;
  for (const change of changes) {
    const x = xScale(Date.parse(change.submitted), minTime, maxTime, left.x0, left.x1);
    const oldY = yScale(current, 0, maxScore, left.y0, left.y1);
    const newY = yScale(change.deliveries, 0, maxScore, left.y0, left.y1);
    path += path ? ` L ${x.toFixed(1)} ${oldY.toFixed(1)} L ${x.toFixed(1)} ${newY.toFixed(1)}` : `M ${x.toFixed(1)} ${oldY.toFixed(1)} L ${x.toFixed(1)} ${newY.toFixed(1)}`;
    current = change.deliveries;
  }
  parts.push(`<path d="${path}" fill="none" stroke="#111827" stroke-width="2.4"/>`);

  for (const tick of [minTime, minTime + (maxTime - minTime) / 2, maxTime]) {
    const x = xScale(tick, minTime, maxTime, left.x0, left.x1);
    parts.push(`<text x="${x}" y="${left.y1 + 22}" text-anchor="middle" class="tick">${timeLabel(tick)}</text>`);
  }
  parts.push(`<text x="${left.x0}" y="${left.y1 + 45}" class="small">Submitted time (UTC)</text>`);

  const sortedTeams = [...teams].sort((a, b) => b.best_deliveries - a.best_deliveries);
  parts.push('<text x="790" y="50" class="label">Team best deliveries</text>');
  for (const score of [850, 900, 950, 1000]) {
    const x = xScale(score, 850, 1010, right.x0, right.x1);
    parts.push(`<line x1="${x}" x2="${x}" y1="${right.y0}" y2="${right.y1}" class="grid"/>`);
    parts.push(`<text x="${x}" y="${right.y1 + 18}" text-anchor="middle" class="tick">${score}</text>`);
  }
  sortedTeams.forEach((team, index) => {
    const y = right.y0 + index * ((right.y1 - right.y0) / Math.max(1, sortedTeams.length - 1));
    const x = xScale(team.best_deliveries, 850, 1010, right.x0, right.x1);
    const fill = team.best_deliveries >= 1000 ? "#d1495b" : team.best_deliveries >= 920 ? "#2a6fbb" : "#65707c";
    parts.push(`<text x="${right.x0 - 10}" y="${y + 4}" text-anchor="end" class="tick">${escapeXml(shortTeamLabel(team.team))}</text>`);
    parts.push(`<line x1="${right.x0}" x2="${x}" y1="${y}" y2="${y}" stroke="#d8d2c8" stroke-width="1.2"/>`);
    parts.push(`<circle cx="${x}" cy="${y}" r="4.2" fill="${fill}"/>`);
    if (index < 3) parts.push(`<text x="${x + 7}" y="${y + 4}" class="tick">${team.best_deliveries}</text>`);
  });

  return makeSvg(1120, 480, parts.join("\n"));
}

function makeLayoutDiffusionFigure(rows, layoutGroups) {
  const successful = rows.filter((row) => row.status === "succeeded");
  const minTime = Math.min(...successful.map((row) => Date.parse(row.submitted)));
  const maxTime = Math.max(...successful.map((row) => Date.parse(row.submitted)));
  const plot = { x0: 210, x1: 880, y0: 95, y1: 405 };
  const largestCommon = layoutGroups[0];
  const olderCommon = layoutGroups[1];
  const final1008 = layoutGroups.find((group) => group.best_deliveries >= 1000);
  const shared930 = layoutGroups.find((group) => group.first_job === "c31ff1c81105") ?? layoutGroups.find((group) => group.best_deliveries >= 925 && group.jobs >= 4);
  const team4 = layoutGroups.find((group) => group.first_job === "7a4738c9956c") ?? layoutGroups.find((group) => teamNumber(group.first_team) === 4 && group.best_deliveries >= 907);
  const reused = new Set(layoutGroups.filter((group) => group.jobs >= 2).map((group) => group.hash));
  const named = new Set([largestCommon?.hash, olderCommon?.hash, final1008?.hash, shared930?.hash, team4?.hash].filter(Boolean));
  const laneDefs = [
    { key: "1008", title: "1008 final layout", group: final1008, color: "#d1495b" },
    { key: "930", title: "930 shared layout", group: shared930, color: "#2a6fbb" },
    { key: "907", title: "907 layout family", group: team4, color: "#269c7f" },
    { key: "common-a", title: "largest common floor", group: largestCommon, color: "#8f7a5f" },
    { key: "common-b", title: "older common floor", group: olderCommon, color: "#b08d62" },
    { key: "reused", title: "other reused layouts", group: null, color: "#7c8fa3" },
    { key: "other", title: "one-off layouts", group: null, color: "#c6ccd3" },
  ];
  const laneY = new Map(laneDefs.map((lane, index) => [lane.key, plot.y0 + index * 48]));
  const parts = [];

  parts.push('<text x="70" y="35" class="title">Layout diffusion across public submissions</text>');
  parts.push('<text x="70" y="57" class="small">Exact layouts spread through the room; the final demand-fitted layout appears once, at the end.</text>');

  function laneFor(row) {
    if (row.replay_layout_hash === final1008?.hash) return "1008";
    if (row.replay_layout_hash === shared930?.hash) return "930";
    if (row.replay_layout_hash === team4?.hash) return "907";
    if (row.replay_layout_hash === largestCommon?.hash) return "common-a";
    if (row.replay_layout_hash === olderCommon?.hash) return "common-b";
    if (reused.has(row.replay_layout_hash) && !named.has(row.replay_layout_hash)) return "reused";
    return "other";
  }

  for (const lane of laneDefs) {
    const y = laneY.get(lane.key);
    const groupRows = successful.filter((row) => laneFor(row) === lane.key);
    const best = groupRows.length > 0 ? Math.max(...groupRows.map((row) => row.deliveries)) : null;
    const teams = new Set(groupRows.map((row) => row.team));
    parts.push(`<line x1="${plot.x0}" x2="${plot.x1}" y1="${y}" y2="${y}" class="grid"/>`);
    parts.push(`<text x="${plot.x0 - 16}" y="${y + 4}" text-anchor="end" class="label">${escapeXml(lane.title)}</text>`);
    parts.push(`<circle cx="${plot.x0 - 5}" cy="${y}" r="4" fill="${lane.color}"/>`);
    if (groupRows.length > 0) {
      const summary = `${groupRows.length} jobs · ${teams.size} teams · best ${best}`;
      parts.push(`<text x="${plot.x1 + 18}" y="${y + 4}" class="small">${escapeXml(summary)}</text>`);
    }
  }

  for (const row of successful) {
    const lane = laneDefs.find((item) => item.key === laneFor(row));
    const x = xScale(Date.parse(row.submitted), minTime, maxTime, plot.x0, plot.x1);
    const baseY = laneY.get(lane.key);
    const jitter = ((row.deliveries % 5) - 2) * 1.4;
    const radius = row.deliveries >= 1000 ? 6 : row.deliveries >= 925 ? 5.2 : row.deliveries >= 895 ? 4.4 : 3.4;
    const opacity = lane.key === "other" ? 0.5 : 0.86;
    parts.push(`<circle cx="${x.toFixed(1)}" cy="${(baseY + jitter).toFixed(1)}" r="${radius}" fill="${lane.color}" opacity="${opacity}"/>`);
  }

  const callouts = [
    { job: "c31ff1c81105", label: "930 appears", dx: -92, dy: -28 },
    { job: "3905ff4f9ead", label: "same layout reaches 931", dx: -118, dy: 30 },
    { job: "c15da13c3eaa", label: "1008 final", dx: -82, dy: -15 },
  ];
  for (const callout of callouts) {
    const row = successful.find((item) => item.job === callout.job);
    if (!row) continue;
    const lane = laneDefs.find((item) => item.key === laneFor(row));
    const x = xScale(Date.parse(row.submitted), minTime, maxTime, plot.x0, plot.x1);
    const y = laneY.get(lane.key);
    const labelX = Math.max(plot.x0, Math.min(plot.x1 - 120, x + callout.dx));
    const labelY = y + callout.dy;
    parts.push(`<line x1="${x}" x2="${labelX + 5}" y1="${y}" y2="${labelY + 5}" stroke="#4b5563" stroke-width="1"/>`);
    parts.push(`<text x="${labelX}" y="${labelY}" class="tick">${escapeXml(callout.label)}</text>`);
  }

  for (const tick of [minTime, minTime + (maxTime - minTime) / 2, maxTime]) {
    const x = xScale(tick, minTime, maxTime, plot.x0, plot.x1);
    parts.push(`<line x1="${x}" x2="${x}" y1="${plot.y0 - 18}" y2="${plot.y1 + 18}" stroke="#eee9df" stroke-width="1"/>`);
    parts.push(`<text x="${x}" y="${plot.y1 + 42}" text-anchor="middle" class="tick">${timeLabel(tick)}</text>`);
  }

  parts.push(`<line x1="${plot.x0}" x2="${plot.x1}" y1="${plot.y1 + 20}" y2="${plot.y1 + 20}" class="axis"/>`);
  parts.push(`<text x="70" y="480" class="small">Unique replay layouts: ${layoutGroups.length}. Exact code files: 83 among 86 successful submissions.</text>`);
  parts.push(`<text x="70" y="500" class="small">Dot size roughly tracks deliveries: small early attempts, larger 895+ plateau submissions, largest 1008.</text>`);
  return makeSvg(1120, 525, parts.join("\n"));
}

async function main() {
  const args = process.argv.slice(2);
  const jobsHtmlPath = argValue(args, "--jobs-html");
  const replayHtmlDir = argValue(args, "--replay-html-dir");
  const codeDir = argValue(args, "--code-dir");
  const summaryOut = argValue(args, "--summary-out") ?? path.join("outputs", "public-site-analysis", "summary.json");
  const figureDir = argValue(args, "--figure-dir") ?? path.join("public", "figures");

  if (!jobsHtmlPath || !replayHtmlDir) {
    usage();
    process.exitCode = 1;
    return;
  }

  const rows = parseJobsHtml(await readFile(jobsHtmlPath, "utf8"));
  await addReplayLayouts(rows, replayHtmlDir);
  await addCodeAnalysis(rows, codeDir);

  const changes = frontierChanges(rows);
  const teams = teamSummaries(rows);
  const layoutGroups = summarizeLayouts(rows);
  const transitions = summarizeTransitions(rows);
  const code = summarizeCode(rows);
  const summary = {
    source: {
      jobs_html: jobsHtmlPath,
      replay_html_dir: replayHtmlDir,
      code_dir: codeDir ?? null,
    },
    totals: {
      jobs: rows.length,
      succeeded: rows.filter((row) => row.status === "succeeded").length,
      safety_rejected: rows.filter((row) => row.status !== "succeeded").length,
      unique_layouts: layoutGroups.length,
    },
    frontier_changes: changes,
    teams,
    layout_groups: layoutGroups,
    layout_transitions: transitions,
    code,
  };

  await mkdir(path.dirname(summaryOut), { recursive: true });
  await mkdir(figureDir, { recursive: true });
  await writeFile(summaryOut, `${JSON.stringify(summary, null, 2)}\n`);
  await writeFile(path.join(figureDir, "event-frontier.svg"), makeFrontierFigure(rows, teams, changes));
  await writeFile(path.join(figureDir, "layout-diffusion.svg"), makeLayoutDiffusionFigure(rows, layoutGroups));

  console.log(`wrote ${summaryOut}`);
  console.log(`wrote ${path.join(figureDir, "event-frontier.svg")}`);
  console.log(`wrote ${path.join(figureDir, "layout-diffusion.svg")}`);
  console.log(JSON.stringify(summary.totals));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
