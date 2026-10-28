import { useState } from "react";
import type { ScenarioConfiguration, Fault } from "../../generated/scenario-config";
import { createScenarioFixtures, inputEvidence, recordFixture } from "../../fixtures/scenarios";
import { Identifier } from "../../ui/Identifier";
import { Metric } from "../../ui/Metric";
import { Panel } from "../../ui/Panel";
import { TimeSeriesChart } from "../../ui/charts/TimeSeriesChart";
import { formatValue } from "../../ui/format";
import type { ScreenProps } from "../types";
import { SCENARIO_STRINGS as S } from "./strings";
import "./scenarios.css";

const fixtures = createScenarioFixtures();
function InputValue({ config, name, value, unit = null }: { config: ScenarioConfiguration; name: string; value: string | number | boolean; unit?: string | null }) {
  const evidence = inputEvidence(config, name, value, unit);
  return <Metric value={value} unit={unit} label={S.labels.assumption} evidence={evidence} />;
}
function onset(hour: number) { return <time dateTime={`PT${hour}H`}>{formatValue(hour)}{S.units.hours}</time>; }
function element(fault: Fault): string {
  for (const key of ["location", "sensor_id", "pump_id", "zone_id", "rtu_group", "valve_id", "node", "station_id"] as const) {
    if (key in fault) return String((fault as unknown as Record<string, unknown>)[key]);
  }
  return "";
}

export interface ScenarioLabProps {
  onLaunch: (config: ScenarioConfiguration) => void | Promise<void>;
}
/** Design/evaluation boundary. No telemetry, detector or operator-view output. */
export function ScenarioLab({ onLaunch }: ScenarioLabProps) {
  const [selected, select] = useState(0);
  const [statuses, setStatuses] = useState<Record<string, "launching" | "recorded" | "failed">>({});
  const fixture = fixtures[selected]!;
  const { config, id, impact } = fixture;
  const status = statuses[id];
  async function launch() {
    setStatuses((previous) => ({ ...previous, [id]: "launching" }));
    try {
      await onLaunch(config);
      setStatuses((previous) => ({ ...previous, [id]: "recorded" }));
    } catch {
      setStatuses((previous) => ({ ...previous, [id]: "failed" }));
    }
  }
  return <div className="ug-scenarios">
    <h1>{S.title}</h1>
    <p className="ug-scenario-notice">{S.notice}</p>
    <p className="ug-fixture-marker">{S.fixture}</p>
    <Panel title={S.choose}><div className="ug-scenario-choices">{fixtures.map((item, index) => <button type="button" key={item.id}
      aria-pressed={selected === index} onClick={() => select(index)}>{S.scenarios[item.id].name}</button>)}</div></Panel>
    <div className="ug-scenario-grid">
      <Panel title={S.design}>
        <h3>{S.scenarios[id].name}</h3><p>{S.scenarios[id].description}</p><Identifier text={id} />
        <dl>
          <div><dt>{S.duration}</dt><dd><InputValue config={config} name="duration_hours" value={config.duration_hours} unit={S.units.hours} /></dd></div>
          <div><dt>{S.seed}</dt><dd><InputValue config={config} name="seed" value={config.seed} /></dd></div>
          <div><dt>{S.start}</dt><dd><time dateTime={config.start}>{config.start}</time></dd></div>
          <div><dt>{S.timestep}</dt><dd><InputValue config={config} name="timestep_minutes" value={config.timestep_minutes} unit={S.units.minutes} /></dd></div>
          <div><dt>{S.heatwave}</dt><dd><InputValue config={config} name="heatwave_multiplier" value={config.demand.heatwave_multiplier} unit={S.units.multiplier} /></dd></div>
          <div><dt>{S.forecastError}</dt><dd><InputValue config={config} name="sigma_pct" value={config.demand.forecast_error.sigma_pct} unit={S.units.percent} /></dd></div>
        </dl>
        <h3>{S.faults}</h3>
        {config.faults.length === 0 ? <p>{S.noFaults}</p> : config.faults.map((fault, index) => <div className="ug-scenario-fault" key={index}>
          <Identifier text={fault.type} />{" "}<Identifier text={element(fault)} />
          <p>{S.onset}{": "}{onset(fault.start_hour)}</p>
          <dl>{Object.entries(fault).filter(([key]) => !["type", "start_hour", "location", "sensor_id", "pump_id"].includes(key)).map(([key, value]) => <div key={key}>
            <dt>{S.parameters[key as keyof typeof S.parameters] ?? key}</dt>
            <dd><InputValue config={config} name={`fault:${index}:${key}`} value={value}
              unit={key.endsWith("hours") ? S.units.hours : key === "final_area_cm2" ? S.units.area : null} /></dd>
          </div>)}</dl>
        </div>)}
        <button type="button" disabled={status === "launching"} onClick={() => void launch()}>{S.launch}</button>
        <p role="status">{status ? S[status] : S.ready}</p>
      </Panel>
      <Panel title={S.impact}>
        <p>{S.illustrative}</p>
        {id === "sensor_stuck_pressure" && <p>{S.sensorNote}</p>}
        <dl>{Object.entries(impact).map(([key, record]) => <div key={key}><dt>{S.metrics[key as keyof typeof S.metrics]}</dt>
          <dd><Metric value={record.value} unit={record.unit} label={S.labels.simulation} evidence={record} /></dd></div>)}</dl>
        <h3>{id === "sensor_stuck_pressure" ? S.referenceJunction : S.mostAffected}</h3><Identifier text={fixture.junction} />
        <TimeSeriesChart title={S.pressureChart} tickMinutes={config.timestep_minutes}
          series={[{ id: fixture.junction, name: S.pressure, unit: S.units.pressure, label: "SIMULATION", points: fixture.points }]} />
      </Panel>
    </div>
    <Panel title={S.timeline}>
      <div className="ug-scenario-horizon"><span>{S.begin}{" "}{onset(0)}</span><span>{S.end}{" "}{onset(config.duration_hours)}</span></div>
      <div className="ug-scenario-track" aria-hidden="true">{config.faults.map((fault, index) => <span key={index} style={{ left: `${fault.start_hour / config.duration_hours * 100}%` }} />)}</div>
      <ul>{config.faults.map((fault, index) => <li key={index}><Identifier text={fault.type} />{": "}{onset(fault.start_hour)}</li>)}</ul>
      {!config.faults.length && <p>{S.noFaults}</p>}
    </Panel>
  </div>;
}
export function ScenarioLabScreen({ route, onLaunch = recordFixture }: ScreenProps & Partial<ScenarioLabProps>) {
  return <><p>{route.empty}</p><ScenarioLab onLaunch={onLaunch} /></>;
}
