import { test, expect } from "@playwright/test";
import { SENSOR_STRINGS as S } from "../src/screens/sensors/strings";

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`fixture controls and labelled numbers at viewport ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/#/sensors");
    await expect(page.getByText(S.fixture)).toBeVisible();
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(13);
    const line = page.getByTestId("series-line");
    const original = await line.getAttribute("d");
    for (const mode of [S.disable, S.stuck, S.drift]) {
      await page.getByRole("button", { name: mode, exact: true }).click();
      await expect(line).not.toHaveAttribute("d", original!);
      await expect(page.getByRole("status")).toHaveText(S.applied);
      await page.getByRole("button", { name: S.reset, exact: true }).click();
      await expect(line).toHaveAttribute("d", original!);
    }
    const unlabelled = await page.locator(".ug-sensors").evaluate((root) => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const failures: string[] = [];
      let node: Node | null;
      while ((node = walker.nextNode())) {
        if (/\d/.test(node.textContent ?? "") && !node.parentElement?.closest("[data-identifier], time") && !node.parentElement?.closest("[data-evidence-label]")) failures.push(node.textContent ?? "");
      }
      return failures;
    });
    expect(unlabelled).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/ug-u05-sensors-${viewport.width}.png`, fullPage: true });
  });
}
