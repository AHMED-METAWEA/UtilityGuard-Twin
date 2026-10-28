import type { EvidenceRecord } from "../../generated/evidence-record";

/** Local D-01 draft; replace with generated types when approved contracts land. */
export interface TimeSeries {
  schema_version: "1"; series_id: string; run_id: string;
  kind: "sensor" | "expectation" | "residual" | "demand_forecast" | "tank_forecast";
  element: string; quantity: "pressure" | "flow" | "level" | "demand"; unit: string;
  label: "SENSOR_SIM" | "OBSERVED" | "BENCHMARK" | "MODEL" | "CALCULATED";
  version?: string; formula_ref?: string; start: string; step_seconds: number;
  values: (number | null)[]; band?: { p10: (number | null)[]; p90: (number | null)[] };
}
export interface ForecastFixture {
  zones: { id: string; demand: TimeSeries; inlet: TimeSeries }[];
  tanks: { id: string; measured: TimeSeries; forecast: TimeSeries; threshold: EvidenceRecord; timeToThreshold: EvidenceRecord }[];
  trends: { sensor: string; evidence: EvidenceRecord }[];
}
