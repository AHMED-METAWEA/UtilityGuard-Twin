import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvidenceRecord } from "../generated/evidence-record";
import { EvidenceProvider } from "./evidence";
import type { MetricProps } from "./Metric";
import { Metric } from "./Metric";
import { formatValue } from "./format";
import { expectEveryNumberLabelled } from "./testing/labelled";

const record: EvidenceRecord = {
  schema_version: "1", evidence_id: "cost.1", label: "CALCULATED", value: -12.5, unit: "EGP",
  formula: "quantity * price", inputs: [
    { name: "quantity", value: 5, unit: "m³", label: "SIMULATION", ref: "quantity.1" },
    { name: "price", value: -2.5, unit: "EGP/m³", label: "ASSUMPTION", ref: "price.1" },
  ], provenance: { seed: 42, cost_model: "fixture_v1" },
  uncertainty: { p10: -15, p50: -12.5, p90: -10, basis: "Assumed fixture range" },
  explanation_template: "Quantity multiplied by the assumed price.",
};
afterEach(cleanup);
// Compiled by tsc: omission must remain a type error. Never executed.
function typeAssertions() {
  // @ts-expect-error An evidence label is mandatory, even with a record.
  return <Metric value={1} unit={null} evidence={record} />;
}
void typeAssertions;

describe("Metric and evidence drawer", () => {
  it("opens, explains inputs and range, traps focus, closes and returns focus", () => {
    const { container } = render(<EvidenceProvider><Metric value={record.value} unit={record.unit} label={record.label} evidence={record} /></EvidenceProvider>);
    const metric = screen.getByRole("button");
    metric.focus();
    fireEvent.click(metric);
    const dialog = screen.getByRole("dialog");
    expect(screen.getByText("quantity * price")).toBeTruthy();
    expect(screen.getByText("Quantity multiplied by the assumed price.")).toBeTruthy();
    expect(screen.getByText("quantity.1")).toBeTruthy();
    expect(screen.getByText("price.1")).toBeTruthy();
    expect(screen.getByText("Assumed fixture range")).toBeTruthy();
    expectEveryNumberLabelled(container);
    const close = screen.getByRole("button", { name: "Close evidence" });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(close, { key: "Tab", shiftKey: true });
    expect(document.activeElement).not.toBe(close);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(metric);
  });
  it("resolves local ids, keeps one drawer, and shows missing records explicitly", () => {
    render(<EvidenceProvider records={[record]}><Metric value={-12.5} unit="EGP" label="CALCULATED" evidenceId={record.evidence_id} /></EvidenceProvider>);
    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(screen.getByText("5").closest("button")!);
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByText("Evidence record unavailable in this offline view.")).toBeTruthy();
  });
  it("requires a label at runtime", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<EvidenceProvider><Metric {...({ value: 2, unit: null, evidenceId: "x" } as unknown as MetricProps)} /></EvidenceProvider>)).toThrow(/evidence label/);
    error.mockRestore();
  });
  it("rejects an inconsistent record and formats deterministically", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<EvidenceProvider><Metric value={1} unit="EGP" label="CALCULATED" evidence={record} /></EvidenceProvider>)).toThrow(/match/);
    error.mockRestore();
    expect(formatValue(-1234.5)).toBe("-1234.5");
    expect(formatValue(0)).toBe("0");
    expect(() => formatValue(Infinity)).toThrow(/finite/);
  });
});
it("keeps a supplied record available when opening its id from the drawer", () => {
  render(<EvidenceProvider><Metric value={record.value} unit={record.unit} label={record.label} evidence={record} /></EvidenceProvider>);
  fireEvent.click(screen.getByRole("button"));
  fireEvent.click(screen.getByRole("dialog").querySelector("button.ug-metric")!);
  expect(screen.queryByText("Evidence record unavailable in this offline view.")).toBeNull();
  expect(screen.getAllByRole("dialog")).toHaveLength(1);
});
it("shows the reason for missing evidence without labelling metadata as missing", () => {
  const missing: EvidenceRecord = { ...record, label: "INSUFFICIENT_EVIDENCE", value: null, unit: null,
    formula: null, inputs: [], uncertainty: undefined, reason: "No readings for sensor 17", explanation_template: undefined };
  const { container } = render(<EvidenceProvider><Metric value={null} unit={null} label={missing.label} evidence={missing} /></EvidenceProvider>);
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByText("No readings for sensor 17")).toBeTruthy();
  expectEveryNumberLabelled(container);
});

it("formats fixed decimals and thin-space grouping without a locale dependency", () => {
  expect(formatValue(12.5, 2)).toBe("12.50");
  expect(formatValue(-12.5, 3)).toBe("-12.500");
  expect(formatValue(12.56, 1)).toBe("12.6");
  expect(formatValue(11520)).toBe("11\u2009520");
  expect(formatValue(-11520)).toBe("-11\u2009520");
  expect(formatValue(1234567.5, 2)).toBe("1\u2009234\u2009567.50");
  expect(formatValue(-11520.5, 2)).toBe("-11\u2009520.50");
  expect(formatValue(9999)).toBe("9999");
  expect(formatValue(10000)).toBe("10\u2009000");
  expect(formatValue(1e21, 2)).toBe("1\u2009000\u2009000\u2009000\u2009000\u2009000\u2009000\u2009000.00");
});
it("renders drawer provenance ids, input keys and versions as identifiers", () => {
  render(<EvidenceProvider><Metric value={record.value} unit={record.unit} label={record.label} evidence={record} /></EvidenceProvider>);
  fireEvent.click(screen.getByRole("button"));
  for (const text of ["cost.1", "quantity.1", "price.1", "fixture_v1", "42", "1", "quantity", "seed"]) {
    const identifier = screen.getByText(text);
    expect(identifier.matches("code.ug-identifier[data-identifier]")).toBe(true);
    expect(identifier.closest("[data-evidence-label]")).toBeNull();
  }
});
