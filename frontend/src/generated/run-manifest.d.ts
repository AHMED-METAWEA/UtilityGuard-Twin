/**
 * Generated from contracts/v1/run-manifest.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

/**
 * One injected fault: one of the catalogue of Master Spec 5.4. A type that is not in the catalogue matches none of the alternatives and is rejected.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "fault".
 */
export type Fault =
  | LeakGradualFault
  | LeakSuddenFault
  | BurstFault
  | BackgroundLeakageFault
  | SensorDriftFault
  | SensorOffsetFault
  | SensorStuckFault
  | SensorNoiseGrowthFault
  | SensorDropoutFault
  | CommsOutageFault
  | PumpOutageFault
  | PumpDegradationFault
  | ValveStateFault
  | FireFlowFault
  | PowerLossFault;

/**
 * Everything needed to reproduce a run (Master Spec 10.4), in the shape `ug_core.Manifest.to_dict()` produces. The configuration is a scenario configuration. Output hashes are recorded next to the manifest and are not part of its input hash.
 */
export interface RunManifest {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  config: ScenarioConfiguration;
  seed: number;
  versions: {
    [k: string]: string;
  };
  libraries: {
    [k: string]: string;
  };
  git_commit: string | null;
  unordered: string[];
  output_hashes: {
    [k: string]: string;
  };
}
/**
 * Master Spec 12.3. Shape and ranges only; whether faults refer to existing elements and fit the horizon is checked by scenario validation against a network.
 */
export interface ScenarioConfiguration {
  /**
   * Contract version; every payload carries it.
   */
  schema_version: "1";
  scenario_id: string;
  network_version: string;
  sensor_set: string;
  seed: number;
  /**
   * UTC, whole seconds.
   */
  start: string;
  duration_hours: number;
  timestep_minutes: number;
  demand: {
    calendar: string;
    holiday: boolean;
    ramadan: boolean;
    heatwave_multiplier: number;
    zone_multipliers: {
      [k: string]: number;
    };
    forecast_error: {
      model: "ar1";
      sigma_pct: number;
    };
  };
  faults: Fault[];
  /**
   * No cross-domain input is defined in v1 (water only). Electricity and cooling add their shape in a later version.
   *
   * @maxItems 0
   */
  cross_domain_inputs: [];
  assumption_set: string;
}
/**
 * F-LEAK-G: a leak that grows over ramp_hours to final_area_cm2.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "leak_gradual".
 */
export interface LeakGradualFault {
  type: "leak";
  start_hour: number;
  profile: "gradual";
  location: string;
  ramp_hours: number;
  final_area_cm2: number;
}
/**
 * F-LEAK-S: a leak that starts at final_area_cm2 at once.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "leak_sudden".
 */
export interface LeakSuddenFault {
  type: "leak";
  start_hour: number;
  profile: "sudden";
  location: string;
  final_area_cm2: number;
}
/**
 * F-BURST: a large step outflow.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "burst".
 */
export interface BurstFault {
  type: "burst";
  start_hour: number;
  location: string;
  final_area_cm2: number;
}
/**
 * F-LEAK-BG: raised night flow in one zone.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "background_leakage".
 */
export interface BackgroundLeakageFault {
  type: "background_leakage";
  start_hour: number;
  zone_id: string;
  fraction: number;
}
/**
 * F-SEN-DRIFT: linear bias.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "sensor_drift".
 */
export interface SensorDriftFault {
  type: "sensor_drift";
  start_hour: number;
  sensor_id: string;
  drift_per_hour: number;
}
/**
 * F-SEN-OFFSET: constant bias.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "sensor_offset".
 */
export interface SensorOffsetFault {
  type: "sensor_offset";
  start_hour: number;
  sensor_id: string;
  magnitude: number;
}
/**
 * F-SEN-STUCK: frozen value.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "sensor_stuck".
 */
export interface SensorStuckFault {
  type: "sensor_stuck";
  start_hour: number;
  sensor_id: string;
  duration_hours: number;
}
/**
 * F-SEN-NOISE: increased variance.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "sensor_noise_growth".
 */
export interface SensorNoiseGrowthFault {
  type: "sensor_noise_growth";
  start_hour: number;
  sensor_id: string;
  factor: number;
}
/**
 * F-SEN-DROP: missing readings; probability is an input of the scenario.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "sensor_dropout".
 */
export interface SensorDropoutFault {
  type: "sensor_dropout";
  start_hour: number;
  sensor_id: string;
  duration_hours: number;
  probability: number;
}
/**
 * F-COMMS: group-wide missing data.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "comms_outage".
 */
export interface CommsOutageFault {
  type: "comms_outage";
  start_hour: number;
  rtu_group: string;
  duration_hours: number;
}
/**
 * F-PUMP-OUT: pump off.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "pump_outage".
 */
export interface PumpOutageFault {
  type: "pump_outage";
  start_hour: number;
  pump_id: string;
  duration_hours: number;
}
/**
 * F-PUMP-DEG: custom degradation model, an ASSUMPTION everywhere it is shown.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "pump_degradation".
 */
export interface PumpDegradationFault {
  type: "pump_degradation";
  start_hour: number;
  pump_id: string;
  rate_per_hour: number;
}
/**
 * F-VALVE: valve closed or stuck.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "valve_state".
 */
export interface ValveStateFault {
  type: "valve_state";
  start_hour: number;
  valve_id: string;
  state: "closed" | "stuck";
}
/**
 * F-FIRE: local demand spike.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "fire_flow".
 */
export interface FireFlowFault {
  type: "fire_flow";
  start_hour: number;
  node: string;
  flow_l_s: number;
  duration_hours: number;
}
/**
 * F-POWER: power loss at a station; the pump outage follows through the dependency.
 *
 * This interface was referenced by `ScenarioConfiguration`'s JSON-Schema
 * via the `definition` "power_loss".
 */
export interface PowerLossFault {
  type: "power_loss";
  start_hour: number;
  station_id: string;
  duration_hours: number;
}
