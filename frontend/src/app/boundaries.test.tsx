// If a part of the top bar fails to render, the rest of the shell, the honesty notice above all,
// stays on screen and the failed part says it could not be determined. Each part is made to
// throw here by replacing its module.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { STRINGS } from "./strings";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetModules();
});

describe("a failing part of the top bar", () => {
  it("leaves the notice and the pill when the badge throws", async () => {
    vi.doMock("../ui/FidelityBadge", () => ({ FidelityBadge: () => { throw new Error("badge"); } }));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { App } = await import("./App");
    render(<App path="/" />);
    expect(screen.getByRole("region", { name: STRINGS.honesty.regionLabel })).toBeTruthy();
    const badge = screen.getByLabelText(`${STRINGS.fidelity.label}: ${STRINGS.fidelity.unknown}`);
    expect(badge.textContent).toBe(STRINGS.fidelity.unknown);
    expect(document.body.textContent).not.toMatch(/Fidelity F\d/);
    expect(screen.getByLabelText(STRINGS.stream.label).textContent).toContain("REPLAY");
    vi.doUnmock("../ui/FidelityBadge");
  });

  it("leaves the notice and the badge when the pill throws, and does not claim a source", async () => {
    vi.doMock("../ui/StreamSourcePill", () => ({ StreamSourcePill: () => { throw new Error("pill"); } }));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { App } = await import("./App");
    render(<App path="/" />);
    expect(screen.getByRole("region", { name: STRINGS.honesty.regionLabel })).toBeTruthy();
    expect(screen.getByLabelText(new RegExp(`${STRINGS.fidelity.label}: ${STRINGS.fidelity.none}`))).toBeTruthy();
    const pill = screen.getByLabelText(STRINGS.stream.label);
    expect(pill.textContent).toContain(STRINGS.stream.unknown);
    expect(pill.textContent).not.toMatch(/REPLAY|SIMULATED|LIVE/);
    vi.doUnmock("../ui/StreamSourcePill");
  });

  it("falls back to a static notice with unknown indicators when the shell itself fails", async () => {
    vi.doMock("../ui/HonestyStrip", () => ({ HonestyStrip: () => { throw new Error("strip"); } }));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { App } = await import("./App");
    render(<App path="/" />);
    const notice = screen.getByRole("region", { name: STRINGS.honesty.regionLabel });
    expect(notice.textContent).toContain(STRINGS.honesty.statement);
    expect(screen.getByLabelText(`${STRINGS.fidelity.label}: ${STRINGS.fidelity.unknown}`).textContent).toBe(STRINGS.fidelity.unknown);
    expect(screen.getByLabelText(STRINGS.stream.label).textContent).toContain(STRINGS.stream.unknown);
    expect(document.body.textContent).not.toMatch(/Fidelity F\d|REPLAY|SIMULATED|LIVE/);
    vi.doUnmock("../ui/HonestyStrip");
  });
});
