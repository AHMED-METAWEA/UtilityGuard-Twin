# Handoff: demo work, state at the stop on 2026-10-27 (lead)

Plan of record: `docs/DEMO_PLAN.md`. The Monday contract is its "best partial version"; the rest is stretch.

## Merged today
#57 records, #58 pump controls, #59 procedural network design (owner), #60 DEMO_PLAN, #61 D-00 routes. Safety net on `951c58a` (after #58, #60, #61): fresh-clone `make ci` exit 0, hosted ci, container, audit success. #59 merged by the owner after that run: **run the safety net on current dev first**.

## Open PRs
- #62 deck.gl 9.4.0 and IBM Plex 5.3.0 (dependencies, owner merges). 14-day rule checked on all 36 new lockfile packages (newest 2026-10-11); npm audit 0. Unblocks U-03 (map) and the font part of U-01.
- #63 U-05 Sensors and Data Quality (Tier 1, review round 1 done and logged in `docs/reviews/U-05.md`; 339 tests, Playwright 4 passed). Lead may merge under D-018 once CI is green.

## Cards
| Card | Where | State | Resume step |
|---|---|---|---|
| U-01 design system (lane A) | `~/Desktop/UG-wt/codex-demo-u01-design-system`, branch `codex/demo-u01-design-system`, nothing committed | First run done (332 tests, Playwright 2 passed, lead screenshot reviewed). Round 1 fix run (identifiers not labelled ASSUMPTION, `[data-identifier]` skip, `formatValue` digits and grouping) was **still running at the stop**: its output is uncommitted in the tree | Read `scratchpad/U-01-fix.result.md` if present, else rerun `U-01-fix.prompt.md`; then `npm run check` + `npx playwright test`, commit with `Agent: codex`, review log `docs/reviews/U-01.md`, PR (Tier 1) |
| U-05 sensors (lane C) | PR #63 | Done | Merge after CI; then lane C takes D-06 code |
| D-04 measurement + quality (lane B, Tier 2 deep) | `~/Desktop/UG-wt/codex-demo-d04`, branch `codex/demo-d04-measurement`, nothing committed | Codex's first run stopped on three design gaps; **the lead decided all three** (below) and relaunched; that run was **still running at the stop** | Read `scratchpad/D-04.result.md`; if the run did not finish, rerun with `D-04-decisions.md` + `D-04.prompt.md`; then the deep review (mutation test: truth must not reach `ug_intel`) |
| D-05a forecast trend, CUSUM D2, incident candidate (lane B after D-04) | card written: `scratchpad/D-05a.prompt.md` | Not started | Launch in the D-04 worktree after D-04 is committed |
| D-06 cost engine code (lane C next) | card not written | Not started | Lead writes the card (formulas below), lane C implements, deep review |
| D-01 four contracts (lead, Tier 2, owner merges) | not on disk | Design only (below) | Write schemas, examples, invalid files with `EXPECTED` entries, fuzz allowlist, regenerate TS types, one PR |
| D-02 OSM calibration (lead) | not started | Unblocked: #59 is merged | Port the #59 rules (tank site inlet, common grade, level controls, clearwell, PRV grade) to `osm_capital_v1.json` and `OsmCapitalProvider`; 7-day validation on the `standard` tier locally |
| D-03 faults for the slice (lead) | not started | Unblocked by #59 | leak, burst, pump outage, demand multiplier at their onset tick |
| U-02 Command Center, U-03 map, U-04, U-06, D-07 API | not started | U-03 waits for #62 | Lane map below |

## D-04 design decisions (decided by the lead, given to Codex; not open)
1. Delivery delays: `WaterMeasurement.measure_with_delivery(truth, seeds) -> (TelemetrySeries, delays per sensor)`; `measure()` returns the series only (port contract); `to_readings(..., delays=None, quality=None)`; `TelemetrySeries` unchanged.
2. RTU group: junction sensor -> its zone; link sensor -> zone of its start junction, else its end junction, else the link id; level sensor -> tank id; one documented function `rtu_group`.
3. What-if durations: `as_faults(whatifs, step_seconds, horizon_ticks)`, duration = (horizon - from_tick) x step / 3600, refuse `from_tick >= horizon`; start hour maps back exactly to `from_tick`.

