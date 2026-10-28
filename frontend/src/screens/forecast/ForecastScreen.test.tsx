import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "../../app/App";
import { expectEveryNumberLabelled } from "../../ui/testing/labelled";
import { createForecastFixture } from "../../fixtures/forecast";
import { FORECAST_STRINGS as S } from "./strings";
afterEach(cleanup);
describe("Forecast and Early Warning", () => {
  it("renders both zone bands, measured series, tank thresholds and labelled numbers", () => {
    const { container } = render(<App path="/forecast" />);
    expect(screen.getByText(S.fixture)).toBeTruthy();
    expect(screen.getAllByTestId("range-band")).toHaveLength(4);
    expect(screen.getAllByTestId("series-line")).toHaveLength(10);
    expect(screen.getByText(S.stableReason, { exact: false })).toBeTruthy();
    expectEveryNumberLabelled(container);
    // Expanded data tables expose every sample and band endpoint as a Metric.
    for (const details of container.querySelectorAll("details")) details.open = true;
    expectEveryNumberLabelled(container);
  });
  it("opens threshold-time evidence with its formula, inputs and conditional explanation", () => {
    const { container } = render(<App path="/forecast" />);
    fireEvent.click(screen.getByRole("button", { name: /^4hCALCULATED$/ }));
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText("(threshold - current_level) / forecast_slope")).toBeTruthy();
    expect(within(drawer).getByText(S.fallingReason)).toBeTruthy();
    expectEveryNumberLabelled(container);
    fireEvent.click(within(drawer).getByRole("button", { name: "Close evidence" }));
    fireEvent.click(screen.getByRole("button", { name: /INSUFFICIENT_EVIDENCE/ }));
    expect(within(screen.getByRole("dialog")).getByText(S.stableReason)).toBeTruthy();
    expectEveryNumberLabelled(container);
  });
  it("is deterministic and has one conditional crossing from forecast slope", () => {
    const fixture = createForecastFixture();
    expect(fixture).toEqual(createForecastFixture());
    expect(fixture.tanks.filter(t => t.timeToThreshold.label === "CALCULATED")).toHaveLength(1);
    const tank = fixture.tanks[0]!;
    const slope = (tank.forecast.values[1]! - tank.forecast.values[0]!) / (tank.forecast.step_seconds / 3600);
    expect((Number(tank.threshold.value) - tank.forecast.values[0]!) / slope).toBe(tank.timeToThreshold.value);
    expect(tank.forecast.values[0]).toBe(tank.measured.values.at(-1));
    expect(Date.parse(tank.forecast.start)).toBe(Date.parse(tank.measured.start) + (tank.measured.values.length - 1) * tank.measured.step_seconds * 1000);
    expect(fixture.tanks[1]!.timeToThreshold.value).toBeNull();
    for (const zone of fixture.zones) {
      expect(zone.demand.label).toBe("MODEL"); expect(zone.inlet.label).toBe("SENSOR_SIM");
      expect(zone.demand.band!.p10.length).toBe(zone.demand.values.length);
    }
    const trend = fixture.trends[0]!.evidence;
    expect(trend.value).toBe(Number(trend.inputs[0]!.value) / Number(trend.inputs[1]!.value));
  });
});
