import { useReplay, replayTick } from "../../app/api";
import { useEffect, useMemo, useRef, useState } from "react";
// The 9.4.0 root barrel eagerly imports optional widgets, whose peer is absent.
// Use the installed, typed component directly; no widget dependency or loader is needed.
import DeckGL from "../../../node_modules/@deck.gl/react/dist/deckgl.js";
import { COORDINATE_SYSTEM, OrthographicView } from "@deck.gl/core";
import type { PickingInfo } from "@deck.gl/core";
import { PathLayer, PolygonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { ScreenProps } from "../types";
import type { Candidate, NetworkView, Point, TickState } from "./types";
import { bounds, candidateRings, colour, fitBounds, FLOW_DOMAIN, linkPath, pathCentre, PRESSURE_DOMAIN, tierWidth } from "./layers";
import type { RGB } from "./layers";
import { MAP_STRINGS as S } from "./strings";
import { createMapFixture, createTickFixture, MAP_CANDIDATES } from "../../fixtures/map";
import "./map.css";

const VIEW = new OrthographicView({ id: "network", flipY: false });
const INITIAL = { zones: true, links: true, nodes: true, equipment: true, sensors: true, faults: true, pressure: true, flow: false };
type Toggle = keyof typeof INITIAL;
type Asset = { id: string; element?: string };
type Palette = { low: RGB; high: RGB; neutral: RGB; warning: RGB };

/** Reads the existing CSS tokens; no duplicate colour literals in the map. */
function readPalette(element: HTMLElement): Palette {
  const style = getComputedStyle(element);
  const read = (name: string): RGB => {
    const value = style.getPropertyValue(name).trim();
    const hex = value.replace("#", "");
    if (/^[a-f\d]{6}$/i.test(hex)) return [0, 2, 4].map((offset) => parseInt(hex.slice(offset, offset + 2), 16)) as RGB;
    // Also accept rgb()/rgba() token definitions.
    const channels = value.match(/[\d.]+/g)?.slice(0, 3).map(Number);
    return channels?.length === 3 ? channels as RGB : [0, 0, 0];
  };
  return { low: read("--ug-border"), high: read("--ug-accent"), neutral: read("--ug-muted"), warning: read("--ug-warn") };
}

export interface NetworkMapProps { fixture?: boolean; network: NetworkView; state: TickState; candidates: readonly Candidate[] }

/** Fixture-independent boundary ready for a validated network-view and telemetry/model snapshot. */
export function NetworkMap({ network, state, candidates, fixture = true }: NetworkMapProps) {
  const host = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [palette, setPalette] = useState<Palette>();
  const [active, setActive] = useState(INITIAL);
  const [fit, setFit] = useState(0);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<Asset>();
  useEffect(() => {
    const element = host.current!;
    setPalette(readPalette(element));
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => { if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height }); });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const geometry = useMemo(() => {
    const positions = new Map<string, Point>(network.nodes.map((n) => [n.id, [n.x, n.y]]));
    const paths = network.links.map((l) => ({ ...l, path: linkPath(l, positions) }));
    for (const link of paths) { const centre = pathCentre(link.path); if (centre) positions.set(link.id, centre); }
    return { positions, paths, equipment: [
      ...network.nodes.filter((n) => n.kind !== "junction").map((n) => ({ id: n.id, position: positions.get(n.id)!, radius: n.kind === "reservoir" ? 15 : 12 })),
      ...paths.filter((l) => l.kind === "pump" || l.valve_kind === "prv").flatMap((l) => { const position = positions.get(l.id); return position ? [{ id: l.id, position, radius: l.kind === "pump" ? 9 : 6 }] : []; }),
    ], sensors: network.sensors.flatMap((s) => { const position = positions.get(s.element); return position ? [{ ...s, position }] : []; }) };
  }, [network]);
  const rings = useMemo(() => candidateRings(candidates, geometry.positions), [candidates, geometry]);
  const initialViewState = useMemo(() => fitBounds(bounds(network), size.width, size.height), [network, size]);
  const layers = useMemo(() => {
    if (!palette) return [];
    const common = { coordinateSystem: COORDINATE_SYSTEM.CARTESIAN, pickable: true };
    return [
      new PolygonLayer<NetworkView["zones"][number]>({ ...common, id: "zones", data: network.zones, visible: active.zones, getPolygon: (z) => z.ring, getFillColor: [...palette.high, 18], getLineColor: [...palette.neutral, 100], stroked: true, lineWidthUnits: "pixels", getLineWidth: 1 }),
      new PathLayer<typeof geometry.paths[number]>({ ...common, id: "links", data: geometry.paths, visible: active.links, getPath: (l) => l.path, widthUnits: "pixels", getWidth: (l) => tierWidth(l.tier), getColor: (l) => active.flow ? colour(state.flow[l.id] === undefined ? undefined : Math.abs(state.flow[l.id]!), FLOW_DOMAIN, palette.low, palette.high, palette.neutral) : palette.neutral, updateTriggers: { getColor: [state, active.flow, palette] } }),
      new ScatterplotLayer<NetworkView["nodes"][number]>({ ...common, id: "nodes", data: network.nodes.filter((n) => n.kind === "junction"), visible: active.nodes, getPosition: (n) => [n.x, n.y], radiusUnits: "pixels", getRadius: 3.5, getFillColor: (n) => active.pressure ? colour(state.pressure[n.id], PRESSURE_DOMAIN, palette.low, palette.high, palette.neutral) : palette.neutral, updateTriggers: { getFillColor: [state, active.pressure, palette] } }),
      new ScatterplotLayer<typeof geometry.equipment[number]>({ ...common, id: "equipment", data: geometry.equipment, visible: active.equipment, getPosition: (e) => e.position, radiusUnits: "pixels", getRadius: (e) => e.radius, getFillColor: palette.warning, stroked: true, getLineColor: palette.neutral, lineWidthUnits: "pixels", getLineWidth: 1 }),
      new ScatterplotLayer<typeof geometry.sensors[number]>({ ...common, id: "sensors", data: geometry.sensors, visible: active.sensors, getPosition: (s) => s.position, radiusUnits: "pixels", getRadius: 10, filled: false, stroked: true, getLineColor: palette.high, lineWidthUnits: "pixels", getLineWidth: 2 }),
      new ScatterplotLayer<typeof rings[number]>({ ...common, id: "candidates", data: rings, visible: active.faults, getPosition: (r) => r.position, radiusUnits: "pixels", getRadius: (r) => r.radius, filled: false, stroked: true, getLineColor: palette.warning, lineWidthUnits: "pixels", getLineWidth: 2 }),
    ];
  }, [network, state, geometry, palette, active, rings]);
  const elementId = hover?.element ?? hover?.id;
  const node = network.nodes.find((n) => n.id === elementId);
  const link = network.links.find((l) => l.id === elementId);
  const candidate = rings.find((r) => r.id === elementId);
  const label = elementId ? state.labels[elementId] ?? "MODEL" : "MODEL";
  const legend: Record<Toggle, string> = { zones: S.zoneLegend, links: S.linkLegend, nodes: S.nodeLegend, equipment: S.equipmentLegend, sensors: S.sensorLegend, faults: S.faultLegend, pressure: S.pressureLegend, flow: S.flowLegend };
  const value = (name: string, amount: number | undefined, unit: string, evidence: string) => <div>{name}{S.separator}<span data-evidence-label={evidence}>{amount === undefined ? S.unavailable : amount.toFixed(2)}{unit}{S.separator}{evidence}</span></div>;
  return <div className="ug-network-map">
    {fixture && <p className="ug-map-fixture">{S.fixture}</p>}
    <p data-evidence-label={network.geometry_label}>{network.fidelity === "F1" && network.geometry_label === "PUBLIC_GEOMETRY" ? S.f1 : S.fidelity}</p>
    {network.geometry_label === "PUBLIC_GEOMETRY" && <p data-evidence-label="PUBLIC_GEOMETRY">{S.attribution}{network.attribution && <span>{S.space}{network.attribution}</span>}</p>}
    <div className="ug-map-layout">
      <aside className="ug-map-panel">
        <fieldset><legend>{S.layers}</legend>{(Object.keys(INITIAL) as Toggle[]).map((key) => <label key={key}><input type="checkbox" checked={active[key]} onChange={() => { setActive((old) => ({ ...old, [key]: !old[key] })); setHover(undefined); }} />{S[key]}</label>)}</fieldset>
        <button type="button" onClick={() => setFit((v) => v + 1)}>{S.fit}</button>
        <section aria-label={S.legend}><h2>{S.legend}</h2><ul>{(Object.keys(active) as Toggle[]).filter((key) => active[key]).map((key) => <li key={key} data-layer-legend={key} data-evidence-label={key === "pressure" || key === "flow" || key === "faults" ? "MODEL" : key === "sensors" ? "SENSOR_SIM" : key === "nodes" ? network.geometry_label : "ASSUMPTION"}>
          {(key === "pressure" || key === "flow") && <span className="ug-map-scale" />}{legend[key]}{key === "nodes" && <span>{S.separator}{network.geometry_label}</span>}
        </li>)}</ul></section>
        {active.faults && <section aria-label={S.candidates}><h2>{S.candidates}</h2><ol className="ug-map-candidates">{rings.map((r) => <li key={r.id}><span data-evidence-label={r.label}>{S.rank}{S.space}{r.rank}{S.separator}{r.label}</span>{S.space}<code data-identifier>{r.id}</code>{value(S.score, r.score, "", r.label)}</li>)}</ol></section>}
      </aside>
      <div>
        <p>{S.help}</p>
        <div className="ug-map-canvas" ref={host} role="region" aria-label={S.map} data-map-ready={ready}>
          {palette && size.width > 0 && <DeckGL key={fit} views={VIEW} initialViewState={initialViewState} controller useDevicePixels={1} layers={layers} onAfterRender={() => setReady(true)} onError={() => setFailed(true)} onHover={(info: PickingInfo<Asset>) => setHover(info.object)} />}
          {failed && <p role="alert">{S.failed}</p>}
          {hover && <div className="ug-map-tooltip" role="tooltip"><code data-identifier>{hover.id}</code>
            {node && <>{value(S.pressure, state.pressure[node.id], S.metres, label)}{value(S.elevation, node.elevation_m, S.metres, network.attribute_labels.elevation_m)}</>}
            {link && <>{value(S.flowValue, state.flow[link.id], S.flowUnit, label)}{value(S.diameter, link.diameter_m, S.metres, network.attribute_labels.diameter_m)}{value(S.length, link.length_m, S.metres, network.attribute_labels.length_m)}</>}
            {candidate && value(S.score, candidate.score, "", candidate.label)}
          </div>}
        </div>
      </div>
    </div>
  </div>;
}

export function NetworkMapScreen({ route }: ScreenProps) {
  const { replay, reason } = useReplay();
  const fixture = useMemo(() => createMapFixture(), []);
  const network = replay?.network ?? fixture;
  const state = useMemo(() => replay ? replayTick(replay) : createTickFixture(network), [network, replay]);
  return <><h1>{route.title}</h1><p>{replay ? "Recorded sensor snapshot" : route.empty}</p>{!replay && <p role="status">{reason}</p>}<NetworkMap fixture={!replay} network={network} state={state} candidates={replay ? [] : MAP_CANDIDATES} /></>;
}
