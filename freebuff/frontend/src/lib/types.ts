// Shared API types. Mirrors the pydantic payloads in backend/app/main.py.

export type EvidenceLabel =
  | 'SIMULATION'
  | 'SENSOR_SIM'
  | 'MODEL'
  | 'ASSUMPTION'
  | 'CALCULATED'
  | 'INSUFFICIENT_EVIDENCE';

export type QualityStatus = 'ok' | 'suspect' | 'bad';

export interface SensorMeta {
  id: string;
  kind: 'pressure' | 'flow' | 'level';
  target: string;
  unit: string;
  sigma: number;
  zone: string | null;
  x: number;
  y: number;
}

export interface NodeSpec {
  id: string;
  kind: 'junction' | 'reservoir' | 'tank';
  x: number;
  y: number;
  elevation_m: number;
  zone: string | null;
}

export interface LinkSpec {
  id: string;
  kind: 'pipe' | 'pump' | 'valve';
  start: string;
  end: string;
  length_m: number | null;
  diameter_mm: number | null;
  valve_type: string | null;
  setting: number | null;
  zone: string | null;
}

export interface ZoneSpec {
  id: string;
  label: string;
  node_ids: string[];
  peak_demand_lps: number;
}

export interface NetworkDescription {
  network_version: string;
  nodes: NodeSpec[];
  links: LinkSpec[];
  sensors: SensorMeta[];
  zones: ZoneSpec[];
  pumps: { id: string; role: string; curve: [number, number][]; initial_status: string }[];
  tank: Record<string, number | string>;
  reservoir: Record<string, number | string>;
  notes: string[];
  sensor_metadata?: SensorMeta[];
  labels?: Record<string, EvidenceLabel>;
  disclaimer?: string;
}

export interface ScenarioConfig {
  scenario_id: string;
  network_version: string;
  seed: number;
  duration_hours: number;
  timestep_minutes: number;
  demand: {
    holiday: boolean;
    heatwave_multiplier: number;
    zone_multipliers: Record<string, number>;
  };
  faults: Record<string, unknown>[];
}

export interface Preset {
  scenario_id: string;
  note: string;
  config: ScenarioConfig;
}

export interface RunSummary {
  run_id: string;
  scenario_id: string;
  status: 'queued' | 'simulating' | 'ready' | 'error';
  error: string | null;
  network_version: string;
  seed: number;
  created_at: string;
  simulated_hours: number;
  ticks: number;
  output_hash: string | null;
  runtime_seconds: number | null;
  config: ScenarioConfig;
  labels: Record<string, EvidenceLabel>;
  speed?: number;
  incident_count?: number;
  has_analysis?: boolean;
}

export interface SensorReading {
  sensor_id: string;
  value: number | null;
  unit: string;
  source: EvidenceLabel;
  quality: { status: QualityStatus; score: number; flags: string[] };
}

export interface Frame {
  run_id: string;
  tick: number;
  sim_time: string;
  readings: SensorReading[];
  tank: { sensor_id: string; level_m: number | null };
  detector: {
    state: 'normal' | 'watch' | 'alert';
    residuals: Record<string, number>;
  };
  alerts_changed: unknown[];
  labels: Record<string, EvidenceLabel>;
}

export interface Incident {
  id: string;
  run_id: string;
  status: string;
  severity: 'low' | 'medium' | 'high';
  diagnosis: 'leak' | 'pump_issue' | 'sensor_fault' | 'demand_change' | 'unknown';
  suspected_location: string | null;
  first_detected_tick: number;
  first_detected_time: string;
  last_tick: number;
  rules_fired: string[];
  sensors: string[];
  candidates: { pipe: string; score: number }[];
  quality_context: Record<string, unknown>;
  evidence_numbers: {
    residuals_sigma?: Record<string, number>;
    [key: string]: unknown;
  };
  strength: string;
  labels: Record<string, EvidenceLabel>;
}

export interface EvidenceRecord {
  name: string;
  value: string | number | boolean | null;
  unit: string;
  label: EvidenceLabel;
  formula: string;
  inputs: { name: string; value?: unknown; unit?: string; label: EvidenceLabel }[];
  sources: Record<string, unknown>;
  explanation: string;
}

