/**
 * Generated from contracts/v1/time-series.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * A series the operator view plots (DEMO_PLAN D-01): sensor readings, the expectation, residuals and forecasts. Twin truth never travels in this shape: SIMULATION is not an allowed label. A missing value is null, never 0.
 */
export type TimeSeries = {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  series_id: string;
  run_id: string;
  kind: "sensor" | "expectation" | "residual" | "demand_forecast" | "tank_forecast";
  element: string;
  quantity: "pressure" | "flow" | "level" | "demand";
  /**
   * The unit of a sensor reading: one ASCII token built only from known physical units (metres, litres, seconds, pascals, watts, ...), optionally with a metric prefix, an exponent, and / * . between factors. A currency, however it is spelled, is not a physical unit, so money cannot be labelled as sensor output. The list of units is ug_core.grammar.PHYSICAL_UNIT_ATOMS; a test keeps this pattern equal to it.
   */
  unit: string;
  label: "SENSOR_SIM" | "OBSERVED" | "BENCHMARK" | "MODEL" | "CALCULATED";
  /**
   * Version of a detector or model, like d2_v1.
   */
  version?: string;
  /**
   * Id of a fixed, reviewed, versioned formula or explanation template (Master Spec 10.3).
   */
  formula_ref?: string;
  /**
   * UTC, whole seconds.
   */
  start: string;
  step_seconds: number;
  values: (number | null)[];
  band?: {
    p10: (number | null)[];
    p90: (number | null)[];
  };
};
