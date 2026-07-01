import { spawn } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const seedConfigPath = path.join(rootDir, "data", "official-seeds.json");

function usage() {
  console.error([
    "Usage: npm run eval:policy -- <policy.py> [options]",
    "",
    "Options:",
    "  --label <name>          Output label. Defaults to policy basename.",
    "  --seeds <a,b,c>         Override evaluation seeds.",
    "  --ticks <n>             Defaults to data/official-seeds.json.",
    "  --budget <seconds>      Defaults to data/official-seeds.json.",
    "  --replay-seed <seed>    Defaults to the first evaluation seed.",
    "  --out-dir <dir>         Defaults to outputs/evals/<label>-<timestamp>.",
  ].join("\n"));
}

function argValue(args, name) {
  const index = args.indexOf(name);

  if (index === -1) {
    return undefined;
  }

  return args[index + 1];
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "Z");
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: rootDir,
      stdio: "inherit",
    });

    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`${command} exited with status ${code}`));
    });
  });
}

async function readSeedConfig() {
  return JSON.parse(await readFile(seedConfigPath, "utf8"));
}

async function main() {
  const args = process.argv.slice(2);
  const policyPath = args.find((arg) => arg.endsWith(".py"));

  if (!policyPath) {
    usage();
    process.exitCode = 1;
    return;
  }

  const seedConfig = await readSeedConfig();
  const label = argValue(args, "--label") ?? path.basename(policyPath, ".py");
  const seeds = argValue(args, "--seeds") ?? seedConfig.official_seeds.join(",");
  const ticks = argValue(args, "--ticks") ?? String(seedConfig.ticks);
  const budget = argValue(args, "--budget") ?? String(seedConfig.policy_budget_seconds);
  const replaySeed = argValue(args, "--replay-seed") ?? seeds.split(",")[0];
  const outDir = argValue(args, "--out-dir")
    ?? path.join("outputs", "evals", `${label}-${timestamp()}`);
  const absoluteOutDir = path.resolve(rootDir, outDir);
  const resultOut = path.join(absoluteOutDir, "result.json");
  const replayOut = path.join(absoluteOutDir, "replay.json");

  await mkdir(absoluteOutDir, { recursive: true });

  const evalArgs = [
    "-m",
    "warehouse.eval_runner",
    policyPath,
    "--submission-id",
    label,
    "--team-name",
    "local-analysis",
    "--seeds",
    seeds,
    "--ticks",
    ticks,
    "--replay-seed",
    replaySeed,
    "--policy-budget-seconds",
    budget,
    "--result-out",
    resultOut,
    "--replay-out",
    replayOut,
  ];

  console.log(`running python3 ${evalArgs.join(" ")}`);
  await run("python3", evalArgs);

  const result = JSON.parse(await readFile(resultOut, "utf8"));
  console.log(JSON.stringify(result, null, 2));
  console.log(`result: ${path.relative(rootDir, resultOut)}`);
  console.log(`replay: ${path.relative(rootDir, replayOut)}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
