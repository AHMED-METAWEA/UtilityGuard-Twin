import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SensorsScreen, SensorDataQuality } from "./SensorsScreen";
import { SENSOR_STRINGS as S } from "./strings";
import { ROUTES } from "../../app/routes";
import { createSensorFixtures, SENSOR_CATALOG } from "../../fixtures/sensors";

const route = ROUTES.find((r) => r.path === "/sensors")!;
afterEach(cleanup);
function chartPath() { return screen.getByTestId("series-line").getAttribute("d"); }
function assertLabelledNumbers(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    if (/\d/.test(node.textContent ?? "") && !node.parentElement?.closest("[data-identifier], time")) {
      expect(node.parentElement?.closest("[data-evidence-label]"), node.textContent ?? "").toBeTruthy();
    }
  }
}

describe("Sensors and Data Quality", () => {
  it("lists sensors, units, evidence and quality flags, and has no unlabelled numeric text", () => {
    const { container } = render(<SensorsScreen route={route} />);
    expect(screen.getByText(S.fixture)).toBeTruthy();
    expect(screen.getByText(S.scope)).toBeTruthy();
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(13);
    for (const sensor of SENSOR_CATALOG) expect(screen.getByRole("button", { name: sensor.id })).toBeTruthy();
    expect(within(rows[3]!).getByText(S.flags.Q04.name)).toBeTruthy();
    expect(within(rows[2]!).getByText(S.flags.Q01.name)).toBeTruthy();
    for (const flag of Object.values(S.flags)) expect(screen.getByText(flag.explanation)).toBeTruthy();
    for (const identifier of container.querySelectorAll("code[data-identifier]")) expect(identifier.closest("[data-evidence-label]")).toBeNull();
    expect(container.querySelector("time")?.dateTime).toBe("2026-01-02T12:00:00Z");
    expect(screen.getByLabelText(S.rate).closest("[data-evidence-label]")).toBeNull();
    expect(screen.getByText(S.late)).toBeTruthy();
    assertLabelledNumbers(container);
  });

  it.each([S.disable, S.stuck, S.drift])("%s changes readings and flags visibly; reset restores exact chart and table", (name) => {
    const { container } = render(<SensorsScreen route={route} />);
    const originalPath = chartPath();
    const originalTable = screen.getByRole("table").innerHTML;
    fireEvent.click(screen.getByRole("button", { name }));
    expect(chartPath()).not.toBe(originalPath);
    expect(screen.getByRole("status").textContent).toBe(S.applied);
    const row = within(screen.getByRole("table")).getAllByRole("row")[1]!;
    const flag = name === S.disable ? S.flags.Q01.name : name === S.stuck ? S.flags.Q04.name : S.flags.Q08.name;
    expect(within(row).getByText(flag)).toBeTruthy();
    assertLabelledNumbers(container);
    fireEvent.click(screen.getByRole("button", { name: S.reset }));
    expect(chartPath()).toBe(originalPath);
    expect(screen.getByRole("table").innerHTML).toBe(originalTable);
  });

  it("injects a request for the selected sensor and replay tick with rate units per hour", () => {
    const onWhatIf = vi.fn();
    const onReset = vi.fn();
    const readings = createSensorFixtures();
    render(<SensorDataQuality readings={readings} sensors={SENSOR_CATALOG} onWhatIf={onWhatIf} onReset={onReset} />);
    fireEvent.click(screen.getByRole("button", { name: "SENSOR_06" }));
    fireEvent.change(screen.getByLabelText(S.cursor), { target: { value: "300" } });
    fireEvent.change(screen.getByLabelText(S.rate), { target: { value: "-0.1" } });
    fireEvent.click(screen.getByRole("button", { name: S.drift }));
    expect(onWhatIf).toHaveBeenLastCalledWith({ sensor_id: "SENSOR_06", from_tick: 300, mode: "drift", drift_per_hour: -0.1 });
    fireEvent.click(screen.getByRole("button", { name: S.stuck }));
    expect(onWhatIf).toHaveBeenLastCalledWith({ sensor_id: "SENSOR_06", from_tick: 300, mode: "stuck" });
    fireEvent.click(screen.getByRole("button", { name: S.reset }));
    expect(onReset).toHaveBeenCalledWith("SENSOR_06");
    expect(onWhatIf).toHaveBeenCalledTimes(2);
  });

  it("uses baseline on repeated modes, preserves other sensors and resets independently", () => {
    render(<SensorsScreen route={route} />);
    const original = chartPath();
    fireEvent.click(screen.getByRole("button", { name: S.drift }));
    const drifted = chartPath();
    fireEvent.click(screen.getByRole("button", { name: S.drift }));
    expect(chartPath()).toBe(drifted);
    fireEvent.click(screen.getByRole("button", { name: "SENSOR_02" }));
    fireEvent.click(screen.getByRole("button", { name: S.disable }));
    fireEvent.click(screen.getByRole("button", { name: "SENSOR_01" }));
    expect(chartPath()).toBe(drifted);
    fireEvent.click(screen.getByRole("button", { name: S.reset }));
    expect(chartPath()).toBe(original);
    fireEvent.click(screen.getByRole("button", { name: "SENSOR_02" }));
    expect(screen.getAllByTestId("quality-marker").length).toBeGreaterThan(50);
  });

  it("handles no readings and refuses a missing current value for stuck mode", () => {
    const { rerender } = render(<SensorDataQuality readings={[]} onWhatIf={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText(S.noData)).toBeTruthy();
    rerender(<SensorDataQuality readings={createSensorFixtures()} onWhatIf={vi.fn()} onReset={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "SENSOR_02" }));
    fireEvent.change(screen.getByLabelText(S.cursor), { target: { value: "330" } });
    expect((screen.getByRole("button", { name: S.stuck }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(S.rate), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: S.drift }));
    expect(screen.getByRole("status").textContent).toBe(S.error);
  });
});
