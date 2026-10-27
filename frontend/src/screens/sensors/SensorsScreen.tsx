import { useMemo, useState } from "react";
import type { TelemetryReading } from "../../generated/telemetry-reading";
import { applySensorWhatIf, createSensorFixtures, SENSOR_CATALOG, TICK_MINUTES, fixtureTickTime } from "../../fixtures/sensors";
import type { SensorDescriptor } from "../../fixtures/sensors";
import { TimeSeriesChart } from "../../ui/charts/TimeSeriesChart";
import { Sparkline } from "../../ui/charts/Sparkline";
import type { ScreenProps } from "../types";
import { SENSOR_STRINGS as S } from "./strings";
import { Value } from "./Value";
import { buildSensorWhatIf } from "./whatif";
import type { SensorWhatIf } from "./whatif";
import "./sensors.css";

type KnownFlag = keyof typeof S.flags;
function knownFlag(flag: string): flag is KnownFlag { return Object.hasOwn(S.flags, flag); }
function Flags({ flags, value }: { flags: readonly string[]; value?: number | null }) {
  return <span className="ug-sensor-flags" data-evidence-label="CALCULATED">
    {flags.length ? flags.map((flag) => <span key={flag} className="ug-sensor-chip" title={knownFlag(flag) ? S.flags[flag].explanation : S.other}>
      {flag === "Q01" && value !== null ? S.late : knownFlag(flag) ? S.flags[flag].name : S.other}
    </span>) : <span className="ug-sensor-ok">{S.ok}</span>}
  </span>;
}

export interface SensorDataQualityProps {
  readings: readonly TelemetryReading[];
  sensors?: readonly SensorDescriptor[];
  onWhatIf: (request: SensorWhatIf) => void;
  onReset: (sensorId: string) => void;
}

