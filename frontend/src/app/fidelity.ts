// The Fidelity badge shows the level of the network that is actually loaded, and never a
// higher one (Master Spec 1.4, owner decisions D-005 and G1 to G3). F1 is the hybrid network: street
// geometry with PUBLIC_GEOMETRY provenance from OpenStreetMap, and district boundaries declared as
// hand-drawn ASSUMPTION. A network that lacks either declaration is shown at the lowest level. The input comes from an API later, so it is validated at run time
// even though it is typed.

import { UNREADABLE, isRecord, snapshot } from "./snapshot";
import { STRINGS } from "./strings";

export type FidelityLevel = "F0" | "F1" | "F2" | "F3";

export interface PublicGeometryProvenance {
  label: "PUBLIC_GEOMETRY";
  source: string;
  licence: string;
  retrieved: string;
  coverage_report: string;
}

/** District boundaries of the hybrid F1 network: drawn by hand, so an ASSUMPTION (decision G3). */
export interface DistrictBoundaryProvenance {
  label: "ASSUMPTION";
  method: "hand-drawn";
  source: string;
  drawn: string;
}

export interface LoadedNetwork {
  network_version: string;
  fidelity: FidelityLevel;
  geometry_provenance?: PublicGeometryProvenance | null;
  district_boundaries?: DistrictBoundaryProvenance | null;
}

export type BadgeLevel = "none" | "F0" | "F1";

export interface BadgeView {
  level: BadgeLevel;
  text: string;
  /** The network declared more than its provenance supports; the badge shows the lowest level. */
  downgraded: boolean;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

/** Does the geometry carry the provenance the F1 rule requires (Spec 1.4 and section 2)? */
export function hasPublicGeometryProvenance(value: unknown): boolean {
  const data = snapshot(value);
  if (!isRecord(data)) return false;
  return (
    data.label === "PUBLIC_GEOMETRY" &&
    isNonEmptyString(data.source) &&
    isNonEmptyString(data.licence) &&
    isNonEmptyString(data.retrieved) &&
    isNonEmptyString(data.coverage_report)
  );
}

// The F1 wording names OpenStreetMap and its licence, so only that exact provenance may unlock
// it (review round 1): the backend network model writes the same two values.
export const OSM_SOURCE = "OpenStreetMap";
export const OSM_LICENCE = "ODbL-1.0";

/** Street geometry from OpenStreetMap under the ODbL, with the full PUBLIC_GEOMETRY record. */
export function hasOsmStreetProvenance(value: unknown): boolean {
  if (!hasPublicGeometryProvenance(value)) return false;
  const data = snapshot(value);
  return isRecord(data) && data.source === OSM_SOURCE && data.licence === OSM_LICENCE;
}

/** Are the district boundaries declared as hand-drawn approximations (decision G3)? */
export function hasHandDrawnDistrictBoundaries(value: unknown): boolean {
  const data = snapshot(value);
  if (!isRecord(data)) return false;
  return (
    data.label === "ASSUMPTION" &&
    data.method === "hand-drawn" &&
    isNonEmptyString(data.source) &&
    isNonEmptyString(data.drawn)
  );
}

export function fidelityBadge(network: LoadedNetwork | null | undefined): BadgeView {
  if (network === null || network === undefined) {
    return { level: "none", text: STRINGS.fidelity.none, downgraded: false };
  }
  // Read a stable copy of own data only: inherited properties, proxies and throwing accessors
  // can never authorise a level. Anything that cannot be read shows the lowest level.
  const data = snapshot(network);
  if (data === UNREADABLE || !isRecord(data)) {
    return { level: "F0", text: STRINGS.fidelity.f0, downgraded: true };
  }
  if (
    data.fidelity === "F1" &&
    hasOsmStreetProvenance(data.geometry_provenance) &&
    hasHandDrawnDistrictBoundaries(data.district_boundaries)
  ) {
    return { level: "F1", text: STRINGS.fidelity.f1, downgraded: false };
  }
  if (data.fidelity === "F0") {
    return { level: "F0", text: STRINGS.fidelity.f0, downgraded: false };
  }
  // F1 without provenance, F2 and F3 (which need ACUD data that does not exist), or anything
  // unrecognised: show the lowest level rather than a claim the data cannot back.
  return { level: "F0", text: STRINGS.fidelity.f0, downgraded: true };
}

/**
 * The line the honesty notice adds for an F1 network: the OpenStreetMap attribution the ODbL
 * requires (decision G2) and what is approximate or synthetic. Null for every other level. It
 * never throws: whatever cannot be read gives no F1, so no line.
 */
export function geometryNotice(network: LoadedNetwork | null | undefined): string | null {
  try {
    return fidelityBadge(network).level === "F1" ? STRINGS.fidelity.f1Notice : null;
  } catch {
    return null;
  }
}

/** The network as the shell reads it: one inert copy per render, or nothing it may trust. */
export type NetworkRead = { readable: true; network: unknown } | { readable: false };

/**
 * Reads `state.network` once, through its property descriptor, so an accessor is never called
 * (review round 1: a getter could answer differently to the badge and to the notice). The badge
 * and the notice are both derived from the copy this returns. Never throws.
 */
export function readNetwork(state: unknown): NetworkRead {
  try {
    if (typeof state !== "object" || state === null) return { readable: false };
    const descriptor = Object.getOwnPropertyDescriptor(state, "network");
    if (descriptor === undefined) return { readable: true, network: null };
    if (!("value" in descriptor)) return { readable: false };
    return { readable: true, network: snapshot(descriptor.value) };
  } catch {
    return { readable: false };
  }
}

