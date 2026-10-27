import type { TelemetryReading, Quality } from "../../generated/telemetry-reading";
import type { SensorWhatIf } from "../../screens/sensors/whatif";

export interface SensorDescriptor {
  id: string;
  kind: "pressure" | "flow" | "level";
  zone: number;
}
export const SENSOR_CATALOG: readonly SensorDescriptor[] = Array.from({ length: 12 }, (_, index) => ({
  id: `SENSOR_${String(index + 1).padStart(2, "0")}`,
  kind: index % 3 === 0 ? "pressure" : index % 3 === 1 ? "flow" : "level",
  zone: index % 4,
}));
export const FIXTURE_TICKS = 576;
export const TICK_MINUTES = 5;

export function fixtureTickTime(tick: number): string {
  return new Date(Date.UTC(2026, 0, 1) + tick * TICK_MINUTES * 60_000).toISOString().replace(".000Z", "Z");
}

export function fixtureQuality(flags: string[] = [], value: number | null = 0): Quality {
  return {
    status: value === null ? "bad" : flags.length ? "suspect" : "ok",
    score: value === null ? 0 : flags.length ? 0.5 : 1,
    flags, label: "CALCULATED", formula_ref: "quality.score.v1",
  };
}

/** Two days of independent telemetry, seed/version fixed; no hydraulic state exists here. */
export function createSensorFixtures(seed = 305): TelemetryReading[] {
  let state = seed >>> 0;
  const next = () => {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
  return SENSOR_CATALOG.flatMap((sensor, index) => {
    let held = 0;
    return Array.from({ length: FIXTURE_TICKS }, (_, tick): TelemetryReading => {
      const base = sensor.kind === "pressure" ? 32 : sensor.kind === "flow" ? 18 : 6;
      const amplitude = sensor.kind === "level" ? 0.8 : 3;
      let value: number | null = Math.round((base + index * 0.2 + amplitude * Math.sin(tick * Math.PI / 144) + (next() - 0.5) * 0.3) * 100) / 100;
      const flags: string[] = [];
      if (index === 1 && tick >= 320 && tick < 370) { value = null; flags.push("Q01"); }
      if (index === 2 && tick === 380) held = value!;
      if (index === 2 && tick >= 380) { value = held; flags.push("Q04"); }
      if (index === 3 && tick >= 540) flags.push("Q01");
      if (index === 4 && tick >= 480) { value = value! + (tick - 480) * 0.015; flags.push("Q08"); }
      return {
        schema_version: "1", sensor_id: sensor.id, tick, value,
        unit: sensor.kind === "flow" ? "L/s" : "m", label: "SENSOR_SIM",
        delivered_at: fixtureTickTime(tick + (index === 3 && tick >= 540 ? 3 : 0)),
        quality: fixtureQuality(flags, value),
      };
    });
  });
}

/** Recompute from the pristine fixture for each sensor request; never compound drift. */
export function applySensorWhatIf(baseline: readonly TelemetryReading[], request: SensorWhatIf): TelemetryReading[] {
  const held = baseline.find((reading) => reading.sensor_id === request.sensor_id && reading.tick === request.from_tick)?.value;
  if (request.mode === "stuck" && held == null) throw new Error("Current reading unavailable");
  if (request.mode === "drift" && !Number.isFinite(request.drift_per_hour)) throw new Error("Invalid drift rate");
  return baseline.map((reading) => {
    if (reading.sensor_id !== request.sensor_id || reading.tick < request.from_tick) return reading;
    let value = reading.value;
    let flag: string;
    switch (request.mode) {
      case "disable": value = null; flag = "Q01"; break;
      case "stuck": value = held!; flag = "Q04"; break;
      case "drift":
        value = value === null ? null : value + request.drift_per_hour * (reading.tick - request.from_tick) * TICK_MINUTES / 60;
        flag = "Q08"; break;
    }
    const flags = [...new Set([...(request.mode === "drift" ? reading.quality?.flags.filter((code) => code !== "Q01") ?? [] : []), flag])];
    const late = reading.delivered_at !== undefined && Date.parse(reading.delivered_at) - Date.parse(fixtureTickTime(reading.tick)) > 2 * TICK_MINUTES * 60_000;
    if ((value === null || late) && !flags.includes("Q01")) flags.push("Q01");
    return { ...reading, value, quality: fixtureQuality(flags, value) };
  });
}
