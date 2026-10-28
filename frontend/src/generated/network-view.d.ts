/**
 * Generated from contracts/v1/network-view.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * The network as the map draws it (DEMO_PLAN D-01): structure and geometry only. By design it carries no simulated state, no fault and no hidden field; states arrive as time series. Coordinates are local metres from the study origin, never geographic.
 */
export interface NetworkView {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  network_hash: string;
  name: string;
  fidelity: "F0" | "F1";
  coordinates: "local_m";
  /**
   * PUBLIC_GEOMETRY when the street geometry comes from a public source (then attribution is required); ASSUMPTION for generated layouts.
   */
  geometry_label: "PUBLIC_GEOMETRY" | "ASSUMPTION";
  attribution?: string;
  attribute_labels: {
    elevation_m: "ASSUMPTION" | "OBSERVED" | "BENCHMARK";
    diameter_m: "ASSUMPTION" | "OBSERVED" | "BENCHMARK";
    length_m: "CALCULATED" | "OBSERVED" | "BENCHMARK";
  };
  /**
   * @minItems 1
   */
  nodes: [
    {
      id: string;
      kind: "junction" | "reservoir" | "tank";
      x: number;
      y: number;
      zone?: string;
      elevation_m: number;
    },
    ...{
      id: string;
      kind: "junction" | "reservoir" | "tank";
      x: number;
      y: number;
      zone?: string;
      elevation_m: number;
    }[]
  ];
  links: {
    id: string;
    kind: "pipe" | "pump" | "valve";
    start: string;
    end: string;
    tier?: "transmission" | "submain" | "distribution";
    diameter_m?: number;
    length_m?: number;
    valve_kind?: "isolation" | "prv";
    /**
     * @minItems 2
     */
    route?: [never[], never[], ...never[][]];
  }[];
  zones: {
    id: string;
    name: string;
    land_use: string;
    /**
     * @minItems 4
     */
    ring: [never[], never[], never[], never[], ...never[][]];
  }[];
  sensors: {
    id: string;
    kind: "pressure" | "flow" | "level";
    element: string;
    sets: string[];
  }[];
}
