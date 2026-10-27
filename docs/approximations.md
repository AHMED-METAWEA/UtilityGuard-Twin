# Approximations of the twin's physics

What the simulation simplifies, and how large the effect is where it has been measured. Every number here is `SIMULATION` or `CALCULATED` on synthetic networks (fidelity F0 and F1); none is a measurement of a real network. Sections are added by the cards that introduce an approximation.

## Hydraulic engine (T-B1-016)

**Engine.** WNTR 1.5.0, `WNTRSimulator` by default: its leak model is the one the fault cards use (EPANET in WNTR does not support it). `EpanetSimulator` (EPANET 2.2) is available as a cross-check; on the test loop network the two agree within 0.05 m of pressure and 1% of pump flow.

**Pressure-driven demand.** A junction receives its full demand at or above the required pressure (20 m), nothing at or below the minimum pressure (0 m), and `((p - p_min) / (p_req - p_min)) ** 0.5` of it in between (WNTR smooths the two ends over a small pressure band). The three values are placeholders (`solver/data/hydraulics_v1.json`, `ASSUMPTION`), not design criteria of any utility. A test checks the delivered share against the formula at 3, 5 and 12 m within 0.1%.

**Time.** One hydraulic and pattern step of 5 minutes; demand is constant within a step (WNTR reads pattern value k at time k x step). When something changes inside a step (a tank reaches a level limit, a control acts), WNTR solves an extra hydraulic step at that moment; `WNTRSimulator` reports every solved time (`report_timestep = "ALL"`), the truth is sampled at the ticks, and energy uses every solved time (below). Every result table must carry the same time axis, which must hold every tick, or the run is an error.

**Demand.** Each junction gets its own pattern: base demand = the mean of its series, multipliers = series / mean. The demand series comes from the demand model (T-B1-012).

**Equipment.** Duty pumps start open and standby pumps closed; a pump follows its head curve: one point (EPANET's rule, `H = 4/3 H1 - (H1/3)(Q/Q1)^2`), three points (WNTR fits `H = A - B Q^C` through them) or more (WNTR fits the same form by least squares, not EPANET's piecewise-linear curve). Two-point curves are refused: WNTR 1.5 computes their slope from squared flows but solves a straight line (`wntr/network/elements.py:1438-1441`), so the operating point would be wrong without an error (review round 2). Isolation valves are throttle control valves with loss coefficient 0, open (no head loss of their own). PRVs hold their setting downstream; a PRV whose downstream node is fed by other pipes cannot regulate, EPANET reports it closed, and `WNTRSimulator` may not converge (found in the procedural network and fixed by T-B1-011b).

**Tanks.** `WNTRSimulator` lets a filling tank pass its maximum level by what flows in during the step in which it fills (0.13 mm on the test loop) and then closes the inlet; EPANET clips at the maximum exactly. A test bounds the overshoot at 1 mm.

**Pump power and energy.** Power is `rho g Q (H_out - H_in) / efficiency` from the flow through the pump and the heads at its ends (rho 1000 kg/m3, g 9.81 m/s2), zero without flow. The energy of a run integrates the power over every interval between two solved times, holding the power at the start of each interval to its end, as EPANET does for its own steps; the last solved time starts no interval. Holding the power of a tick over the whole 5-minute step instead overstated the energy by 38% when a small tank filled 3 s into a step (review round 1); the engine now agrees with the same network solved at a 1 s step within 1%, and with WNTR's own `pump_power` over the solved times within 1%. `EpanetSimulator` cannot report the extra steps, so it returns no energy (`None`), never a number that may be wrong. A pump that carries flow while losing head (it runs past the flow where its curve reaches zero head; WNTR only warns) is an error, not negative consumption.

**Failures.** Non-convergence, a non-finite result, a results axis that is not the demand series' axis, and reverse flow through a pump beyond 1e-9 m3/s are errors; nothing is replaced by zero.

**Performance (Spec 4.8).** 48 hours at 5 minutes on the procedural network (260 junctions, 340 pipes, 9 pumps, 32 valves, 3 tanks): 5.7 s with `WNTRSimulator` on the lead's laptop (budget 60 s), measured by `test_48_hours_on_the_procedural_network_within_the_budget`.

## OSM network (T-B1-013)

Aggregate numbers below come from OpenStreetMap: © OpenStreetMap contributors, ODbL. No coordinate, name or geometry derived from it is written to the repository (owner ruling on G2, 2026-10-27).

**Streets kept.** The segments of the cached extract whose midpoint lies inside the study box; Overpass returns whole ways, which reach beyond it. Roads under construction are a separate opt-in layer.

**Projection.** Equirectangular about the centre of the study box; the largest relative length error over the box is about 0.1% (measured by `projection_error`).

**Pipes follow streets.** A pipe is a complete street route between two junctions: chains of degree-2 nodes are contracted, and when close junctions are joined (rule below) a pipe gains the street route to its group's representative, in length and in segments. Every junction is an OSM node. On the cached extract no pipe leaves the streets.

**Tiers.** `lite` (about 250 junctions) and `standard` (about 800) use the main roads (motorway, trunk, primary, secondary and their links); `full` uses every street class except service roads and has about 6,000 junctions. To reach a target, junctions closer than a radius along a street are joined; the radius is found by bisection (0.1 m) as the smallest whose skeleton holds at most the target, and the tier must then hold at least 90% of it. In the joined tiers the two carriageways of a divided road become one main. Measured on the cached extract: lite 250 junctions and 339 pipes (radius 335 m), standard 799 and 1,072 (24 m), full 6,020 junctions.

**Pipe tier, diameter, roughness.** A pipe's tier is that of the road classes covering most of its length (trunk and primary: transmission; secondary and tertiary: submain; the rest: distribution); diameters and roughness by tier are placeholders (`network/data/osm_capital_v1.json`).

**Zones and demand.** Zones come from the schematic overlay (rings around the Wikidata anchor, owner ruling 2, option A): it places no real district. A zone's demand is its land use's rate (L/s per hectare, placeholder) times its area inside the study box, shared equally by its junctions. With the placeholder rates the total is about 12 m3/s, beyond what the placeholder mains carry: the rates and sizes are calibrated with network validation (T-B1-014), not here.

**Terrain, source, tanks.** Elevations are a seeded synthetic plane with one wave (no survey); the source is a ground reservoir beside the transmission junction furthest to the configured side, with two duty and one standby pumps sized for the peak; three elevated tanks stand beside the highest junction of three sectors around the centre. All `ASSUMPTION`.
