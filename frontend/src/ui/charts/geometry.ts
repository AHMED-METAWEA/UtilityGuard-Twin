export interface ChartPoint {
  tick: number;
  value: number | null;
  lower?: number | null;
  upper?: number | null;
  flags?: readonly string[];
}

/** A gap starts a new subpath, so missing telemetry is never interpolated. */
export function linePath(points: readonly ChartPoint[], x: (tick: number) => number, y: (value: number) => number): string {
  let penDown = false;
  return points.map((point) => {
    if (point.value === null || !Number.isFinite(point.value)) { penDown = false; return ""; }
    const command = penDown ? "L" : "M";
    penDown = true;
    return `${command}${x(point.tick)},${y(point.value)}`;
  }).join(" ");
}

export function bandPath(points: readonly ChartPoint[], x: (tick: number) => number, y: (value: number) => number): string {
  const segments: ChartPoint[][] = [];
  let segment: ChartPoint[] = [];
  for (const point of points) {
    if (point.lower == null || point.upper == null || !Number.isFinite(point.lower) || !Number.isFinite(point.upper)) {
      if (segment.length) segments.push(segment);
      segment = [];
    } else segment.push(point);
  }
  if (segment.length) segments.push(segment);
  return segments.map((part) => `${part.map((p, i) => `${i ? "L" : "M"}${x(p.tick)},${y(p.upper!)}`).join(" ")} ${[...part].reverse().map((p) => `L${x(p.tick)},${y(p.lower!)}`).join(" ")} Z`).join(" ");
}
