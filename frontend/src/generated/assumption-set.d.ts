/**
 * Generated from contracts/v1/assumption-set.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * Master Spec 11.1 and Appendix A. Every assumption is a triangular distribution with a unit, a source note and a verified flag. `min <= mode <= max` is checked by the loader, not by this schema. A value may be marked verified only with a source note of some length; whether the source is real is a human review.
 */
export interface AssumptionSet {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  set_id: string;
  parent: string | null;
  note: string;
  assumptions: {
    [k: string]: Assumption;
  };
}
/**
 * This interface was referenced by `AssumptionSet`'s JSON-Schema
 * via the `definition` "assumption".
 */
export interface Assumption {
  /**
   * A unit written as one ASCII token (no spaces, no letters outside A-Z, a-z): m, m3, L/s, kWh, EGP/m3. Currencies are written EGP only (see money_consistency).
   */
  unit: string;
  distribution: {
    type: "triangular";
    min: number;
    mode: number;
    max: number;
  };
  source_note: string;
  verified: boolean;
}
