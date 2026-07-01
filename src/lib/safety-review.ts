export type SafetyFinding = {
  evidence: string;
  tag: string;
};

export type SafetyReview = {
  findings: SafetyFinding[];
  message: string;
  status: "approved" | "rejected";
};

const allowedImportRoots = new Set([
  "__future__",
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

const dynamicImportRoots = new Set(["importlib", "pkgutil", "runpy"]);
const filesystemRoots = new Set(["pathlib", "shutil"]);
const hiddenRuntimeRoots = new Set(["builtins", "ctypes", "gc", "inspect", "os", "sys"]);
const networkRoots = new Set(["ftplib", "http", "requests", "socket", "ssl", "urllib"]);
const processRoots = new Set(["asyncio", "concurrent", "multiprocessing", "subprocess", "threading"]);
const privateWarehouseRoots = new Set(["warehouse"]);
const tamperingTags = new Set(["dynamic import", "evaluation bypass", "unauthorized internal import"]);

const dynamicImportCallPattern = /\b__import__\s*\(/;
const dynamicCodeCallPattern = /\b(?:eval|exec|compile)\s*\(/;
const filesystemCallPattern = /\b(?:open|input)\s*\(/;
const introspectionCallPattern = /\b(?:delattr|dir|getattr|globals|hasattr|locals|setattr|vars)\s*\(/;
const introspectionAttributePattern = /\.(?:__base__|__bases__|__builtins__|__class__|__code__|__dict__|__globals__|__mro__|__subclasses__)\b|\bsys\.modules\b/;
const evaluatorAssignmentPattern = /(?:\.(?:target_for)\s*=|\b(?:evaluation|evaluator|module|result|runner|simulation)\w*(?:\.\w+)*\.(?:deliveries|evaluate|run|score|simulate|target_for)\s*=)/;
const tamperingLanguagePattern = /\b(?:monkey|patch|patching|tamper|fake score|fake_score)\b/i;

function byteLength(source: string) {
  return new TextEncoder().encode(source).byteLength;
}

function linePrefix(lineNumber: number) {
  return `line ${lineNumber}`;
}

function summarizeTags(findings: SafetyFinding[]) {
  return Array.from(new Set(findings.map((finding) => finding.tag))).join(", ");
}

function dedupeFindings(findings: SafetyFinding[]) {
  return findings.filter((finding, index, all) => {
    return all.findIndex((candidate) => candidate.tag === finding.tag && candidate.evidence === finding.evidence) === index;
  });
}

function classifyImport(lineNumber: number, moduleName: string, statement: string): SafetyFinding | null {
  const rootName = moduleName.split(".")[0] ?? "";

  if (privateWarehouseRoots.has(rootName) || (rootName.startsWith("warehouse_") && rootName !== "warehouse_api")) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "unauthorized internal import",
    };
  }

  if (dynamicImportRoots.has(rootName)) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "dynamic import",
    };
  }

  if (filesystemRoots.has(rootName)) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "filesystem access",
    };
  }

  if (hiddenRuntimeRoots.has(rootName)) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "hidden introspection",
    };
  }

  if (networkRoots.has(rootName)) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "network access",
    };
  }

  if (processRoots.has(rootName)) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "process or concurrency escape",
    };
  }

  if (!allowedImportRoots.has(rootName)) {
    return {
      evidence: `${linePrefix(lineNumber)}: ${statement}`,
      tag: "disallowed import",
    };
  }

  return null;
}

function scanImportFindings(source: string) {
  const findings: SafetyFinding[] = [];
  const lines = source.split(/\r?\n/);

  for (const [index, rawLine] of lines.entries()) {
    const lineNumber = index + 1;
    const trimmed = rawLine.trim();

    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const relativeImportMatch = trimmed.match(/^from\s+\./);
    if (relativeImportMatch) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: relative imports are not permitted`,
        tag: "disallowed import",
      });
      continue;
    }

    const fromMatch = trimmed.match(/^from\s+([A-Za-z0-9_.]+)\s+import\b/);
    if (fromMatch?.[1]) {
      const finding = classifyImport(lineNumber, fromMatch[1], `from ${fromMatch[1]} import ...`);
      if (finding) {
        findings.push(finding);
      }
      continue;
    }

    const importMatch = trimmed.match(/^import\s+(.+)/);
    if (!importMatch?.[1]) {
      continue;
    }

    for (const importClause of importMatch[1].split(",")) {
      const moduleName = importClause.trim().split(/\s+as\s+|\s+/)[0] ?? "";
      if (!moduleName) {
        continue;
      }

      const finding = classifyImport(lineNumber, moduleName, `import ${moduleName}`);
      if (finding) {
        findings.push(finding);
      }
    }
  }

  return findings;
}

function scanPatternFindings(source: string) {
  const findings: SafetyFinding[] = [];

  for (const [index, rawLine] of source.split(/\r?\n/).entries()) {
    const lineNumber = index + 1;
    const codeOnly = rawLine.split("#", 1)[0] ?? "";

    if (dynamicImportCallPattern.test(codeOnly)) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: __import__()`,
        tag: "dynamic import",
      });
    }

    const dynamicCodeMatch = dynamicCodeCallPattern.exec(codeOnly);
    if (dynamicCodeMatch?.[0]) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: ${dynamicCodeMatch[0].trim()}`,
        tag: "dynamic code execution",
      });
    }

    const filesystemMatch = filesystemCallPattern.exec(codeOnly);
    if (filesystemMatch?.[0]) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: ${filesystemMatch[0].trim()}`,
        tag: "filesystem access",
      });
    }

    const introspectionCallMatch = introspectionCallPattern.exec(codeOnly);
    if (introspectionCallMatch?.[0]) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: ${introspectionCallMatch[0].trim()}`,
        tag: "introspection-escape",
      });
    }

    const introspectionAttributeMatch = introspectionAttributePattern.exec(codeOnly);
    if (introspectionAttributeMatch?.[0]) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: ${introspectionAttributeMatch[0].trim()}`,
        tag: "introspection-escape",
      });
    }

    const evaluatorAssignmentMatch = evaluatorAssignmentPattern.exec(codeOnly);
    if (evaluatorAssignmentMatch?.[0]) {
      findings.push({
        evidence: `${linePrefix(lineNumber)}: assignment to evaluator-like attribute`,
        tag: "evaluation bypass",
      });
    }
  }

  return findings;
}

function buildReview(findings: SafetyFinding[]): SafetyReview {
  const uniqueFindings = dedupeFindings(findings);

  if (uniqueFindings.length === 0) {
    return {
      findings: [],
      message: "No apparent security risks under the live instruction rules: uses permitted imports and the public warehouse API, with no filesystem, network, subprocess, dynamic import/code execution, hidden introspection, or evaluator tampering behavior.",
      status: "approved",
    };
  }

  const tags = summarizeTags(uniqueFindings);

  return {
    findings: uniqueFindings,
    message: `Safety review blocked this submission: local live-instruction rules flagged ${tags}. The code appears to reach outside the public policy contract instead of only computing layout and robot actions. (${tags})`,
    status: "rejected",
  };
}

export function reviewPolicySource(source: string): SafetyReview {
  const findings: SafetyFinding[] = [];

  if (byteLength(source) > 256 * 1024) {
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

  findings.push(...scanImportFindings(source));
  findings.push(...scanPatternFindings(source));

  if (tamperingLanguagePattern.test(source) && findings.some((finding) => tamperingTags.has(finding.tag))) {
    findings.push({
      evidence: "source mentions tampering or fake scores alongside sandbox escape indicators",
      tag: "sandbox tampering",
    });
  }

  return buildReview(findings);
}
