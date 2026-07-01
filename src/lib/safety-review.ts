export type SafetyFinding = {
  evidence: string;
  tag: string;
};

export type SafetyReview = {
  findings: SafetyFinding[];
  message: string;
  status: "approved" | "rejected";
};

type Rule = {
  pattern: RegExp;
  tag: string;
  reason: string;
};

const rules: Rule[] = [
  {
    pattern: /^\s*(?:from|import)\s+(?:warehouse\.(?!api)|warehouse_(?!api)|warehouse\.simulation|warehouse\.state|warehouse\.targets)/m,
    tag: "unauthorized internal import",
    reason: "imports private simulator or warehouse internals",
  },
  {
    pattern: /\b(?:__import__|importlib|pkgutil|runpy)\b/,
    tag: "dynamic import",
    reason: "uses dynamic import machinery",
  },
  {
    pattern: /\b(?:eval|exec|compile)\s*\(/,
    tag: "dynamic code execution",
    reason: "executes generated code dynamically",
  },
  {
    pattern: /\b(?:open|input)\s*\(|\bpathlib\b|\bshutil\b/,
    tag: "filesystem access",
    reason: "attempts file or interactive IO",
  },
  {
    pattern: /^\s*(?:from|import)\s+(?:os|sys|inspect|ctypes|gc|builtins)\b/m,
    tag: "hidden introspection",
    reason: "imports modules commonly used to inspect or alter the runtime",
  },
  {
    pattern: /\b(?:sys\.modules|globals|locals|vars|dir|getattr|setattr|delattr|object\.__subclasses__)\s*\(/,
    tag: "introspection-escape",
    reason: "uses runtime introspection patterns that can escape the public API",
  },
  {
    pattern: /^\s*(?:from|import)\s+(?:socket|http|urllib|requests|ftplib|ssl)\b/m,
    tag: "network access",
    reason: "imports network-capable modules",
  },
  {
    pattern: /^\s*(?:from|import)\s+(?:subprocess|threading|asyncio|multiprocessing|concurrent)\b/m,
    tag: "process or concurrency escape",
    reason: "imports subprocess, threading, async, or multiprocessing APIs",
  },
  {
    pattern: /\.(?:target_for|score|deliveries|evaluate|run|simulate)\s*=/,
    tag: "evaluation bypass",
    reason: "assigns to evaluator-like attributes",
  },
  {
    pattern: /\b(?:monkey|patch|patching|tamper|fake score|fake_score)\b/i,
    tag: "sandbox tampering",
    reason: "contains explicit tampering or monkey-patching language",
  },
];

const allowedImportPattern = /^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))/gm;
const allowedTopLevelModules = new Set([
  "array",
  "bisect",
  "collections",
  "copy",
  "dataclasses",
  "enum",
  "functools",
  "hashlib",
  "heapq",
  "itertools",
  "math",
  "networkx",
  "numba",
  "numpy",
  "operator",
  "queue",
  "random",
  "scipy",
  "sortedcontainers",
  "statistics",
  "typing",
  "warehouse_api",
]);

function lineForIndex(source: string, index: number) {
  return source.slice(0, index).split("\n").length;
}

function checkImports(source: string) {
  const findings: SafetyFinding[] = [];

  for (const match of source.matchAll(allowedImportPattern)) {
    const moduleName = match[1] ?? match[2] ?? "";
    const topLevel = moduleName.split(".")[0] ?? "";

    if (!allowedTopLevelModules.has(topLevel)) {
      findings.push({
        evidence: `line ${lineForIndex(source, match.index ?? 0)}: ${match[0].trim()}`,
        tag: "disallowed import",
      });
    }
  }

  return findings;
}

function summarizeTags(findings: SafetyFinding[]) {
  return Array.from(new Set(findings.map((finding) => finding.tag))).join(", ");
}

export function reviewPolicySource(source: string): SafetyReview {
  const findings: SafetyFinding[] = [];

  if (new Blob([source]).size > 256 * 1024) {
    findings.push({
      evidence: "file exceeds 256 KB",
      tag: "file size limit",
    });
  }

  if (!/\bdef\s+create_layout\s*\(/.test(source)) {
    findings.push({
      evidence: "missing def create_layout(...)",
      tag: "contract violation",
    });
  }

  if (!/\bdef\s+act\s*\(/.test(source)) {
    findings.push({
      evidence: "missing def act(...)",
      tag: "contract violation",
    });
  }

  findings.push(...checkImports(source));

  for (const rule of rules) {
    const match = rule.pattern.exec(source);

    if (match) {
      findings.push({
        evidence: `${rule.reason}: ${match[0].trim()}`,
        tag: rule.tag,
      });
    }
  }

  const uniqueFindings = findings.filter((finding, index, all) => {
    return all.findIndex((candidate) => candidate.tag === finding.tag && candidate.evidence === finding.evidence) === index;
  });

  if (uniqueFindings.length === 0) {
    return {
      findings: [],
      message: "No apparent security risks: uses permitted imports and the public warehouse API, with no filesystem, network, subprocess, dynamic code execution, obfuscation, hidden introspection, or sandbox tampering behavior.",
      status: "approved",
    };
  }

  const tags = summarizeTags(uniqueFindings);

  return {
    findings: uniqueFindings,
    message: `Safety review blocked this submission: local deterministic rules flagged ${tags}. The code appears to reach outside the public policy contract instead of only computing layout and robot actions. (${tags})`,
    status: "rejected",
  };
}
