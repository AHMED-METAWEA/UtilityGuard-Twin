import { expect, it } from "vitest";
import { createCommandFixture, tickTime } from "../../fixtures/command";

it("recreates the exact fixture snapshot without a wall clock or mutable shared candidates", () => {
  const first = createCommandFixture();
  const second = createCommandFixture();
  expect(first).toEqual(second);
  first.incidents[0]!.location.candidates[0]!.score = -1;
  expect(createCommandFixture()).toEqual(second);
  expect(tickTime(second.tick)).toEqual({ dateTime: "2026-10-28T10:00:00Z", text: "10:00:00" });
});

it("uses existing map assets and model scores for incident candidates", () => {
  const { incidents, network, candidateEvidence } = createCommandFixture();
  const assets = new Set([...network.nodes, ...network.links].map((asset) => asset.id));
  expect(incidents.map((incident) => [incident.status, incident.hypothesis, incident.support])).toEqual([
    ["open", "leak", "strong"], ["open", "sensor_fault", "weak"],
  ]);
  for (const incident of incidents) {
    expect(network.zones.some((zone) => zone.id === incident.location.zone_id)).toBe(true);
    for (const candidate of incident.location.candidates) {
      expect(assets.has(candidate.asset_id)).toBe(true);
      const record = candidateEvidence[`${incident.incident_id}:${candidate.asset_id}`]!;
      expect(record.value).toBe(candidate.score);
      expect(record.label).toBe("MODEL");
    }
  }
});

it("derives the minimum only from pressure sensors and keeps money conditional on its inputs", () => {
  const { kpis, cost, network, state } = createCommandFixture();
  expect(kpis.pressure.value).toBe(Math.min(...network.sensors.filter((sensor) => sensor.kind === "pressure").map((sensor) => state.pressure[sensor.element]!)));
  expect(kpis.pressure.label).toBe("SENSOR_SIM");
  expect(kpis.tanks.label).toBe("CALCULATED");
  expect(kpis.flags.label).toBe("CALCULATED");
  expect(cost.label).toBe("CALCULATED");
  const volume = cost.inputs.find((input) => input.name === "lost_volume_per_hour")!;
  const price = cost.inputs.find((input) => input.name === "unit_price")!;
  expect(cost.value).toBe(Number(volume.value) * Number(price.value));
  expect(price.label).toBe("ASSUMPTION");
  expect(price.verified).toBe(false);
  expect(cost.provenance.assumption_set).toBe(price.version);
  expect(cost.uncertainty).toMatchObject({ p10: 480, p50: 720, p90: 1200 });
  expect(cost.provenance.run_id).toBeUndefined();
});
