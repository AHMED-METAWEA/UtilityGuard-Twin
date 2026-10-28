import { test, expect } from "@playwright/test";
import { SCENARIO_STRINGS as S } from "../src/screens/scenarios/strings";

for (const width of [1440, 390]) {
  test(`scenario fixtures, launch and evidence at width ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const external: string[] = [];
    page.on("request", (request) => { if (new URL(request.url()).hostname !== "127.0.0.1") external.push(request.url()); });
    await page.goto("/#/scenarios");
    for (const scenario of Object.values(S.scenarios)) {
      await page.getByRole("button", { name: scenario.name, exact: true }).click();
      await expect(page.getByText(S.notice)).toBeVisible();
      await expect(page.getByText(S.fixture)).toBeVisible();
      await expect(page.getByText(scenario.description)).toBeVisible();
      await page.getByRole("button", { name: S.launch, exact: true }).click();
      await expect(page.getByRole("status")).toHaveText(S.recorded);
      const unlabelled = await page.locator(".ug-scenarios").evaluate((root) => {
        const failures: string[] = [];
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          if (/\d/.test(node.textContent ?? "") && !node.parentElement?.closest("time, [data-identifier], [data-evidence-label]")) failures.push(node.textContent ?? "");
        }
        return failures;
      });
      expect(unlabelled).toEqual([]);
    }
    await expect(page.getByText(S.sensorNote)).toBeVisible();
    await page.getByRole("region", { name: S.impact }).getByRole("button", { name: "41 m SIMULATION", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("min(pressure_samples)")).toBeVisible();
    expect(external).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
