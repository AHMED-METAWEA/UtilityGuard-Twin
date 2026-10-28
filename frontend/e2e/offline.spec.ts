// Card T-A1-014: prove in a real browser what the static scan (check-offline.mjs) and the
// Content-Security-Policy only claim, that the built shell makes no request to another origin.
//
//   1. The shell, opened on every route, requests nothing but its own files, opens no WebSocket
//      or EventSource, and the CSP reports no violation.
//   2. Code that tries to reach another origin (fetch, image, stylesheet, script, frame,
//      WebSocket, EventSource, beacon) is stopped by the CSP: the browser reports the violation
//      and the request never reaches the network.
//
// The second test is what fails if the Content-Security-Policy tag is removed from the page.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { STRINGS } from "../src/app/strings";

interface Violation {
  directive: string;
  blocked: string;
}
interface Probe {
  violations: Violation[];
  calls: string[];
}
type ProbeWindow = Window & { __ug: Probe };

const ROUTES = [
  { url: "/", heading: STRINGS.pages.commandCenter.title },
  { url: "/#/map", heading: STRINGS.pages.networkMap.title },
  { url: "/#/sensors", heading: STRINGS.pages.sensors.title },
  { url: "/#/scenarios", heading: STRINGS.pages.scenarioLab.title },
  { url: "/#/forecast", heading: STRINGS.pages.forecast.title },
  { url: "/#/decision", heading: STRINGS.pages.decision.title },
  { url: "/#/runs", heading: STRINGS.pages.runs.title },
  { url: "/#/health", heading: STRINGS.pages.systemHealth.title },
  { url: "/#/no-such-screen", heading: STRINGS.pages.notFound.title },
];

// Runs in the page before any of its own script: records every policy violation, and every
// attempt of the page's own code to open a connection.
test.beforeEach(async ({ page }) => {
  // No recorded run here: the same-origin API answers an empty list, so screens show fixtures.
  await page.route("**/api/runs", (route) => route.fulfill({ json: [] }));
  await page.addInitScript(() => {
    const probe: Probe = { violations: [], calls: [] };
    (window as unknown as ProbeWindow).__ug = probe;
    document.addEventListener(
      "securitypolicyviolation",
      (event) => {
        probe.violations.push({ directive: event.effectiveDirective, blocked: event.blockedURI });
      },
      true,
    );
    const asText = (input: unknown) => (input instanceof Request ? input.url : String(input));
    const realFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      probe.calls.push(`fetch ${asText(input)}`);
      return realFetch(input, init);
    };
    const realBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = (url, data) => {
      probe.calls.push(`sendBeacon ${asText(url)}`);
      return realBeacon(url, data);
    };
    for (const name of ["WebSocket", "EventSource"] as const) {
      const Real = window[name];
      window[name] = new Proxy(Real, {
        construct(target, args: [string | URL, ...unknown[]], newTarget) {
          probe.calls.push(`${name} ${asText(args[0])}`);
          return Reflect.construct(target, args, newTarget) as object;
        },
      }) as never;
    }
  });
});

async function expectHonestShell(page: Page, heading: string): Promise<void> {
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await expect(page.getByRole("region", { name: STRINGS.honesty.regionLabel })).toContainText(
    STRINGS.honesty.statement,
  );
  await expect(page.getByText(STRINGS.fidelity.none, { exact: true })).toBeVisible();
  const pill = page.getByLabel(STRINGS.stream.label);
  await expect(pill).toContainText("REPLAY");
  await expect(pill).toContainText(STRINGS.stream.noStream);
  await expect(pill).not.toContainText("LIVE");
}

