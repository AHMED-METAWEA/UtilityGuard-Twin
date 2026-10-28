import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { expectEveryNumberLabelled } from "../../ui/testing/labelled";

vi.mock("../../../node_modules/@deck.gl/react/dist/deckgl.js", () => ({ default: () => <canvas /> }));
afterEach(cleanup);

it("labels every command number and supplies local evidence for each metric", () => {
  const { container } = render(<App path="/" />);
  const metrics = [...container.querySelectorAll<HTMLButtonElement>(".ug-command .ug-metric")];
  expect(metrics.length).toBeGreaterThanOrEqual(10);
  expectEveryNumberLabelled(container);
  for (const metric of metrics) {
    fireEvent.click(metric);
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).queryByText(/unavailable in this offline view/)).toBeNull();
    expectEveryNumberLabelled(container);
    fireEvent.click(within(drawer).getByRole("button", { name: "Close evidence" }));
  }
});

it("shows open hypotheses with word support, identifier candidates and timestamp detection", () => {
  render(<App path="/" />);
  const alerts = screen.getByRole("region", { name: "Active alerts" });
  expect(within(alerts).getByText("strong")).toBeTruthy();
  expect(within(alerts).getByText("weak")).toBeTruthy();
  expect(within(alerts).getByRole("heading", { name: "Leak" })).toBeTruthy();
  expect(within(alerts).getByRole("heading", { name: "Sensor fault" })).toBeTruthy();
  expect(alerts.textContent).not.toMatch(/probab|confidence|%/i);
  expect(alerts.querySelectorAll("time")).toHaveLength(2);
  expect(alerts.querySelectorAll(".ug-command-candidates li")).toHaveLength(4);
});

it("shows conditional hourly cost with a range, advisory wording and decision link", () => {
  render(<App path="/" />);
  const cost = screen.getByRole("region", { name: "Cost of waiting" });
  expect(cost.textContent).toContain("Model-estimated, conditional on assumptions. Advisory only: a human approves every action.");
  // jsdom has no flex layout; Chromium supplies spaces between the Metric spans.
  const metric = within(cost).getByRole("button", { name: /^720\s*EGP\/h\s*CALCULATED\s*p10: 480\s*p50: 720\s*p90: 1200$/ });
  fireEvent.click(metric);
  expect(screen.getByText("lost_volume_per_hour * unit_price")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Close evidence" }));
  expect(within(cost).getByRole("link", { name: "Compare actions in Decision Studio" }).getAttribute("href")).toBe("#/decision");
  expect(screen.getByLabelText("Replay clock").querySelector("time")?.dateTime).toBe("2026-10-28T10:00:00Z");
});
