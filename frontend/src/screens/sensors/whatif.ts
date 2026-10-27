/** UI request aligned with D-04; drift is in sensor units per hour. */
export type SensorWhatIf = {
  sensor_id: string;
  from_tick: number;
} & (
  | { mode: "disable" | "stuck" }
  | { mode: "drift"; drift_per_hour: number }
);

export function buildSensorWhatIf(sensor_id: string, from_tick: number, action:
  | { mode: "disable" | "stuck" }
  | { mode: "drift"; drift_per_hour: number },
): SensorWhatIf {
  if (!sensor_id || !Number.isSafeInteger(from_tick) || from_tick < 0) throw new Error("Invalid sensor or tick");
  if (action.mode === "drift" && !Number.isFinite(action.drift_per_hour)) throw new Error("Invalid drift rate");
  return { sensor_id, from_tick, ...action };
}
