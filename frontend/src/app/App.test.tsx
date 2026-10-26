import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent } from "@testing-library/react";

import { App } from "./App";
import type { LoadedNetwork } from "./fidelity";
import { ROUTES } from "./routes";
import { INITIAL_STATE } from "./state";
import type { ShellState } from "./state";
import { STRINGS } from "./strings";

afterEach(cleanup);

const PROVENANCE = {
  label: "PUBLIC_GEOMETRY" as const,
  source: "OpenStreetMap",
  licence: "ODbL-1.0",
  retrieved: "2026-10-01",
  coverage_report: "coverage.json",
};

const DISTRICTS = {
  label: "ASSUMPTION" as const,
  method: "hand-drawn" as const,
  source: "manual overlay capital_districts_v1",
  drawn: "2026-10-26",
};

const F1_NETWORK: LoadedNetwork = {
  network_version: "capital_f1_v1",
  fidelity: "F1",
  geometry_provenance: PROVENANCE,
  district_boundaries: DISTRICTS,
};

const envelope = (source: string) => ({ type: "tick", payload: { stream_source: source } });

const STATES: [string, ShellState][] = [
  ["ready", INITIAL_STATE],
  ["loading", { ...INITIAL_STATE, status: { kind: "loading" } }],
  ["error", { ...INITIAL_STATE, status: { kind: "error", message: "The API did not answer." } }],
];

const PATHS = [...ROUTES.map((route) => route.path), "/no-such-screen", "/health/extra", ""];

function expectShell(fidelityText: string, source: string) {
  const notice = screen.getByRole("region", { name: STRINGS.honesty.regionLabel });
  expect(notice).toBeTruthy();
  expect(within(notice).getByText(STRINGS.honesty.statement)).toBeTruthy();
  expect(screen.getByLabelText(`${STRINGS.fidelity.label}: ${fidelityText}`).textContent).toBe(
    fidelityText,
  );
  const pill = screen.getByLabelText(STRINGS.stream.label);
  expect(within(pill).getByText(source)).toBeTruthy();
}

describe("the shell", () => {
  describe.each(STATES)("in the %s state", (_name, state) => {
    it.each(PATHS)("shows the notice, badge and stream source at %j", (path) => {
      render(<App state={state} path={path} />);
      expectShell("No network loaded", "REPLAY");
    });
  });

  it("renders the right screen for each route, and a not-found screen inside the shell", () => {
    for (const route of ROUTES) {
      render(<App path={route.path} />);
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(route.title);
      expect(screen.getByText(route.empty)).toBeTruthy();
      cleanup();
    }
    render(<App path="/no-such-screen" />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      STRINGS.pages.notFound.title,
    );
  });

  it("marks loading as a status and errors as an alert", () => {
    render(<App state={STATES[1]![1]} path="/" />);
    expect(screen.getByRole("status").textContent).toBe(STRINGS.status.loading);
    cleanup();
    render(<App state={STATES[2]![1]} path="/" />);
    expect(screen.getByRole("alert").textContent).toContain("The API did not answer.");
  });

  it("shows the F1 text only for a network with PUBLIC_GEOMETRY provenance", () => {
    render(<App state={{ ...INITIAL_STATE, network: F1_NETWORK }} path="/" />);
    expectShell(STRINGS.fidelity.f1, "REPLAY");
    cleanup();
    const noProvenance = { ...F1_NETWORK, geometry_provenance: null };
    render(<App state={{ ...INITIAL_STATE, network: noProvenance }} path="/" />);
    expectShell(STRINGS.fidelity.f0, "REPLAY");
    expect(document.body.textContent).not.toContain("Fidelity F1");
    expect(screen.getByLabelText(new RegExp(STRINGS.fidelity.f0)).getAttribute("data-downgraded")).toBe(
      "true",
    );
  });

  it("never shows Fidelity F1 with no network or with an F0 network", () => {
    render(<App path="/" />);
    expect(document.body.textContent).not.toContain("Fidelity F1");
    cleanup();
    const f0: LoadedNetwork = { network_version: "n0", fidelity: "F0" };
    render(<App state={{ ...INITIAL_STATE, network: f0 }} path="/" />);
    expectShell(STRINGS.fidelity.f0, "REPLAY");
    expect(document.body.textContent).not.toContain("Fidelity F1");
  });

  it("shows LIVE only when the envelope says so, in every state", () => {
    for (const [, state] of STATES) {
      for (const source of ["REPLAY", "SIMULATED"]) {
        render(<App state={{ ...state, lastEnvelope: envelope(source) }} path="/" />);
        expect(within(screen.getByLabelText(STRINGS.stream.label)).queryByText("LIVE")).toBeNull();
        expect(within(screen.getByLabelText(STRINGS.stream.label)).getByText(source)).toBeTruthy();
        cleanup();
      }
      render(<App state={{ ...state, lastEnvelope: envelope("LIVE") }} path="/" />);
      expect(within(screen.getByLabelText(STRINGS.stream.label)).getByText("LIVE")).toBeTruthy();
      cleanup();
      render(<App state={{ ...state, lastEnvelope: envelope("live") }} path="/" />);
      expect(within(screen.getByLabelText(STRINGS.stream.label)).queryByText("LIVE")).toBeNull();
      cleanup();
    }
  });

  it("says when no stream is connected", () => {
    render(<App path="/" />);
    expect(screen.getByText(STRINGS.stream.noStream)).toBeTruthy();
    cleanup();
    render(<App state={{ ...INITIAL_STATE, lastEnvelope: envelope("SIMULATED") }} path="/" />);
    expect(screen.queryByText(STRINGS.stream.noStream)).toBeNull();
  });

  it("lets the notice collapse to a chip but never disappear", () => {
    render(<App path="/" />);
    fireEvent.click(screen.getByRole("button", { name: STRINGS.honesty.collapse }));
    const notice = screen.getByRole("region", { name: STRINGS.honesty.regionLabel });
    expect(within(notice).getByText(STRINGS.honesty.chip)).toBeTruthy();
    expect(within(notice).queryByText(STRINGS.honesty.statement)).toBeNull();
    expect(screen.queryByRole("button", { name: /close|dismiss|hide|remove/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: STRINGS.honesty.expand }));
    expect(within(notice).getByText(STRINGS.honesty.statement)).toBeTruthy();
  });

  it("follows the address hash", () => {
    window.location.hash = "#/health";
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(STRINGS.pages.systemHealth.title);
    window.location.hash = "";
  });
});

