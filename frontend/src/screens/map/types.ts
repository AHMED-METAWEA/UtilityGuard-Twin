import type { EvidenceLabel } from "../../generated/common";

// Temporary network-view boundary; replace with the D-01 generated type when frozen.
export type Point = [number, number];
export interface NetworkNode { id: string; kind: "junction" | "reservoir" | "tank"; x: number; y: number; zone?: string; elevation_m: number }
export interface NetworkLink { id: string; kind: "pipe" | "pump" | "valve"; start: string; end: string; tier?: "transmission" | "submain" | "distribution"; diameter_m?: number; length_m?: number; valve_kind?: "isolation" | "prv"; route?: Point[] }
export interface NetworkView {
  schema_version: "1"; network_hash: string; name: string; fidelity: "F0" | "F1"; coordinates: "local_m";
  geometry_label: "PUBLIC_GEOMETRY" | "ASSUMPTION"; attribution?: string;
  attribute_labels: { elevation_m: EvidenceLabel; diameter_m: EvidenceLabel; length_m: EvidenceLabel };
  nodes: NetworkNode[]; links: NetworkLink[];
  zones: { id: string; name: string; land_use: string; ring: Point[] }[];
  sensors: { id: string; kind: "pressure" | "flow" | "level"; element: string; sets: string[] }[];
}
export interface Candidate { asset_id: string; score: number; label: "MODEL" }
export interface TickState { pressure: Record<string, number>; flow: Record<string, number>; labels: Record<string, "SENSOR_SIM" | "MODEL"> }