/** Integration boundary: only generated telemetry readings and optional display metadata. */
export function SensorDataQuality({ readings, sensors = [], onWhatIf, onReset }: SensorDataQualityProps) {
  const grouped = useMemo(() => {
    const result = new Map<string, TelemetryReading[]>();
    for (const reading of readings) {
      const group = result.get(reading.sensor_id) ?? [];
      group.push(reading);
      result.set(reading.sensor_id, group);
    }
    for (const group of result.values()) group.sort((a, b) => a.tick - b.tick);
    return result;
  }, [readings]);
  const [selection, setSelection] = useState<string>();
  const selected = selection && grouped.has(selection) ? selection : grouped.keys().next().value;
  const history = selected ? grouped.get(selected) ?? [] : [];
  const lastTick = history.at(-1)?.tick ?? 0;
  const [cursor, setCursor] = useState(432);
  const nowTick = Math.max(history[0]?.tick ?? 0, Math.min(cursor, lastTick));
  const current = history.find((reading) => reading.tick === nowTick);
  const [rate, setRate] = useState("0.05");
  const [message, setMessage] = useState("");
  const points = history.map((reading) => ({ tick: reading.tick, value: reading.value, flags: reading.quality?.flags }));
  function apply(mode: SensorWhatIf["mode"]) {
    if (!selected) return;
    try {
      const action = mode === "drift" ? { mode, drift_per_hour: rate.trim() === "" ? NaN : Number(rate) } : { mode };
      onWhatIf(buildSensorWhatIf(selected, nowTick, action));
      setMessage(S.applied);
    } catch { setMessage(S.error); }
  }
  if (!selected) return <p>{S.noData}</p>;
  return <div className="ug-sensors-layout">
    <section className="ug-sensor-panel" aria-label={S.inventory}>
      <h2>{S.inventory}</h2>
      <div className="ug-sensor-table-scroll">
        <table className="ug-sensor-table">
          <thead><tr>{[S.sensor, S.kind, S.zone, S.latest, S.quality, S.trend].map((heading) => <th key={heading} scope="col">{heading}</th>)}</tr></thead>
          <tbody>{[...grouped].map(([id, sensorReadings]) => {
            const latest = sensorReadings.at(-1)!;
            const meta = sensors.find((sensor) => sensor.id === id);
            // Q01 has two display names, derived only from each reading's value.
            const flagReadings = new Map<string, { code: string; value: number | null }>();
            for (const reading of sensorReadings) for (const code of reading.quality?.flags ?? []) {
              const key = code === "Q01" && reading.value === null ? "missing" : code;
              flagReadings.set(key, { code, value: reading.value });
            }
            return <tr key={id} data-selected={selected === id}>
              <th scope="row"><button type="button" aria-pressed={selected === id} onClick={() => { setSelection(id); setMessage(""); }}><code data-identifier>{id}</code></button></th>
              <td>{meta ? S.kinds[meta.kind] : S.unknown}</td>
              <td>{meta ? S.zones[meta.zone] ?? S.unknown : S.unknown}</td>
              <td><Value label={latest.label}>{latest.value === null ? S.unavailable : latest.value.toFixed(2)}{S.space}{latest.unit}</Value><small className="ug-sensor-evidence">{latest.label}</small></td>
              <td>{flagReadings.size ? [...flagReadings].map(([key, flag]) => <Flags key={key} flags={[flag.code]} value={flag.value} />) : <Flags flags={[]} />}</td>
              <td><Sparkline points={sensorReadings.map((reading) => ({ tick: reading.tick, value: reading.value }))} /></td>
            </tr>;
          })}</tbody>
        </table>
      </div>
    </section>
    <section className="ug-sensor-panel" aria-label={S.detail}>
      <h2><code data-identifier>{selected}</code></h2>
      <p className="ug-sensor-muted">{S.preview}</p>
      <TimeSeriesChart title={S.history} series={[{ id: selected, name: selected, unit: history[0]?.unit ?? "", label: history[0]?.label ?? "SENSOR_SIM", points }]} nowTick={nowTick} tickMinutes={TICK_MINUTES} />
      <div className="ug-sensor-cursor">
        <label htmlFor="sensor-replay-cursor">{S.cursor}</label>
        <time dateTime={fixtureTickTime(nowTick)}>{fixtureTickTime(nowTick)}{S.openTick}{nowTick}{S.closeTick}</time>
        <input id="sensor-replay-cursor" type="range" min={history[0]?.tick ?? 0} max={lastTick} step="1" value={nowTick} onChange={(event) => setCursor(Number(event.target.value))} />
      </div>
      <fieldset className="ug-sensor-whatif">
        <legend>{S.whatIf}</legend>
        <p>{S.scope}</p>
        <label htmlFor="sensor-drift-rate">{S.rate}</label>
        <input id="sensor-drift-rate" type="number" step="any" value={rate} onChange={(event) => setRate(event.target.value)} />
        <div className="ug-sensor-actions">
          <button type="button" onClick={() => apply("disable")}>{S.disable}</button>
          <button type="button" disabled={current?.value == null} onClick={() => apply("stuck")}>{S.stuck}</button>
          <button type="button" onClick={() => apply("drift")}>{S.drift}</button>
          <button type="button" onClick={() => { onReset(selected); setMessage(S.applied); }}>{S.reset}</button>
        </div>
        <p role="status">{message}</p>
      </fieldset>
      <h3>{S.quality}</h3>
      <dl className="ug-sensor-explanations">{Object.entries(S.flags).map(([flag, text]) => <div key={flag}>
        <dt><Flags flags={[flag]} value={null} /></dt><dd>{text.explanation}</dd>
      </div>)}</dl>
    </section>
  </div>;
}

/** Fixture host injects a local effect; production wiring can render SensorDataQuality directly. */
export function SensorsScreen({ route }: ScreenProps) {
  const baseline = useMemo(() => createSensorFixtures(), []);
  const [requests, setRequests] = useState<ReadonlyMap<string, SensorWhatIf>>(new Map());
  const readings = useMemo(() => {
    let result = baseline;
    for (const request of requests.values()) result = applySensorWhatIf(result, request);
    return result;
  }, [baseline, requests]);
  return <div className="ug-sensors">
    <h1>{route.title}</h1>
    <p>{route.empty}</p>
    <p className="ug-sensor-fixture">{S.fixture}</p>
    <SensorDataQuality readings={readings} sensors={SENSOR_CATALOG} onWhatIf={(request) => {
      setRequests((previous) => {
        const next = new Map(previous);
        next.set(request.sensor_id, request);
        return next;
      });
    }} onReset={(sensorId) => setRequests((previous) => {
      const next = new Map(previous);
      next.delete(sensorId);
      return next;
    })} />
  </div>;
}
