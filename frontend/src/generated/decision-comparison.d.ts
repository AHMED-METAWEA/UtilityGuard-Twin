/**
 * Generated from contracts/v1/decision-comparison.schema.json by json-schema-to-typescript.
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

/**
 * Options for one incident compared by expected cost, worst case (the 90th percentile of sampled costs), expected regret and break-even (DEMO_PLAN D-01, Master Spec 9.4). Advisory only: a human approves every action. Every number is an evidence record in `evidence`, referenced by id; savings are model-estimated, conditional on assumptions, and a negative net benefit is representable. No probability of a real-world event.
 */
export interface DecisionComparison {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  decision_id: string;
  run_id: string;
  incident_id: string;
  assumption_set: string;
  advisory: true;
  /**
   * @minItems 2
   */
  options: [
    {
      option_id: string;
      action: "fix_now" | "wait" | "isolate_then_fix";
      delay_hours: number;
      expected_cost: string;
      worst_case: string;
      expected_regret: string;
      /**
       * @minItems 1
       */
      cost_lines: [string, ...string[]];
    },
    {
      option_id: string;
      action: "fix_now" | "wait" | "isolate_then_fix";
      delay_hours: number;
      expected_cost: string;
      worst_case: string;
      expected_regret: string;
      /**
       * @minItems 1
       */
      cost_lines: [string, ...string[]];
    },
    ...{
      option_id: string;
      action: "fix_now" | "wait" | "isolate_then_fix";
      delay_hours: number;
      expected_cost: string;
      worst_case: string;
      expected_regret: string;
      /**
       * @minItems 1
       */
      cost_lines: [string, ...string[]];
    }[]
  ];
  break_even: {
    /**
     * @minItems 2
     */
    between: never[];
    parameter: string;
    evidence_id: string;
  }[];
  preferred_by_expected_cost: string | null;
  /**
   * @minItems 1
   */
  evidence: [EvidenceRecord, ...EvidenceRecord[]];
}
