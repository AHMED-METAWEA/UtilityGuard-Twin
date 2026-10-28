import type { EvidenceRecord, Input } from "../../generated/evidence-record";
import type { Incident } from "../../generated/incident";
import { createMapFixture, createTickFixture, MAP_CANDIDATES } from "../map";
import { COMMAND_STRINGS as S } from "../../screens/command/strings";

const ORIGIN = Date.parse("2026-10-28T08:00:00Z");
const TICK_SECONDS = 60;
export function tickTime(tick: number) {
  const dateTime = new Date(ORIGIN + tick * TICK_SECONDS * 1000).toISOString().replace(".000Z", "Z");
  return { dateTime, text: dateTime.slice(11, 19) };
}

function evidence(id: string, value: number, unit: string | null, label: EvidenceRecord["label"], formula: string | null = null, inputs: Input[] = []): EvidenceRecord {
  return {
    schema_version: "1", evidence_id: `command_fixture_${id}`, value, unit, label, formula, inputs,
    provenance: { network_version: "command_fixture_v1", detector_version: "fixture_rules_v1" },
    explanation_template: S.fixtureSource,
  };
}
function input(name: string, value: number, unit: string | null, label: Input["label"]): Input {
  return { name, value, unit, label, ref: `command_fixture_${name}` };
}

/** Fixed telemetry/model snapshot only. No hydraulic truth or hidden fault fields. */
export function createCommandFixture() {
  const tick = 120;
  const network = createMapFixture();
  const state = createTickFixture(network, tick);
  const incidents: Incident[] = [
    {
      schema_version: "1", incident_id: "INC_LEAK_01", run_id: "fixture_not_a_run", status: "open",
      false_alarm: false, severity: "high", hypothesis: "leak", support: "strong",
      rules_fired: ["pressure_residual_sustained", "flow_balance_residual"],
      location: { zone_id: "ZONE_0", candidates: MAP_CANDIDATES.map((c) => ({ ...c })) },
      first_detected_tick: 108, closed_at: null, contributing_sensors: ["SENSOR_0", "SENSOR_1"],
    },
    {
      schema_version: "1", incident_id: "INC_SENSOR_02", run_id: "fixture_not_a_run", status: "open",
      false_alarm: false, severity: "low", hypothesis: "sensor_fault", support: "weak",
      rules_fired: ["unchanged_pressure_readings"],
      location: { zone_id: "ZONE_1", candidates: [{ asset_id: "J_13", score: 0.31, label: "MODEL" }] },
      first_detected_tick: 115, closed_at: null, contributing_sensors: ["SENSOR_1"],
    },
  ];
  const pressureInputs = network.sensors.filter((s) => s.kind === "pressure")
    .map((s) => input(s.id, state.pressure[s.element]!, S.pressureUnit, "SENSOR_SIM"));
  const tankInputs = [input("TANK_A_level", 2.4, "m", "SENSOR_SIM"), input("TANK_B_level", 5.1, "m", "SENSOR_SIM")];
  const threshold = input("tank_threshold", 3, "m", "ASSUMPTION");
  const flaggedInputs = [input("SENSOR_1_has_quality_flag", 1, null, "SENSOR_SIM"), input("SENSOR_3_has_quality_flag", 1, null, "SENSOR_SIM")];
  const kpis = {
    demand: evidence("demand", 148, S.flowUnit, "MODEL"),
    delivered: evidence("delivered", 132, S.flowUnit, "SENSOR_SIM"),
    pressure: evidence("lowest_sensor_pressure", Math.min(...pressureInputs.map((i) => Number(i.value))), S.pressureUnit, "SENSOR_SIM", "min(pressure_sensor_readings)", pressureInputs),
    tanks: evidence("tanks_below", tankInputs.filter((i) => Number(i.value) < Number(threshold.value)).length, S.countUnit, "CALCULATED", "count(tank_level < tank_threshold)", [...tankInputs, threshold]),
    flags: evidence("flagged_sensors", flaggedInputs.length, S.countUnit, "CALCULATED", "count_unique(sensors_with_quality_flags)", flaggedInputs),
  };
  const volume = input("lost_volume_per_hour", 120, "m³/h", "MODEL");
  const price: Input = {
    ...input("unit_price", 6, "EGP/m³", "ASSUMPTION"),
    range: { p10: 4, p50: 6, p90: 10 }, version: "fixture_prices_v1", verified: false,
  };
  const cost: EvidenceRecord = {
    ...evidence("delay_cost", Number(volume.value) * Number(price.value), S.costUnit, "CALCULATED", "lost_volume_per_hour * unit_price", [volume, price]),
    provenance: { network_version: "command_fixture_v1", assumption_set: "fixture_prices_v1", cost_model: "fixture_water_only_v1" },
    uncertainty: { p10: Number(volume.value) * 4, p50: Number(volume.value) * 6, p90: Number(volume.value) * 10, basis: S.costRange },
  };
  const candidateEvidence = Object.fromEntries(incidents.flatMap((incident) => incident.location.candidates.map((c) => [
    `${incident.incident_id}:${c.asset_id}`,
    evidence(`${incident.incident_id}_${c.asset_id}_score`, c.score, null, c.label),
  ])));
  return { tick, network, state, incidents, kpis, cost, candidateEvidence };
}
