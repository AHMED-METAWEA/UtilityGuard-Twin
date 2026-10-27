# Handoff: network tuning (lead card, Wave 3, Tier 2)

Why: T-B1-014's validation (merged as #54) failed the procedural network on `min_pressure_any_time`, `max_velocity` and `tank_pinned_full` (seeds 1 to 3).

## Causes found (SIMULATION, procedural network)
1. The source's grade (a reservoir 40 m above terrain, plus pumps up to 45 m) sat 50 to 80 m above every tank top, so the tanks filled at start-up and stayed full, and no pump ever stopped (no level controls).
2. The tanks stood at three different grades (each a fixed height above its own ground, two of them on the ground): the higher tanks drained into the lower one through the pumps' discharge.
3. Each tank hung off the highest junction inside a district grid, so while the pumps were off its whole outflow went through 100 to 200 mm distribution pipes (velocities about 3.7 m/s, pressures 4 to 5 m).
4. Demand was low for a capital-scale district (a synthetic design choice, ASSUMPTION; no benchmark is cited); once raised six-fold, the 100 to 200 mm distribution pipes lost about 30 m at peak in the densest district (seed 3).

## Design (all values ASSUMPTION, synthetic, in `procedural_capital_v1.json`)
- Source: a ground-level clearwell, 5 m above terrain.
- Three stations (2 duty, 1 standby each) lift into three elevated tanks on one common grade: tank bottom 36 m above the highest junction (`tank.bottom_above_highest_m`), each tank on the highest zone inlet of its zones, on the transmission main (`tank.site` "inlet", `tank.pipe_tier` "transmission").
- Tank-level pump controls (`equipment.level_control`): each station's duty pumps switch on its own tank, on below 2.5 m, off above 7.0 m.
- Pump curve (0, 58), (0.08, 46), (0.14, 24) in m3/s and m.
- Demand densities x6 (327 L/s average base demand); distribution diameters 150, 200, 250 mm; PRV setting 30 m.
- PRV static margin: the upstream grade is now the source head or, when higher, the lowest tank grade at minimum level (the tanks set the grade above a pumped source). For the old config the source head was higher, so its result is unchanged.

## Measured (SIMULATION, seven days, `normal_week`, 5-minute ticks)
| seed | min pressure at peak (>= 15 m) | min pressure any time (>= 10 m) | max velocity (<= 3 m/s) | lowest tank level above minimum | share of time pinned full (< 0.95) |
|---|---|---|---|---|---|
| 1 | 25.6 m | 24.7 m | 1.44 m/s | 1.95 m | 0.0 |
| 2 | 26.9 m | 25.5 m | 1.37 m/s | 1.94 m | 0.0 |
| 3 | 25.5 m | 25.0 m | 1.59 m/s | 1.86 m | 0.0 |

Seed 1: pumps run at 0.103 to 0.117 m3/s (inside the curve; no WNTR overrun warning on seeds 1 and 3), 0.9 to 1.4 starts per day; station east runs 86% of the time, north 25%, west 30%; the tanks cycle between 2.5 and 7.0 m. Total demand 0.131 to 0.493 m3/s.

The CI test `test_procedural_validation.py` runs two days for seeds 1 to 3 (about 3 s each); it fails on all three seeds with the old config.

## Changed hashes
Deliberate network change: the demand golden hashes in `test_demand_determinism.py` change (the demand rates belong to the network). Every procedural network hash and run id changes.

## Not done (next)
- The OSM network: calibrate `osm_capital_v1.json` (demand rates, pipe sizes, tank grade, controls) the same way; its placeholder demand (about 12 m3/s) is beyond its pipe sizes. Separate card.
- The standby pumps never run; failover belongs to T-B1-017 (faults).
