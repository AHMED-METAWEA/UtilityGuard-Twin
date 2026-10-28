import { expect, test } from "@playwright/test";
import { createMapFixture } from "../src/fixtures/map";

test("recorded bundle renders the map with REPLAY and run fidelity", async ({ page, baseURL }) => {
  const network = { ...createMapFixture(), network_hash: "a".repeat(64) };
  const sensor = network.sensors.find((s) => s.kind === "pressure")!;
  const series = { schema_version: "1", series_id: `${sensor.id}.sensor`, run_id: "recorded_baseline", kind: "sensor", element: sensor.element, quantity: "pressure", unit: "m", label: "SENSOR_SIM", start: "2027-03-04T22:00:00Z", step_seconds: 300, values: [23.5, 24.1] };
  const outside: string[] = [];
  page.on("request", (request) => { if (new URL(request.url()).origin !== new URL(baseURL!).origin) outside.push(request.url()); });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const payload = path === "/api/runs" ? [{ run_id: series.run_id, scenario_id: "normal_week", seed: 1, simulation_start: series.start }]
      : path.endsWith("/network") ? network : path.endsWith("/series") ? [{ series_id: series.series_id, kind: series.kind, element: series.element, label: series.label }] : series;
    await route.fulfill({ json: payload });
  });
  await page.goto("/#/map");
  await expect(page.locator(".ug-topbar code[data-identifier]")).toHaveText(series.run_id);
  await expect(page.locator(".ug-pill")).toContainText("REPLAY");
  await expect(page.locator(".ug-badge")).toHaveAttribute("data-level", network.fidelity);
  await expect(page.getByText("Fixture data, not a run", { exact: false })).toHaveCount(0);
  await expect(page.locator("[data-map-ready=true]")).toBeVisible();
  await page.getByRole("link", { name: "Command Center", exact: true }).click();
  await expect(page.getByRole("region", { name: "Recorded sensor readings" })).toBeVisible();
  await expect(page.locator('dd[data-evidence-label="SENSOR_SIM"]')).toContainText("24.10 m");
  expect(outside).toEqual([]);
});
