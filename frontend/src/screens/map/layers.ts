import type { Candidate, NetworkLink, NetworkView, Point } from "./types";
export type RGB = [number, number, number];
export const PRESSURE_DOMAIN: [number, number] = [0, 80];
export const FLOW_DOMAIN: [number, number] = [0, 100];

/** Include routed vertices and zone rings, not just endpoints. Empty bounds remain usable. */
export function bounds(network: NetworkView): [Point, Point] {
  const points: Point[] = [...network.nodes.map((n): Point => [n.x, n.y]), ...network.links.flatMap((l) => l.route ?? []), ...network.zones.flatMap((z) => z.ring)];
  if (!points.length) return [[0, 0], [1, 1]];
  return points.reduce<[Point, Point]>(([[a, b], [c, d]], [x, y]) => [[Math.min(a, x), Math.min(b, y)], [Math.max(c, x), Math.max(d, y)]], [[Infinity, Infinity], [-Infinity, -Infinity]]);
}
export function fitBounds(box: [Point, Point], width: number, height: number) {
  const [[x0, y0], [x1, y1]] = box;
  return { target: [(x0 + x1) / 2, (y0 + y1) / 2, 0] as [number, number, number], zoom: Math.log2(Math.max(1, Math.min(width, height) - 64) / Math.max(x1 - x0, y1 - y0, 1)), minZoom: -12, maxZoom: 5 };
}
export function linkPath(link: NetworkLink, nodes: ReadonlyMap<string, Point>): Point[] {
  if (link.route && link.route.length >= 2) return link.route;
  const start = nodes.get(link.start), end = nodes.get(link.end);
  return start && end ? [start, end] : [];
}
/** Sequential token interpolation; missing values use the neutral token, never zero. */
export function colour(value: number | undefined, domain: [number, number], low: RGB, high: RGB, missing: RGB): RGB {
  if (value === undefined || !Number.isFinite(value)) return missing;
  const t = Math.max(0, Math.min(1, (value - domain[0]) / (domain[1] - domain[0])));
  return low.map((v, i) => Math.round(v + (high[i]! - v) * t)) as RGB;
}
export function tierWidth(tier: NetworkLink["tier"]): number { return tier === "transmission" ? 5 : tier === "submain" ? 3 : 1.5; }
/** Arc-length midpoint handles bends and uneven segment spacing. */
export function pathCentre(path: Point[]): Point | undefined {
  if (!path.length) return undefined;
  const lengths = path.slice(1).map((p, i) => Math.hypot(p[0] - path[i]![0], p[1] - path[i]![1]));
  let remaining = lengths.reduce((a, b) => a + b, 0) / 2;
  for (let i = 0; i < lengths.length; i++) {
    const length = lengths[i]!;
    if (length > 0 && remaining <= length) { const a = path[i]!, b = path[i + 1]!; return [a[0] + (b[0] - a[0]) * remaining / length, a[1] + (b[1] - a[1]) * remaining / length]; }
    remaining -= length;
  }
  return path[0];
}
export function candidateRings(candidates: readonly Candidate[], positions: ReadonlyMap<string, Point>) {
  const seen = new Set<string>();
  return [...candidates].filter((c) => Number.isFinite(c.score) && positions.has(c.asset_id)).sort((a, b) => b.score - a.score || (a.asset_id < b.asset_id ? -1 : a.asset_id > b.asset_id ? 1 : 0)).filter((c) => { if (seen.has(c.asset_id)) return false; seen.add(c.asset_id); return true; }).slice(0, 3).map((c, i) => ({ ...c, id: c.asset_id, position: positions.get(c.asset_id)!, rank: i + 1, radius: 24 - i * 5 }));
}
