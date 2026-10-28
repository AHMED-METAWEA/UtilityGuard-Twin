import { describe, expect, it } from "vitest";
import { bounds, candidateRings, colour, fitBounds, FLOW_DOMAIN, linkPath, pathCentre, PRESSURE_DOMAIN, tierWidth } from "./layers";
import { createMapFixture, createTickFixture } from "../../fixtures/map";
import type { NetworkView, Point } from "./types";

const empty: NetworkView = { ...createMapFixture(), nodes: [], links: [], zones: [], sensors: [] };
const low: [number, number, number] = [10, 20, 30], high: [number, number, number] = [110, 220, 230], missing: [number, number, number] = [50, 50, 50];
describe("map geometry and styling", () => {
  it("bounds includes nodes, bends and zone edges; empty bounds are usable", () => {
    expect(bounds(empty)).toEqual([[0, 0], [1, 1]]);
    const network = createMapFixture();
    network.links[0]!.route = [[-900, -800], [8000, 9000]];
    network.zones[0]!.ring.push([-1000, -2000]);
    expect(bounds(network)).toEqual([[-1000, -2000], [8000, 9000]]);
  });
  it("fits and centres bounds within a padded viewport, including degenerate bounds", () => {
    const view = fitBounds([[0, 0], [1000, 500]], 800, 600);
    expect(view.target).toEqual([500, 250, 0]);
    expect(1000 * 2 ** view.zoom).toBeLessThanOrEqual(736);
    expect(500 * 2 ** view.zoom).toBeLessThanOrEqual(536);
    expect(Number.isFinite(fitBounds([[2, 2], [2, 2]], 0, 0).zoom)).toBe(true);
  });
  it("uses supplied route or resolves endpoints, and handles unresolved links", () => {
    const positions = new Map<string, Point>([["a", [0, 0]], ["b", [100, 20]]]);
    const link = { id: "l", start: "a", end: "b", kind: "pipe" as const };
    expect(linkPath(link, positions)).toEqual([[0, 0], [100, 20]]);
    const route: Point[] = [[0, 0], [0, 20], [100, 20]];
    expect(linkPath({ ...link, route }, positions)).toBe(route);
    expect(linkPath({ ...link, route: [[1, 1]] }, positions)).toEqual([[0, 0], [100, 20]]);
    expect(linkPath({ ...link, end: "missing" }, positions)).toEqual([]);
  });
  it("places equipment and candidate centres halfway along bent paths", () => {
    expect(pathCentre([])).toBeUndefined();
    expect(pathCentre([[2, 3]])).toEqual([2, 3]);
    expect(pathCentre([[0, 0], [0, 10], [90, 10]])).toEqual([40, 10]);
    expect(pathCentre([[1, 1], [1, 1]])).toEqual([1, 1]);
  });
  it.each([PRESSURE_DOMAIN, FLOW_DOMAIN])("clamps sequential scale domain %s–%s, interpolates and marks missing", (min, max) => {
    const scale = (v: number | undefined) => colour(v, [min, max], low, high, missing);
    expect(scale(min)).toEqual(low);
    expect(scale(max)).toEqual(high);
    expect(scale(min - 1000)).toEqual(low);
    expect(scale(max + 1000)).toEqual(high);
    expect(scale((min + max) / 2)).toEqual([60, 120, 130]);
    expect(scale(undefined)).toEqual(missing);
    expect(scale(NaN)).toEqual(missing);
    expect(scale(Infinity)).toEqual(missing);
    expect(scale(12)).toEqual(scale(12));
  });
  it("assigns distinct tier widths with distribution as the default", () => {
    expect([tierWidth("transmission"), tierWidth("submain"), tierWidth("distribution"), tierWidth(undefined)]).toEqual([5, 3, 1.5, 1.5]);
  });
  it("ranks top three located unique finite candidates deterministically, without mutating input", () => {
    const positions = new Map<string, Point>(["a", "b", "c", "d"].map((id, i) => [id, [i, i]]));
    const candidates = ["d", "c", "b", "a", "a", "unknown"].map((asset_id) => ({ asset_id, score: 0.5, label: "MODEL" as const }));
    candidates.push({ asset_id: "d", score: NaN, label: "MODEL" });
    const rings = candidateRings(candidates, positions);
    expect(rings.map((r) => [r.id, r.rank, r.radius])).toEqual([["a", 1, 24], ["b", 2, 19], ["c", 3, 14]]);
    expect(candidates[0]!.asset_id).toBe("d");
    expect(candidateRings([], positions)).toEqual([]);
    expect(candidateRings([{ asset_id: "d", score: 0.9, label: "MODEL" }, ...candidates], positions)[0]!.id).toBe("d");
  });
});

describe("synthetic map fixtures", () => {
  it("generates deterministic local geometry, equipment and sensor inventory", () => {
    const n = createMapFixture();
    expect(n).toEqual(createMapFixture());
    expect(n.geometry_label).toBe("ASSUMPTION");
    expect(n.fidelity).toBe("F0");
    expect(n.coordinates).toBe("local_m");
    expect(n.nodes.filter((x) => x.kind === "junction")).toHaveLength(250);
    expect(n.nodes.filter((x) => x.kind === "reservoir")).toHaveLength(1);
    expect(n.nodes.filter((x) => x.kind === "tank")).toHaveLength(2);
    expect(n.links.filter((x) => x.kind === "pump")).toHaveLength(3);
    expect(n.links.filter((x) => x.valve_kind === "prv")).toHaveLength(2);
    expect(n.zones).toHaveLength(4);
    expect(n.sensors).toHaveLength(24);
    const ids = new Set([...n.nodes, ...n.links].map((x) => x.id));
    expect(n.sensors.every((s) => ids.has(s.element))).toBe(true);
    const tick = createTickFixture(n);
    expect(tick).toEqual(createTickFixture(n));
    expect(tick).not.toEqual(createTickFixture(n, 1));
    expect(tick.labels.J_0).toBe("SENSOR_SIM");
    expect(tick.labels.J_1).toBe("MODEL");
    const stress = createMapFixture(800, 1100);
    expect(stress.nodes.filter((x) => x.kind === "junction")).toHaveLength(800);
    expect(stress.links).toHaveLength(1100);
  });
});
