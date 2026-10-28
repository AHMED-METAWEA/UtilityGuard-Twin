import type { EvidenceRecord } from "../../generated/evidence-record";
import type { ForecastFixture, TimeSeries } from "../../screens/forecast/types";
import { FORECAST_STRINGS as S } from "../../screens/forecast/strings";

const provenance = { run_id: "fixture_forecast", detector_version: "linear_fixture_v1", assumption_set: "fixture_prices_v1" };
export function forecastEvidence(id: string, value: EvidenceRecord["value"], unit: string | null,
  label: EvidenceRecord["label"], inputs: EvidenceRecord["inputs"] = [], formula: string | null = null): EvidenceRecord {
  return { schema_version: "1", evidence_id: id, value, unit, label, inputs, formula, provenance };
}
function series(id: string, kind: TimeSeries["kind"], quantity: TimeSeries["quantity"], values: number[]): TimeSeries {
  const model = kind !== "sensor";
  return { schema_version: "1", series_id: id, run_id: "fixture_forecast", kind, element: id.split(":")[0]!, quantity,
    unit: quantity === "level" ? S.units.level : S.units.flow, label: model ? "MODEL" : "SENSOR_SIM",
    ...(model ? { version: "linear_fixture_v1" } : {}), start: "2026-01-02T12:00:00Z", step_seconds: 3600, values,
    ...(model ? { band: { p10: values.map(v => v - (quantity === "level" ? 0.2 : 8)), p90: values.map(v => v + (quantity === "level" ? 0.2 : 8)) } } : {}) };
}
/** Closed-form fixtures; no random state, hidden fault data or network reads. */
export function createForecastFixture(): ForecastFixture {
  return {
    zones: ["Civic", "Residential"].map((id, i) => ({ id,
      demand: series(`${id}:demand`, "demand_forecast", "demand", [100, 104, 108, 112, 116].map(v => v + i * 60)),
      inlet: series(`${id}:inlet`, "sensor", "flow", [103, 106, 109, 115, 118].map(v => v + i * 60)) })),
    tanks: ["Tank-West", "Tank-East"].map((id, i) => {
      const measured = series(`${id}:measured`, "sensor", "level", i ? [4, 4.1, 4.2] : [6, 5.5, 5]);
      const forecast = series(`${id}:forecast`, "tank_forecast", "level", i ? [4.2, 4.3, 4.4, 4.5, 4.6] : [5, 4.5, 4, 3.5, 3]);
      // The model starts at the last available measurement, not at a future sensor reading.
      forecast.start = "2026-01-02T14:00:00Z";
      const threshold = forecastEvidence(`${id}:threshold`, 3, S.units.level, "ASSUMPTION");
      threshold.explanation_template = "fixture.threshold.v1";
      threshold.reason = "Unverified fixture lower operating limit; assumption version fixture_prices_v1.";
      const timeToThreshold = i ? { ...forecastEvidence(`${id}:time`, null, S.units.hours, "INSUFFICIENT_EVIDENCE"), reason: S.stableReason }
        : { ...forecastEvidence(`${id}:time`, 4, S.units.hours, "CALCULATED", [
          { name: "current_level", value: 5, unit: "m", label: "SENSOR_SIM", ref: `${id}:current` },
          { name: "forecast_slope", value: -0.5, unit: "m/h", label: "MODEL", ref: `${id}:slope` },
          { name: "threshold", value: 3, unit: "m", label: "ASSUMPTION", ref: threshold.evidence_id },
        ], "(threshold - current_level) / forecast_slope"), explanation_template: "fixture.threshold_time.v1", reason: S.fallingReason };
      return { id, measured, forecast, threshold, timeToThreshold };
    }),
    trends: [{ sensor: "Tank-West:level", evidence: forecastEvidence("trend:west", -1.25, S.units.slope, "CALCULATED", [
      { name: "sensor_slope", value: -0.5, unit: "m/h", label: "SENSOR_SIM", ref: "Tank-West:sensor-slope" },
      { name: "baseline_sigma", value: 0.4, unit: "m", label: "MODEL", ref: "baseline:west" },
    ], "sensor_slope / baseline_sigma") }],
  };
}
export const forecastFixture = createForecastFixture();