test("the shell makes no request to another origin on any route", async ({ page, context, baseURL }) => {
  const origin = new URL(baseURL ?? "").origin;
  const requests: string[] = [];
  const sockets: string[] = [];
  const problems: string[] = [];
  const violations: Violation[] = [];
  const calls: string[] = [];
  context.on("request", (request) => requests.push(request.url()));
  page.on("websocket", (socket) => sockets.push(socket.url()));
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console error: ${message.text()}`);
  });

  for (const route of ROUTES) {
    await page.goto("about:blank");
    await page.goto(route.url);
    await expectHonestShell(page, route.heading);
    await page.waitForLoadState("networkidle");
    const probe = await page.evaluate(() => (window as unknown as ProbeWindow).__ug);
    violations.push(...probe.violations);
    calls.push(...probe.calls);
  }

  const files = requests.filter((url) => url.startsWith(`${origin}/`));
  expect(files.length, "the shell's own files were requested").toBeGreaterThanOrEqual(3);
  const outside = requests.filter((url) => !url.startsWith(`${origin}/`) && !url.startsWith("data:") && url !== "about:blank");
  expect(outside, "requests to another origin").toEqual([]);
  expect(sockets, "WebSockets opened").toEqual([]);
  // The recorded-run client (src/app/api.ts) may fetch same-origin /api/runs paths; nothing else.
  const apiCall = /^fetch \/api\/runs(?:\/[A-Za-z0-9_.:@-]+)*$/;
  expect(
    calls.filter((call) => !apiCall.test(call)),
    "fetch, beacon, WebSocket or EventSource calls made by the shell",
  ).toEqual([]);
  expect(violations, "Content-Security-Policy violations").toEqual([]);
  expect(problems, "errors reported by the page").toEqual([]);
});

// Each attempt uses its own host under `.invalid`, which never resolves, so a request that is
// not stopped by the policy would fail with a name-resolution error, not a policy error (the
// browser names a policy block `csp`).
const ATTEMPTS = [
  { kind: "fetch", directive: /^connect-src$/ },
  { kind: "image", directive: /^img-src$/ },
  { kind: "stylesheet", directive: /^style-src(-elem)?$/ },
  { kind: "script", directive: /^script-src(-elem)?$/ },
  { kind: "frame", directive: /^frame-src$/ },
  { kind: "websocket", directive: /^connect-src$/ },
  { kind: "eventsource", directive: /^connect-src$/ },
  { kind: "beacon", directive: /^connect-src$/ },
] as const;

test("the Content-Security-Policy stops every kind of outside request", async ({ page, context }) => {
  const failed: { url: string; error: string }[] = [];
  const finished: string[] = [];
  context.on("requestfailed", (request) => failed.push({ url: request.url(), error: request.failure()?.errorText ?? "" }));
  context.on("requestfinished", (request) => finished.push(request.url()));
  await page.goto("/");
  await expectHonestShell(page, STRINGS.pages.commandCenter.title);

  const violations = await page.evaluate(async () => {
    const host = (kind: string) => `${kind}.example.invalid`;
    const settle = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
    const target = (kind: string) => `https://${host(kind)}/x`;
    const wait = (attach: (done: () => void) => void) =>
      new Promise<void>((resolve) => {
        attach(resolve);
        setTimeout(resolve, 1500);
      });

    await fetch(target("fetch")).catch(() => undefined);
    await wait((done) => {
      const image = new Image();
      image.onload = image.onerror = done;
      image.src = target("image");
    });
    await wait((done) => {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.onload = link.onerror = done;
      link.href = target("stylesheet");
      document.head.append(link);
    });
    await wait((done) => {
      const script = document.createElement("script");
      script.onload = script.onerror = done;
      script.src = target("script");
      document.head.append(script);
    });
    await wait((done) => {
      const frame = document.createElement("iframe");
      frame.onload = done;
      frame.src = target("frame");
      document.body.append(frame);
    });
    await wait((done) => {
      const socket = new WebSocket(`wss://${host("websocket")}/x`);
      socket.onerror = socket.onclose = done;
    });
    await wait((done) => {
      const source = new EventSource(target("eventsource"));
      source.onerror = done;
    });
    navigator.sendBeacon(target("beacon"), "x");
    await settle(500);
    return (window as unknown as ProbeWindow).__ug.violations;
  });

  for (const attempt of ATTEMPTS) {
    const seen = violations.find((violation) => violation.blocked.includes(`${attempt.kind}.example.invalid`));
    expect(seen, `${attempt.kind}: the browser reported no Content-Security-Policy violation`).toBeDefined();
    expect(seen?.directive, `${attempt.kind}: wrong directive`).toMatch(attempt.directive);
  }
  const notStopped = [
    ...failed.filter((entry) => entry.url.includes(".invalid") && !/csp/i.test(entry.error)),
    ...finished.filter((url) => url.includes(".invalid")).map((url) => ({ url, error: "finished" })),
  ];
  expect(notStopped, "outside requests that the policy did not stop").toEqual([]);
});
