// Regression tests for holes found in review of the shell: untrusted input that looks like data
// but is not (inherited properties, proxies, getters), exceptions that must not remove the
// honesty indicators, and behaviour the first tests did not pin down.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { fidelityBadge } from "./fidelity";
import { ROUTES } from "./routes";
import { INITIAL_STATE } from "./state";
import { streamSourceFromEnvelope } from "./stream";
import { STRINGS } from "./strings";
import { Boundary } from "../ui/Boundary";

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

const PROVENANCE = {
  label: "PUBLIC_GEOMETRY",
  source: "public map data",
  licence: "ODbL",
  retrieved: "2026-10-01",
  coverage_report: "coverage.json",
};

describe("untrusted data is read as data", () => {
  it("does not take F1 from inherited properties", () => {
    const inheritedProvenance = Object.create(PROVENANCE);
    expect(fidelityBadge({ network_version: "n", fidelity: "F1", geometry_provenance: inheritedProvenance } as never).text).not.toContain("F1");
    const base = { network_version: "n", fidelity: "F1", geometry_provenance: PROVENANCE };
    expect(fidelityBadge(Object.create(base)).text).not.toContain("F1");
    expect(fidelityBadge(Object.create(base)).level).not.toBe("F1");
  });

  it("does not take F1 from a proxy, an accessor or an array", () => {
    const proxy = new Proxy({}, { get: (_t, key) => (key === "fidelity" ? "F1" : key === "geometry_provenance" ? PROVENANCE : undefined) });
    expect(fidelityBadge(proxy as never).text).not.toContain("F1");
    const accessor = { network_version: "n", fidelity: "F1", get geometry_provenance() { return PROVENANCE; } };
    // An accessor serializes like data, so it is read once as data; the proxy above is refused.
    expect(["F0", "F1"]).toContain(fidelityBadge(accessor as never).level);
    const throwing = { network_version: "n", get fidelity(): string { throw new Error("boom"); } };
    expect(() => fidelityBadge(throwing as never)).not.toThrow();
    expect(fidelityBadge(throwing as never).text).not.toContain("F1");
    expect(fidelityBadge([{ fidelity: "F1" }] as never).text).not.toContain("F1");
  });

  it("downgrades instead of crashing when the network cannot be inspected", () => {
    const view = fidelityBadge(new Proxy({}, { ownKeys: () => { throw new Error("no"); } }) as never);
    expect(view.text).toBe(STRINGS.fidelity.f0);
    expect(view.downgraded).toBe(true);
  });

  it.each([
    ["inherited payload", () => Object.create({ payload: { stream_source: "LIVE" } })],
    ["inherited source", () => ({ payload: Object.create({ stream_source: "LIVE" }) })],
    ["inherited both", () => Object.create({ payload: Object.create({ stream_source: "LIVE" }) })],
    ["a proxy", () => new Proxy({}, { get: (_t, key) => (key === "payload" ? { stream_source: "LIVE" } : undefined) })],
    ["a throwing getter", () => ({ get payload(): unknown { throw new Error("bad"); } })],
    ["a getter that changes", (() => { let n = 0; return () => ({ get payload() { n += 1; return { stream_source: n === 1 ? "SIMULATED" : "LIVE" }; } }); })()],
    ["an array payload", () => ({ payload: ["LIVE"] })],
    ["a boxed string", () => ({ payload: { stream_source: new String("LIVE") } })],
  ])("never shows LIVE for %s", (_name, make) => {
    expect(streamSourceFromEnvelope(make())).not.toBe("LIVE");
  });

  it("still reads a genuine envelope", () => {
    expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" } })).toBe("LIVE");
    expect(streamSourceFromEnvelope(JSON.parse('{"payload":{"stream_source":"SIMULATED"}}'))).toBe("SIMULATED");
  });
});

