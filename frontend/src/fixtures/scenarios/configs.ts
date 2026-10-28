import type { ScenarioConfiguration } from "../../generated/scenario-config";

export const scenarioConfigs = [
  {
    "schema_version": "1",
    "scenario_id": "burst_main",
    "network_version": "procedural-capital-v1-seed1",
    "sensor_set": "S_base",
    "seed": 1,
    "start": "2027-03-04T22:00:00Z",
    "duration_hours": 48,
    "timestep_minutes": 5,
    "demand": {
      "calendar": "default_egypt",
      "holiday": false,
      "ramadan": false,
      "heatwave_multiplier": 1.0,
      "zone_multipliers": {},
      "forecast_error": {
        "model": "ar1",
        "sigma_pct": 6.0
      }
    },
    "faults": [
      {
        "type": "burst",
        "start_hour": 30,
        "location": "pipe:p_0229",
        "final_area_cm2": 50.0
      }
    ],
    "cross_domain_inputs": [],
    "assumption_set": "demand_v1"
  },
  {
    "schema_version": "1",
    "scenario_id": "leak_gradual_medium",
    "network_version": "procedural-capital-v1-seed1",
    "sensor_set": "S_base",
    "seed": 1,
    "start": "2027-03-04T22:00:00Z",
    "duration_hours": 48,
    "timestep_minutes": 5,
    "demand": {
      "calendar": "default_egypt",
      "holiday": false,
      "ramadan": false,
      "heatwave_multiplier": 1.0,
      "zone_multipliers": {},
      "forecast_error": {
        "model": "ar1",
        "sigma_pct": 6.0
      }
    },
    "faults": [
      {
        "type": "leak",
        "profile": "gradual",
        "start_hour": 24,
        "location": "pipe:p_0276",
        "ramp_hours": 24,
        "final_area_cm2": 4.0
      }
    ],
    "cross_domain_inputs": [],
    "assumption_set": "demand_v1"
  },
  {
    "schema_version": "1",
    "scenario_id": "pump_outage_standby",
    "network_version": "procedural-capital-v1-seed1",
    "sensor_set": "S_base",
    "seed": 1,
    "start": "2027-03-04T22:00:00Z",
    "duration_hours": 48,
    "timestep_minutes": 5,
    "demand": {
      "calendar": "default_egypt",
      "holiday": false,
      "ramadan": false,
      "heatwave_multiplier": 1.0,
      "zone_multipliers": {},
      "forecast_error": {
        "model": "ar1",
        "sigma_pct": 6.0
      }
    },
    "faults": [
      {
        "type": "pump_outage",
        "start_hour": 20,
        "pump_id": "station_east_duty_0",
        "duration_hours": 6
      }
    ],
    "cross_domain_inputs": [],
    "assumption_set": "demand_v1"
  },
  {
    "schema_version": "1",
    "scenario_id": "heatwave",
    "network_version": "procedural-capital-v1-seed1",
    "sensor_set": "S_base",
    "seed": 1,
    "start": "2027-03-04T22:00:00Z",
    "duration_hours": 168,
    "timestep_minutes": 5,
    "demand": {
      "calendar": "default_egypt",
      "holiday": false,
      "ramadan": false,
      "heatwave_multiplier": 1.25,
      "zone_multipliers": {},
      "forecast_error": {
        "model": "ar1",
        "sigma_pct": 6.0
      }
    },
    "faults": [],
    "cross_domain_inputs": [],
    "assumption_set": "demand_v1"
  },
  {
    "schema_version": "1",
    "scenario_id": "sensor_stuck_pressure",
    "network_version": "procedural-capital-v1-seed1",
    "sensor_set": "S_base",
    "seed": 1,
    "start": "2027-03-04T22:00:00Z",
    "duration_hours": 48,
    "timestep_minutes": 5,
    "demand": {
      "calendar": "default_egypt",
      "holiday": false,
      "ramadan": false,
      "heatwave_multiplier": 1.0,
      "zone_multipliers": {},
      "forecast_error": {
        "model": "ar1",
        "sigma_pct": 6.0
      }
    },
    "faults": [
      {
        "type": "sensor_stuck",
        "start_hour": 12,
        "sensor_id": "SENSOR_01",
        "duration_hours": 6
      }
    ],
    "cross_domain_inputs": [],
    "assumption_set": "demand_v1"
  }
] satisfies ScenarioConfiguration[];
