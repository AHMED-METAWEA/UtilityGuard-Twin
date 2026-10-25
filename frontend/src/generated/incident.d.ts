/**
 * Generated from contracts/v1/incident.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * Master Spec 8 and 11.1. A hypothesis comes with a rule-based support strength and the rules that fired, never with an invented probability; a model score, where one exists, is labelled MODEL. Candidate locations are scored by the localizer (MODEL).
 */
export type Incident = {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  incident_id: string;
  run_id: string;
  status: "watch" | "open" | "acknowledged" | "mitigating" | "resolved" | "closed";
  false_alarm: boolean;
  severity: "low" | "medium" | "high" | "critical";
  hypothesis:
    "leak" | "burst" | "sensor_fault" | "demand_change" | "pump_issue" | "valve_issue" | "comms_outage" | "unknown";
  support: "strong" | "moderate" | "weak";
  rules_fired: string[];
  model_score?: {
    value: number;
    label: "MODEL";
    basis: string;
  };
  location: {
    zone_id: string | null;
    candidates: {
      asset_id: string;
      score: number;
      label: "MODEL";
    }[];
  };
  first_detected_tick: number;
  closed_at: string | null;
  contributing_sensors: string[];
};
