import { describe, expect, it } from "vitest";

import { fidelityBadge, hasPublicGeometryProvenance } from "./fidelity";
import type { LoadedNetwork } from "./fidelity";
import { STRINGS } from "./strings";

const PROVENANCE = {
  label: "PUBLIC_GEOMETRY" as const,
  source: "public map data",
  licence: "ODbL",
  retrieved: "2026-10-01",
  coverage_report: "coverage.json",
};

function omit<T extends object>(value: T, key: keyof T): Partial<T> {
  const copy = { ...value };
  delete copy[key];
  return copy;
}

function network(overrides: Partial<LoadedNetwork>): LoadedNetwork {
  return { network_version: "n1", fidelity: "F1", geometry_provenance: PROVENANCE, ...overrides };
}

describe("fidelity badge", () => {
  it("says no network is loaded when there is none", () => {
    for (const none of [null, undefined]) {
      expect(fidelityBadge(none)).toEqual({
        level: "none",
        text: STRINGS.fidelity.none,
        downgraded: false,
      });
    }
    expect(STRINGS.fidelity.none).toBe("No network loaded");
  });

  it("shows F0 for the procedural fallback", () => {
    const view = fidelityBadge(network({ fidelity: "F0", geometry_provenance: null }));
    expect(view).toMatchObject({ level: "F0", downgraded: false });
    expect(view.text).toBe("Fidelity F0: Generic synthetic");
  });

  it("shows the F1 text only when the geometry carries PUBLIC_GEOMETRY provenance", () => {
    const view = fidelityBadge(network({}));
    expect(view).toMatchObject({ level: "F1", downgraded: false });
    expect(view.text).toBe(
      "Fidelity F1: Public capital layout, inferred pipes, synthetic hydraulics",
    );
  });

  it.each([
    ["missing", undefined],
    ["null", null],
    ["wrong label", { ...PROVENANCE, label: "SIMULATION" }],
    ["empty source", { ...PROVENANCE, source: "" }],
    ["blank licence", { ...PROVENANCE, licence: "  " }],
    ["no retrieval date", omit(PROVENANCE, "retrieved")],
    ["a blank retrieval date", { ...PROVENANCE, retrieved: " " }],
    ["no coverage report", omit(PROVENANCE, "coverage_report")],
    ["a blank coverage report", { ...PROVENANCE, coverage_report: "" }],
    ["no source", omit(PROVENANCE, "source")],
    ["no licence", omit(PROVENANCE, "licence")],
    ["no label", omit(PROVENANCE, "label")],
    ["an undefined field (not data)", { ...PROVENANCE, retrieved: undefined }],
    ["a string", "PUBLIC_GEOMETRY"],
    ["a number", 1],
  ])("never shows F1 when the provenance is %s", (_name, provenance) => {
    const view = fidelityBadge(network({ geometry_provenance: provenance as never }));
    expect(view.text).not.toContain("F1");
    expect(view).toMatchObject({ level: "F0", downgraded: true });
  });

  it.each(["F2", "F3", "F4", "f1", "", 1, null])(
    "never claims a level the product cannot back (%s)",
    (level) => {
      const view = fidelityBadge(network({ fidelity: level as never }));
      expect(view.level).toBe("F0");
      expect(view.downgraded).toBe(true);
      expect(view.text).not.toMatch(/F[1-9]/);
    },
  );

  it("treats a malformed network object as lowest level, never as F1", () => {
    for (const bad of [{}, { fidelity: "F1" }, "F1", 7, []]) {
      expect(fidelityBadge(bad as never).text).not.toContain("F1");
    }
  });

  it("validates provenance on its own", () => {
    expect(hasPublicGeometryProvenance(PROVENANCE)).toBe(true);
    expect(hasPublicGeometryProvenance({})).toBe(false);
    expect(hasPublicGeometryProvenance(null)).toBe(false);
  });
});
