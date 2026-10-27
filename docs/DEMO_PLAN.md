# DEMO_PLAN: committee demo, Monday 2 November 2026

Owner direction of 2026-10-27 ("OWNER DIRECTION, FINAL"); it replaces the earlier priority messages. This is an **ordering and effort re-allocation, not a scope reduction**: everything not in the demo slice stays in `docs/COLLAB_PLAN.md` and the Adoption Plan, marked *after the demo*. The Honesty Rules, contracts rule, tiers and stop-and-ask list are unchanged. The demo date may move by a week; the scope does not.

## 1. Owner decisions recorded here
- #54 (T-B1-014) stays merged. From now on every Tier 2 PR waits for the owner's merge (D-018 unchanged).
- #53 (T-B1-013) merged by the owner; the owner deletes its branch.
- Tank-level pump controls are their own Tier 2 PR (#58); the network design that uses them is #59.
- B2 starts now; up to three Codex lanes are approved for it.
- **Network design time box: 3 hours.** "Good enough" = plausible: pressures roughly 15 to 60 m, velocities under 3 m/s, tanks cycling, all values ASSUMPTION. No trial-and-error after the box.
- **Review policy.** Deep Tier 2 review (two rounds, lead mutation test) ONLY for (a) the cost and decision engine and the evidence kernel (every money line = one physical quantity x one unit price, formula and inputs shown, CALCULATED) and (b) honesty labels and the truth/telemetry separation. Everything else (UI, docs, tooling, geometry, tuning): one review round or CI only, no extra mutation runs. Reviews run in the background while the next card starts.
- Automated gates on every UI PR: every displayed number carries an evidence label; the page works offline (Playwright proves no outside request); no truth field reaches the UI (the existing truth-leak tests extended to the API payloads).

## 2. The demo slice (what runs end to end on Monday)
One path, scenario to telemetry to detection to cost to decision, on the capital network:

1. **Network.** OSM `standard` tier (about 800 junctions): OSM streets, the hand-drawn district overlay (ASSUMPTION), inferred pipes (F1), tanks, pumps, PRVs and sensors; calibrated with the procedural design rules (#59) so its seven-day `normal_week` passes validation. The honesty banner, the Fidelity badge (F1) and the stream-source indicator are on every screen. OSM-derived data stays in the git-ignored cache (G2); the map renders from it locally.
2. **Five scenarios** with visible effects on pressure, flow, unserved demand and lost water: `burst_main`, `leak_slow` (small constant leak from its onset tick; growing leaks come with T-B1-018), `pump_outage_standby`, `heatwave`, and one sensor fault (`sensor_stuck` on a pressure sensor, a telemetry-only fault).
3. **Live dashboard.** The replay stream (REPLAY) plays recorded runs tick by tick; readings come from the measurement layer (SENSOR_SIM: noise, quantization, dropouts), plotted over time, with data-quality flags *missing*, *stale*, *stuck* and *drift*.
4. **Early warning.** The T-B1-012 demand forecast (never sees truth, MODEL); tank-level forecast with time to threshold (mass balance on forecast demand and the current pump state, MODEL); trend anomaly on sensors; detection D2 (residual CUSUM against the forecast-driven expectation); physics localization, top 3 candidates from a precomputed leak-signature matrix (CALCULATED). No probabilities of real events: scores, thresholds and break-evens only.
5. **Money.** "Cost of each hour of delay": lost water, unserved demand, energy and crew, each = quantity x a versioned ASSUMPTION unit price (`assumptions/`), range p10/p50/p90 from sampling the price ranges, CALCULATED, formula and inputs shown. Decision Studio compares *fix now* and *wait 6, 24, 72 h* (and *isolate then fix* where a valve allows it) by expected cost, worst case (p90), regret and break-even; negative net benefit is representable; savings worded "model-estimated, conditional on assumptions".
6. **Sensor what-if.** The operator disables a sensor or sets it stuck or drifting. Applied to telemetry only (SENSOR_SIM), never to truth: the hydraulics are not re-solved; the measurement layer, quality flags, detection, localization and cost are recomputed on the recorded truth. Visible effects: the quality flag, later or no detection, a wider top 3 or INSUFFICIENT_EVIDENCE, and the added cost of the later detection (CALCULATED, range). Deterministic (seeded) and fast (target under 2 s on `standard`).
7. **Explain every number.** Clicking any number opens the evidence drawer: label, formula, inputs, source, version (the v1 `evidence-record` contract).
8. **Fallback.** A recorded run of each scenario on the presenter's machine (local run store), so the demo works with the engine offline or failing.

### After the demo (kept, not deleted)
T-B1-017's other fault types (the demo needs leak, burst, pump outage, demand multiplier and the sensor faults), T-B1-018 (chunking and growing leaks), T-B1-019 presets beyond the five, T-B1-022 M1 acceptance, T-B1-030 B1 exit gate; the OSM `full` tier; quality rules beyond the four flags (Q01 to Q12); detectors D1 and D3, diagnosis, the full incident lifecycle; design grid, CVaR beyond p90, the decision map, reports, `ug reproduce`; Arabic and RTL (the i18n scaffold is built now, EN only); the 60 fps formal check; B5 and B6.

## 3. UI direction (set by the lead; Codex lanes build it)
- **Design language "Lapis Night Operations".** Ground #0A0F1E; accents blue #3B6CFF, teal #35E0C2, amber #FFB454, red #FF6B6B; IBM Plex Sans and IBM Plex Mono; an evidence-label chip on every number; calm, dense, control-room feel; smooth transitions; no template look. Tokens live in `frontend/src/ui/tokens.css` (one source).
- **Offline-first.** No CDN, no network fonts: the Plex fonts (OFL) and every asset are bundled; a Playwright run proves no outside request.
- **Stack.** React 18 + TypeScript + Vite; deck.gl for the map (no base-map tiles: the streets come from the local cache); generated TS types from `contracts/` with the drift check; i18n EN first.
- **Screens.** (1) Command Center: map, live KPIs, active alerts, the "cost of waiting" card. (2) Network Map: layers pressure, flow, sensors, zones, fault location. (3) Sensors and Data Quality: time series, flags, the what-if control. (4) Scenario Lab: choose and launch, timeline, impact. (5) Forecast and Early Warning: demand, tank levels, time to threshold. (6) Cost and Decision Studio. (7) Evidence drawer. (8) Run, manifest and provenance page. Numbers in the earlier concept mockup (for example EGP 11,520) are placeholders; real values come from the engine.
- Screens are built on frozen contracts and fixture data first, then wired to the engine as it lands.

## 4. Contracts
The frozen v1 contracts already carry most of the slice: `telemetry-reading` (with `quality`), `stream-envelope` (tick), `incident` (location, support, contributing sensors), `evidence-record` (kinds quantity and cost, formula, inputs, p10/p50/p90 uncertainty), `run-manifest`, `scenario-config`, `assumption-set`. Missing for the slice, to be drafted by the lead and **approved by the owner** (contract rule): a network view for the map (nodes, links, zones, sensors with geometry), a time series (sensor, forecast and tank series with labels), a decision comparison (options, each a set of evidence-record ids) and a what-if request. One PR, Tier 2.

## 5. Cards, lanes and days
Lead = Claude Code (physics, faults, measurement and truth separation, detection, localization, cost and decision, evidence, contracts, UI direction, review triage). Codex lanes A, B, C in their own worktrees with disjoint allowed files. Days are working days from Tuesday 27 October afternoon.

| Card | What | Owner | Tier | Days | Needs |
|---|---|---|---|---|---|
| D-00 | This plan; routes and screen placeholders; lane file map | lead | 0 | 0.2 | |
| D-01 | Contract additions (section 4) | lead | 2 | 0.4 | owner approval |
| D-02 | OSM network calibration with the #59 design rules | lead | 1 | 0.5 | #58, #59 |
| D-03 | Faults for the slice (leak, burst, pump outage, demand multiplier) at their onset tick; part of T-B1-017 | lead | 2 | 1.0 | #59 |
| D-04 | Measurement layer and replay stream; sensor faults (stuck, drift, dropout); quality flags missing, stale, stuck, drift | lead (Codex writes the tests) | 2 | 0.7 | D-01 |
| D-05 | Detection D2 CUSUM, trend anomaly, tank forecast and time to threshold, localization top 3 | lead | 2 | 1.0 | D-03, D-04 |
| D-06 | Cost lines and Decision Studio engine (quantity x price, p10/p50/p90, regret, break-even), evidence records | lead | 2 (deep) | 1.0 | D-05 |
| D-07 | API: runs, stream, series, incidents, evidence, decisions, what-if (`ug_api`) | Codex C | 1 | 1.0 | D-01 |
| U-01 | Design system (tokens, Plex fonts bundled, chips, panels, motion), shell, i18n scaffold, evidence drawer, provenance page | Codex A | 1 | 1.0 | font package approval |
| U-02 | Command Center | Codex A | 1 | 0.7 | U-01 |
| U-03 | Network Map (deck.gl) | Codex B | 1 | 1.0 | deck.gl approval, D-01 |
| U-04 | Scenario Lab | Codex B | 1 | 0.7 | U-03 |
| U-05 | Sensors and Data Quality with the what-if control | Codex C | 1 | 0.7 | U-01 |
| U-06 | Forecast and Early Warning; Cost and Decision Studio screens | Codex C | 1 | 1.0 | U-01 |
| W-01 | Wire screens to the API, Playwright end-to-end and offline proof, recorded fallback runs | lead + Codex A | 1 | 0.7 | all |
| R-01 | Fresh-clone run, rehearsal script, fallback plan | lead | 0 | 0.5 | W-01 |

**Lane file map.** A: `frontend/src/ui/`, `frontend/src/app/`, `frontend/src/screens/command/`, `frontend/src/screens/evidence/`, `frontend/src/screens/provenance/`, fonts. B: `frontend/src/screens/map/`, `frontend/src/screens/scenarios/`. C: `frontend/src/screens/sensors/`, `frontend/src/screens/forecast/`, `frontend/src/screens/decision/`, then `platform/ug_api/`. Shared fixtures: `frontend/src/fixtures/<screen>/`, one folder per lane. The lead pre-registers every route in D-00, so lanes never edit the same file.

## 6. Schedule and critical path
- **Tue 27 (afternoon):** D-00, D-01 drafted; #58 and #59 in review; lanes A and C start (U-01; U-05 on fixtures).
- **Wed 28:** D-02, D-03. Lanes: U-01 done, U-02; U-03 (after deck.gl approval); U-05.
- **Thu 29:** D-04, D-05. Lanes: U-04; U-06; D-07.
- **Fri 30 (feature freeze, end of day):** D-06, W-01.
- **Sat 31:** end-to-end run, fresh-clone run, recorded fallback runs.
- **Sun 1:** rehearsal script (what to click, in what order, what to say), fallback plan, fixes only.

Critical path (lead): #59 merge, D-02, D-03, D-04, D-05, D-06, W-01. The lead's items total about 5.5 days against 3.5 working days to the freeze.

**Honest warning.** The full slice is at risk for Monday 2 November on the lead's path (detection, localization and the cost engine are the last items and have the least slack). The best partial version for Monday: all five scenarios as recorded runs; replay dashboard with quality flags; detection D2 and the tank time to threshold; localization top 3; cost of delay with the four lines; Decision Studio with fix now versus wait 6, 24, 72 h; the what-if on disable and stuck (drift after). With the one-week extension (9 November) the full slice fits, including the drift what-if and isolate-then-fix. Nothing is cut from the plan either way.

## 7. Models and effort
Opus at high effort for physics, contracts, detection, cost and Tier 2 triage; lower effort for UI direction notes, docs and bookkeeping; switch only at card boundaries. Codex lanes run at medium reasoning effort for UI cards, high for D-07 (truth must not reach the API).

## 8. Status and limits
`make status` and `docs/STATUS.md` are updated with `PROGRESS.md` after every merge. At about 85% of the usage limit the lead finishes the command in progress, commits what is green, writes the handoff in `docs/progress/claude-code/`, lists open PRs, running jobs and what to resume first, then stops.