export interface EvidenceBundle {
  incident: Incident;
  numbers: EvidenceRecord[];
  reproducibility: Record<string, unknown>;
  decision_available: boolean;
  disclaimer: string;
}

export interface CostLine {
  line: string;
  quantity: number;
  unit: string;
  unit_price: number;
  unit_price_unit: string;
  assumption: string;
  formula: string;
  label: EvidenceLabel;
  cost: number;
  evidence?: string;
}

export interface MonteCarlo {
  samples: number;
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  label: EvidenceLabel;
  formula: string;
  note: string;
}

export interface Impact {
  action: string;
  leak_variant: string;
  leak_area_cm2: number;
  estimated_leak_area_cm2: number;
  leak_pipe: string | null;
  horizon_hours: number;
  water_lost_m3: number;
  unserved_m3: number;
  low_pressure_node_hours: number;
  affected_nodes: number;
  pump_energy_kwh: number;
  series: {
    tick: number[];
    time_iso: string[];
    leak_flow_lps: number[];
    unserved_lps: number[];
    min_pressure_m: number[];
    tank_level_m: number[];
    pump_flow_lps: number[];
  };
  labels: Record<string, EvidenceLabel>;
  method: string;
}

export interface DecisionAction {
  action: string;
  label: string;
  expected_cost: number;
  mode_cost: number;
  cost_p10: number;
  cost_p50: number;
  cost_p90: number;
  cost_lines: CostLine[];
  representative_cost_lines: CostLine[];
  impacts: Record<string, Impact>;
  remaining_risk: {
    water_lost_m3: number;
    unserved_m3: number;
    low_pressure_node_hours: number;
    affected_nodes: number;
    label: EvidenceLabel;
  };
  constraint_ok: boolean;
  within_budget: boolean;
  monte_carlo: MonteCarlo;
}

export interface Decision {
  decision_id: string;
  incident_id: string;
  run_id: string;
  scenario_id: string;
  diagnosis: string;
  actions: DecisionAction[];
  ranking: string[];
  feasible_ranking: string[];
  recommended_action: string;
  recommended_label: string;
  savings_vs_monitor: number;
  savings_label: EvidenceLabel;
  savings_note: string;
  break_even: {
    action: string;
    threshold: number | null;
    text: string;
    label: EvidenceLabel;
    formula: string;
  }[];
  sensitivity: {
    assumption: string;
    unit: string;
    low: number;
    mode: number;
    high: number;
    winner_at_low: string;
    winner_at_high: string;
    flips_ranking: boolean;
    flip_value: number | null;
    label: EvidenceLabel;
    note: string;
  }[];
  constraints: {
    max_unserved_m3: number;
    budget: number | null;
    constraint_ok: boolean;
    note: string;
  };
  horizon_hours: number;
  assumptions_version: string;
  assumption_values: Record<string, number>;
  labels: Record<string, EvidenceLabel>;
  advisory: string;
  method_note: string;
  evidence: Record<string, unknown>;
}

export interface AssumptionItem {
  value: number;
  unit: string;
  low: number;
  high: number;
  label: EvidenceLabel;
  description: string;
}

export interface AssumptionsPayload {
  version: string;
  base_version: string;
  currency: string;
  updated_at: string | null;
  assumptions: Record<string, AssumptionItem>;
  labels: Record<string, EvidenceLabel>;
  disclaimer: string;
  editable: boolean;
}

export interface TruthBundle {
  run_id: string;
  labels: Record<string, EvidenceLabel>;
  disclaimer: string;
  truth: {
    time_iso: string[];
    pressure: Record<string, number[]>;
    flow_lps: Record<string, number[]>;
    tank_level: number[];
    leak_flow_lps: number[];
    leak_area_cm2: number[];
    leak_node: string | null;
    leak_pipe: string | null;
    pump_status: Record<string, string[]>;
    delivered_lps: Record<string, number[]>;
  };
  baseline: {
    pressure: Record<string, number[]>;
    tank_level: number[];
    leak_flow_lps: number[];
  };
}
