/**
 * Generated from contracts/v1/whatif-request.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * Operator what-if on sensors (DEMO_PLAN D-01): disable a sensor, hold it stuck at its reading at from_tick, or add a drift. It changes telemetry only (SENSOR_SIM); the simulated network and its truth are never touched. Reset is the absence of a change.
 */
export interface SensorWhatIfRequest {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  run_id: string;
  /**
   * @maxItems 64
   */
  changes: {
    sensor_id: string;
    mode: "disable" | "stuck" | "drift";
    from_tick: number;
    drift_per_hour?: number;
  }[];
}
