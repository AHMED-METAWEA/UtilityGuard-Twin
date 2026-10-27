import { describe, expect, it } from "vitest";
import { applySensorWhatIf, createSensorFixtures, FIXTURE_TICKS, SENSOR_CATALOG, TICK_MINUTES, fixtureTickTime } from "./index";
import { buildSensorWhatIf } from "../../screens/sensors/whatif";
import telemetrySchema from "../../../../contracts/v1/telemetry-reading.schema.json";
import commonSchema from "../../../../contracts/v1/common.schema.json";
import type { TelemetryReading } from "../../generated/telemetry-reading";
import type { SensorWhatIf } from "../../screens/sensors/whatif";

// Dependency-free checks use the reading schema and referenced common definitions.
function assertTelemetryContract(reading: TelemetryReading) {
  const defs = commonSchema.$defs;
  expect(Object.keys(reading).every((key) => key in telemetrySchema.properties)).toBe(true);
  for (const key of telemetrySchema.required) expect(reading).toHaveProperty(key);
  expect(reading.schema_version).toBe(defs.schema_version.const);
  expect(Number.isSafeInteger(reading.tick) && reading.tick >= 0).toBe(true);
  expect(reading.sensor_id).toMatch(new RegExp(defs.identifier.pattern));
  expect(reading.value === null || (typeof reading.value === "number" && Number.isFinite(reading.value))).toBe(true);
  expect(defs.telemetry_label.enum).toContain(reading.label);
  expect(["m", "L/s"]).toContain(reading.unit);
  if (reading.delivered_at !== undefined) expect(reading.delivered_at).toMatch(new RegExp(defs.utc_timestamp.pattern));
  const quality = reading.quality!;
  for (const key of defs.quality.required) expect(quality).toHaveProperty(key);
  expect(Object.keys(quality).every((key) => key in defs.quality.properties)).toBe(true);
  expect(defs.quality.properties.status.enum).toContain(quality.status);
  expect(Number.isFinite(quality.score) && quality.score >= 0 && quality.score <= 1).toBe(true);
  expect(quality.label).toBe(defs.quality.properties.label.const);
  expect(new Set(quality.flags).size).toBe(quality.flags.length);
  for (const flag of quality.flags) expect(flag).toMatch(new RegExp(defs.quality.properties.flags.items.pattern));
  expect(quality.formula_ref).toMatch(new RegExp(defs.template_id.pattern));
  expect(quality.formula_ref).not.toMatch(new RegExp(defs.template_id.not.pattern));
  expect(quality.formula_ref).toBe("quality.score.v1");
}

const baseline = createSensorFixtures();
const sensor = SENSOR_CATALOG[0]!.id;
const at = (tick: number) => baseline.find((r) => r.sensor_id === sensor && r.tick === tick)!;
const from = 432;

describe("deterministic telemetry fixtures and what-if requests", () => {
  it("generates twelve sensors at five-minute ticks for two days with all four flag examples", () => {
    expect(baseline).toEqual(createSensorFixtures());
    expect(baseline).not.toEqual(createSensorFixtures(306));
    expect(baseline).toHaveLength(12 * 2 * 24 * 12);
    expect(new Set(baseline.map((r) => r.sensor_id)).size).toBe(12);
    expect(baseline[FIXTURE_TICKS - 1]?.tick).toBe(575);
    expect(Date.parse(baseline[1]!.delivered_at!) - Date.parse(baseline[0]!.delivered_at!)).toBe(300_000);
    expect(new Set(baseline.flatMap((r) => r.quality!.flags))).toEqual(new Set(["Q01", "Q04", "Q08"]));
    for (const reading of baseline) {
      expect(Object.keys(reading).sort()).toEqual(["schema_version", "tick", "sensor_id", "value", "unit", "label", "delivered_at", "quality"].sort());
      expect(reading.label).toBe("SENSOR_SIM");
      assertTelemetryContract(reading);
      const late = Date.parse(reading.delivered_at!) - Date.parse(fixtureTickTime(reading.tick)) > 2 * TICK_MINUTES * 60_000;
      expect(reading.quality?.flags.includes("Q01")).toBe(reading.value === null || late);
    }
  });

  it.each(["disable", "stuck", "drift"] as const)("builds a typed deterministic %s request and applies it only to the target telemetry", (mode) => {
    const action = mode === "drift" ? { mode, drift_per_hour: -0.05 } : { mode };
    const request: SensorWhatIf = buildSensorWhatIf(sensor, from, action);
    expect(request).toEqual(buildSensorWhatIf(sensor, from, action));
    expect(JSON.parse(JSON.stringify(request))).toEqual(request);
    const changed = applySensorWhatIf(baseline, request);
    for (let i = 0; i < baseline.length; i++) {
      const original = baseline[i]!, result = changed[i]!;
      assertTelemetryContract(result);
      if (original.sensor_id !== sensor || original.tick < from) {
        expect(result).toEqual(original);
        continue;
      }
      if (mode === "disable") { expect(result.value).toBeNull(); expect(result.quality?.flags).toEqual(["Q01"]); }
      if (mode === "stuck") { expect(result.value).toBe(at(from).value); expect(result.quality?.flags).toEqual(["Q04"]); }
      if (mode === "drift") { expect(result.value).toBe(original.value! - 0.05 * (original.tick - from) * TICK_MINUTES / 60); expect(result.quality?.flags).toEqual(["Q08"]); }
    }
    expect(createSensorFixtures()).toEqual(baseline); // input was never mutated
  });

  it("converts hourly drift at five-minute ticks and retains latency quality when stuck", () => {
    const drifted = applySensorWhatIf(baseline, buildSensorWhatIf(sensor, from, { mode: "drift", drift_per_hour: 12 }));
    expect(drifted.find((r) => r.sensor_id === sensor && r.tick === from + 12)!.value).toBe(at(from + 12).value! + 12);
    drifted.forEach(assertTelemetryContract);
    const stuck = applySensorWhatIf(baseline, buildSensorWhatIf("SENSOR_04", 540, { mode: "stuck" }));
    expect(stuck.find((r) => r.sensor_id === "SENSOR_04" && r.tick === 550)!.quality!.flags).toEqual(["Q04", "Q01"]);
    stuck.forEach(assertTelemetryContract);
  });

  it("does not turn a missing reading into zero when drifting", () => {
    const id = SENSOR_CATALOG[1]!.id;
    const changed = applySensorWhatIf(baseline, buildSensorWhatIf(id, 300, { mode: "drift", drift_per_hour: 0.1 }));
    changed.forEach(assertTelemetryContract);
    expect(changed.find((r) => r.sensor_id === id && r.tick === 330)?.value).toBeNull();
  });

  it("rejects invalid ticks, unavailable stuck values and nonfinite rates", () => {
    for (const tick of [-1, NaN, 0.5]) expect(() => buildSensorWhatIf(sensor, tick, { mode: "disable" })).toThrow();
    expect(buildSensorWhatIf(sensor, from, { mode: "stuck" })).toEqual({ sensor_id: sensor, from_tick: from, mode: "stuck" });
    expect(() => applySensorWhatIf(baseline, buildSensorWhatIf("SENSOR_02", 330, { mode: "stuck" }))).toThrow();
    for (const drift_per_hour of [NaN, Infinity, -Infinity]) expect(() => buildSensorWhatIf(sensor, 0, { mode: "drift", drift_per_hour })).toThrow();
  });
});
