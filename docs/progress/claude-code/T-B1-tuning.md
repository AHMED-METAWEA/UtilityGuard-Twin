# Handoff: network tuning (lead card, Wave 3; WIP)

Why: T-B1-014's validation (merged as #54) fails the procedural network on `min_pressure_any_time`, `max_velocity` and `tank_pinned_full` (seeds 1 to 3); the OSM network's placeholder demand (about 12 m3/s) is beyond its pipe sizes.

## Found (procedural network, SIMULATION, 2- to 7-day validation runs)
- The source's grade (gravity reservoir 157.6 m plus pumps up to 45 m) sat 50 to 80 m above every tank top, so tanks filled at start-up (velocities 4 to 5 m/s, pressure dip to 4 m) and stayed full; demand density was about 10 times below urban values.
- Config changes that fix pressure and velocity (validated over 4 days, seed 1): demand density x6 (327 L/s), every tank elevated 38 m, pump curve heads x0.42 and flows x1.2 (design point about 15 m at 0.048 m3/s), PRV setting 35 m (static margin 15.7 m against 15 m). Result: lowest pressure 19.1 m, top velocity 2.5 m/s, no starvation.
- What no setting fixes: tanks still sit near full 96% of the week. The pumps run all the time; the model has no level controls (pumps off when tanks are full, on when low), so the tanks are floating storage that only fill. Pumping at curve run-out "passes" but is not a design to accept (WNTR warns the pumps exceed their maximum flow).

## Next step
1. Solver feature (lead, Tier 2): tank-level pump controls (on below a level, off above one; per station, from the network's equipment config), through WNTR controls; declare the control symbols in the WNTR API manifest first (`ug doctor` verifies them).
2. Then apply the config changes above to `procedural_capital_v1.json`, update the demand golden hashes in `test_demand_determinism.py` (deliberate network change), and rerun the 7-day validation for seeds 1 to 3.
3. The OSM network: calibrate `osm_capital_v1.json` (demand rates and pipe sizes) the same way once #53 is merged.
