import type { Candidate, NetworkView, TickState } from "../../screens/map/types";

/** Deterministic, wholly invented local grid. No geographic data or hydraulic truth. */
export function createMapFixture(junctions = 250, linkCount?: number): NetworkView {
  const columns = Math.ceil(Math.sqrt(junctions));
  const rows = Math.ceil(junctions / columns);
  let seed = 7303;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const nodes: NetworkView["nodes"] = Array.from({ length: junctions }, (_, i) => ({ id: `J_${i}`, kind: "junction", x: (i % columns) * 100 + random() * 24, y: Math.floor(i / columns) * 100 + random() * 24, elevation_m: 90 + random() * 10, zone: `ZONE_${(i % columns < columns / 2 ? 0 : 1) + (Math.floor(i / columns) < rows / 2 ? 0 : 2)}` }));
  nodes.push({ id: "RESERVOIR", kind: "reservoir", x: -160, y: 700, elevation_m: 125 }, { id: "TANK_A", kind: "tank", x: 400, y: rows * 100, elevation_m: 115 }, { id: "TANK_B", kind: "tank", x: 1100, y: rows * 100, elevation_m: 118 });
  const links: NetworkView["links"] = [];
  const add = (start: string, end: string, kind: "pipe" | "pump" | "valve" = "pipe") => {
    const a = nodes.find((n) => n.id === start)!, b = nodes.find((n) => n.id === end)!;
    const i = links.length;
    links.push({ id: `L_${i}`, kind, start, end, tier: i % 17 === 0 ? "transmission" : i % 4 === 0 ? "submain" : "distribution", diameter_m: 0.25, length_m: i % 11 === 0 ? Math.abs(b.x - a.x) + Math.abs(b.y - a.y) : Math.hypot(b.x - a.x, b.y - a.y), ...(kind === "valve" ? { valve_kind: "prv" as const } : {}), ...(i % 11 === 0 ? { route: [[a.x, a.y], [a.x, b.y], [b.x, b.y]] as [number, number][] } : {}) });
  };
  add("RESERVOIR", "J_0", "pump"); add("TANK_A", "J_1", "pump"); add("TANK_B", "J_2", "pump"); add("J_4", "J_5", "valve"); add("J_6", "J_7", "valve");
  for (let i = 0; i < junctions; i++) {
    if (i % columns !== columns - 1 && i + 1 < junctions) add(`J_${i}`, `J_${i + 1}`);
    if (i + columns < junctions) add(`J_${i}`, `J_${i + columns}`);
  }
  if (linkCount !== undefined) links.splice(linkCount);
  return { schema_version: "1", network_hash: `synthetic-grid-v1-${junctions}`, name: "Synthetic grid", coordinates: "local_m", fidelity: "F0", geometry_label: "ASSUMPTION", attribute_labels: { elevation_m: "ASSUMPTION", diameter_m: "ASSUMPTION", length_m: "CALCULATED" }, nodes, links,
    zones: Array.from({ length: 4 }, (_, i) => { const x = (i % 2) * columns * 50 - 40, y = Math.floor(i / 2) * rows * 50 - 40; return { id: `ZONE_${i}`, name: `District ${i}`, land_use: "mixed", ring: [[x, y], [x + columns * 50, y], [x + columns * 50, y + rows * 50], [x, y + rows * 50], [x, y]] }; }),
    sensors: Array.from({ length: 24 }, (_, i) => ({ id: `SENSOR_${i}`, kind: i < 16 ? "pressure" : i < 22 ? "flow" : "level", element: i < 16 ? `J_${i * 13}` : i < 22 ? `L_${i * 7}` : i === 22 ? "TANK_A" : "TANK_B", sets: ["fixture"] })),
  };
}
export function createTickFixture(network: NetworkView, tick = 0): TickState {
  const labels: TickState["labels"] = {};
  for (const n of network.nodes) labels[n.id] = "MODEL";
  for (const l of network.links) labels[l.id] = "MODEL";
  for (const s of network.sensors) labels[s.element] = "SENSOR_SIM";
  return { pressure: Object.fromEntries(network.nodes.map((n, i) => [n.id, 20 + ((i * 7 + tick) % 55)])), flow: Object.fromEntries(network.links.map((l, i) => [l.id, ((i * 11 + tick) % 190) - 95])), labels };
}
export const MAP_CANDIDATES: Candidate[] = [{ asset_id: "L_40", score: 0.83, label: "MODEL" }, { asset_id: "L_90", score: 0.61, label: "MODEL" }, { asset_id: "J_70", score: 0.42, label: "MODEL" }];
