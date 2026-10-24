# Scenario schema

Every run is described by a `ScenarioConfig` (pydantic, `backend/app/scenarios/schema.py`). The API accepts a preset id or a full config. The config is canonicalised and hashed for reproducibility.

```json
{
  "scenario_id": "leak_sudden",
  "network_version": "ugtwin-v1",
  "seed": 105,
  "duration_hours": 48,
  "timestep_minutes": 5,
  "demand": {
    "holiday": false,
    "heatwave_multiplier": 1.0,
    "zone_multipliers": {"gov": 1.0, "res": 1.0, "com": 1.0}
  },
  "faults": [
    {
      "type": "leak",
      "location": "pipe:PIPE_17",
      "start_hour": 12,
      "profile": "sudden",
      "ramp_hours": 0,
      "final_area_cm2": 8.0
    }
  ]
}
```

## Validation rules

- `duration_hours * 60 / timestep_minutes` must be a whole number.
- `network_version` must match this build (`ugtwin-v1`).
- Faults must start before the end of the run; durations cannot exceed the run.
- A gradual leak requires `ramp_hours > 0`; a sudden leak ignores it.
- Leak locations must be `pipe:PIPE_01` … `pipe:PIPE_60`. Three grid edges are valves (`PIPE_10`, `PIPE_25`, `PIPE_45`) and cannot host a leak.
- Zone multipliers must lie in `(0, 3]`; heatwave multiplier in `[0.5, 2]`.

## Fault types

| Type | Fields | Effect |
| --- | --- | --- |
| `leak` | `location`, `start_hour`, `profile`, `ramp_hours`, `final_area_cm2` | WNTR leak at the pipe midpoint (pipe split into two) |
| `sensor_drift` | `sensor_id`, `start_hour`, `drift_per_hour` | Linear offset added to **measurements only** |
| `sensor_stuck` | `sensor_id`, `start_hour`, `duration_hours` | Reading frozen at its value when the fault starts |
| `sensor_dropout` | `sensor_id`, `start_hour`, `duration_hours`, `probability` | Reading becomes `null` with the given probability per tick |
| `pump_outage` | `pump_id`, `start_hour`, `duration_hours` | Pump set closed; standby is not automatic |
| `demand_change` | `zone_multipliers`, `start_hour` | Unforecast demand change (used by evaluation; no preset requires it) |

## Approximations

1. **Gradual leak**: WNTR uses a constant leak area per simulation. The runner splits the ramp into hourly chunks, updates the area, and carries the tank level into the next chunk. Tank level is continuous; other states restart from the new steady solve at each chunk boundary.
2. **Leak location**: a pipe is split at its midpoint into two pipes with a new junction. Diameter, roughness, minor loss and status are preserved; each half keeps half the length.
3. **Pump outage**: the pump link status is changed at chunk boundaries; no ramp-down or cavitation is modelled.
4. **Sensor faults**: applied after noise, so a stuck sensor holds a noisy value at the moment of sticking. Dropouts produce missing values; no interpolation is performed anywhere.
5. **Demand**: zone patterns are ASSUMPTIONs (see `network/zones.py`), applied per junction with a fixed spatial allocation.

These approximations are intentional and are restated in the UI and README.
