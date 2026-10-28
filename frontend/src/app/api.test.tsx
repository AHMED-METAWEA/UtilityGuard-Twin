import { EvidenceProvider } from "../ui/evidence";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { loadReplay, ReplayContext, replayTick } from "./api";
import { CommandCenterScreen } from "../screens/command/CommandCenterScreen";
import { createMapFixture } from "../fixtures/map";
import { ROUTES } from "./routes";

// Avoid GPU initialization in a jsdom component check.
vi.mock("../screens/map/NetworkMapScreen", () => ({ NetworkMap: () => <div>Map</div> }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const run = { run_id: "recorded", scenario_id: "normal_week", seed: 1, simulation_start: "2027-03-04T22:00:00Z" };
const sensor = { schema_version: "1", series_id: "P1.sensor", run_id: "recorded", kind: "sensor", element: createMapFixture().sensors[0]!.element, quantity: "pressure", unit: "m", label: "SENSOR_SIM", start: run.simulation_start, step_seconds: 300, values: [12, null] };
function respond(payloads: unknown[]) {
  const mock = vi.fn();
  payloads.forEach((value) => mock.mockResolvedValueOnce({ ok: true, json: async () => value }));
  vi.stubGlobal("fetch", mock);
  return mock;
}
describe("recorded API boundary", () => {
  it("loads same-origin sensor data and preserves missing values", async () => {
    const network = { ...createMapFixture(), network_hash: "a".repeat(64) };
    const mock = respond([[run], network, [{ series_id: sensor.series_id, kind: "sensor", element: sensor.element, label: "SENSOR_SIM" }], sensor]);
    const state = await loadReplay();
    expect(state.replay?.runId).toBe("recorded");
    expect(state.replay!.series[0]!.values.at(-1)).toBeNull();
    expect(replayTick(state.replay!).pressure[sensor.element]).toBeUndefined();
    for (const [path] of mock.mock.calls) expect(path).toMatch(/^\/api\/runs/);
  });
  it.each([null, {}, [{ ...run, run_id: "../private" }]])("rejects malformed run lists and shows the fixture reason", async (payload) => {
    respond([payload]);
    const state = await loadReplay();
    expect(state.replay).toBeNull();
    render(<EvidenceProvider><ReplayContext.Provider value={state}><CommandCenterScreen route={ROUTES[0]!} /></ReplayContext.Provider></EvidenceProvider>);
    expect(screen.getByText("Fixture data, not a run")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe("Invalid run list");
  });
  it("rejects a bad numeric payload instead of rendering blank numbers", async () => {
    respond([[run], { ...createMapFixture(), nodes: [{ id: "j1", kind: "junction", x: null, y: 0, elevation_m: 0 }] }]);
    expect(await loadReplay()).toEqual({ replay: null, reason: "Invalid recorded network" });
  });
  it("rejects truth fields recursively", async () => {
    respond([[{ ...run, nested: { truth: 10 } }]]);
    expect(await loadReplay()).toEqual({ replay: null, reason: "Unsafe API payload" });
  });
  it("reports no runs and network failures", async () => {
    respond([[]]);
    expect((await loadReplay()).reason).toBe("No recorded runs available");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect((await loadReplay()).reason).toBe("Recorded-run API unavailable");
  });
});
