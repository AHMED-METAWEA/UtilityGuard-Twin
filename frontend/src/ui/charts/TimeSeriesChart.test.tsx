import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TimeSeriesChart } from "./TimeSeriesChart";
import type { ChartSeries } from "./TimeSeriesChart";
import { Sparkline } from "./Sparkline";

afterEach(cleanup);
const series: ChartSeries[] = [{
  id: "pressure", name: "Pressure", unit: "m", label: "SENSOR_SIM",
  points: [
    { tick: 0, value: 20, lower: 18, upper: 23 },
    { tick: 1, value: null, flags: ["Q01"] },
    { tick: 2, value: 25, lower: 22, upper: 28, flags: ["Q08"] },
    { tick: 3, value: 24, lower: 21, upper: 27, flags: ["Q01", "Q04"] },
  ],
}, {
  id: "expected", name: "Expected", unit: "m", label: "MODEL",
  points: [{ tick: 0, value: 22 }, { tick: 3, value: 25 }],
}];

describe("hand-written charts", () => {
  it("plots multiple series, a discontinuous band, quality markers, time axes and replay cursor", () => {
    const { container } = render(<TimeSeriesChart title="Pressure history" series={series} nowTick={2} />);
    const lines = screen.getAllByTestId("series-line");
    expect(lines).toHaveLength(2);
    expect(lines[0]?.getAttribute("d")?.match(/M/g)).toHaveLength(2);
    expect(screen.getAllByTestId("range-band")[0]?.getAttribute("d")?.match(/Z/g)).toHaveLength(2);
    expect(screen.getAllByTestId("quality-marker")).toHaveLength(3);
    const cursor = screen.getByTestId("now-marker").querySelector("line")!;
    expect(cursor.getAttribute("x1")).toBe(cursor.getAttribute("x2"));
    expect(Number(cursor.getAttribute("x1"))).toBeGreaterThan(72);
    expect(Number(cursor.getAttribute("x1"))).toBeLessThan(712);
    expect(screen.getByText("00:00").getAttribute("data-evidence-label")).toBe("SENSOR_SIM");
    expect(screen.getByText("25.00").closest("[data-evidence-label]")?.getAttribute("data-evidence-label")).toBe("MODEL");
    for (const text of container.querySelectorAll("svg text")) {
      if (/\d/.test(text.textContent ?? "")) expect(text.getAttribute("data-evidence-label")).toBe("SENSOR_SIM");
    }
  });

  it("handles empty, all-missing and constant series without invalid geometry", () => {
    const { rerender, container } = render(<TimeSeriesChart title="Empty" series={[]} />);
    expect(screen.getByText("No readings to plot")).toBeTruthy();
    for (const value of [null, 0, -2]) {
      rerender(<TimeSeriesChart title="Edge cases" series={[{ ...series[0]!, points: [{ tick: 7, value }] }]} nowTick={999} />);
      expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
      expect(screen.queryByTestId("now-marker")).toBeNull();
    }
  });

  it("keeps gaps and zero values in compact sparklines", () => {
    const { container } = render(<Sparkline points={[{ tick: 0, value: 0 }, { tick: 1, value: null }, { tick: 2, value: 2 }]} />);
    expect(container.querySelector("path")?.getAttribute("d")?.match(/M/g)).toHaveLength(2);
    expect(screen.getByRole("img", { name: "Reading trend" })).toBeTruthy();
  });
});
