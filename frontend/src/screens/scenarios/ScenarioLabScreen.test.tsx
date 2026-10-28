import { cleanup, fireEvent, render, screen, within, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScenarioLab } from "./ScenarioLabScreen";
import { SCENARIO_STRINGS as S } from "./strings";
import { EvidenceProvider } from "../../ui/evidence";
import { expectEveryNumberLabelled } from "../../ui/testing/labelled";
import { scenarioConfigs } from "../../fixtures/scenarios";

afterEach(cleanup);
function mount(onLaunch = vi.fn()) {
  return render(<EvidenceProvider><ScenarioLab onLaunch={onLaunch} /></EvidenceProvider>);
}
describe("Scenario Lab", () => {
  it("keeps the notice and fixture marker on every selection and labels every number", () => {
    const { container } = mount();
    for (const scenario of Object.values(S.scenarios)) {
      fireEvent.click(screen.getByRole("button", { name: scenario.name }));
      expect(screen.getByText(S.notice)).toBeTruthy();
      expect(screen.getByText(S.fixture)).toBeTruthy();
      expect(screen.getByText(scenario.description)).toBeTruthy();
      expectEveryNumberLabelled(container);
    }
    expect(screen.getByText(S.sensorNote)).toBeTruthy();
  });
  it.each(scenarioConfigs)("launches the selected config: $scenario_id", async (config) => {
    const onLaunch = vi.fn().mockResolvedValue(undefined);
    mount(onLaunch);
    fireEvent.click(screen.getByRole("button", { name: S.scenarios[config.scenario_id as keyof typeof S.scenarios].name }));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: S.launch })));
    expect(onLaunch).toHaveBeenCalledExactlyOnceWith(config);
    expect(screen.getByRole("status").textContent).toBe(S.recorded);
  });
  it("records independently across selection changes and blocks duplicate launches", async () => {
    let resolve!: () => void;
    const onLaunch = vi.fn(() => new Promise<void>((done) => { resolve = done; }));
    mount(onLaunch);
    fireEvent.click(screen.getByRole("button", { name: S.launch }));
    expect((screen.getByRole("button", { name: S.launch }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: S.scenarios.heatwave.name }));
    await act(async () => resolve());
    expect(screen.getByRole("status").textContent).toBe(S.ready);
    fireEvent.click(screen.getByRole("button", { name: S.scenarios.burst_main.name }));
    expect(screen.getByRole("status").textContent).toBe(S.recorded);
    expect(onLaunch).toHaveBeenCalledTimes(1);
  });
  it("allows retry after a launch failure", async () => {
    mount(vi.fn().mockRejectedValue(new Error("fixture failure")));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: S.launch })));
    expect(screen.getByRole("status").textContent).toBe(S.failed);
    expect((screen.getByRole("button", { name: S.launch }) as HTMLButtonElement).disabled).toBe(false);
  });
  it("opens impact formula and inputs, with labels in the evidence drawer", () => {
    const { container } = mount();
    const panel = screen.getByRole("region", { name: S.impact });
    fireEvent.click(within(panel).getByRole("button", { name: "16mSIMULATION" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("min(pressure_samples)")).toBeTruthy();
    expect(within(dialog).getByText("pressure_0")).toBeTruthy();
    expectEveryNumberLabelled(container);
  });
});
