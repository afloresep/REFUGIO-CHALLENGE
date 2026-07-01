"use client";

import {
  type CSSProperties,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  RefugioFrame,
  RefugioLayout,
  RefugioPosition,
  RefugioReplay,
  RefugioRobot,
} from "@/lib/refugio-replay";

const padding = 10;
const speeds = [
  [240, "1x"],
  [120, "2x"],
  [60, "4x"],
  [30, "8x"],
] as const;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function cellOrigin(x: number, y: number, cellSize: number, view: ViewState) {
  return [
    padding + x * cellSize * view.zoom + view.offsetX,
    padding + y * cellSize * view.zoom + view.offsetY,
  ] as const;
}

function cellKind(layout: RefugioLayout, x: number, y: number) {
  const value = layout.grid[y]?.[x];

  if (value === layout.cell_encoding.shelf) {
    return "shelf";
  }

  if (value === layout.cell_encoding.base) {
    return "base";
  }

  return "empty";
}

function interpolateFrame(
  frames: RefugioFrame[],
  fromIndex: number,
  toIndex: number,
  progress: number,
) {
  const fromFrame = frames[fromIndex] ?? frames[0];
  const toFrame = frames[toIndex] ?? fromFrame;

  if (!fromFrame || fromIndex === toIndex || progress <= 0) {
    return fromFrame;
  }

  const nextRobots = new Map(toFrame.robots.map((robot) => [robot.id, robot]));

  return {
    tick: fromFrame.tick,
    robots: fromFrame.robots.map((robot) => {
      const nextRobot = nextRobots.get(robot.id);

      if (!nextRobot) {
        return robot;
      }

      return {
        ...robot,
        pos: [
          robot.pos[0] + (nextRobot.pos[0] - robot.pos[0]) * progress,
          robot.pos[1] + (nextRobot.pos[1] - robot.pos[1]) * progress,
        ],
      } satisfies RefugioRobot;
    }),
  } satisfies RefugioFrame;
}

type ViewState = {
  offsetX: number;
  offsetY: number;
  zoom: number;
};

type HoveredCell = {
  position: RefugioPosition;
  robots: RefugioRobot[];
} | null;

function drawWarehouseFrame({
  baseIdLabels,
  canvas,
  cellSize,
  frame,
  layout,
  selectedRobotId,
  showTargets,
  view,
}: {
  baseIdLabels: boolean;
  canvas: HTMLCanvasElement;
  cellSize: number;
  frame: RefugioFrame;
  layout: RefugioLayout;
  selectedRobotId: number | null;
  showTargets: boolean;
  view: ViewState;
}) {
  const context = canvas.getContext("2d");

  if (!context) {
    return;
  }

  const ratio = window.devicePixelRatio || 1;
  const cssWidth = layout.width * cellSize + padding * 2;
  const cssHeight = layout.height * cellSize + padding * 2;
  const scaledCell = cellSize * view.zoom;

  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  canvas.width = Math.floor(cssWidth * ratio);
  canvas.height = Math.floor(cssHeight * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);

  context.fillStyle = "#f1e6c8";
  context.fillRect(0, 0, cssWidth, cssHeight);

  for (let y = 0; y < layout.height; y += 1) {
    for (let x = 0; x < layout.width; x += 1) {
      const [left, top] = cellOrigin(x, y, cellSize, view);
      const kind = cellKind(layout, x, y);

      if (kind === "shelf") {
        context.fillStyle = "#111111";
      } else if (kind === "base") {
        context.fillStyle = "#2465a9";
      } else if (x === 0 || y === 0 || x === layout.width - 1 || y === layout.height - 1) {
        context.fillStyle = "#f1e6c8";
      } else {
        context.fillStyle = (x + y) % 2 === 0 ? "#fbf9f1" : "#ffffff";
      }

      context.fillRect(left, top, scaledCell, scaledCell);
    }
  }

  context.strokeStyle = "rgba(17, 17, 17, 0.12)";
  context.lineWidth = 1;
  context.beginPath();

  for (let x = 0; x <= layout.width; x += 1) {
    const lineX = padding + x * scaledCell + view.offsetX + 0.5;
    context.moveTo(lineX, padding + view.offsetY);
    context.lineTo(lineX, padding + layout.height * scaledCell + view.offsetY);
  }

  for (let y = 0; y <= layout.height; y += 1) {
    const lineY = padding + y * scaledCell + view.offsetY + 0.5;
    context.moveTo(padding + view.offsetX, lineY);
    context.lineTo(padding + layout.width * scaledCell + view.offsetX, lineY);
  }

  context.stroke();

  if (showTargets) {
    for (const robot of frame.robots) {
      if (!robot.target || robot.carrying) {
        continue;
      }

      const [left, top] = cellOrigin(robot.target[0], robot.target[1], cellSize, view);
      context.fillStyle = "#f1b91e";
      context.globalAlpha = 0.75;
      context.fillRect(left + 1, top + 1, scaledCell - 2, scaledCell - 2);
      context.globalAlpha = 1;
    }
  }

  for (const base of layout.bases) {
    if (!baseIdLabels) {
      break;
    }

    const [left, top] = cellOrigin(base.position[0], base.position[1], cellSize, view);
    context.fillStyle = "#fffaf0";
    context.font = `${Math.max(7, scaledCell * 0.45)}px monospace`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(base.robot_id), left + scaledCell / 2, top + scaledCell / 2);
  }

  for (const robot of frame.robots) {
    const [left, top] = cellOrigin(robot.pos[0], robot.pos[1], cellSize, view);
    const radius = Math.max(2, scaledCell * 0.34);

    context.beginPath();
    context.arc(left + scaledCell / 2, top + scaledCell / 2, radius, 0, Math.PI * 2);
    context.fillStyle = robot.carrying ? "#f1b91e" : "#c43d2f";
    context.fill();
    context.strokeStyle = robot.id === selectedRobotId ? "#ffffff" : "#111111";
    context.lineWidth = robot.id === selectedRobotId ? 3 : 1;
    context.stroke();
  }
}

