/**
 * Generated from contracts/v1/stream-envelope.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * WebSocket frame (Master Spec 12.2). Version 1 specifies the `tick` frame only; the other frame types of the Spec (incident.updated, analysis.progress, analysis.done, run.control, notification) are added when their payloads are specified, and until then they are rejected rather than accepted without a shape. A tick always states its stream source and never carries truth or hidden fault tags.
 */
export interface StreamEnvelope {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  type: "tick";
  run_id: string;
  seq: number;
  payload: TickPayload;
}
/**
 * This interface was referenced by `StreamEnvelope`'s JSON-Schema
 * via the `definition` "tick_payload".
 */
export interface TickPayload {
  tick: number;
  /**
   * UTC, whole seconds.
   */
  sim_time: string;
  /**
   * Where a stream comes from; always shown.
   */
  stream_source: "REPLAY" | "SIMULATED" | "LIVE";
  speed: number;
  readings: StreamReading[];
  network_confidence: {
    value: number;
    basis: string;
    label: "CALCULATED";
    /**
     * Id of a fixed, reviewed, versioned formula or explanation template (Master Spec 10.3).
     */
    formula_ref: string;
  };
  detectors: {
    [k: string]: {
      state: "normal" | "watch" | "alert";
      residuals: {
        [k: string]: number;
      };
      label: "MODEL";
      /**
       * Version of a detector or model, like d2_v1.
       */
      version: string;
    };
  };
  incidents_changed: string[];
}
/**
 * This interface was referenced by `StreamEnvelope`'s JSON-Schema
 * via the `definition` "stream_reading".
 */
export interface StreamReading {
  sensor_id: string;
  value: number | null;
  /**
   * The unit of a sensor reading: one ASCII token built only from known physical units (metres, litres, seconds, pascals, watts, ...), optionally with a metric prefix, an exponent, and / * . between factors. A currency, however it is spelled, is not a physical unit, so money cannot be labelled as sensor output. The list of units is ug_core.grammar.PHYSICAL_UNIT_ATOMS; a test keeps this pattern equal to it.
   */
  unit: string;
  /**
   * What a sensor reading may be: simulated sensor, real measurement or public benchmark.
   */
  label: "SENSOR_SIM" | "OBSERVED" | "BENCHMARK";
  quality: Quality;
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
