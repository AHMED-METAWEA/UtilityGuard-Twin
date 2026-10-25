/**
 * Generated from contracts/v1/telemetry-reading.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * One sensor reading at one tick (Master Spec 11.2 and 12.2). A missing reading has value null, never 0. By design there is no field for twin truth, injected faults or fault tags: telemetry is what a sensor would report, and detectors and the operator view only ever see this shape.
 */
export interface TelemetryReading {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  tick: number;
  sensor_id: string;
  value: number | null;
  /**
   * A unit written as one ASCII token (no spaces, no letters outside A-Z, a-z): m, m3, L/s, kWh, EGP/m3. Currencies are written EGP only (see money_consistency).
   */
  unit: string;
  /**
   * What a sensor reading may be: simulated sensor, real measurement or public benchmark.
   */
  label: "SENSOR_SIM" | "OBSERVED" | "BENCHMARK";
  /**
   * UTC, whole seconds.
   */
  delivered_at?: string;
  quality?: Quality;
}
/**
 * Data-quality score of one reading (Master Spec 6.2). The score is computed by a fixed, versioned formula, so it is CALCULATED and names that formula.
 */
export interface Quality {
  status: "ok" | "suspect" | "bad";
  score: number;
  flags: string[];
  label: "CALCULATED";
  /**
   * Id of a fixed, reviewed, versioned formula or explanation template (Master Spec 10.3).
   */
  formula_ref: string;
}
