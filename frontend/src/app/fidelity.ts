// The Fidelity badge shows the level of the network that is actually loaded, and never a
// higher one (Master Spec 1.4, owner decision D-005). F1 needs geometry that carries
// PUBLIC_GEOMETRY provenance. The input comes from an API later, so it is validated at run time
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

export interface LoadedNetwork {
  network_version: string;
  fidelity: FidelityLevel;
  geometry_provenance?: PublicGeometryProvenance | null;
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
  if (data.fidelity === "F1" && hasPublicGeometryProvenance(data.geometry_provenance)) {
    return { level: "F1", text: STRINGS.fidelity.f1, downgraded: false };
  }
  if (data.fidelity === "F0") {
    return { level: "F0", text: STRINGS.fidelity.f0, downgraded: false };
  }
  // F1 without provenance, F2 and F3 (which need ACUD data that does not exist), or anything
  // unrecognised: show the lowest level rather than a claim the data cannot back.
  return { level: "F0", text: STRINGS.fidelity.f0, downgraded: true };
}