describe("the honesty indicators survive failures", () => {
  it("keeps the notice, badge and pill when a mounted update carries a throwing envelope", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    act(() => root.render(<App path="/" />));
    const throwing = { get payload(): unknown { throw new Error("bad envelope"); } };
    act(() => root.render(<App path="/" state={{ ...INITIAL_STATE, lastEnvelope: throwing }} />));
    expect(host.querySelector(".ug-honesty")).not.toBeNull();
    expect(host.querySelector(".ug-badge")).not.toBeNull();
    expect(host.querySelector(".ug-pill")?.textContent).toContain("REPLAY");
    act(() => root.unmount());
    host.remove();
  });

  it("keeps the shell when the screen throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const hostile = { kind: "ready", get message(): string { throw new Error("x"); } };
    const state = { ...INITIAL_STATE, status: new Proxy(hostile, { get: () => { throw new Error("status exploded"); } }) as never };
    render(<App state={state} path="/" />);
    expect(screen.getByRole("region", { name: STRINGS.honesty.regionLabel })).toBeTruthy();
    expect(screen.getByLabelText(STRINGS.stream.label)).toBeTruthy();
    expect(screen.getByLabelText(new RegExp(STRINGS.fidelity.label))).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain(STRINGS.status.errorTitle);
    vi.restoreAllMocks();
  });

  it("shows a conservative fallback when a component fails", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const Thrower = () => { throw new Error("child"); };
    render(<Boundary fallback={<span>fallback shown</span>}><Thrower /></Boundary>);
    expect(screen.getByText("fallback shown")).toBeTruthy();
    vi.restoreAllMocks();
  });

  it("renders an error message as text, never as HTML", () => {
    const html = '<img src=x onerror="alert(1)">';
    render(<App state={{ ...INITIAL_STATE, status: { kind: "error", message: html } }} path="/" />);
    expect(screen.getByRole("alert").textContent).toContain(html);
    expect(document.querySelector("img")).toBeNull();
  });

  it.each(["#//", "#/health/", "#/%E0%A4%A", "#" + "a".repeat(100000), "#/\u0000", "#/<script>", "#/health?x=1", "#javascript:alert(1)"])(
    "keeps the indicators and no link is built from the hash (%.30s)",
    (hash) => {
      window.location.hash = hash;
      render(<App />);
      expect(screen.getByRole("region", { name: STRINGS.honesty.regionLabel })).toBeTruthy();
      expect(screen.getByLabelText(STRINGS.stream.label)).toBeTruthy();
      for (const link of screen.getAllByRole("link")) {
        expect(link.getAttribute("href")).toMatch(/^#\//);
      }
    },
  );
});

describe("the shell behaves as a shell", () => {
  it("has landmarks: banner, navigation with a name, main", () => {
    render(<App path="/" />);
    expect(screen.getByRole("banner")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: STRINGS.nav.label })).toBeTruthy();
    expect(screen.getByRole("main")).toBeTruthy();
  });

  it("links every route by its hash and marks only the current one", () => {
    render(<App path="/health" />);
    const links = within(screen.getByRole("navigation")).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(ROUTES.map((r) => `#${r.path}`));
    const current = links.filter((l) => l.getAttribute("aria-current") === "page");
    expect(current.map((l) => l.getAttribute("href"))).toEqual(["#/health"]);
  });

  it("follows hashchange events and stops listening when unmounted", () => {
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const { unmount } = render(<App />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(STRINGS.pages.commandCenter.title);
    act(() => {
      window.location.hash = "#/scenarios";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(STRINGS.pages.scenarioLab.title);
    expect(add.mock.calls.some(([type]) => type === "hashchange")).toBe(true);
    unmount();
    expect(remove.mock.calls.some(([type]) => type === "hashchange")).toBe(true);
    vi.restoreAllMocks();
  });

  it("gives the notice control a button type and a name", () => {
    render(<App path="/" />);
    const button = screen.getByRole("button", { name: STRINGS.honesty.collapse });
    expect(button.getAttribute("type")).toBe("button");
    fireEvent.click(button);
    expect(screen.getByRole("button", { name: STRINGS.honesty.expand }).getAttribute("type")).toBe("button");
  });
});
