import { describe, expect, it } from "vitest";

import {
  fidelityBadge,
  geometryNotice,
  hasHandDrawnDistrictBoundaries,
  hasPublicGeometryProvenance,
} from "./fidelity";
import type { LoadedNetwork } from "./fidelity";
import { STRINGS } from "./strings";

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

function omit<T extends object>(value: T, key: keyof T): Partial<T> {
  const copy = { ...value };
  delete copy[key];
  return copy;
}

function network(overrides: Partial<LoadedNetwork>): LoadedNetwork {
  return {
    network_version: "n1",
    fidelity: "F1",
    geometry_provenance: PROVENANCE,
    district_boundaries: DISTRICTS,
    ...overrides,
  };
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
      "Fidelity F1: Real OSM streets, hand-drawn districts, inferred pipes, synthetic hydraulics",
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

describe("the hybrid F1 network (owner decisions G1 to G3)", () => {
  it("shows F1 only when the streets are PUBLIC_GEOMETRY and the districts are declared hand-drawn", () => {
    expect(fidelityBadge(network({})).level).toBe("F1");
    expect(fidelityBadge(network({})).text).toBe(
      "Fidelity F1: Real OSM streets, hand-drawn districts, inferred pipes, synthetic hydraulics",
    );
  });

  it.each([
    ["missing", undefined],
    ["null", null],
    ["labelled PUBLIC_GEOMETRY", { ...DISTRICTS, label: "PUBLIC_GEOMETRY" }],
    ["drawn some other way", { ...DISTRICTS, method: "traced" }],
    ["without a source", { ...DISTRICTS, source: " " }],
    ["without a date", { ...DISTRICTS, drawn: "" }],
    ["a string", "hand-drawn"],
  ])("shows the lowest level when the district boundaries are %s", (_name, districts) => {
    const view = fidelityBadge(network({ district_boundaries: districts as never }));
    expect(view).toEqual({ level: "F0", text: STRINGS.fidelity.f0, downgraded: true });
    expect(geometryNotice(network({ district_boundaries: districts as never }))).toBeNull();
    expect(hasHandDrawnDistrictBoundaries(districts)).toBe(false);
  });

  it("adds the attribution and approximation line for F1 only", () => {
    expect(geometryNotice(network({}))).toBe(STRINGS.fidelity.f1Notice);
    expect(STRINGS.fidelity.f1Notice).toContain("© OpenStreetMap contributors (ODbL)");
    expect(STRINGS.fidelity.f1Notice).toContain("hand-drawn approximations");
    for (const other of [null, undefined, network({ fidelity: "F0", geometry_provenance: null })]) {
      expect(geometryNotice(other)).toBeNull();
    }
  });

  it("never throws and never adds the line for unreadable data", () => {
    const exploding = new Proxy({}, { get() { throw new Error("network exploded"); } });
    expect(geometryNotice(exploding as never)).toBeNull();
  });
});

describe("the OpenStreetMap claim needs OpenStreetMap provenance (review round 1)", () => {
  it.each([
    ["another source", { ...PROVENANCE, source: "municipal CAD export, not OpenStreetMap" }],
    ["another licence", { ...PROVENANCE, licence: "CC0" }],
    ["a licence spelled loosely", { ...PROVENANCE, licence: "ODbL" }],
    ["the source in another case", { ...PROVENANCE, source: "openstreetmap" }],
  ])("shows no F1 badge and no attribution line for %s", (_name, provenance) => {
    const loaded = network({ geometry_provenance: provenance as never });
    expect(fidelityBadge(loaded).level).not.toBe("F1");
    expect(geometryNotice(loaded)).toBeNull();
  });
});

