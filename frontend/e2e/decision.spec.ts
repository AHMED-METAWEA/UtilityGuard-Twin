import { test, expect } from "@playwright/test";
import { DECISION_STRINGS as S } from "../src/screens/decision/strings";

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`decision fixture and evidence at ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const external: string[] = [];
    page.on("request", request => {
      if (new URL(request.url()).origin !== new URL(page.url()).origin && page.url() !== "about:blank") external.push(request.url());
    });
    await page.goto("/#/decision");
    await expect(page.getByText(S.fixture, { exact: true })).toBeVisible();
    await expect(page.getByText(S.advisory, { exact: true })).toBeVisible();
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(5);
    await expect(page.getByTestId("net-wait_short")).toContainText("-60");
    await expect(page.getByText(S.lowest, { exact: true })).toBeVisible();
    await page.getByRole("table").getByRole("row").nth(1).getByRole("button").nth(1).click();
    await expect(page.getByRole("dialog").getByText("quantity * unit_price")).toBeVisible();
    await expect(page.getByRole("dialog").getByText("unit_price", { exact: true })).toBeVisible();
    const unlabelled = await page.locator("body").evaluate(root => {
      const failures: string[] = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!/\d/.test(node.textContent ?? "")) continue;
        const parent = node.parentElement;
        if (!parent || parent.closest("time, [data-identifier], .ug-honesty, .ug-badge")) continue;
        if (!parent.checkVisibility()) continue;
        const label = parent.closest("[data-evidence-label]")?.getAttribute("data-evidence-label");
        if (!label || !["OBSERVED", "BENCHMARK", "PUBLIC_GEOMETRY", "SIMULATION", "SENSOR_SIM", "MODEL", "ASSUMPTION", "CALCULATED", "INSUFFICIENT_EVIDENCE"].includes(label)) failures.push(node.textContent ?? "");
      }
      return failures;
    });
    expect(unlabelled).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.locator(".ug-honesty")).toBeVisible();
    await expect(page.locator(".ug-badge")).toBeVisible();
    await expect(page.locator(".ug-pill")).toBeVisible();
    await page.getByRole("dialog").getByRole("button", { name: "Close evidence" }).click();
    const afterClose = await page.locator("body").evaluate(root => {
      const failures: string[] = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!/\d/.test(node.textContent ?? "")) continue;
        const parent = node.parentElement;
        if (!parent || parent.closest("time, [data-identifier], .ug-honesty, .ug-badge")) continue;
        if (!parent.checkVisibility()) continue;
        const label = parent.closest("[data-evidence-label]")?.getAttribute("data-evidence-label");
        if (!label || !["OBSERVED", "BENCHMARK", "PUBLIC_GEOMETRY", "SIMULATION", "SENSOR_SIM", "MODEL", "ASSUMPTION", "CALCULATED", "INSUFFICIENT_EVIDENCE"].includes(label)) failures.push(node.textContent ?? "");
      }
      return failures;
    });
    expect(afterClose).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(external).toEqual([]);
    await page.screenshot({ path: `/tmp/ug-u06-decision-${viewport.width}.png`, fullPage: true });
  });
}