function getRobotsAtCell(frame: RefugioFrame | undefined, position: RefugioPosition | null) {
  if (!frame || !position) {
    return [];
  }

  return frame.robots.filter((robot) => {
    return Math.round(robot.pos[0]) === position[0] && Math.round(robot.pos[1]) === position[1];
  });
}

function getTotalDeliveries(frame: RefugioFrame | undefined) {
  return frame?.robots.reduce((total, robot) => total + robot.deliveries, 0) ?? 0;
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function ReplayViewer({ replay }: Readonly<{ replay: RefugioReplay }>) {
  const frames = replay.frames;
  const layout = replay.layout;
  const [frameIndex, setFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [frameMs, setFrameMs] = useState(120);
  const [cellSize, setCellSize] = useState(10);
  const [loop, setLoop] = useState(false);
  const [showTargets, setShowTargets] = useState(true);
  const [baseIdLabels, setBaseIdLabels] = useState(false);
  const [selectedRobotId, setSelectedRobotId] = useState<number | null>(null);
  const [hoveredCell, setHoveredCell] = useState<HoveredCell>(null);
  const [view, setView] = useState<ViewState>({ offsetX: 0, offsetY: 0, zoom: 1 });
  const [dragStart, setDragStart] = useState<{ x: number; y: number; view: ViewState } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const frameIndexRef = useRef(0);
  const currentFrame = frames[frameIndex];
  const totalTicks = frames.at(-1)?.tick ?? replay.ticks;
  const selectedRobot = currentFrame?.robots.find((robot) => robot.id === selectedRobotId) ?? null;
  const carryingCount = currentFrame?.robots.filter((robot) => robot.carrying).length ?? 0;

  const baseByRobot = useMemo(() => {
    return new Map(layout.bases.map((base) => [base.robot_id, base]));
  }, [layout.bases]);

  const drawFrame = useCallback((index: number, progress = 0) => {
    if (!canvasRef.current || frames.length === 0) {
      return;
    }

    const nextIndex = clamp(index + 1, 0, frames.length - 1);
    const frame = interpolateFrame(frames, index, nextIndex, progress);

    if (!frame) {
      return;
    }

    drawWarehouseFrame({
      baseIdLabels,
      canvas: canvasRef.current,
      cellSize,
      frame,
      layout,
      selectedRobotId,
      showTargets,
      view,
    });
  }, [baseIdLabels, cellSize, frames, layout, selectedRobotId, showTargets, view]);

  const jumpTo = useCallback((index: number) => {
    const nextIndex = clamp(index, 0, frames.length - 1);
    frameIndexRef.current = nextIndex;
    setFrameIndex(nextIndex);
  }, [frames.length]);

  const stopPlayback = useCallback((reset = false) => {
    if (animationRef.current !== null) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }

    setIsPlaying(false);

    if (reset) {
      jumpTo(0);
    }
  }, [jumpTo]);

  useEffect(() => {
    const shell = shellRef.current;

    if (!shell) {
      return;
    }

    const updateSize = () => {
      const availableWidth = shell.clientWidth - padding * 2;
      setCellSize(clamp(Math.floor(availableWidth / 52), 5, 12));
    };

    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(shell);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    frameIndexRef.current = frameIndex;

    if (!isPlaying) {
      drawFrame(frameIndex);
    }
  }, [drawFrame, frameIndex, isPlaying]);

  useEffect(() => {
    if (!isPlaying || frames.length < 2) {
      return;
    }

    let startedAt = performance.now();
    let startFrame = frameIndexRef.current;

    const tick = (timestamp: number) => {
      const progress = prefersReducedMotion()
        ? 0
        : clamp((timestamp - startedAt) / frameMs, 0, 1);
      const elapsedFrame = timestamp - startedAt >= frameMs;

      drawFrame(startFrame, progress);

      if (progress >= 1 || elapsedFrame) {
        const nextFrame = startFrame + 1;

        if (nextFrame >= frames.length) {
          if (loop) {
            startFrame = 0;
            jumpTo(0);
            startedAt = timestamp;
          } else {
            setIsPlaying(false);
            animationRef.current = null;
            return;
          }
        } else {
          startFrame = nextFrame;
          jumpTo(nextFrame);
          startedAt = timestamp;
        }
      }

      animationRef.current = requestAnimationFrame(tick);
    };

    animationRef.current = requestAnimationFrame(tick);

    return () => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    };
  }, [drawFrame, frameMs, frames.length, isPlaying, jumpTo, loop]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (event.key === " ") {
        event.preventDefault();
        setIsPlaying((playing) => !playing);
      } else if (event.key === "ArrowLeft") {
        stopPlayback();
        jumpTo(frameIndexRef.current - 1);
      } else if (event.key === "ArrowRight") {
        stopPlayback();
        jumpTo(frameIndexRef.current + 1);
      } else if (event.key === "Home") {
        stopPlayback();
        jumpTo(0);
      } else if (event.key === "End") {
        stopPlayback();
        jumpTo(frames.length - 1);
      }
    };

    window.addEventListener("keydown", onKeyDown);

    return () => window.removeEventListener("keydown", onKeyDown);
  }, [frames.length, jumpTo, stopPlayback]);

  const cellFromPoint = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current;

    if (!canvas) {
      return null;
    }

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((clientX - rect.left - padding - view.offsetX) / (cellSize * view.zoom));
    const y = Math.floor((clientY - rect.top - padding - view.offsetY) / (cellSize * view.zoom));

    if (x < 0 || y < 0 || x >= layout.width || y >= layout.height) {
      return null;
    }

    return [x, y] satisfies RefugioPosition;
  }, [cellSize, layout.height, layout.width, view]);

  const selectedBase = selectedRobot ? baseByRobot.get(selectedRobot.id) ?? null : null;

  return (
    <div className="replay-shell" ref={shellRef}>
      <section className="stage">
        <div className="stage-head">
          <span className="replay-name">{replay.name ?? "Replay"}</span>
          <span className="stage-chips">
            {replay.global_seed ? <span className="chip">seed {replay.global_seed}</span> : null}
            <span className="chip chip-accent">{replay.total_deliveries} deliveries</span>
          </span>
        </div>

        <div className="transport">
          <div className="transport-buttons">
            <button type="button" disabled={frameIndex <= 0} onClick={() => jumpTo(0)}>
              &lt;&lt;
            </button>
            <button type="button" disabled={frameIndex <= 0} onClick={() => jumpTo(frameIndex - 1)}>
              -1
            </button>
            <button
              className="primary"
              type="button"
              onClick={() => setIsPlaying((playing) => !playing)}
            >
              {isPlaying ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              disabled={frameIndex >= frames.length - 1}
              onClick={() => jumpTo(frameIndex + 1)}
            >
              +1
            </button>
            <button
              type="button"
              disabled={frameIndex >= frames.length - 1}
              onClick={() => jumpTo(frames.length - 1)}
            >
              &gt;&gt;
            </button>
          </div>

          <input
            aria-label="Tick"
            className="timeline"
            max={Math.max(0, frames.length - 1)}
            min={0}
            style={{ "--progress": `${(frameIndex / Math.max(1, frames.length - 1)) * 100}%` } as CSSProperties}
            type="range"
            value={frameIndex}
            onChange={(event) => {
              stopPlayback();
              jumpTo(Number(event.target.value));
            }}
          />

          <span className="tick-readout">
            {String(currentFrame?.tick ?? 0).padStart(String(totalTicks).length, "0")} / {totalTicks}
          </span>

          <div className="seg-group" role="group" aria-label="Playback speed">
            {speeds.map(([speed, label]) => (
              <button
                className={frameMs === speed ? "active" : undefined}
                key={speed}
                type="button"
                onClick={() => setFrameMs(speed)}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            aria-pressed={loop}
            className={loop ? "toggle active" : "toggle"}
            type="button"
            onClick={() => setLoop((value) => !value)}
          >
            Loop
          </button>
        </div>

        <div
          className="canvas-wrap"
          style={{ cursor: view.zoom > 1 ? "grab" : undefined }}
          onMouseDown={(event) => {
            if (view.zoom <= 1) {
              return;
            }

            setDragStart({ x: event.clientX, y: event.clientY, view });
          }}
          onMouseLeave={() => {
            setDragStart(null);
            setHoveredCell(null);
          }}
          onMouseMove={(event) => {
            if (dragStart) {
              setView({
                ...dragStart.view,
                offsetX: dragStart.view.offsetX + event.clientX - dragStart.x,
                offsetY: dragStart.view.offsetY + event.clientY - dragStart.y,
              });
              return;
            }

            const position = cellFromPoint(event.clientX, event.clientY);
            const robots = getRobotsAtCell(currentFrame, position);
            setHoveredCell(position ? { position, robots } : null);
          }}
          onMouseUp={() => setDragStart(null)}
          onWheel={(event) => {
            event.preventDefault();
            const direction = event.deltaY > 0 ? -0.1 : 0.1;
            setView((previous) => ({
              ...previous,
              zoom: clamp(Number((previous.zoom + direction).toFixed(2)), 1, 3),
            }));
          }}
        >
          <canvas
            aria-label="REFUGIO warehouse replay"
            ref={canvasRef}
            onClick={(event) => {
              const position = cellFromPoint(event.clientX, event.clientY);
              const robots = getRobotsAtCell(currentFrame, position);

              if (robots.length === 0) {
                setSelectedRobotId(null);
                return;
              }

              const currentIndex = robots.findIndex((robot) => robot.id === selectedRobotId);
              const nextRobot = robots[(currentIndex + 1) % robots.length];
              setSelectedRobotId(nextRobot?.id ?? null);
            }}
          />
        </div>

        <p className="kbd-hints">
          <kbd>space</kbd> play/pause, <kbd>left</kbd>/<kbd>right</kbd> step,{" "}
          <kbd>home</kbd>/<kbd>end</kbd> jump, scroll to zoom, drag to pan.
          {hoveredCell ? ` Hovering ${hoveredCell.position.join(", ")} with ${hoveredCell.robots.length} robot(s).` : ""}
        </p>
      </section>

      <aside className="sidebar">
        <section className="panel">
          <h2>Scoreboard</h2>
          <div className="score-value">{getTotalDeliveries(currentFrame)}</div>
          <p className="score-detail">deliveries, {replay.total_deliveries} final</p>
          <dl className="stat-rows">
            <div>
              <dt>Carrying item</dt>
              <dd>{carryingCount} / {currentFrame?.robots.length ?? 0}</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <h2>Robot</h2>
          {selectedRobot ? (
            <div className="robot-details">
              <div><span>ID</span><strong>{selectedRobot.id}</strong></div>
              <div><span>Position</span><strong>{selectedRobot.pos.join(", ")}</strong></div>
              <div><span>Target</span><strong>{selectedRobot.target?.join(", ") ?? "returning"}</strong></div>
              <div><span>Base</span><strong>{selectedBase?.position.join(", ") ?? "unknown"}</strong></div>
              <div><span>Deliveries</span><strong>{selectedRobot.deliveries}</strong></div>
              <button className="secondary" type="button" onClick={() => setSelectedRobotId(null)}>
                Clear
              </button>
            </div>
          ) : (
            <p className="instruction-copy">Click a robot to inspect it.</p>
          )}
        </section>

        <section className="panel">
          <h2>View</h2>
          {view.zoom > 1 ? (
            <button className="secondary" type="button" onClick={() => setView({ offsetX: 0, offsetY: 0, zoom: 1 })}>
              Reset zoom
            </button>
          ) : (
            <p className="instruction-copy">Scroll to zoom. Drag to pan when zoomed in.</p>
          )}
          <label className="toggle-row">
            <input checked={showTargets} type="checkbox" onChange={(event) => setShowTargets(event.target.checked)} />
            Target shelves
          </label>
          <label className="toggle-row">
            <input checked={baseIdLabels} type="checkbox" onChange={(event) => setBaseIdLabels(event.target.checked)} />
            Base IDs
          </label>
        </section>

        <section className="panel legend">
          <h2>Legend</h2>
          <ul>
            <li><span className="swatch robot" />Robot searching</li>
            <li><span className="swatch carrying" />Robot carrying</li>
            <li><span className="swatch target" />Target shelf</li>
            <li><span className="swatch shelf" />Shelf</li>
            <li><span className="swatch base" />Outer base</li>
          </ul>
        </section>
      </aside>
    </div>
  );
}
