export type RefugioPosition = [number, number];

export type RefugioRobot = {
  carrying: boolean;
  deliveries: number;
  id: number;
  pos: RefugioPosition;
  target?: RefugioPosition;
};

export type RefugioFrame = {
  robots: RefugioRobot[];
  tick: number;
};

export type RefugioBase = {
  position: RefugioPosition;
  robot_id: number;
  side: "top" | "bottom" | "left" | "right";
};

export type RefugioLayout = {
  bases: RefugioBase[];
  cell_encoding: {
    base: string;
    empty: string;
    shelf: string;
  };
  grid: string[];
  height: number;
  shelf_cells?: RefugioPosition[];
  width: number;
};

export type RefugioReplay = {
  frames: RefugioFrame[];
  global_seed?: string;
  layout: RefugioLayout;
  name?: string;
  schema_version: number;
  ticks: number;
  total_deliveries: number;
};

const nextFlightPushPattern = /self\.__next_f\.push\(([\s\S]*?)\)<\/script>/g;

function findJsonObjectEnd(source: string, start: number) {
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let index = start; index < source.length; index += 1) {
    const char = source[index];

    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === "\"") {
        inString = false;
      }

      continue;
    }

    if (char === "\"") {
      inString = true;
      continue;
    }

    if (char === "{") {
      depth += 1;
      continue;
    }

    if (char === "}") {
      depth -= 1;

      if (depth === 0) {
        return index;
      }
    }
  }

  throw new Error("Could not find the end of the embedded replay object.");
}

function isPosition(value: unknown): value is RefugioPosition {
  return Array.isArray(value)
    && value.length === 2
    && value.every((entry) => typeof entry === "number");
}

function isRobot(value: unknown): value is RefugioRobot {
  if (!value || typeof value !== "object") {
    return false;
  }

  const robot = value as Partial<RefugioRobot>;

  return typeof robot.carrying === "boolean"
    && typeof robot.deliveries === "number"
    && typeof robot.id === "number"
    && isPosition(robot.pos)
    && (robot.target === undefined || isPosition(robot.target));
}

function isReplay(value: unknown): value is RefugioReplay {
  if (!value || typeof value !== "object") {
    return false;
  }

  const replay = value as Partial<RefugioReplay>;
  const layout = replay.layout as Partial<RefugioLayout> | undefined;

  return Array.isArray(replay.frames)
    && replay.frames.every((frame) => {
      return frame
        && typeof frame.tick === "number"
        && Array.isArray(frame.robots)
        && frame.robots.every(isRobot);
    })
    && !!layout
    && typeof layout.width === "number"
    && typeof layout.height === "number"
    && Array.isArray(layout.grid)
    && Array.isArray(layout.bases)
    && typeof replay.ticks === "number"
    && typeof replay.total_deliveries === "number";
}

export function extractRefugioReplayFromHtml(html: string): RefugioReplay {
  const payloadChunks: string[] = [];

  for (const match of html.matchAll(nextFlightPushPattern)) {
    try {
      const pushed = JSON.parse(match[1]) as unknown[];
      const chunk = pushed[1];

      if (typeof chunk === "string") {
        payloadChunks.push(chunk);
      }
    } catch {
      // Ignore non-flight scripts. A missing replay is reported below.
    }
  }

  const payload = payloadChunks.join("");
  const markerIndex = payload.indexOf("\"replay\":");

  if (markerIndex === -1) {
    throw new Error("The replay payload was not found in the REFUGIO page.");
  }

  const objectStart = payload.indexOf("{", markerIndex);

  if (objectStart === -1) {
    throw new Error("The embedded replay payload is malformed.");
  }

  const objectEnd = findJsonObjectEnd(payload, objectStart);
  const parsed = JSON.parse(payload.slice(objectStart, objectEnd + 1)) as unknown;

  if (!isReplay(parsed)) {
    throw new Error("The embedded replay payload did not match the expected schema.");
  }

  return parsed;
}
