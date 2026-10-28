import { expect, test } from "@playwright/test";
import { COMMAND_STRINGS as S } from "../src/screens/command/strings";
import { MAP_STRINGS as MAP } from "../src/screens/map/strings";

for (const viewport of [{ width: 1600, height: 1100 }, { width: 390, height: 844 }]) {
  test(`command fixtures, evidence and offline fonts at ${viewport.width}`, async ({ page, baseURL }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "reduce" });
    const requests: string[] = [];
    const errors: string[] = [];
    page.on("request", (request) => requests.push(request.url()));
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(() => {
      const violations: string[] = [];
      (window as unknown as { commandViolations: string[] }).commandViolations = violations;
      document.addEventListener("securitypolicyviolation", (event) => violations.push(event.effectiveDirective));
    });
    await page.goto("/#/");
    const command = page.locator(".ug-command");
    await expect(command.getByText(S.fixture, { exact: true }).first()).toBeVisible();
    await expect(command.getByRole("heading", { level: 1, name: "Command Center" })).toBeVisible();
    const map = command.getByRole("region", { name: MAP.map });
    await expect(map).toHaveAttribute("data-map-ready", "true");
    await expect(map.locator("canvas")).toBeVisible();
    // The compact map keeps the fault layer enabled, with the same candidates as the alerts.
    await expect(command.getByLabel(MAP.faults, { exact: true })).toBeHidden();
    await expect(command.getByLabel(MAP.faults, { exact: true })).toBeChecked();
    await expect(command.locator(".ug-map-candidates li")).toHaveCount(3);
    const indicators = command.getByRole("region", { name: S.kpis });
    await expect(indicators.getByRole("button")).toHaveCount(5);
    await expect(indicators.getByRole("button", { name: "148 L/s MODEL", exact: true })).toBeVisible();
    await expect(indicators.getByRole("button", { name: "132 L/s SENSOR_SIM", exact: true })).toBeVisible();
    const alerts = command.getByRole("region", { name: S.alerts });
    await expect(alerts.getByText("strong", { exact: true })).toBeVisible();
    await expect(alerts.getByText("weak", { exact: true })).toBeVisible();
    expect(await alerts.textContent()).not.toMatch(/probab|confidence|%/i);
    await expect(alerts.locator("time")).toHaveCount(2);
    await expect(alerts.locator(".ug-command-candidates li")).toHaveCount(4);
    await expect(command.getByLabel(S.clock).locator("time")).toHaveAttribute("datetime", "2026-10-28T10:00:00Z");
    const cost = command.getByRole("region", { name: S.cost });
    await expect(cost.getByText(S.advisory, { exact: true })).toBeVisible();
    const costMetric = cost.getByRole("button", { name: "720 EGP/h CALCULATED p10: 480 p50: 720 p90: 1200", exact: true });
    await expect(costMetric).toBeVisible();
    await costMetric.click();
    const drawer = page.getByRole("dialog", { name: "Evidence", exact: true });
    await expect(drawer.getByText("lost_volume_per_hour * unit_price", { exact: true })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "120 m³/h MODEL", exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Honesty notice" })).toBeVisible();
    await drawer.getByRole("button", { name: "Close evidence", exact: true }).click();
    await expect(costMetric).toBeFocused();
    // Open each summary Metric, ensuring that no fixture evidence is missing.
    const metrics = command.locator(".ug-metric");
    for (let index = 0; index < await metrics.count(); index++) {
      await metrics.nth(index).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText("Evidence record unavailable in this offline view.", { exact: true })).toHaveCount(0);
      await page.keyboard.press("Escape");
    }
    const unlabelled = await command.evaluate((root) => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const failures: string[] = [];
      let node: Node | null;
      while ((node = walker.nextNode())) {
        if (/\d/.test(node.textContent ?? "") && !node.parentElement?.closest("[data-identifier], time, [data-evidence-label]")) failures.push(node.textContent ?? "");
      }
      return failures;
    });
    expect(unlabelled).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.evaluate(async () => {
      for (const family of ["IBM Plex Sans", "IBM Plex Mono"]) {
        await document.fonts.load(`400 16px "${family}"`);
        await document.fonts.load(`600 16px "${family}"`);
      }
      await document.fonts.ready;
    });
    expect(await page.evaluate(() => ["IBM Plex Sans", "IBM Plex Mono"].every((family) =>
      [400, 600].every((weight) => document.fonts.check(`${weight} 16px "${family}"`))))).toBe(true);
    await page.waitForLoadState("networkidle");
    const origin = new URL(baseURL!).origin;
    expect(requests.filter((url) => !url.startsWith(`${origin}/`) && !url.startsWith("data:"))).toEqual([]);
    expect(requests.filter((url) => /\.woff2?$/.test(url)).length).toBeGreaterThanOrEqual(4);
    expect(await page.evaluate(() => (window as unknown as { commandViolations: string[] }).commandViolations)).toEqual([]);
    expect(errors).toEqual([]);
    await page.screenshot({ path: `/tmp/ug-u02-command-${viewport.width}.png`, fullPage: true });
    await cost.getByRole("link", { name: S.decision, exact: true }).click();
    await expect(page).toHaveURL(/#\/decision$/);
  });
}
