import { readFile } from "node:fs/promises";
import path from "node:path";
import type { RefugioReplay } from "@/lib/refugio-replay";

export const localReplayIds = [
  "bf4184ae5b49",
  "c15da13c3eaa",
  "3905ff4f9ead",
  "7a4738c9956c",
  "1b294895f546",
  "202607021024",
] as const;

export type LocalReplayId = typeof localReplayIds[number];

export function isLocalReplayId(jobId: string): jobId is LocalReplayId {
  return localReplayIds.includes(jobId as LocalReplayId);
}

export async function getLocalReplay(jobId: string): Promise<RefugioReplay> {
  if (!/^[a-f0-9]{12}$/i.test(jobId)) {
    throw new Error("Expected a 12-character REFUGIO job ID.");
  }

  if (!isLocalReplayId(jobId)) {
    throw new Error(`Replay ${jobId} is not bundled in this self-hosted repo.`);
  }

  const replayPath = path.join(process.cwd(), "public", "replays", `${jobId}.json`);
  const source = await readFile(replayPath, "utf8");

  return JSON.parse(source) as RefugioReplay;
}
