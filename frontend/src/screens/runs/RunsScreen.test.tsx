import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { App } from "../../app/App";
import { expectEveryNumberLabelled } from "../../ui/testing/labelled";
afterEach(cleanup);
it("marks the fixture and labels every number including drawer provenance", () => {
  const { container } = render(<App path="/runs" />);
  expect(screen.getByText("Fixture data, not a run")).toBeTruthy();
  expectEveryNumberLabelled(container);
  fireEvent.click(screen.getByText("168").closest("button")!);
  expect(screen.getByRole("dialog")).toBeTruthy();
  expectEveryNumberLabelled(container);
});

it("uses identifiers for run metadata and plain text for unavailable hashes", () => {
  render(<App path="/runs" />);
  for (const text of ["fixture_run_001", "42", "normal_week", "fixture_sensors_v1", "fixture_assumptions_v1"]) {
    const identifier = screen.getByText(text);
    expect(identifier.matches("code.ug-identifier[data-identifier]")).toBe(true);
    expect(identifier.closest("[data-evidence-label]")).toBeNull();
  }
  for (const identifier of [...screen.getAllByText("fixture_network_v1"), ...screen.getAllByText("1")]) {
    expect(identifier.matches("code.ug-identifier[data-identifier]")).toBe(true);
  }
  for (const missing of screen.getAllByText("Not available")) {
    expect(missing.closest("[data-evidence-label], [data-identifier]")).toBeNull();
  }
  expect(screen.getAllByText("Not available")).toHaveLength(2);
  expect(screen.getAllByRole("button", { name: /ASSUMPTION/ })).toHaveLength(2);
});
