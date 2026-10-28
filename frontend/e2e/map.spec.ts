import { expect, test } from "@playwright/test";
import { MAP_STRINGS as S } from "../src/screens/map/strings";

test("fixture map renders, toggles legends and stays entirely offline", async ({ page, context, baseURL }) => {
  const requests: string[] = [], errors: string[] = [], sockets: string[] = [];
  context.on("request", (request) => requests.push(request.url()));
  page.on("websocket", (socket) => sockets.push(socket.url()));
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.addInitScript(() => {
    const probe = { calls: [] as string[], violations: [] as string[] };
    (window as unknown as { __mapProbe: typeof probe }).__mapProbe = probe;
    document.addEventListener("securitypolicyviolation", (event) => probe.violations.push(`${event.effectiveDirective} ${event.blockedURI}`));
    const realFetch = window.fetch.bind(window);
    window.fetch = (input, init) => { probe.calls.push(`fetch ${String(input)}`); return realFetch(input, init); };
    const realBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = (url, data) => { probe.calls.push(`beacon ${String(url)}`); return realBeacon(url, data); };
    for (const name of ["Worker", "SharedWorker", "WebSocket", "EventSource"] as const) {
      const Real = window[name];
      if (Real) window[name] = new Proxy(Real, { construct(target, args, newTarget) { probe.calls.push(`${name} ${String(args[0])}`); return Reflect.construct(target, args, newTarget) as object; } }) as never;
    }
  });
  await page.goto("/#/map");
  const map = page.getByRole("region", { name: S.map });
  await expect(map.locator("canvas")).toBeVisible();
  await expect(map).toHaveAttribute("data-map-ready", "true");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByText(S.fixture, { exact: true })).toBeVisible();
  const legend = page.getByRole("region", { name: S.legend });
  for (const [key, name] of Object.entries({ zones: S.zones, links: S.links, nodes: S.nodes, equipment: S.equipment, sensors: S.sensors, faults: S.faults, pressure: S.pressure, flow: S.flow })) {
    const checkbox = page.getByRole("checkbox", { name, exact: true });
    const initiallyChecked = await checkbox.isChecked();
    await checkbox.setChecked(!initiallyChecked);
    await expect(legend.locator(`[data-layer-legend="${key}"]`)).toHaveCount(initiallyChecked ? 0 : 1);
    await checkbox.setChecked(initiallyChecked);
  }
  const canvas = map.locator("canvas");
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 40, { steps: 15 });
  await page.mouse.up();
  await page.mouse.wheel(0, -150);
  await page.getByRole("button", { name: S.fit }).click();
  await expect(map.locator("canvas")).toBeVisible();
  await page.waitForLoadState("networkidle");
  const unlabelled = await page.locator(".ug-network-map").evaluate((root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const failures: string[] = [];
    let node: Node | null;
    while ((node = walker.nextNode())) if (/\d/.test(node.textContent ?? "") && !node.parentElement?.closest("[data-identifier], time, [data-evidence-label]")) failures.push(node.textContent ?? "");
    return failures;
  });
  expect(unlabelled).toEqual([]);
  const probe = await page.evaluate(() => (window as unknown as { __mapProbe: { calls: string[]; violations: string[] } }).__mapProbe);
  expect(probe.calls).toEqual([]);
  expect(probe.violations).toEqual([]);
  expect(sockets).toEqual([]);
  expect(errors).toEqual([]);
  const origin = new URL(baseURL!).origin;
  expect(requests.filter((url) => !url.startsWith(`${origin}/`) && !url.startsWith("data:"))).toEqual([]);
});
