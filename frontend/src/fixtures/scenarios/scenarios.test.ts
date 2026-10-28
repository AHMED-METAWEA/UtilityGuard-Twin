import { describe, expect, it } from "vitest";
import type { Fault, ScenarioConfiguration } from "../../generated/scenario-config";
import { createScenarioFixtures, scenarioConfigs } from ".";
import commonSchema from "../../../../contracts/v1/common.schema.json";
import evidenceSchema from "../../../../contracts/v1/evidence-record.schema.json";
import burst from "../../../../domains/water/src/ug_water/scenarios/presets/burst_main.json";
import leak from "../../../../domains/water/src/ug_water/scenarios/presets/leak_gradual_medium.json";
import pump from "../../../../domains/water/src/ug_water/scenarios/presets/pump_outage_standby.json";
import heatwave from "../../../../domains/water/src/ug_water/scenarios/presets/heatwave.json";

const catalogue = ["leak", "burst", "background_leakage", "sensor_drift", "sensor_offset", "sensor_stuck", "sensor_noise_growth", "sensor_dropout", "comms_outage", "pump_outage", "pump_degradation", "valve_state", "fire_flow", "power_loss"] satisfies Fault["type"][];
// Compile-time coverage of every generated catalogue type, in addition to fixture membership.
const catalogueCoverage = {
  leak: true, burst: true, background_leakage: true, sensor_drift: true, sensor_offset: true,
  sensor_stuck: true, sensor_noise_growth: true, sensor_dropout: true, comms_outage: true,
  pump_outage: true, pump_degradation: true, valve_state: true, fire_flow: true, power_loss: true,
} satisfies Record<Fault["type"], true>;

describe("scenario fixtures", () => {
  it("matches the generated config type, real presets and only catalogue faults", () => {
    const typed: ScenarioConfiguration[] = scenarioConfigs;
    expect(typed).toHaveLength(5);
    expect(typed.slice(0, 4)).toEqual([burst, leak, pump, heatwave]);
    expect(new Set(catalogue).size).toBe(14);
    for (const config of typed) {
      expect(config.schema_version).toBe("1");
      expect(Number.isInteger(config.seed)).toBe(true);
      for (const fault of config.faults) {
        expect(catalogueCoverage[fault.type]).toBe(true);
        expect(fault.start_hour).toBeGreaterThanOrEqual(0);
        expect(fault.start_hour).toBeLessThan(config.duration_hours);
      }
    }
    expect(typed[4]!.faults).toEqual([{ type: "sensor_stuck", start_hour: 12, sensor_id: "SENSOR_01", duration_hours: 6 }]);
  });

  it("is deterministic, with reconstructable evidence and unchanged sensor-fault hydraulics", () => {
    const fixtures = createScenarioFixtures();
    expect(fixtures).toEqual(createScenarioFixtures());
    for (const fixture of fixtures) {
      expect(fixture.impact.minimumPressure.value).toBe(Math.min(...fixture.points.map((p) => p.value)));
      for (const record of Object.values(fixture.impact)) {
        expect(record.label).toBe("SIMULATION");
        expect(record.formula).toBeTruthy();
        expect(record.inputs.length).toBeGreaterThan(0);
        expect(record.provenance.scenario_id).toBe(fixture.config.scenario_id);
        expect(record.schema_version).toBe("1");
        for (const required of evidenceSchema.required) expect(record).toHaveProperty(required);
        expect(record.evidence_id).toMatch(new RegExp(commonSchema.$defs.identifier.pattern));
        expect(record.unit).toMatch(new RegExp(commonSchema.$defs.unit.pattern));
        expect(record.explanation_template).toMatch(new RegExp(evidenceSchema.properties.explanation_template.pattern));
        for (const input of record.inputs) {
          expect(input.ref).toMatch(new RegExp(commonSchema.$defs.identifier.pattern));
          expect(input.unit).toMatch(new RegExp(commonSchema.$defs.unit.pattern));
        }
        expect(record.reason).toContain("not field validation");
      }
      for (const key of ["unservedDemand", "lostWater"] as const) {
        const record = fixture.impact[key];
        expect(record.value).toBe(Number(record.inputs[0]!.value) * Number(record.inputs[1]!.value) / 1000);
      }
      const flow = fixture.impact.peakFlowChange;
      expect(Math.abs(Number(flow.value))).toBe(Math.max(...flow.inputs.map((i) => Math.abs(Number(i.value)))));
    }
    const sensor = fixtures[4]!;
    expect(sensor.impact.peakFlowChange.value).toBe(0);
    expect(sensor.impact.unservedDemand.value).toBe(0);
    expect(sensor.impact.lostWater.value).toBe(0);
    expect(sensor.points.map((p) => p.value)).toEqual([42, 41, 42, 41, 42]);
  });
});
