/**
 * Generated from contracts/v1/evidence-record.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * Master Spec 10.1. Every displayed number has one label from the nine. INSUFFICIENT_EVIDENCE if and only if there is no value, and then a reason is given; an input is never INSUFFICIENT_EVIDENCE. CALCULATED needs a formula and at least one input. Money (see common money_consistency, applied to the record and to each input): currencies are written EGP, an amount is never simulator, model, sensor or geometry output (pitfall P-14), a cost (kind 'cost') is an amount in EGP and CALCULATED, and money values are JSON numbers.
 */
export type EvidenceRecord = {
  [k: string]: unknown;
} & {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  evidence_id: string;
  /**
   * Absent means quantity.
   */
  kind?: "quantity" | "cost";
  value: number | string | boolean | null;
  unit: string | null;
  /**
   * The nine evidence labels (Honesty Rules).
   */
  label:
    | "OBSERVED"
    | "BENCHMARK"
    | "PUBLIC_GEOMETRY"
    | "SIMULATION"
    | "SENSOR_SIM"
    | "MODEL"
    | "ASSUMPTION"
    | "CALCULATED"
    | "INSUFFICIENT_EVIDENCE";
  formula: string | null;
  inputs: Input[];
  reason?: string;
  provenance: {
    run_id?: string;
    scenario_id?: string;
    seed?: number;
    network_version?: string;
    /**
     * Version of a detector or model, like d2_v1.
     */
    detector_version?: string;
    assumption_set?: string;
    cost_model?: string;
    git_commit?: string;
  };
  explanation_template?: string;
  uncertainty?: {
    p10: number;
    p50: number;
    p90: number;
    basis: string;
  };
};
/**
 * This interface was referenced by `undefined`'s JSON-Schema
 * via the `definition` "input".
 */
export type Input = {
  [k: string]: unknown;
} & {
  name: string;
  /**
   * A displayable value. JSON has no NaN or infinity.
   */
  value: number | string | boolean;
  unit: string | null;
  /**
   * Labels of a value that exists. An input that is INSUFFICIENT_EVIDENCE makes the result INSUFFICIENT_EVIDENCE too, so it is not an input.
   */
  label:
    "OBSERVED" | "BENCHMARK" | "PUBLIC_GEOMETRY" | "SIMULATION" | "SENSOR_SIM" | "MODEL" | "ASSUMPTION" | "CALCULATED";
  ref: string;
};
