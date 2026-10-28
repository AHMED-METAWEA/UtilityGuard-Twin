import { createContext, useContext, useEffect, useState } from "react";
import type { NetworkView as ContractNetwork } from "../generated/network-view";
import type { TimeSeries } from "../generated/time-series";
import type { NetworkView, TickState } from "../screens/map/types";

export interface Replay { runId: string; network: NetworkView; series: TimeSeries[] }
export type ReplayState = { replay: Replay | null; reason: string };
export const ReplayContext = createContext<ReplayState>({ replay: null, reason: "Loading recorded runs" });
export const useReplay = () => useContext(ReplayContext);
const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const id = (v: unknown): v is string => typeof v === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$/.test(v);
const point = (v: unknown) => Array.isArray(v) && v.length === 2 && v.every(finite);
function safe(value: unknown): void {
  if (Array.isArray(value)) value.forEach(safe);
  else if (record(value)) for (const [key, child] of Object.entries(value)) {
    if (/truth|hidden|fault_tag|faulttag|injected|ground_truth/i.test(key)) throw new Error("Unsafe API payload");
    safe(child);
  }
}
function fields(v: Record<string, unknown>, required: string[], optional: string[] = []) {
  return required.every((k) => k in v) && Object.keys(v).every((k) => [...required, ...optional].includes(k));
}
function networkShape(v: unknown): v is ContractNetwork {
  if (!record(v) || !fields(v, ["schema_version", "network_hash", "name", "fidelity", "coordinates", "geometry_label", "attribute_labels", "nodes", "links", "zones", "sensors"], ["attribution"])) return false;
  if (v.schema_version !== "1" || typeof v.network_hash !== "string" || !/^[a-f0-9]{64}$/.test(v.network_hash) || typeof v.name !== "string" || !v.name || !["F0", "F1"].includes(String(v.fidelity)) || v.coordinates !== "local_m" || !["ASSUMPTION", "PUBLIC_GEOMETRY"].includes(String(v.geometry_label))) return false;
  if (v.fidelity === "F1" && v.geometry_label !== "PUBLIC_GEOMETRY") return false;
  if (v.geometry_label === "PUBLIC_GEOMETRY" && (typeof v.attribution !== "string" || !v.attribution)) return false;
  const a = v.attribute_labels;
  if (!record(a) || !fields(a, ["elevation_m", "diameter_m", "length_m"]) || !["ASSUMPTION", "OBSERVED", "BENCHMARK"].includes(String(a.elevation_m)) || !["ASSUMPTION", "OBSERVED", "BENCHMARK"].includes(String(a.diameter_m)) || !["CALCULATED", "OBSERVED", "BENCHMARK"].includes(String(a.length_m))) return false;
  if (!Array.isArray(v.nodes) || !v.nodes.length || !v.nodes.every((n) => record(n) && fields(n, ["id", "kind", "x", "y", "elevation_m"], ["zone"]) && id(n.id) && ["junction", "tank", "reservoir"].includes(String(n.kind)) && [n.x, n.y, n.elevation_m].every(finite) && (n.zone === undefined || id(n.zone)))) return false;
  const nodes = new Set(v.nodes.map((n) => n.id));
  if (nodes.size !== v.nodes.length || !Array.isArray(v.links) || !v.links.every((l) => record(l) && fields(l, ["id", "kind", "start", "end"], ["tier", "diameter_m", "length_m", "valve_kind", "route"]) && id(l.id) && ["pipe", "pump", "valve"].includes(String(l.kind)) && nodes.has(l.start) && nodes.has(l.end) && [l.diameter_m, l.length_m].every((n) => n === undefined || finite(n) && n > 0) && (l.tier === undefined || ["transmission", "submain", "distribution"].includes(String(l.tier))) && (l.valve_kind === undefined || ["isolation", "prv"].includes(String(l.valve_kind))) && (l.route === undefined || Array.isArray(l.route) && l.route.length >= 2 && l.route.every(point)))) return false;
  const elements = new Set([...nodes, ...v.links.map((l) => l.id)]);
  if (elements.size !== nodes.size + v.links.length) return false;
  return Array.isArray(v.zones) && v.zones.every((z) => record(z) && fields(z, ["id", "name", "land_use", "ring"]) && id(z.id) && typeof z.name === "string" && id(z.land_use) && Array.isArray(z.ring) && z.ring.length >= 4 && z.ring.every(point)) && Array.isArray(v.sensors) && v.sensors.every((s) => record(s) && fields(s, ["id", "kind", "element", "sets"]) && id(s.id) && ["pressure", "flow", "level"].includes(String(s.kind)) && elements.has(s.element) && Array.isArray(s.sets) && s.sets.every(id));
}
function seriesShape(v: unknown, runId: string): v is TimeSeries {
  if (!record(v) || !fields(v, ["schema_version", "series_id", "run_id", "kind", "element", "quantity", "unit", "label", "start", "step_seconds", "values"], ["version", "formula_ref", "band"])) return false;
  return v.schema_version === "1" && id(v.series_id) && v.run_id === runId && id(v.element) && v.kind === "sensor" && v.label === "SENSOR_SIM" && ["pressure", "flow", "level"].includes(String(v.quantity)) && v.unit === (v.quantity === "flow" ? "L/s" : "m") && typeof v.start === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(v.start) && Number.isFinite(Date.parse(v.start)) && finite(v.step_seconds) && Number.isInteger(v.step_seconds) && v.step_seconds > 0 && Array.isArray(v.values) && v.values.length > 0 && v.values.every((n) => n === null || finite(n));
}
async function get(path: string, signal?: AbortSignal): Promise<unknown> {
  // All paths are constructed here, never supplied as a URL by a payload.
  if (!/^\/api\/runs(?:\/[A-Za-z0-9_.:@-]+)*$/.test(path)) throw new Error("Invalid API path");
  const response = await fetch(path, { signal, credentials: "same-origin" });
  if (!response.ok) throw new Error("Recorded-run API unavailable");
  const value: unknown = await response.json();
  safe(value);
  return value;
}
export async function loadReplay(signal?: AbortSignal): Promise<ReplayState> {
  try {
    const runs = await get("/api/runs", signal);
    if (!Array.isArray(runs) || !runs.every((r) => record(r) && fields(r, ["run_id", "scenario_id", "seed", "simulation_start"]) && id(r.run_id) && id(r.scenario_id) && finite(r.seed) && Number.isInteger(r.seed) && r.seed >= 0 && typeof r.simulation_start === "string")) throw new Error("Invalid run list");
    if (!runs.length) return { replay: null, reason: "No recorded runs available" };
    const runId: string = runs[0].run_id;
    const prefix = `/api/runs/${encodeURIComponent(runId)}`;
    const network = await get(`${prefix}/network`, signal);
    if (!networkShape(network)) throw new Error("Invalid recorded network");
    const index = await get(`${prefix}/series`, signal);
    if (!Array.isArray(index) || !index.every((s) => record(s) && fields(s, ["series_id", "kind", "element", "label"]) && id(s.series_id) && id(s.element) && ["sensor", "expectation", "residual", "demand_forecast", "tank_forecast"].includes(String(s.kind)) && s.label === (s.kind === "sensor" ? "SENSOR_SIM" : s.kind === "residual" ? "CALCULATED" : "MODEL"))) throw new Error("Invalid series index");
    const series: TimeSeries[] = [];
    for (const entry of index.filter((s) => s.kind === "sensor")) {
      const value = await get(`${prefix}/series/${encodeURIComponent(entry.series_id)}`, signal);
      if (!seriesShape(value, runId) || value.series_id !== entry.series_id || value.element !== entry.element || !network.sensors.some((s) => s.element === value.element && s.kind === value.quantity) || series.some((s) => s.series_id === value.series_id) || series.length && (series[0]!.start !== value.start || series[0]!.step_seconds !== value.step_seconds || series[0]!.values.length !== value.values.length)) throw new Error("Invalid recorded sensor series");
      series.push(value);
    }
    if (!series.length) throw new Error("No recorded sensor series");
    // The generator currently represents coordinate tuples as never[]. The
    // runtime guard above checks each coordinate before the map boundary.
    return { replay: { runId, network: network as unknown as NetworkView, series }, reason: "" };
  } catch (error) {
    return { replay: null, reason: error instanceof Error && !/JSON|token/i.test(error.message) ? error.message : "Invalid recorded-run payload" };
  }
}
export function useRecordedRun(enabled = true): ReplayState {
  const [state, setState] = useState<ReplayState>({ replay: null, reason: "Loading recorded runs" });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    void loadReplay(controller.signal).then((next) => { if (!controller.signal.aborted) setState(next); });
    return () => controller.abort();
  }, [enabled]);
  return state;
}
export function replayTick(replay: Replay): TickState {
  const state: TickState = { pressure: {}, flow: {}, labels: {} };
  for (const series of replay.series) {
    const value = series.values.at(-1);
    if (value === null || value === undefined || series.quantity === "level") continue;
    if (series.quantity === "pressure") state.pressure[series.element] = value;
    if (series.quantity === "flow") state.flow[series.element] = value;
    state.labels[series.element] = "SENSOR_SIM";
  }
  return state;
}
