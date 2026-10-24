# WNTR API notes

`pip` resolved **WNTR 1.5.0** (with `pandas` 2.x, `numpy` 2.x). The following APIs were checked by introspection and by running the network before being used. If WNTR is upgraded, re-check these first.

## Model construction

- `WaterNetworkModel()` + `add_junction`, `add_reservoir`, `add_tank`, `add_pipe`, `add_pump`, `add_valve`, `add_pattern`, `add_curve` accept the keyword arguments used in `builder.py`.
- Junction demand: `junction.demand_timeseries_list[0].base_value` (m³/s) and `demand_pattern` at creation.
- Pump curve: `add_curve(name, "HEAD", [(flow, head), ...])`, then `add_pump(..., pump_type="HEAD", pump_parameter=name)`.
- Pump status: `link.status` is read-only; `link.initial_status = LinkStatus.Open/Closed` sets the status used by the solver at t=0. `result.link["status"]` is the solved status (1 open, 0 closed).
- Tank initial level: `tank.init_level` (m above tank elevation).

## Options

- `wn.options.hydraulic.demand_model = "PDD"`, `minimum_pressure`, `required_pressure`, `pressure_exponent`.
- `wn.options.time.duration`, `hydraulic_timestep`, `report_timestep`, `pattern_timestep` (seconds).
- Pattern objects need `pattern.time_options = wn.options.time` when multipliers are replaced between chunks.

## Leaks

- WNTR 1.5 provides `Junction.add_leak(wn, area, discharge_coeff=..., start_time=...)`; there is **no** `add_leak` on pipes.
- A mid-pipe leak is therefore modelled by splitting the pipe: remove the original link, add a junction at the midpoint with the average elevation, and add two half-length pipes with the same diameter/roughness/minor loss/status.
- Leak flow appears in `results.node["leak_demand"]` (m³/s); emitter fields are not used.
- `result.node["pressure"]` for a tank is the level above its elevation (metres), which is why the runner stores it directly as tank level. This was verified against the known initial level and the mass balance of F01−F02.

## Results

- `WNTRSimulator(wn).run_sim()` returns a result with `node` and `link` DataFrames keyed in SI units.
- `result.node["pressure"]`, `["demand"]`, `["head"]`, `["leak_demand"]`; `result.link["flowrate"]`, `["status"]`.
- Link flow is m³/s; the sensor layer converts flow to L/s for measurement, and the API exposes truth flow in L/s.
- Report rows are at `report_timestep`; with hydraulic = report = pattern timestep, row *i* is tick *i*. Chunks longer than one tick are solved in one call, and row 0 of later chunks duplicates the carried state, so it is skipped.

## Known constraints

- No valve operation API is used for isolation/repair; the impact runner represents isolation by reducing the leak area. Changing valve status mid-run would require an event-based WNTR simulation (`run_sim` with controls), which is out of scope here.
- Constant leak area per chunk: gradual leaks are approximated by hourly chunks.
- The solver can warn about negative pressures during a large leak; these are reported as simulated values, not hidden.
