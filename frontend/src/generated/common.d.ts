/**
 * Generated from contracts/v1/common.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * Contract version; every payload carries it.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "schema_version".
 */
export type SchemaVersion = "1";
/**
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "identifier".
 */
export type Identifier = string;
/**
 * The nine evidence labels (Honesty Rules).
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "evidence_label".
 */
export type EvidenceLabel =
  | "OBSERVED"
  | "BENCHMARK"
  | "PUBLIC_GEOMETRY"
  | "SIMULATION"
  | "SENSOR_SIM"
  | "MODEL"
  | "ASSUMPTION"
  | "CALCULATED"
  | "INSUFFICIENT_EVIDENCE";
/**
 * What a sensor reading may be: simulated sensor, real measurement or public benchmark.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "telemetry_label".
 */
export type TelemetryLabel = "SENSOR_SIM" | "OBSERVED" | "BENCHMARK";
/**
 * Where a stream comes from; always shown.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "stream_source".
 */
export type StreamSource = "REPLAY" | "SIMULATED" | "LIVE";
/**
 * UTC, whole seconds.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "utc_timestamp".
 */
export type UtcTimestamp = string;
/**
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "sha256".
 */
export type Sha256 = string;
/**
 * A displayable value. JSON has no NaN or infinity.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "scalar".
 */
export type Scalar = number | string | boolean;
/**
 * Id of a fixed, reviewed, versioned formula or explanation template (Master Spec 10.3).
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "template_id".
 */
export type TemplateId = string;
/**
 * Labels of a value that exists. An input that is INSUFFICIENT_EVIDENCE makes the result INSUFFICIENT_EVIDENCE too, so it is not an input.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "evidence_label_with_value".
 */
export type EvidenceLabelWithValue =
  "OBSERVED" | "BENCHMARK" | "PUBLIC_GEOMETRY" | "SIMULATION" | "SENSOR_SIM" | "MODEL" | "ASSUMPTION" | "CALCULATED";
/**
 * A unit written as one ASCII token (no spaces, no letters outside A-Z, a-z): m, m3, L/s, kWh, EGP/m3. Currencies are written EGP only (see money_consistency).
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "unit".
 */
export type Unit = string;
/**
 * The unit of a sensor reading: one ASCII token built only from known physical units (metres, litres, seconds, pascals, watts, ...), optionally with a metric prefix, an exponent, and / * . between factors. A currency, however it is spelled, is not a physical unit, so money cannot be labelled as sensor output. The list of units is ug_core.grammar.PHYSICAL_UNIT_ATOMS; a test keeps this pattern equal to it.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "physical_unit".
 */
export type PhysicalUnit = Unit;
/**
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "nullable_unit".
 */
export type NullableUnit = Unit | null;
/**
 * A key in a map the operator sees, naming a sensor or a metric: upper-case letters, digits and underscore only, and none of the reserved words (truth, fault, hidden, probability, confidence, percent, ground, inject). A grammar plus a word list, not proof: code checks the key against the sensors of the run.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "sensor_key".
 */
export type SensorKey = string;
/**
 * A detector id used as a map key: lower-case letters, digits and underscore only, none of the reserved words.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "detector_key".
 */
export type DetectorKey = string;
/**
 * Version of a detector or model, like d2_v1.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "model_version".
 */
export type ModelVersion = string;
/**
 * Rules for an object with unit, label and value (an evidence record or one of its inputs). A unit that looks like a currency must be spelled exactly EGP or EGP/<m3|kWh|MWh|kW|h|day|month|year>. Money, whether an amount or a price, is never simulator, model, sensor or geometry output (pitfall P-14): it is CALCULATED, an ASSUMPTION, OBSERVED or BENCHMARK. A money value is a JSON number, never formatted text. The currency recogniser is a list of common codes and words: a currency it does not list is caught by the evidence kernel in code. A value labelled SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY carries a physical unit (physical_unit), so a currency in a spelling nobody listed cannot be labelled as simulator, model, sensor or geometry output either.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "money_consistency".
 */
export type MoneyConsistency = {
  [k: string]: unknown;
};

/**
 * Shared building blocks. Not a payload on its own.
 */
export interface CommonDefinitionsContractsV1 {
  [k: string]: unknown;
}
/**
 * Data-quality score of one reading (Master Spec 6.2). The score is computed by a fixed, versioned formula, so it is CALCULATED and names that formula.
 *
 * This interface was referenced by `CommonDefinitionsContractsV1`'s JSON-Schema
 * via the `definition` "quality".
 */
export interface Quality {
  status: "ok" | "suspect" | "bad";
  score: number;
  flags: string[];
  label: "CALCULATED";
  formula_ref: TemplateId;
}