describe("the geometry line of an F1 network (decisions G1 to G3)", () => {
  it("adds the attribution and keeps it visible when the notice is collapsed", () => {
    render(<App state={{ ...INITIAL_STATE, network: F1_NETWORK }} path="/" />);
    const notice = screen.getByRole("region", { name: STRINGS.honesty.regionLabel });
    expect(within(notice).getByText(STRINGS.fidelity.f1Notice)).toBeTruthy();
    fireEvent.click(within(notice).getByRole("button", { name: STRINGS.honesty.collapse }));
    expect(within(notice).getByText(STRINGS.honesty.chip)).toBeTruthy();
    expect(within(notice).getByText(STRINGS.fidelity.f1Notice)).toBeTruthy();
  });

  it("shows no geometry line without an F1 network", () => {
    const noDistricts = { ...F1_NETWORK, district_boundaries: null };
    for (const network of [null, { ...F1_NETWORK, fidelity: "F0" as const }, noDistricts]) {
      cleanup();
      render(<App state={{ ...INITIAL_STATE, network }} path="/" />);
      expect(document.body.textContent).not.toContain("OpenStreetMap");
      expect(document.body.textContent).toContain(STRINGS.honesty.statement);
    }
  });

  it("keeps the notice when reading the network for the line fails", () => {
    const state = { ...INITIAL_STATE };
    Object.defineProperty(state, "network", { get() { throw new Error("network exploded"); } });
    render(<App state={state} path="/" />);
    const notice = screen.getByRole("region", { name: STRINGS.honesty.regionLabel });
    expect(notice.textContent).toContain(STRINGS.honesty.statement);
    expect(document.body.textContent).not.toContain("OpenStreetMap");
  });
});

describe("badge and notice come from one read of the network (review round 1)", () => {
  it("never shows the F1 badge without the attribution when the network changes between reads", () => {
    let reads = 0;
    const state = { ...INITIAL_STATE };
    Object.defineProperty(state, "network", {
      get() {
        reads += 1;
        return reads === 1 ? F1_NETWORK : null;
      },
      enumerable: true,
    });
    render(<App state={state} path="/" />);
    expect(reads).toBe(0); // an accessor is never called
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("Fidelity F1");
    expect(text).not.toContain("OpenStreetMap");
    expect(text).toContain(STRINGS.fidelity.unknown);
  });

  it("shows the badge and the attribution again when a valid F1 network follows a failed read", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = { ...INITIAL_STATE };
    Object.defineProperty(broken, "network", { get() { throw new Error("network exploded"); } });
    const { rerender } = render(<App state={broken} path="/" />);
    expect(document.body.textContent).not.toContain("Fidelity F1");
    rerender(<App state={{ ...INITIAL_STATE, network: F1_NETWORK }} path="/" />);
    expect(screen.getByText(STRINGS.fidelity.f1)).toBeTruthy();
    expect(screen.getByText(STRINGS.fidelity.f1Notice)).toBeTruthy();
  });

  it("shows the F1 badge exactly when it shows the attribution", () => {
    const networks = [
      null,
      F1_NETWORK,
      { ...F1_NETWORK, district_boundaries: null },
      { ...F1_NETWORK, geometry_provenance: { ...PROVENANCE, licence: "CC0" } },
      { ...F1_NETWORK, fidelity: "F0" as const },
    ];
    for (const network of networks) {
      cleanup();
      render(<App state={{ ...INITIAL_STATE, network }} path="/" />);
      const text = document.body.textContent ?? "";
      expect(text.includes(STRINGS.fidelity.f1)).toBe(text.includes(STRINGS.fidelity.f1Notice));
    }
  });
});

describe("a failed part of the shell recovers when new state arrives (review round 1)", () => {
  it("shows the stream source again after the envelope could not be read", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = { ...INITIAL_STATE };
    Object.defineProperty(broken, "lastEnvelope", { get() { throw new Error("envelope exploded"); } });
    const { rerender } = render(<App state={broken} path="/" />);
    expect(screen.getByLabelText(STRINGS.stream.label).textContent).toContain(STRINGS.stream.unknown);
    rerender(<App state={{ ...INITIAL_STATE, lastEnvelope: envelope("SIMULATED") }} path="/" />);
    expect(screen.getByLabelText(STRINGS.stream.label).textContent).toContain("SIMULATED");
  });
});