## D-01 design (to write)
- `network-view`: network_hash, name, fidelity F0|F1, coordinates `local_m`, geometry_label PUBLIC_GEOMETRY|ASSUMPTION (+ attribution when PUBLIC_GEOMETRY), attribute_labels (elevation_m, diameter_m: ASSUMPTION|OBSERVED|BENCHMARK; length_m: CALCULATED|OBSERVED|BENCHMARK), nodes, links (with optional route), zones (rings), sensors (with sets). No state, no fault. Examples synthetic only (G2).
- `time-series`: series_id, run_id, kind sensor|expectation|residual|demand_forecast|tank_forecast, element, quantity, unit (physical_unit), label in SENSOR_SIM|OBSERVED|BENCHMARK|MODEL|CALCULATED (never SIMULATION: truth never reaches the UI), version when MODEL, formula_ref when CALCULATED, start, step_seconds, values (number|null), optional band p10/p90; kind sensor -> telemetry label, forecasts/expectation -> MODEL, residual -> CALCULATED.
- `decision-comparison`: decision_id, run_id, incident_id, assumption_set, advisory const true, options (>= 2: option_id, action fix_now|wait|isolate_then_fix, delay_hours, expected_cost, worst_case, expected_regret, cost_lines as evidence ids), break_even (pairs with an evidence id), preferred_by_expected_cost (option id or null), evidence (array of `evidence-record` by $ref). No probability field.
- `whatif-request`: run_id, changes (<= 64) of {sensor_id, mode disable|stuck|drift, from_tick, drift_per_hour required iff drift, else forbidden} (if/then, not oneOf, so the rejection reason tests stay simple).
- Invalid files: missing_schema_version and one honesty case per schema (network-view extra_field; time-series simulation_label and model_without_version; decision-comparison single_option, not_advisory, probability_field; whatif-request drift_without_rate, unknown_mode), each with its `EXPECTED` entry in `platform/tests/contract/test_contracts.py`.

## D-06 cost engine (formulas for the card)
Per option, from the hypothesis run (leak of the estimated size at the top-1 candidate, SIMULATION conditional on the MODEL hypothesis): lost water rate, unserved demand rate, extra pump energy rate. Exposure hours = delay + crew_response_hours + repair_duration_hours. Lines: lost water m3 x water_production_cost; unserved m3 x unserved_water_penalty; extra kWh x electricity_price; repair (emergency for fix now and wait 6 h, planned for 24 and 72 h); crew via inspection_cost. Prices sampled from the `assumptions/v1.yaml` triangular distributions, seeded, 1,000 samples; p10/p50/p90 per line and total; expected regret per option against the per-sample minimum; break-even leak rate between fix now and wait 24 h. Every line is an evidence record (quantity x price, formula and inputs, CALCULATED, EGP); negative net benefit allowed; wording "model-estimated, conditional on assumptions".

## Lane map (owner direction 2026-10-27: Codex implements, lead designs and reviews)
| Lane | Next cards (days) |
|---|---|
| A | U-01 fix (0.1) -> U-02 Command Center (0.5) -> U-03 map after #62 (0.8) |
| B | D-04 (0.6) -> D-05a (0.6) -> D-07 API (0.8) |
| C | D-06 code (0.8, deep review) -> U-06 forecast and decision screens (0.8) -> U-04 Scenario Lab (0.5) |
| Lead | safety net on dev; D-01 (0.4); D-02 (0.5); D-03 (0.8); localization top 3 + D-06 card (0.6); reviews; W-01 (0.6) |
Critical path: D-03 -> localization -> W-01 (lead, about 2.5 days) and D-04 -> D-05a -> D-06 code -> W-01 (lanes).

## Resume first
1. Safety net on current dev (#59 merged after the last one).
2. Collect the U-01 fix and D-04 runs (results in the scratchpad, trees uncommitted); verify, commit, PR.
3. Merge #63 when green; launch D-05a (lane B) and write the D-06 card (lane C).
4. D-01 contracts PR. 5. D-02, then D-03.

Prompts are saved in `docs/tasks/` (U-01, U-01-fix, U-05, U-05-fix, D-04, D-04-decisions, D-05a). Scratchpad: `/private/tmp/claude-501/-Users-ahmedmetawea-Desktop-UtilityGuard-Twin/5be14cf2-bce8-4e3b-b06f-6518a449118e/scratchpad/` (prompts `U-01.prompt.md`, `U-01-fix.prompt.md`, `U-05*.prompt.md`, `D-04.prompt.md`, `D-04-decisions.md`, `D-05a.prompt.md`; results `*.result.md`; `safety.sh`, `tune2.py`). It is session-local and may be gone: the prompts' content is summarised above.

Codex tokens this wave: reviews 90,297 (#57 20,082; #58/#59 70,215); U-01 67,808; U-05 67,202 + 63,124; D-04 first run 41,253.
