import type { ScenarioConfiguration } from "../../generated/scenario-config";
import type { EvidenceRecord, Input } from "../../generated/evidence-record";
import { scenarioConfigs } from "./configs";
import { SCENARIO_STRINGS as S } from "../../screens/scenarios/strings";
export { scenarioConfigs };

export type ScenarioId = keyof typeof S.scenarios;
export type ImpactKey = keyof typeof S.metrics;
export function inputEvidence(config: ScenarioConfiguration, name: string, value: number | string | boolean, unit: string | null): EvidenceRecord {
  return { schema_version: "1", evidence_id: `${config.scenario_id}:input:${name}`, value, unit, label: "ASSUMPTION",
    formula: null, inputs: [], provenance: { scenario_id: config.scenario_id, seed: config.seed, assumption_set: config.assumption_set }, explanation_template: "scenario.fixture_input.v1", reason: S.source };
}
function impactRecord(config: ScenarioConfiguration, key: ImpactKey, value: number, unit: string, formula: string, inputs: Input[]): EvidenceRecord {
  return { schema_version: "1", evidence_id: `${config.scenario_id}:impact:${key}`, value, unit, label: "SIMULATION", formula, inputs,
    provenance: { scenario_id: config.scenario_id, seed: config.seed, network_version: config.network_version }, explanation_template: "scenario.fixture_impact.v1", reason: S.impactSource };
}
// Deliberately small illustrative arrays. These are not WNTR results or telemetry.
const samples = [
  { pressure: [42, 41, 16, 22, 28], flow: [0, 0, 85, 62, 40], deficit: 12, loss: 20 },
  { pressure: [42, 41, 38, 34, 30], flow: [0, 0, 4, 8, 12], deficit: 1, loss: 2 },
  { pressure: [42, 41, 26, 38, 42], flow: [0, 0, -15, 5, 0], deficit: 3, loss: 0 },
  { pressure: [42, 36, 32, 35, 38], flow: [0, 15, 25, 20, 12], deficit: 5, loss: 0 },
  { pressure: [42, 41, 42, 41, 42], flow: [0, 0, 0, 0, 0], deficit: 0, loss: 0 },
];
export function createScenarioFixtures() {
  return scenarioConfigs.map((config, index) => {
    const sample = samples[index]!;
    const ref = (name: string, value: number, unit: string): Input => ({ name, value, unit, label: "SIMULATION", ref: `${config.scenario_id}:sample:${name}` });
    const pressureInputs = sample.pressure.map((value, i) => ref(`pressure_${i}`, value, S.units.pressure));
    const flowInputs = sample.flow.map((value, i) => ref(`flow_change_${i}`, value, S.units.flow));
    const interval = ref("interval", 3600, "s");
    const volume = (key: "unservedDemand" | "lostWater", rate: number) => impactRecord(config, key, rate * 3600 / 1000, S.units.volume,
      `${key}_rate * interval / 1000`, [ref(`${key}_rate`, rate, S.units.flow), interval]);
    const impact: Record<ImpactKey, EvidenceRecord> = {
      minimumPressure: impactRecord(config, "minimumPressure", Math.min(...sample.pressure), S.units.pressure, "min(pressure_samples)", pressureInputs),
      peakFlowChange: impactRecord(config, "peakFlowChange", sample.flow.reduce((a, b) => Math.abs(b) > Math.abs(a) ? b : a, 0), S.units.flow, "flow_change_sample with maximum absolute magnitude (signed)", flowInputs),
      unservedDemand: volume("unservedDemand", sample.deficit), lostWater: volume("lostWater", sample.loss),
    };
    const onset = config.faults[0]?.start_hour ?? 0;
    const hours = [0, Math.max(0, onset - 1), onset, Math.min(config.duration_hours, onset + 1), config.duration_hours];
    // Heatwave and sensor reference chart span their horizon evenly.
    const chartHours = config.scenario_id === "heatwave" || config.scenario_id === "sensor_stuck_pressure" ? [0, 12, 24, 36, config.duration_hours] : hours;
    return { config, id: config.scenario_id as ScenarioId, junction: "node:j_0088", impact,
      points: sample.pressure.map((value, i) => ({ tick: chartHours[i]! * 60 / config.timestep_minutes, value })) };
  });
}

/** A local presentation delay only; tests inject a resolved/deferred promise. */
export function recordFixture(_config: ScenarioConfiguration): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, 180));
}
