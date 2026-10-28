import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "../../app/App";
import { expectEveryNumberLabelled } from "../../ui/testing/labelled";
import { createDecisionFixture } from "../../fixtures/decision";
import { DECISION_STRINGS as S } from "./strings";
afterEach(cleanup);
describe("Decision Studio", () => {
  it("labels every number, shows advisory wording and preserves signed net benefit", () => {
    const { container } = render(<App path="/decision" />);
    expect(screen.getByText(S.fixture)).toBeTruthy(); expect(screen.getByText(S.advisory)).toBeTruthy();
    expect(screen.getByTestId("net-wait_short").textContent).toContain("-60");
    expect(screen.getByTestId("net-wait_day").textContent).toContain("+1260");
    expect(screen.getByText(S.lowest).closest("tr")?.textContent).toContain("wait_short");
    expectEveryNumberLabelled(container);
    expect(container.textContent).not.toMatch(/recommended|likely|chance|%/i);
  });
  it("opens each option cost, worst case and regret with formula and inputs", () => {
    const { container } = render(<App path="/decision" />);
    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    for (const row of rows) {
      for (const button of within(row).getAllByRole("button").slice(1)) {
        fireEvent.click(button);
        const drawer = screen.getByRole("dialog");
        expect(within(drawer).getByText("quantity * unit_price")).toBeTruthy();
        expect(within(drawer).getByText("quantity")).toBeTruthy();
        expect(within(drawer).getByText("unit_price")).toBeTruthy();
        expectEveryNumberLabelled(container);
        fireEvent.click(within(drawer).getByRole("button", { name: "Close evidence" }));
      }
    }
  });
  it("reconciles deterministic comparison records, line sums, regret and net benefit", () => {
    const fixture = createDecisionFixture(), payload = fixture.comparison;
    expect(fixture).toEqual(createDecisionFixture()); expect(payload.options).toHaveLength(4); expect(payload.advisory).toBe(true);
    const find = (id: string) => payload.evidence.find(r => r.evidence_id === id)!;
    for (const item of payload.evidence) {
      expect(item.kind).toBe("cost"); expect(item.label).toBe("CALCULATED"); expect(item.unit).toBe("EGP");
      expect(item.inputs).toHaveLength(2);
      const quantities = item.inputs.filter(i => ["MODEL", "SIMULATION"].includes(i.label));
      const prices = item.inputs.filter(i => i.label === "ASSUMPTION");
      expect(quantities).toHaveLength(1); expect(prices).toHaveLength(1);
      expect(["m3", "kWh"]).toContain(quantities[0]!.unit);
      expect(["EGP/m3", "EGP/kWh", "EGP"]).toContain(prices[0]!.unit);
      expect(item.value).toBeCloseTo(Number(quantities[0]!.value) * Number(prices[0]!.value));
      expect(item.explanation_template).toMatch(/^[a-z0-9_]+(\.[a-z0-9_]+)*\.v[0-9]+$/);
    }
    const minimum = Math.min(...payload.options.map(o => Number(find(o.expected_cost).value)));
    for (const option of payload.options) {
      const expected = Number(find(option.expected_cost).value);
      expect(option.cost_lines).toHaveLength(5);
      expect(option.cost_lines.reduce((sum, id) => sum + Number(find(id).value), 0)).toBeCloseTo(expected);
      expect(find(option.worst_case).value).toBeCloseTo(find(option.expected_cost).uncertainty!.p90);
      expect(find(option.expected_regret).value).toBeCloseTo(expected - minimum);
      if (option.option_id === payload.preferred_by_expected_cost) expect(expected).toBe(minimum);
    }
    const now = Number(find(payload.options[0]!.expected_cost).value);
    for (const net of fixture.netBenefits) {
      const option = payload.options.find(o => o.option_id === net.option_id)!;
      expect(net.evidence.value).toBe(Number(find(option.expected_cost).value) - now);
    }
    expect(fixture.netBenefits.some(n => Number(n.evidence.value) < 0)).toBe(true);
    const q = Number(fixture.breakEven.value), delay = 6, operatingRate = 24;
    const nowRepair = payload.options[0]!.cost_lines.slice(3).reduce((sum, id) => sum + Number(find(id).value), 0);
    const waitRepair = payload.options[1]!.cost_lines.slice(3).reduce((sum, id) => sum + Number(find(id).value), 0);
    expect(q * delay * operatingRate).toBeCloseTo(nowRepair - waitRepair);
    expect(fixture.waitingCost.value).toBeCloseTo((5 / 3) * operatingRate);
  });
});
