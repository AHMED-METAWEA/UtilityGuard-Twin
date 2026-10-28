import { FIXTURE_STRINGS } from "./strings";
import type { RunManifest } from "../../generated/run-manifest";
import type { EvidenceRecord } from "../../generated/evidence-record";
// UI fixture only: no simulation was executed and no manifest hash was computed.
export const manifest: RunManifest = {
  schema_version: "1", seed: 42,
  config: {
    schema_version: "1", scenario_id: "normal_week", network_version: "fixture_network_v1",
    sensor_set: "fixture_sensors_v1", seed: 42, start: "2026-10-27T00:00:00Z",
    duration_hours: 168, timestep_minutes: 5,
    demand: { calendar: "weekday", holiday: false, ramadan: false, heatwave_multiplier: 1,
      zone_multipliers: {}, forecast_error: { model: "ar1", sigma_pct: 5 } },
    faults: [], cross_domain_inputs: [], assumption_set: "fixture_assumptions_v1",
  },
  versions: { manifest: "1", network: "fixture_network_v1" }, libraries: {},
  git_commit: null, unordered: [], output_hashes: {},
};
export const runFixture = { runId: "fixture_run_001", manifestHash: null, manifest };
export function fixtureEvidence(key: string, value: EvidenceRecord["value"], unit: string | null = null): EvidenceRecord {
  return { schema_version: "1", evidence_id: `fixture.${key}`, value, unit,
    label: value === null ? "INSUFFICIENT_EVIDENCE" : "ASSUMPTION", formula: null, inputs: [],
    ...(value === null ? { reason: FIXTURE_STRINGS.missing } : {}),
    provenance: { run_id: runFixture.runId, network_version: manifest.config.network_version, seed: manifest.seed },
    explanation_template: FIXTURE_STRINGS.explanation,
  };
}
