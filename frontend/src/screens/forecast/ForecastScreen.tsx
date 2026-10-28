import type { EvidenceRecord } from "../../generated/evidence-record";
import { forecastEvidence, forecastFixture } from "../../fixtures/forecast";
import { Metric } from "../../ui/Metric";
import { Identifier } from "../../ui/Identifier";
import { Panel } from "../../ui/Panel";
import { TimeSeriesChart } from "../../ui/charts/TimeSeriesChart";
import type { ChartSeries } from "../../ui/charts/TimeSeriesChart";
import type { ScreenProps } from "../types";
import type { TimeSeries } from "./types";
import { FORECAST_STRINGS as S } from "./strings";
import "./forecast.css";

function chart(series: TimeSeries, name: string, origin: string): ChartSeries {
  const offset = (Date.parse(series.start) - Date.parse(origin)) / 3600000;
  return { id: series.series_id, name, label: series.label, unit: series.unit.replace("m3", "m³"),
    points: series.values.map((value, i) => ({ tick: offset + i * series.step_seconds / 3600, value,
      lower: series.band?.p10[i], upper: series.band?.p90[i] })) };
}
function Reading({ record }: { record: EvidenceRecord }) {
  return <Metric evidence={record} label={record.label} value={record.value} unit={record.unit} />;
}
function Samples({ series }: { series: TimeSeries }) {
  return <details><summary><Identifier text={series.series_id} /></summary>
    <ul>{series.values.map((value, i) => <li key={i}>
      <time dateTime={new Date(Date.parse(series.start) + i * series.step_seconds * 1000).toISOString()}>{new Date(Date.parse(series.start) + i * series.step_seconds * 1000).toISOString()}</time>{" "}
      <Reading record={forecastEvidence(`${series.series_id}:${i}`, value, series.unit, series.label)} />
      {series.band && <><span>{S.lower}</span><Reading record={forecastEvidence(`${series.series_id}:lower:${i}`, series.band.p10[i] ?? null, series.unit, "MODEL")} />
        <span>{S.upper}</span><Reading record={forecastEvidence(`${series.series_id}:upper:${i}`, series.band.p90[i] ?? null, series.unit, "MODEL")} /></>}
    </li>)}</ul>
  </details>;
}
export function ForecastScreen({ route }: ScreenProps) {
  return <div className="ug-forecast">
    <h1>{S.title}</h1><p className="ug-forecast-fixture">{S.fixture}</p><p>{S.scope}</p>
    <Panel title={S.demand}><div className="ug-forecast-grid">{forecastFixture.zones.map(zone => <section key={zone.id}>
      <h3><Identifier text={zone.id} /></h3>
      <TimeSeriesChart title={S.demand} tickMinutes={60} series={[chart(zone.demand, S.demandSeries, zone.demand.start), chart(zone.inlet, S.inletSeries, zone.demand.start)]} />
      <p>{S.band}{" "}<Identifier text="p10–p90" /></p><Samples series={zone.demand} /><Samples series={zone.inlet} />
    </section>)}</div></Panel>
    <Panel title={S.tanks}><div className="ug-forecast-grid">{forecastFixture.tanks.map(tank => <section key={tank.id}>
      <h3><Identifier text={tank.id} /></h3>
      <TimeSeriesChart title={S.tanks} tickMinutes={60} nowTick={2} series={[
        chart(tank.measured, S.tankSeries, tank.measured.start), chart(tank.forecast, S.forecastSeries, tank.measured.start),
        { id: tank.threshold.evidence_id, name: S.threshold, unit: S.units.level, label: "ASSUMPTION", points: [{ tick: 0, value: Number(tank.threshold.value) }, { tick: 6, value: Number(tank.threshold.value) }] },
      ]} />
      <p>{S.threshold}{" "}<Reading record={tank.threshold} /></p>
      <p>{S.time}{" "}<Reading record={tank.timeToThreshold} /></p>
      {tank.timeToThreshold.label === "INSUFFICIENT_EVIDENCE" && <p>{S.notApproaching}{": "}{tank.timeToThreshold.reason}</p>}
      <Samples series={tank.measured} /><Samples series={tank.forecast} />
    </section>)}</div></Panel>
    <Panel title={S.trends}><ul>{forecastFixture.trends.map(trend => <li key={trend.sensor}><Identifier text={trend.sensor} />{": "}{S.trend}{" "}<Reading record={trend.evidence} /></li>)}</ul></Panel>
    <details><summary>{S.integration}</summary><p>{S.runContext}</p><p>{route.empty}</p></details>
  </div>;
}
