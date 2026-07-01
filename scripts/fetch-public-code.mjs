import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_BASE_URL = "https://refugio-hackathon-nine.vercel.app/code";

function decodeHtml(value) {
  const named = {
    amp: "&",
    apos: "'",
    gt: ">",
    lt: "<",
    nbsp: " ",
    quot: "\"",
  };

  return value.replace(/&(#x[0-9a-fA-F]+|#\d+|[A-Za-z]+);/g, (entity, body) => {
    if (body.startsWith("#x")) {
      return String.fromCodePoint(Number.parseInt(body.slice(2), 16));
    }

    if (body.startsWith("#")) {
      return String.fromCodePoint(Number.parseInt(body.slice(1), 10));
    }

    return named[body] ?? entity;
  });
}

function usage() {
  console.error("Usage: npm run fetch:public-code -- <job-id> [url]");
}

async function main() {
  const jobId = process.argv[2];

  if (!jobId || !/^[a-f0-9]{12}$/i.test(jobId)) {
    usage();
    process.exitCode = 1;
    return;
  }

  const sourceUrl = process.argv[3] ?? `${DEFAULT_BASE_URL}/${jobId}`;
  const response = await fetch(sourceUrl, {
    headers: {
      "user-agent": "refugio-challenge-analysis/1.0",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch ${sourceUrl}: HTTP ${response.status}`);
  }

  const html = await response.text();
  const match = html.match(/<pre><code>([\s\S]*?)<\/code><\/pre>/);

  if (!match) {
    throw new Error(`Could not find a <pre><code> block in ${sourceUrl}`);
  }

  const source = `${decodeHtml(match[1]).replace(/\r\n/g, "\n").trimEnd()}\n`;
  const outputDir = path.join(rootDir, "solutions", "public");
  const outputPath = path.join(outputDir, `${jobId}.py`);
  const metadataPath = path.join(outputDir, `${jobId}.metadata.json`);

  await mkdir(outputDir, { recursive: true });
  await writeFile(outputPath, source, "utf8");
  await writeFile(
    metadataPath,
    `${JSON.stringify(
      {
        captured_on: "2026-07-01",
        job_id: jobId,
        source_bytes: Buffer.byteLength(source),
        source_lines: source.split("\n").length - 1,
        source_url: sourceUrl,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );

  console.log(`wrote ${path.relative(rootDir, outputPath)}`);
  console.log(`wrote ${path.relative(rootDir, metadataPath)}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
