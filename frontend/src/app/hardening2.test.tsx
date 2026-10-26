// Round 2 of the review: state read inside the boundaries, input accepted only as inert data,
// and the offline check applying the same URL normalisation as a browser.
import { act, cleanup, render, screen } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { fidelityBadge } from "./fidelity";
import { INITIAL_STATE } from "./state";
import { streamSourceFromEnvelope } from "./stream";
import { STRINGS } from "./strings";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const PROVENANCE = { label: "PUBLIC_GEOMETRY", source: "s", licence: "l", retrieved: "2026-10-01", coverage_report: "c" };

describe("state is read inside the boundaries", () => {
  it.each(["network", "lastEnvelope", "status"])("keeps the notice when state.%s throws on a mounted update", (key) => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    act(() => root.render(<App path="/" />));
    const state = { ...INITIAL_STATE };
    Object.defineProperty(state, key, { get() { throw new Error(`${key} exploded`); }, enumerable: true });
    act(() => root.render(<App path="/" state={state} />));
    expect(host.querySelector(".ug-honesty")).not.toBeNull();
    expect(host.textContent).toContain(STRINGS.honesty.statement);
    expect(host.querySelector(".ug-badge")).not.toBeNull();
    expect(host.querySelector(".ug-pill")).not.toBeNull();
    expect(host.querySelector("nav")).not.toBeNull(); // only the failing part is replaced
    expect(host.textContent).not.toMatch(/Fidelity F\d/);
    expect(host.textContent).not.toContain("LIVE");
    act(() => root.unmount());
    host.remove();
  });

  it("shows a static notice with unknown indicators when the whole shell fails", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const state = new Proxy({}, { get() { throw new Error("everything exploded"); } });
    render(<App path="/" state={state as never} />);
    expect(screen.getByRole("region", { name: STRINGS.honesty.regionLabel })).toBeTruthy();
    expect(document.body.textContent).toContain(STRINGS.honesty.statement);
    expect(document.body.textContent).not.toMatch(/Fidelity F\d|REPLAY|SIMULATED|LIVE/);
  });
});

describe("only inert data is accepted", () => {
  class WithHook {
    fidelity = "F1";
    geometry_provenance = PROVENANCE;
    toJSON() { return { fidelity: "F0" }; }
  }
  const hidden = (o: object, key: string, value: unknown) => Object.defineProperty(o, key, { value, enumerable: false });

  it.each([
    ["a class instance", () => new WithHook()],
    ["a non-enumerable toJSON", () => hidden({ fidelity: "F1", geometry_provenance: PROVENANCE }, "toJSON", () => ({}))],
    ["a symbol key", () => ({ fidelity: "F1", geometry_provenance: PROVENANCE, [Symbol("x")]: 1 })],
    ["an accessor", () => ({ fidelity: "F1", get geometry_provenance() { return PROVENANCE; } })],
    ["a Date", () => new Date()],
    ["a Map", () => new Map([["fidelity", "F1"]])],
    ["a non-enumerable field", () => hidden({ fidelity: "F1" }, "geometry_provenance", PROVENANCE)],
    ["a cyclic object", () => { const o: Record<string, unknown> = { fidelity: "F1", geometry_provenance: PROVENANCE }; o.self = o; return o; }],
    ["a deeply nested object", () => { let o: Record<string, unknown> = { fidelity: "F1" }; for (let i = 0; i < 200; i++) o = { next: o }; return { fidelity: "F1", geometry_provenance: o }; }],
    ["a huge string", () => ({ fidelity: "F1", geometry_provenance: { ...PROVENANCE, source: "x".repeat(1_000_000) } })],
  ])("never gives F1 for %s", (_name, make) => {
    const view = fidelityBadge(make() as never);
    expect(view.text).not.toContain("F1");
    expect(view.level).not.toBe("F1");
  });

  it.each([
    ["a class instance", () => { class E { payload = { stream_source: "LIVE" }; toJSON() { return {}; } } return new E(); }],
    ["a non-enumerable toJSON", () => hidden({ payload: { stream_source: "LIVE" } }, "toJSON", () => ({}))],
    ["an alternating accessor", (() => { let n = 0; return () => ({ payload: { get stream_source() { n += 1; return n % 2 ? "LIVE" : "REPLAY"; } } }); })()],
    ["a symbol key", () => ({ payload: { stream_source: "LIVE" }, [Symbol("x")]: 1 })],
    ["a cyclic object", () => { const o: Record<string, unknown> = { payload: { stream_source: "LIVE" } }; o.self = o; return o; }],
    ["a Map", () => new Map([["payload", { stream_source: "LIVE" }]])],
  ])("never shows LIVE for %s", (_name, make) => {
    expect(streamSourceFromEnvelope(make())).toBe("REPLAY");
  });

  it("accepts the data a JSON parser produces, nested and plain", () => {
    expect(streamSourceFromEnvelope(JSON.parse('{"schema_version":"1","payload":{"stream_source":"LIVE","readings":[]}}'))).toBe("LIVE");
    const districts = { label: "ASSUMPTION", method: "hand-drawn", source: "manual overlay", drawn: "2026-10-26" };
    const network = JSON.parse(JSON.stringify({ network_version: "n", fidelity: "F1", geometry_provenance: PROVENANCE, district_boundaries: districts }));
    expect(fidelityBadge(network).level).toBe("F1");
  });

  it("accepts objects without a prototype", () => {
    const bare = Object.assign(Object.create(null), { payload: Object.assign(Object.create(null), { stream_source: "SIMULATED" }) });
    expect(streamSourceFromEnvelope(bare)).toBe("SIMULATED");
  });

  it("rejects a proxy that forges consistent own properties", () => {
    const forged = new Proxy({}, {
      ownKeys: () => ["payload"],
      getOwnPropertyDescriptor: (_t, key) =>
        key === "payload" ? { value: { stream_source: "LIVE" }, enumerable: true, configurable: true, writable: true } : undefined,
    });
    expect(streamSourceFromEnvelope(forged)).toBe("REPLAY");
    const forgedNetwork = new Proxy({}, {
      ownKeys: () => ["fidelity", "geometry_provenance"],
      getOwnPropertyDescriptor: (_t, key) =>
        key === "fidelity"
          ? { value: "F1", enumerable: true, configurable: true, writable: true }
          : key === "geometry_provenance"
            ? { value: PROVENANCE, enumerable: true, configurable: true, writable: true }
            : undefined,
    });
    expect(fidelityBadge(forgedNetwork as never).text).not.toContain("F1");
  });

  it("refuses data nested deeper than the limit and non-finite numbers", () => {
    let deep: Record<string, unknown> = { leaf: 1 };
    for (let i = 0; i < 40; i += 1) deep = { next: deep };
    expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" }, pad: deep })).toBe("REPLAY");
    expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" }, pad: { a: { b: { c: 1 } } } })).toBe("LIVE");
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" }, value: bad })).toBe("REPLAY");
    }
    expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" }, big: "x".repeat(20000) })).toBe("REPLAY");
    expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" }, items: [1, 2, 3] })).toBe("LIVE");
    expect(streamSourceFromEnvelope({ payload: { stream_source: "LIVE" }, undefinedValue: undefined })).toBe("REPLAY");
  });
});
