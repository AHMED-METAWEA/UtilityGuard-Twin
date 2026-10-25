# UtilityGuard Twin: Master Specification

**Product:** UtilityGuard Twin, a Capital Utility Twin and decision-intelligence platform
**Client context:** Administrative Capital for Urban Development (ACUD), New Administrative Capital of Egypt
**Document status:** v1.0, build-ready specification. Source of truth for the team and for Claude Code.
**First domain:** Water. **Designed-in domains:** Electricity, District Cooling (plugin architecture, specified in Sections 18 and 19).

---

## 0. How to use this document

1. Read Sections 1 to 4 completely before writing any code. They define what we are building, what we refuse to claim, and the architecture every later decision must respect.
2. Build in the order of the roadmap (Section 21). Each milestone has acceptance checks. Do not start a milestone until the previous one passes its checks.
3. Contracts (Section 12 and the JSON schemas under `contracts/`) are the interface between modules and between the two team members. Change them only by a versioned, reviewed change.
4. The Honesty Rules (Section 2) are non-negotiable. If any instruction anywhere seems to conflict with them, the Honesty Rules win. Ask the human before changing them.
5. Where this document says "verify", the implementer must check the real API, library version, or public source before relying on it. Never guess a signature.
6. Scope is the full specification. Prioritization exists only as build order, not as removal.

Conventions: `MUST` and `MUST NOT` are binding. `SHOULD` is strong default. All code is Python 3.11+ (backend) and TypeScript (frontend). All times in the system are timezone-aware UTC internally and shown in the Cairo timezone in the UI. All physical units are SI-based with explicit unit strings in every payload (pressure in metres of head `m`, flow in `m3/h`, volume in `m3`, energy in `kWh`, power in `kW`, money in `EGP`).

---

## 1. Vision and positioning

### 1.1 What UtilityGuard Twin is

A simulation-driven **virtual twin of a capital-scale city utility system**, with a live telemetry stream, a data-quality layer, fault detection and diagnosis, consequence simulation, cost and decision analysis, and a complete evidence trail for every number shown to the user.

It answers one question, end to end:

> Given the sensor evidence, the network model, the possible faults, the operating constraints and the economic assumptions: what is happening, where, what could it cost if we wait, which action is best, and why?

### 1.2 Defining principle

**No number without evidence. No recommendation without a transparent decision basis. No financial figure without documented assumptions.**

### 1.3 What it is not

- It is not a replica of ACUD's real networks, and it MUST NOT be presented as one until real data has been loaded (see the Fidelity Ladder below).
- It does not control real equipment. It is advisory. A human approves every action.
- It does not claim calibrated failure probabilities, verified savings, or field validation unless and until real data supports them.

### 1.4 The Fidelity Ladder (how "a twin of the capital" is made honest)

A digital twin is defined by how closely it is tied to the real asset. We make that explicit and visible in the UI as a permanent **Fidelity badge**.

| Level | Name | What it means | Status |
|---|---|---|---|
| F0 | Generic synthetic | Procedurally generated network, no relation to any city | Fallback for tests |
| **F1** | **Public layout, synthetic hydraulics** | The real layout of the New Administrative Capital taken from public sources (districts, roads, parks and other land use), with pipe routes inferred from that layout. Pipe sizes, demands, equipment and all hydraulics are synthetic placeholders. It is not ACUD's network and not a survey of it | **What we build now** |
| F2 | Calibrated | Network topology, demand patterns and equipment curves replaced or calibrated with ACUD-provided data. Detectors re-tuned | Enabled by architecture, needs ACUD data |
| F3 | Live-synced | Real SCADA/IoT stream replaces the replay source; model re-calibrates continuously | Enabled by architecture, needs integration |

F1 rules:
- Geometry (district boundaries, roads, parks, land use) comes from public sources and carries provenance: source, licence, retrieval date and a coverage report. It is labelled `PUBLIC_GEOMETRY`. Whether a source is usable is decided by a geometry feasibility test before the provider is built (Adoption Plan, Phase B1).
- Pipe routes are inferred from the street layout by a documented, seeded rule. Pipe sizes, demands and equipment are placeholders. All of these are `ASSUMPTION` and are never presented as ACUD's network.
- District names (for example Government District, Central Business District, Diplomatic District, residential districts, Green River and park corridors, medical, education and sports clusters) are used as **labels for demand zones and map regions**. Verify the list against the official ACUD masterplan before the demo. Areas come from the public geometry; demands are synthetic.
- The UI MUST show the Fidelity badge in the shell at all times. For an F1 network the text is `Fidelity F1: Public capital layout, inferred pipes, synthetic hydraulics`. The badge states the level of the network that is actually loaded (`Fidelity F0: Generic synthetic` for the procedural fallback, `No network loaded` before any run) and never claims a higher level than the loaded network has.
- Every module MUST read its network, demand and equipment parameters from versioned data files and providers, never from constants, so moving from F1 to F2 is a data swap and a re-calibration, not a rewrite.

### 1.5 Differentiation

Digital twins and utility monitoring already exist commercially. Our differentiation is a **modular reliability-testing and decision-intelligence layer** that:
1. evaluates fault detectors by their **operational and financial consequence**, not classification scores alone;
2. labels every number by its epistemic origin (observed, simulated, modeled, assumed, calculated);
3. shows when and why the preferred decision changes (break-even and sensitivity), instead of one confident figure;
4. is reproducible bit-for-bit from a manifest.

---

## 2. Honesty rules (non-negotiable)

1. The permanent banner and Fidelity badge are shown on every screen and in every exported report.
2. "Real-time" means a **replayed or simulated stream** until a real source is connected. The UI shows the stream source (`REPLAY`, `SIMULATED`, `LIVE`) at all times.
3. Every number carries one evidence label:

| Label | Meaning |
|---|---|
| `OBSERVED` | Measured by a real source (only after F3 or an imported real dataset) |
| `BENCHMARK` | From a public benchmark dataset (for example BattLeDIM), which is itself model-generated, never described as field data |
| `PUBLIC_GEOMETRY` | Layout (districts, roads, parks, land use) taken from public sources, with recorded provenance: source, licence, retrieval date and coverage report. Geometry only: inferred pipe routes, pipe sizes and demands are not public geometry, and none of it is ACUD data |
| `SIMULATION` | Output of the physical solver (WNTR/EPANET or domain solver) |
| `SENSOR_SIM` | Output of the measurement simulator (noise, drift, dropout) |
| `MODEL` | Output of a detector, classifier, or statistical model, with version |
| `ASSUMPTION` | A user-editable input, versioned (prices, durations, effectiveness, probabilities) |
| `CALCULATED` | Derived from the above by a displayed formula |
| `INSUFFICIENT_EVIDENCE` | The system declines to produce a number |

4. Probabilities of real-world events MUST NOT be invented. They are `ASSUMPTION` inputs, scenario-conditional values, or replaced by break-even thresholds.
5. No LLM in any calculation path. Explanations are generated from structured evidence with fixed, reviewed templates. An LLM, if ever used, may only rephrase an already-computed report and MUST NOT add or alter numbers. This is off by default.
6. Savings and ROI are always labeled **model-estimated and conditional on assumptions**. Negative net benefit MUST be representable and displayed.
7. Synthetic-fault results are never described as field validation.
8. The platform is advisory. No actuation interface to real equipment exists in this codebase.
9. Prohibited claims (UI copy, reports, demo script): verified savings in EGP as fact, "AI confidence 95%" without a defined statistic, calibrated failure probabilities, remaining-useful-life for real pumps, claims that the model represents ACUD's actual network at fidelity F1.

---

## 3. Users and jobs to be done

| Persona | Job | Primary screens |
|---|---|---|
| Control-room operator | Notice problems early, know what is wrong and where, decide what to do now | Command Center, Twin Map, Incident Center |
| Maintenance planner | Decide inspect vs repair vs wait, schedule crews | Decision Studio, Incident case file |
| Asset or portfolio manager | Understand exposure, budget, where more sensors pay off | Decision Studio, Evaluation Lab |
| ACUD executive | One-page situational picture, exposure ranges, assumptions | Executive Brief |
| Auditor or contract reviewer | Verify any number back to its sources | Evidence Explorer, reports |
| Data scientist | Compare detectors, tune, validate | Evaluation Lab, Scenario Lab |

Core questions the product answers: Which assets are at risk? What evidence supports it? Is it a sensor fault, an equipment fault, a network fault, or normal demand change? What could happen if it escalates? Which zones are affected? What financial exposure exists, with what uncertainty? Which actions are available and what does each cost? Why is one recommended? When would a different decision be better? How confident should the manager be, and in what sense?

---

## 4. Architecture

This section is written as the architecture of record. Every module author MUST follow it.

### 4.1 Architectural principles

| # | Principle | Consequence |
|---|---|---|
| P1 | **Truth and measurement are separate worlds** | The twin holds *physical truth*. Sensors produce *telemetry* derived from truth plus error. Detectors only ever see telemetry. Truth is exposed only to the evaluation harness and the optional "twin truth" UI toggle |
| P2 | **Determinism and reproducibility** | Every run is fully described by a manifest (config, seed, versions, hashes). Same manifest, same output, byte for byte |
| P3 | **Contracts before code** | All cross-module data crosses versioned, schema-validated contracts. Contract tests run in CI |
| P4 | **Domain-agnostic core, domain plugins** | Water, Electricity, Cooling implement one `DomainAdapter` interface. The core never imports domain code |
| P5 | **Evidence is first-class data** | Every derived value is created together with its provenance record. Evidence is not reconstructed later |
| P6 | **Ports and adapters (hexagonal)** | Telemetry sources (replay, simulated, live), solvers, stores and buses sit behind ports and can be swapped without touching business logic |
| P7 | **Append-only run log** | Runs are immutable. Derived views (alerts, incidents, costs) are rebuildable from the run log plus manifests |
| P8 | **Compute and serve are separated** | Heavy simulation runs in workers. The API and WebSocket hub stay responsive |
| P9 | **Degrade explicitly** | Bad data lowers confidence and is visible. The system never silently fabricates or smooths over missing evidence |
| P10 | **Offline-first** | The full demo runs on a laptop with no internet: no CDN fonts, no map tiles, no external APIs |
| P11 | **Human in the loop** | Recommendations are advisory and require explicit acknowledgment |
| P12 | **Observable by default** | Structured logs, metrics and traces from day one |
| P13 | **Boring technology** | Prefer proven components. Add infrastructure only when a measured need exists. Every swap-in path is designed, not built prematurely |

### 4.2 System context

```
                     ┌────────────────────────────────────────────┐
   Operators,        │              UtilityGuard Twin             │
   planners,   ───►  │  Web App  ◄──►  API + Stream Hub  ◄──►  Core│
   executives        └───────────────┬───────────────┬────────────┘
                                     │               │
              ┌──────────────────────┘               └───────────────────────┐
              ▼                                                              ▼
   Telemetry sources (ports)                                   External data (adapters, future)
   REPLAY (default) · SIMULATED · LIVE (F3)                    ACUD network files, asset registry,
                                                               tariffs, maintenance records, SCADA
```

### 4.3 Logical architecture (layers and components)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ L7  PRESENTATION    Web App (React/TS): shell, map engine, screens, i18n AR/EN │
├───────────────────────────────────────────────────────────────────────────────┤
│ L6  API & STREAM    REST (FastAPI) · WebSocket hub · SSE for notifications     │
├───────────────────────────────────────────────────────────────────────────────┤
│ L5  APPLICATION     Run Orchestrator · Incident Manager · Analysis Orchestrator │
│                     Report Service · Assumption Service · Evaluation Service   │
├──────────────────┬────────────────────────────────────────────────────────────┤
│ L4  INTELLIGENCE │ Data Quality · Baseline/Expectation · Detectors · Diagnosis │
│                  │ Localization · Impact Model · Cost Engine · Decision Engine │
├──────────────────┴────────────────────────────────────────────────────────────┤
│ L3  DOMAIN PLUGINS  water/ · electricity/ · cooling/  (DomainAdapter)          │
│                     asset model · solver · measurement model · fault library   │
├───────────────────────────────────────────────────────────────────────────────┤
│ L2  PLATFORM CORE   Entities · Scenario engine · Time model · Evidence kernel  │
│                     Event bus · Registry · Config · Versioning · Provenance    │
├───────────────────────────────────────────────────────────────────────────────┤
│ L1  INFRASTRUCTURE  SQL store · Parquet/DuckDB time-series · Artifact store    │
│                     Event bus impl · Worker pool · Observability · Packaging   │
└───────────────────────────────────────────────────────────────────────────────┘
Dependency rule: a layer may depend only on layers below it. L3 plugins depend on L2 only.
L4 intelligence modules receive domain objects through L3 interfaces, never by importing a domain.
```

### 4.4 Runtime topology

| Process | Responsibility | Scaling note |
|---|---|---|
| `api` | REST, WebSocket hub, auth stub, serves the built frontend | Stateless. Horizontal later |
| `sim-worker` | Runs full scenarios and what-if simulations, writes results to the store | Process pool. One process per core. Remote workers later via queue |
| `stream-player` | Reads a finished run from the store and emits ticks (replay), handles pause, speed, seek | One per active session. Cheap |
| `analytics` | Consumes ticks: quality, expectation, detection, diagnosis, incident updates | In-process consumer first, separate process via bus later |
| `scheduler` | Queues long jobs (evaluation sweeps), retries, cleans up | Small |
| Stores | SQL (SQLite in dev, PostgreSQL in compose), Parquet files queried by DuckDB, filesystem artifact store | Postgres and optional TimescaleDB as upgrade path |
| Bus | `EventBus` port. Default in-process asyncio. Redis Streams adapter provided behind a compose profile | Kafka is explicitly rejected as unnecessary at this scale |

### 4.5 Core runtime flow

```
Scenario config ──► Run Orchestrator ──► sim-worker
                                          │ 1) build twin state (domain adapter)
                                          │ 2) run physical solver (ground truth)
                                          │ 3) run fault-free expectation (baseline)
                                          │ 4) apply measurement model (telemetry)
                                          ▼
                                   Run Store (truth, telemetry, expectation) + Manifest
                                          │
              stream-player (replay, speed, seek) ──► tick events ──► EventBus
                                                                   │
                         analytics: quality → detect → diagnose → localize
                                                                   │
                                 Incident Manager (group, severity, lifecycle)
                                                                   │ incident.opened
                                    Analysis Orchestrator (async jobs on sim-worker)
                                    impact sims → cost engine → decision engine
                                                                   │
                                        Evidence Kernel (provenance for every output)
                                                                   │
                                  API / WebSocket ──► Web App (map, alerts, evidence)
```

**Key engineering decision.** Hydraulic simulation is expensive and the stream is a replay. Therefore the full scenario is simulated once, up front, and the analytics pipeline processes a deterministic replay. This makes the stream cheap, the demo smooth, results reproducible, and lets evaluation sweeps run thousands of scenarios without a UI. It also means the same analytics code path serves replay today and a live source at F3.

**Second key decision.** Monte Carlo cost analysis MUST NOT re-run the hydraulic solver per sample. Hydraulic outcomes come from a small design-of-experiments grid (delay × leak size × action) computed once per incident. Samples vary the economic assumptions and interpolate hydraulic outcomes across the grid. This keeps analysis under the performance budget.

### 4.6 Domain plugin architecture

```python
class DomainAdapter(Protocol):
    domain_id: str                        # "water" | "electricity" | "cooling"
    def asset_model(self, params) -> AssetModel: ...          # topology, assets, sensors, zones
    def solver(self) -> PhysicalSolver: ...                   # run(state, scenario, horizon) -> TruthSeries
    def measurement_model(self) -> MeasurementModel: ...      # truth -> telemetry with errors/faults
    def fault_library(self) -> FaultLibrary: ...              # fault types, parameters, injectors
    def expectation_model(self) -> ExpectationModel: ...      # fault-free expected behavior
    def detectors(self) -> list[Detector]: ...                # domain detectors behind the common interface
    def localizer(self) -> Localizer | None: ...
    def impact_model(self) -> ImpactModel: ...                # what-if simulations -> physical KPIs
    def action_catalog(self) -> list[ActionSpec]: ...         # interventions and how to simulate them
    def cost_model(self) -> CostModelSpec: ...                # cost components and formulas
    def ui_manifest(self) -> UiManifest: ...                  # layers, legends, units, panels the UI should render
    def validate_dataset(self, path) -> ValidationReport: ... # import/benchmark validation
```

Rules:
- The core platform entities (`Asset`, `Sensor`, `Reading`, `Zone`, `Scenario`, `Fault`, `Run`, `Incident`, `Action`, `Evidence`, `Assumption`) are domain-agnostic. Domain-specific attributes live in typed `attributes` extension blocks validated by the adapter's schema.
- Adapters register via an entry-point registry. The UI discovers domains and layers from `GET /domains` and each adapter's `ui_manifest`, so adding a domain adds UI layers and panels without frontend rewrites of core screens.
- **Cross-domain interdependencies** are modeled in an `InterdependencyGraph` (core). Example: electricity feeder F-12 supplies pump station PS-2. A scenario fault in electricity yields a derived input to the water solver (pump outage over a time window). Cooling plants consume water and electricity. Cross-domain effects are explicit scenario inputs, evidence-labeled `SIMULATION`, never implicit coupling.
- Each adapter MUST pass the **adapter conformance test suite** in `platform/tests/conformance/` before it can be enabled.

### 4.7 Technology decisions

| Concern | Choice | Reason | Rejected |
|---|---|---|---|
| Backend language | Python 3.11+ | WNTR, scientific stack, ML | Go/Java: no solver ecosystem |
| API | FastAPI, pydantic v2, uvicorn | Typed contracts, OpenAPI, async WebSocket | Flask, Django |
| Hydraulics | WNTR over EPANET (verify installed API) | Open, leaks, PDD, pump controls, resilience metrics | Custom solver |
| Time-series storage | Parquet files + DuckDB | Columnar, fast replay and analytics, zero server | InfluxDB, Timescale at start (kept as upgrade path) |
| Relational store | SQLite dev, PostgreSQL compose | Simple, reliable, migration path | NoSQL |
| Migrations | Alembic | Standard | Hand scripts |
| Bus | `EventBus` port, asyncio default, Redis Streams adapter | Right-sized | Kafka, RabbitMQ |
| Jobs | Process pool plus a `jobs` table, with an `arq` adapter optional | No broker needed at first | Celery as default |
| ML | scikit-learn, LightGBM, optional PyTorch | Detectors behind a common interface | Heavy frameworks by default |
| Explainability | SHAP for model attribution only | Never presented as physical root cause | Free-text LLM explanation |
| Frontend | React 18, TypeScript, Vite | Team familiarity, ecosystem | Streamlit (kept only as emergency fallback) |
| State and data | TanStack Query, Zustand | Server state vs UI state separation | Redux |
| Map engine | deck.gl on a local Cartesian coordinate system, plus an SVG schematic view | GPU rendering of thousands of animated paths, no tile server | Mapbox/Google (online, licensing) |
| 3D city view | three.js via react-three-fiber (optional visual layer) | Atmosphere for executive demos | Mandatory 3D |
| Time-series charts | uPlot for streaming, ECharts for rich charts | 60 fps streaming performance | Heavy chart libs for streaming |
| i18n | i18next, full RTL support | Arabic and English | Hard-coded strings |
| Packaging | Docker Compose, plus one-command local run | Offline demo | Kubernetes |
| Quality | pytest, hypothesis, Playwright, ruff, mypy, ESLint, Vitest | Full stack | — |
| CI | GitHub Actions | Standard | — |

### 4.8 Performance budgets

| Item | Budget |
|---|---|
| Full 48 h scenario simulation, about 250-node network, 5-minute step | Under 60 s on a laptop (verify; chunking allowed) |
| Replay tick processing (quality plus detection for 60 sensors) | p95 under 50 ms |
| Incident analysis (impact grid, cost, decision) | Under 90 s end to end, in background |
| UI frame rate with map, 300 nodes, 400 animated pipe segments | 60 fps on a mid laptop GPU |
| Evidence drawer open | Under 300 ms |
| Evaluation sweep of 200 scenarios | Completes headless, parallel across cores, resumable |

### 4.9 Failure modes and mitigations

| Failure | Mitigation |
|---|---|
| Solver non-convergence | Catch per chunk, mark the run segment `INSUFFICIENT_EVIDENCE`, never interpolate silently |
| Missing or late telemetry | Quality layer flags it, detector lowers network confidence, UI shows degraded state |
| Sensor outage widespread | Detector declares `unknown` and widens uncertainty instead of guessing |
| Slow analysis | Jobs are async with visible progress and partial results |
| Contract drift | Contract tests, schema versions in every payload |
| Non-determinism | Seeds are explicit. Numeric tolerances are defined in golden tests |
| Wrong assumptions silently flip a decision | Sensitivity analysis always attached to a recommendation |

### 4.9a Security, governance and data handling

- No real ACUD data exists in the repository. If data is provided later: import through the dataset adapter, keep it out of git (`data/private/`, git-ignored), record provenance, and label the Fidelity level.
- Auth is stubbed with a single local role at first. The API is designed for OIDC and role-based access (viewer, operator, analyst, admin) with an append-only audit log. Every acknowledgement and assumption edit is audit-logged with user, time and diff.
- Secrets via environment only. Dependency pinning with lockfiles. Version pinning of every script CDN is unnecessary because there are no CDNs (offline-first).
- Safety statement shown in the UI: advisory only, human approval required, not certified for operation of critical infrastructure.

### 4.9b Observability

Structured JSON logs with `run_id`, `incident_id`, `trace_id`. Prometheus-style metrics endpoint (`/metrics`): tick latency, queue depth, sim durations, detector alarms. OpenTelemetry tracing optional behind a flag. A built-in **System Health** panel in the UI shows worker status, queue depth, last run durations.

### 4.9c Versioning

Every artifact carries a version: `network_version`, `scenario_schema_version`, `sensor_layer_version`, `detector_version`, `assumption_set_version`, `cost_model_version`, `contract_version`. A **Run Manifest** records all of them plus the git commit hash and library versions, so any result can be re-created.

---

# PART II: THE WATER DOMAIN AND THE INTELLIGENCE LAYERS

## 5. Domain 1: the Capital Water Twin

### 5.1 Network (fidelity F1: public layout, inferred pipes, synthetic hydraulics)

> Note (2026-10-25, owner ruling): F1 is defined in section 1.4 as the real public layout with inferred pipes. The generator below, `ProceduralCapitalProvider`, builds a capital-inspired synthetic network and is therefore the **F0 fallback** and the test fixture. The F1 provider (`OsmCapitalProvider`: public geometry, inferred pipes, scale tiers) is specified in `docs/ADOPTION_PLAN.md` (G01, G02, Phase B1) and will be written into this section when Phase B1 starts.

Hierarchy modeled: abstract source and treatment, transmission mains, pump stations, ground and elevated storage, district metered areas (DMAs), distribution grids.

| Element | Target scale (parameters, tunable) |
|---|---|
| Demand zones / DMAs | 8 to 10, each mapped to a labeled capital district (labels from the masterplan, geometry synthetic) |
| Junctions | about 260 |
| Pipes | about 340, tiered diameters (transmission, sub-main, distribution) |
| Pump stations | 3, each with 2 duty pumps and 1 standby, with head and efficiency curves |
| Storage tanks | 3 (one elevated, two ground), with level sensors |
| Valves | about 30 isolation valves, 2 pressure-reducing valves |
| Sensors | about 48 pressure, 10 flow (pump discharges and DMA inlets), 3 tank levels |

Generator (`ProceduralCapitalProvider`, seeded, deterministic):
1. Place districts on a 2D plane with plausible proportions and adjacency: government cluster, central business district, diplomatic area, residential rings, green corridors, medical, education and sports clusters.
2. Generate street grids per land use (regular grid for planned districts, mild irregularity for others), connected by a transmission ring and radial mains.
3. Assign elevations from a synthetic gentle terrain; place tanks at the highest practical points.
4. Assign diameters by hierarchy, roughness by age class, demands by land use × area × per-capita parameters (all `ASSUMPTION`, in `assumptions/demand.yaml`).
5. Place sensors by a coverage heuristic (greedy maximization of residual observability) with a fixed seed, and expose three named sensor sets: `S_base`, `S_dense`, `S_sparse`.
6. Validate: connectivity, no isolated junction, minimum pressure at peak demand (default 15 m, assumption), no tank overflow or starvation over a 7-day normal run, velocity limits. Failure means re-seed or fail loudly.

`NetworkProvider` implementations: `OsmCapitalProvider` (F1, Phase B1), `ProceduralCapitalProvider` (F0 fallback and test fixture), `InpFileProvider` (any EPANET `.inp`, used for the BattLeDIM L-Town benchmark and future ACUD files), `GeoJsonProvider` (future GIS import). Coordinates are local Cartesian metres with an optional CRS transform for georeferenced F2 data.

### 5.2 Demand model

Base demand per junction from land use. Layered multipliers, all versioned `ASSUMPTION`:
- diurnal pattern per land use: residential double peak, government and commercial weekday daytime, medical near-flat, irrigation overnight;
- weekly pattern with Friday and Saturday weekend, holidays calendar, Ramadan pattern with evening peak shifted to Iftar, seasonal factor;
- heatwave multiplier, special-event surge, fire-flow injection;
- stochastic correlated noise per zone (AR(1)) from the seed.

The **expectation model** (Section 7.1) uses a *forecast* of demand that differs from the true demand by a forecast-error process. This prevents trivially perfect detection and is mandatory.

### 5.3 Hydraulic engine

- WNTR over EPANET with pressure-driven demand. Verify supported simulator options for leaks and PDD in the installed version, and the exact API for leak creation and pipe splitting.
- **Gradual faults** are simulated piecewise: the run is divided into chunks (default 30 minutes), fault parameters are updated per chunk, tank levels and pump states are handed off between chunks. A convergence test compares chunk sizes and the approximation error is reported in `docs/approximations.md`.
- **Pump degradation** is a custom model (head-curve scaling and efficiency decay over time) and is labeled `ASSUMPTION` everywhere. It is not a validated remaining-life model.
- Pump energy from head and efficiency curves, giving kWh per run and per action.
- Optional later: water quality and pipe-failure statistics.

### 5.4 Fault catalog

| ID | Fault | Parameters | Truth effect | Measurement effect | Early warning feasible |
|---|---|---|---|---|---|
| F-LEAK-G | Gradual leak | pipe, start, ramp hours, final area | Growing outflow | Slow pressure decay near leak, flow rise | Yes |
| F-LEAK-S | Sudden leak | pipe, start, area | Step outflow | Step pressure drop | No (detect only) |
| F-BURST | Burst | pipe, start, large area | Large step outflow | Large drop, tank draw | No |
| F-LEAK-BG | Background leakage | per DMA fraction | Raised night flow | Elevated minimum night flow | Yes (trend) |
| F-SEN-DRIFT | Sensor drift | sensor, rate | None | Linear bias | Yes |
| F-SEN-OFFSET | Sensor offset | sensor, magnitude | None | Constant bias | Detect only |
| F-SEN-STUCK | Stuck sensor | sensor, duration | None | Frozen value | Detect only |
| F-SEN-NOISE | Noise growth | sensor, factor | None | Increased variance | Yes |
| F-SEN-DROP | Dropout | sensor, duration, probability | None | Missing readings | Detect only |
| F-COMMS | Correlated comms loss | RTU group, duration | None | Group-wide missing data | Detect only |
| F-PUMP-OUT | Pump outage | pump, start, duration | Pump off | Pressure and flow collapse downstream | No |
| F-PUMP-DEG | Pump degradation (custom) | pump, rate | Falling head and efficiency | Slow pressure and energy drift | Yes (modeled) |
| F-VALVE | Valve closed or stuck | valve, state | Rerouting | Pressure redistribution | Detect only |
| F-DEMAND | Demand surge or drop | zone, factor | Demand change | Smooth proportional shift | n/a (not a fault) |
| F-FIRE | Fire-flow event | node, flow, duration | Local demand spike | Local pressure dip | n/a |
| F-POWER | Power loss (cross-domain) | feeder or station, duration | Pump outage via dependency | As pump outage | No |
| F-COMPOUND | Any combination | list | Combined | Combined | Varies |

### 5.5 Scenario library (presets)

| # | Name | Intent |
|---|---|---|
| 1 | `normal_week` | Baseline, false-alarm measurement |
| 2 | `holiday` | Government zone demand drop, no alert expected |
| 3 | `heatwave` | Network-wide demand rise, no alert expected |
| 4 | `ramadan_peak` | Iftar peak, no alert expected |
| 5 | `friday_weekend_pattern` | Weekly pattern test |
| 6 | `fire_flow_event` | Demand spike versus leak confusion test |
| 7 | `leak_gradual_small` / `_medium` / `_large` | Early-warning sensitivity |
| 8 | `leak_sudden` | Detection delay and localization |
| 9 | `burst_main` | Severe impact and isolation action |
| 10 | `background_leakage_growth` | Night-flow trend detection |
| 11 | `sensor_drift` | Sensor fault versus leak diagnosis |
| 12 | `sensor_stuck` | Stuck detection |
| 13 | `sensor_offset` | Calibration error |
| 14 | `sensor_noise_growth` | Degrading sensor |
| 15 | `comms_outage_rtu` | Correlated missing data, confidence reduction |
| 16 | `pump_outage_standby` | Response with standby pump |
| 17 | `pump_degradation` | Custom model, early-warning demonstration |
| 18 | `valve_closed_wrong` | Operational error pattern |
| 19 | `leak_plus_sensor_drift` | Compound, diagnosis robustness |
| 20 | `pump_degradation_plus_heatwave` | Demand versus equipment confusion |
| 21 | `leak_during_pump_maintenance` | Constrained response |
| 22 | `power_loss_station` | Cross-domain event (electricity dependency input) |
| 23 | `multi_leak_cascade` | Several leaks, grouping logic |
| 24 | `night_leak_low_demand` | Easy detection regime |
| 25 | `peak_hour_leak` | Hard detection regime |
| 26 | `forecast_error_stress` | Large demand forecast error, false-alarm stress |
| 27 | `model_mismatch_roughness` | Twin roughness error, discrepancy-monitor demonstration |
| 28 | `benchmark_battledim_2019` | Replay of the public benchmark through the same pipeline |

---

## 6. Measurement layer and data-quality layer

### 6.1 Measurement model

Separate from physics. Per-sensor spec in `sensors.yaml`: type, unit, accuracy class and noise sigma, resolution and quantization, sampling interval, latency, jitter, RTU group. Effects: Gaussian noise (seeded), quantization, timestamp jitter, late and out-of-order delivery, duplicates, and the fault injectors of Section 5.4. Truth is stored separately and is never sent to detectors.

### 6.2 Data-quality checks

| ID | Check | Logic | Default threshold (configurable) |
|---|---|---|---|
| Q01 | Completeness and latency | Missing, late beyond interval multiple | More than 2 intervals late |
| Q02 | Physical range | Outside min and max, negative pressure | Per sensor type |
| Q03 | Rate of change | Spike beyond physical bound | Per sensor type |
| Q04 | Flatline | Variance near zero over window | N ticks |
| Q05 | Noise anomaly | Variance ratio against its own history | Ratio above 3 |
| Q06 | Duplicate or out-of-order | Timestamp logic | Any |
| Q07 | Spatial consistency | Robust z-score of sensor residual against hydraulic neighbors | z above 3.5 |
| Q08 | Model consistency | Residual against expectation, persistence aware | Sigma units |
| Q09 | DMA mass balance | Inlet flow against expected sum of demand | Tolerance band |
| Q10 | Tank balance | Level change against net flow | Tolerance band |
| Q11 | Headloss plausibility | Sign and magnitude between connected sensors | Per pipe class |
| Q12 | Unit and scale sanity | Order-of-magnitude jumps | Factor 10 |

Reading score: `score = exp(-Σ w_i · v_i)` with violation severity `v_i` in 0..1 and configurable weights `w_i`. Status: `ok` at 0.8 and above, `suspect` from 0.5 to 0.8, `bad` below 0.5. Each sensor has a rolling EWMA quality score. The **network confidence index** is the observability-weighted mean of sensor quality per zone and is shown on the Command Center. Detectors down-weight `suspect` and exclude `bad` readings. A persistently flagged sensor raises a **sensor-maintenance recommendation**, which is separate from network incidents.

---

## 7. Detection, diagnosis and localization

### 7.1 Expectation model

A fault-free twin run with the *forecast* demand (calendar, weather, known events), including a forecast-error process (assumption) and optional model-mismatch variants. Residual `r_i(t) = (y_i(t) - ŷ_i(t)) / σ_i(t)`, where `σ_i` is a robust (MAD-based) estimate from fault-free ensemble runs per time-of-day bucket.

### 7.2 Detector interface and the detector set

All detectors implement `Detector.update(tick) -> DetectorOutput` and are benchmarked against each other by the evaluation harness. The production policy is chosen by evaluation results, not by default.

| ID | Detector | Role |
|---|---|---|
| D1 | Fixed-threshold on raw values | Mandatory naive baseline |
| D2 | Residual CUSUM with persistence | Primary transparent detector |
| D3 | Multivariate residual (PCA T² and SPE, or Mahalanobis) | Multivariate baseline |
| D4 | Isolation Forest on residual features | Unsupervised ML comparison |
| D5 | LightGBM on windowed residual features | Supervised diagnosis, trained on synthetic scenarios with held-out parameters |
| D6 | Temporal autoencoder or sequence model (optional) | Included only if it beats D2 and D5 on evaluation |

States: `normal`, `watch`, `alert`. Persistence logic and hysteresis control false alarms.

### 7.3 Diagnosis (structural reasoning)

Hypotheses: `leak`, `burst`, `sensor_fault` (drift, offset, stuck, noise, dropout), `demand_change`, `pump_issue`, `valve_issue`, `comms_outage`, `unknown`.

| Pattern in residuals and context | Leading hypothesis |
|---|---|
| One sensor deviates, hydraulic neighbors, flows and tank consistent | `sensor_fault` (subtype from time profile) |
| Several nearby sensors fall with spatial gradient, DMA inflow imbalance, tank draw | `leak` or `burst` (step versus ramp separates them) |
| Smooth, network-wide, proportional shift matching calendar or weather drivers | `demand_change` (no alert) |
| Signature at a pump station: discharge pressure and flow change, energy change | `pump_issue` |
| Pressure redistribution with no inflow imbalance | `valve_issue` |
| Whole RTU group missing | `comms_outage` |
| None of the above is supported | `unknown` |

Output per hypothesis: rule-based support strength (`strong`, `moderate`, `weak`) with the rules fired, plus a model score where an ML model exists. No percentage "confidence" is shown unless it has a defined statistical meaning. A probability from the supervised model is labeled `MODEL, conditional on the simulated scenario distribution`.

### 7.4 Localization

Precompute a **leak signature matrix**: for every candidate pipe and each reference demand state, simulate a reference leak and store the sensor residual response. At runtime, match the observed residual vector against signatures with non-negative least squares and cosine similarity, with size scaling. Output: top-k candidate pipes with scores, the DMA first, then the pipe. Cache by `network_version` and `sensor_set`. Report hit@1, hit@3 and distance error in hops and metres.

### 7.5 Early warning

Trend detection on residual slope (Theil–Sen) plus CUSUM for incipient faults. Lead time is defined against the moment the true fault crosses a stated size threshold and is reported only for gradual scenarios. Sudden faults report detection delay only.

### 7.6 Model-discrepancy monitor

During fault-free periods, track long-term bias between expectation and telemetry per sensor and zone. Sustained bias produces a **recalibration recommendation**. At F1 this demonstrates the concept. At F2 it becomes the main tool for tuning the twin against real data.

---

## 8. Incident management

**Grouping.** Detector events are clustered into incidents by time overlap, graph distance on the network, and hypothesis compatibility. One root-cause hypothesis yields one incident, with contributing sensors listed. Merge and split rules are unit-tested.

**Severity.** A lookup over: estimated impact (unserved rate, affected zones weighted by zone criticality, where government and medical weights are higher by assumption), growth rate, support strength, and asset criticality. Levels: `low`, `medium`, `high`, `critical`.

**Lifecycle.** `watch` then `open` then `acknowledged` then `mitigating` then `resolved` then `closed`, with `false_alarm` as a terminal flag. Every transition is audit-logged.

**Alert-fatigue controls.** Deduplication, cooldown and hysteresis, rate limits, grouping. Metric: alerts per simulated week on fault-free scenarios.

**Notification.** In-app notification center, webhook and email stubs, escalation timers (assumptions).

**Operator feedback.** Confirm or reject a diagnosis. Feedback is stored as evaluation data and never silently retrains the detector.

---

## 9. Impact, finance and decision engine

### 9.1 Impact analysis

On incident open, an analysis job runs on a **design grid**: delay `D` in {0, 3, 6, 12, 24, 48, 72} hours, leak size in {low, mid, high} (spanning size-estimate uncertainty), and each feasible action. Each run starts from a state snapshot (tank levels, pump status) and records `SIMULATION` KPIs: water lost, unserved demand (m3), service availability, hours of low pressure, affected junctions and critical customers, recovery time, pump energy (kWh), minimum pressure.

| Action | Simulation semantics |
|---|---|
| `monitor` | No change |
| `inspect` | Information action: cost and duration, after which the hypothesis is resolved (decision tree over leak real versus not) |
| `repair_isolate` | Close isolation valve set at `t + crew_response`, repair for `repair_duration`, reopen |
| `switch_standby_pump` | Start standby, stop faulty pump (pump incidents) |
| `reduce_pressure` | Lower pump speed or PRV setpoint to reduce leak outflow, within service constraints |
| `temporary_supply` | Tanker supply modeled as cost and partial unserved reduction (assumption) |

### 9.2 Cost model

Each money line is derived from exactly one physical quantity multiplied by one unit price, so nothing is double counted.

| Component | Formula | Label |
|---|---|---|
| Lost water | `V_leak × c_prod` (marginal production cost) | CALCULATED from SIMULATION and ASSUMPTION |
| Unserved water | `V_unserved × c_unserved` (service penalty or social cost, can be 0) | CALCULATED |
| Pump energy | `E_kWh × c_elec` | CALCULATED |
| Repair | `fixed + duration × crew_rate + parts` (planned or emergency) | CALCULATED |
| Inspection | `c_inspect` | ASSUMPTION |
| Secondary damage | `hours_above_threshold × c_damage` (optional) | ASSUMPTION |
| Contractual penalty | Only when a contract flag is set | ASSUMPTION |

Every line stores quantity, unit, unit price, label of each input, formula, assumption-set version, and date.

### 9.3 Uncertainty and sensitivity

`assumptions/*.yaml` entries carry: value or distribution (triangular as default), min, mode, max, unit, source note, version, and verified flag. Method: Latin-hypercube sample of about 500 draws over economic assumptions, interpolating hydraulic outcomes across the design grid. Outputs: P10, P50, P90, optional CVaR at 90, tornado sensitivity (one-at-a-time) and optional Morris screening. All results are labeled *conditional on the assumed ranges*.

### 9.4 Decision engine

- **Primary objective:** minimize expected total cost `E[C(a)]` across the scenario ensemble.
- **Constraints:** maximum unserved demand rate for critical zones, maintenance budget, crew availability, feasibility of the action, mandatory human approval.
- **Secondary reports:** CVaR90, regret versus best action, remaining risk.
- **Break-even:** for inspection, the probability of a real leak above which inspecting beats monitoring, computed in closed form from the cost grid.
- **Decision stability:** one-dimensional sweeps and a two-dimensional **decision map** of the two most influential assumptions, showing where the recommended action flips.
- **Negative benefit allowed:** recommends `monitor` when it is cheaper.
- **Method:** transparent expected-cost minimization with rule-based constraints. Constrained optimization with OR-Tools is added only for multi-incident resource allocation (crew scheduling across concurrent incidents).

### 9.5 Evaluation without circularity

Compare policies on identical scenario sets, costs and constraints: Reactive, Threshold-alert, Fixed-interval inspection, and UtilityGuard. Test under **perturbed** hydraulics and **held-out** cost regimes that were not used to tune. Report regret, win-frequency, tail exposure, and every setting where UtilityGuard loses. Results are conditional on the simulator and assumptions, and the UI says so.

### 9.6 Before and after

The same seed is replayed twice: without action and with the chosen action at time `t`. The UI shows both branches side by side with differences in pressure, unserved water, cost and recovery time.

### 9.7 Deployment economics (platform ROI), parametric only

A separate module, never mixed with per-incident benefit. Inputs: implementation, integration, hardware, hosting, model maintenance, expected incident frequency (an assumed range). Benefit is the evaluated per-incident avoided cost multiplied by assumed frequency. Outputs: payback, multi-year NPV, and **break-even incident frequency**. A permanent warning states that all inputs are assumptions. Negative ROI MUST be possible and visible. No default value is presented as a finding.

### 9.8 Sensor placement analysis

For candidate sensor sets, run the scenario ensemble and measure mean detection delay and localization hit rate. Value is expressed as avoided unserved water from earlier detection, converted to money with assumed prices. Greedy selection yields a ranked list of locations with evidence.

---

## 10. Evidence system

### 10.1 Evidence record

```json
{
  "evidence_id": "ev_cost_24h_0007",
  "value": 11520.0,
  "unit": "EGP",
  "label": "CALCULATED",
  "formula": "lost_water_m3 * unit_price_egp_per_m3",
  "inputs": [
    {"name": "lost_water_m3", "value": 1440.0, "unit": "m3", "label": "SIMULATION", "ref": "ev_sim_loss_0003"},
    {"name": "unit_price_egp_per_m3", "value": 8.0, "unit": "EGP/m3", "label": "ASSUMPTION", "ref": "as_water_price@v1"}
  ],
  "provenance": {
    "run_id": "run_0042", "scenario_id": "leak_gradual_medium", "seed": 42,
    "network_version": "capital_f1_v1", "detector_version": "d2_v1",
    "assumption_set": "v1", "cost_model": "v1", "git_commit": "abc123"
  },
  "explanation_template": "cost.lost_water.v1",
  "uncertainty": {"p10": 7400, "p50": 11520, "p90": 19000, "basis": "300 draws over assumed ranges"}
}
```

### 10.2 Provenance graph

A directed acyclic graph whose nodes are sources (run, reading), transformations (solver, model, formula), assumptions and results. The UI renders it in the Evidence Explorer. A result's badge shows its label and a **weakest-link marker** when any upstream node is an `ASSUMPTION`.

### 10.3 Explanations

Fixed templates, reviewed and versioned, rendering from evidence records. Bilingual (Arabic and English). No generated prose in the calculation path.

### 10.4 Reproducibility

The Run Manifest contains config, seed, versions, library versions, git commit and output hashes. `ug reproduce <manifest>` re-runs and verifies the hashes. Numeric tolerances for cross-platform runs are defined in golden tests.

### 10.5 Reports

Incident report, generated as HTML, PDF and JSON: summary, timeline, detection evidence, diagnosis rules fired, localization, impact table, cost breakdown with ranges, decision ranking, break-even and sensitivity, assumptions list with versions, limitations, and the reproducibility block. Every exported page carries the Fidelity badge and honesty banner.

---

# PART III: DATA, CONTRACTS AND THE WEB APPLICATION

## 11. Data model

### 11.1 Relational schema (SQLite in dev, PostgreSQL in compose, Alembic migrations)

| Table | Key columns |
|---|---|
| `domains` | `domain_id`, `enabled`, `adapter_version` |
| `networks` | `network_version`, `domain_id`, `provider`, `fidelity` (F0..F3), `content_hash`, `created_at` |
| `assets` | `asset_id`, `network_version`, `type`, `zone_id`, `x`, `y`, `criticality`, `attributes` (JSON, schema per adapter) |
| `sensors` | `sensor_id`, `asset_id`, `type`, `unit`, `sigma`, `sampling_s`, `rtu_group`, `sensor_set` |
| `zones` | `zone_id`, `label`, `land_use`, `criticality_weight`, `polygon` |
| `scenarios` | `scenario_id`, `schema_version`, `config` (JSON), `preset` |
| `runs` | `run_id`, `scenario_id`, `status`, `manifest` (JSON), `started_at`, `finished_at`, `output_hashes` |
| `incidents` | `incident_id`, `run_id`, `status`, `severity`, `hypothesis`, `location`, `first_detected_tick`, `closed_at` |
| `incident_events` | `incident_id`, `tick`, `event_type`, `payload`, `actor`, `at` |
| `analyses` | `analysis_id`, `incident_id`, `status`, `grid_spec`, `result_ref` |
| `assumption_sets` | `set_id`, `version`, `parent`, `created_at`, `note` |
| `assumptions` | `set_id`, `key`, `distribution`, `min`, `mode`, `max`, `unit`, `source_note`, `verified` |
| `evidence_nodes` / `evidence_edges` | Provenance DAG with node type, label, value, unit, formula |
| `reports` | `report_id`, `incident_id`, `format`, `path`, `manifest_hash` |
| `eval_runs` / `eval_results` | Detector, policy, scenario set, split, metrics (JSON) |
| `jobs` | `job_id`, `kind`, `status`, `progress`, `payload`, `attempts` |
| `audit_log` | `at`, `actor`, `action`, `object`, `diff` |
| `users` | `user_id`, `role` (stub in v1) |

### 11.2 Time-series layout (Parquet, queried through DuckDB)

```
data/runs/{run_id}/
  manifest.json
  truth.parquet          # tick, element_id, quantity, value, fault_tag_hidden   (SIMULATION)
  telemetry.parquet      # tick, sensor_id, value, unit, delivered_at
  expectation.parquet    # tick, sensor_id, expected_value, sigma  (MODEL)
  quality.parquet        # tick, sensor_id, status, score, flags
  detector_{id}.parquet  # tick, state, residuals, support
  analysis_{incident}/   # design-grid results, cost samples, decision outputs
```
`fault_tag_hidden` is stored only in the truth bundle and is excluded from every API that feeds detectors or the operator view.

---

## 12. API and contracts

Contracts live in `contracts/` as JSON Schema generated from pydantic models. TypeScript types are generated from OpenAPI (`openapi-typescript`). Every payload has `schema_version`. CI fails if generated artifacts drift from the source.

### 12.1 REST (`/api/v1`)

| Group | Endpoints |
|---|---|
| Platform | `GET /domains`, `GET /domains/{id}/ui-manifest`, `GET /health`, `GET /metrics` |
| Network | `GET /networks`, `GET /networks/{v}`, `GET /networks/{v}/geometry`, `POST /networks/import` (validated `.inp`) |
| Scenarios | `GET /scenarios`, `GET /scenarios/presets`, `POST /scenarios`, `POST /scenarios/validate` |
| Runs | `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/manifest`, `POST /runs/{id}/control` (play, pause, speed, seek), `GET /runs/{id}/series` (windowed) |
| Quality | `GET /runs/{id}/quality`, `GET /runs/{id}/sensors/{sid}/history` |
| Incidents | `GET /incidents`, `GET /incidents/{id}`, `POST /incidents/{id}/ack`, `POST /incidents/{id}/feedback`, `POST /incidents/{id}/analyze`, `GET /incidents/{id}/analysis` |
| Decisions | `GET /analyses/{id}/decision`, `POST /analyses/{id}/whatif` (assumption overrides, recomputed from cached grid), `GET /analyses/{id}/sensitivity`, `POST /analyses/{id}/branch` (before/after) |
| Evidence | `GET /evidence/{id}`, `GET /evidence/{id}/graph`, `POST /runs/{id}/verify` (reproducibility check) |
| Assumptions | `GET /assumption-sets`, `GET /assumption-sets/{id}`, `POST /assumption-sets`, `PUT /assumption-sets/{id}`, `GET /assumption-sets/{a}/diff/{b}` |
| Reports | `POST /incidents/{id}/report?format=pdf|html|json` |
| Evaluation | `POST /eval/runs`, `GET /eval/runs/{id}`, `GET /eval/leaderboard` |
| Deployment economics | `POST /economics/evaluate` |

Errors follow RFC 7807 problem details. Long jobs return `202` with a `job_id` and are observed over the WebSocket.

### 12.2 WebSocket

`/ws/runs/{run_id}` (frames in JSON, optional MessagePack for binary efficiency), `/ws/notifications`. Envelope:

```json
{"schema_version": "1", "type": "tick", "run_id": "run_0042", "seq": 8123, "payload": {}}
```

`type` is one of: `tick`, `incident.updated`, `analysis.progress`, `analysis.done`, `run.control`, `notification`. Ticks are batched when the client is slow, with `seq` gaps detectable. Contracts v1 specify the `tick` frame only; each other frame type is added to the contract when its payload is specified, and until then a frame of that type is rejected.

Tick payload:

```json
{
  "tick": 144, "sim_time": "2026-01-01T12:00:00Z", "stream_source": "REPLAY", "speed": 60,
  "readings": [{
    "sensor_id": "P05", "value": 31.2, "unit": "m", "label": "SENSOR_SIM",
    "quality": {"status": "suspect", "score": 0.62, "flags": ["Q07"],
                "label": "CALCULATED", "formula_ref": "quality.reading_score.v1"}
  }],
  "network_confidence": {"value": 0.91, "basis": "observability-weighted sensor quality",
                         "label": "CALCULATED", "formula_ref": "quality.network_confidence.v1"},
  "detectors": {"d2": {"state": "watch", "residuals": {"P05": -8.1},
                       "label": "MODEL", "version": "d2_v1"}},
  "incidents_changed": ["inc_003"]
}
```
The tick never contains truth values or hidden fault tags. The "twin truth" overlay uses a separate, explicitly authorized endpoint.

Every number in a tick carries its evidence label (section 2). A reading is `SENSOR_SIM`, `OBSERVED` or `BENCHMARK` (never `SIMULATION`: that is truth). The quality score and the network confidence index are `CALCULATED` and name the fixed, reviewed formula they come from (`formula_ref`, section 10.3); a detector output is `MODEL` and carries the detector `version`. `stream_source` is required on every tick. Names used as keys in the tick (detector ids, residual names) are plain tokens: a residual name is an upper-case sensor token such as `P05`, a detector id is lower-case such as `d2`, and neither may name truth, hidden state, injected faults, probabilities or percent confidence. The contract is `contracts/v1/stream-envelope.schema.json`; the tick example above validates against it unchanged.

### 12.3 Scenario configuration (contract)

```json
{
  "schema_version": "1", "scenario_id": "leak_gradual_medium",
  "network_version": "capital_f1_v1", "sensor_set": "S_base",
  "seed": 42, "start": "2026-01-01T00:00:00Z", "duration_hours": 72, "timestep_minutes": 5,
  "demand": {"calendar": "default_egypt", "holiday": false, "ramadan": false,
             "heatwave_multiplier": 1.0, "zone_multipliers": {"gov": 1.0, "res": 1.0, "cbd": 1.0},
             "forecast_error": {"model": "ar1", "sigma_pct": 6.0}},
  "faults": [
    {"type": "leak", "location": "pipe:P_0217", "start_hour": 20,
     "profile": "gradual", "ramp_hours": 24, "final_area_cm2": 6.0},
    {"type": "sensor_drift", "sensor_id": "P05", "start_hour": 14, "drift_per_hour": 0.3}
  ],
  "cross_domain_inputs": [],
  "assumption_set": "v1"
}
```
Validation rules: faults refer to existing elements, times are inside the horizon, parameters inside physical ranges, and incompatible combinations are rejected with a message that says how to fix them.

---

## 13. The web application: design and experience

### 13.1 Design brief

**Subject:** a live control surface for a capital-scale utility twin. **Audience:** control-room operators, planners, and ACUD executives who will watch a demo on a large display. **Primary job:** see the state of a living network at a glance, understand a problem, and trust the decision behind a number.

**Concept, "Lapis Night Operations".** A calm, deep-blue operations environment where the *network itself* is the hero. The memorable thing, and the only place we spend visual boldness, is the **living network**: water visibly flows through pipes, pressure glows in the nodes, and a problem ripples outward from where the twin says it began. Everything else (panels, tables, charts) stays quiet, precise and typographically strong so the network and the evidence carry the screen.

Futuristic here means precision, depth and responsiveness, not decoration. No neon wash, no gradient-heavy cards, no stock "cyberpunk".

### 13.2 Visual identity and tokens

Palette (names are part of the design language):

| Token | Dark (default) | Day theme | Role |
|---|---|---|---|
| `lapis-night` | `#0C1A33` | `#EEF3F8` | App background |
| `lapis-raised` | `#132746` | `#FFFFFF` | Panels |
| `lapis-line` | `#25406B` | `#C9D6E6` | Borders and dividers |
| `sand-white` | `#EAF0F8` | `#0C1A33` | Primary text |
| `haze` | `#9FB1CC` | `#4B6285` | Secondary text |
| `flow-cyan` | `#3FD0E8` | `#0A7F96` | Water, flow, selection, primary interactive |
| `capital-gold` | `#E5B94E` | `#9A6B00` | Money, decisions, recommendations |
| `calm-teal` | `#2DBFA0` | `#0F7A63` | OK status |
| `amber-signal` | `#F2A93B` | `#A8650A` | Watch status |
| `coral-alarm` | `#FF5A4F` | `#C42B22` | Incident, critical |
| `haze-violet` | `#9A8CFF` | `#5547C9` | Unknown, insufficient evidence |

Rules:
- Each accent has one job. Cyan is water and interaction. Gold is only money and decisions. Status colors are only status.
- **Never color alone.** Status uses a glyph shape as well: circle (ok), triangle (watch), diamond (incident), hexagon (unknown), square (bad data).
- Contrast meets WCAG AA in both themes. A color-blind-safe check is part of CI visual tests.
- Evidence labels each have a fixed chip style (outline for `SIMULATION`, solid for `MODEL`, gold outline for `ASSUMPTION`, hatched for `INSUFFICIENT_EVIDENCE`).

Typography:
- **Readex Pro** (variable, supports Arabic and Latin with matched proportions) is the single UI and display family, self-hosted. Hierarchy comes from weight and width contrast: large light-weight numerals for headline metrics, medium-weight labels, regular body.
- **JetBrains Mono** is used only for identifiers, hashes, formulas and code in the Evidence Explorer.
- Scale (ratio about 1.2): 12, 14, 16, 19, 23, 28, 34, 56. Sentence case everywhere. No all-caps eyebrow labels. Tabular numerals for every number. Line length under 80 characters.

Shape and depth: panels radius 14, controls 8, map overlays 20. Depth comes from luminance steps and a 1 px inner border, not drop shadows. Translucent blurred panels (backdrop blur 12 px) are allowed only for overlays that sit on the map, so the map reads as a continuous surface.

Brand mark: a droplet outline whose interior is a small node-and-pipe lattice, drawn as a single-weight vector. Wordmark in Readex Pro, medium.

Motion principles:
1. Ambient motion lives only in the map: flow along pipes (speed proportional to flow, direction by sign), node glow, incident ripple.
2. One orchestrated moment: on first load the network draws itself from the pump stations outward (about 1.4 s), then the interface settles.
3. Interaction motion answers an action: opening a drawer, flying to an incident, switching a branch. Durations 120 to 240 ms, with a small set of easing tokens.
4. `prefers-reduced-motion`: replace animated flow with static chevrons whose density encodes flow, and shorten transitions.

### 13.3 Application shell

```
┌ top bar ──────────────────────────────────────────────────────────────────────────┐
│ mark  Fidelity F1 · Public layout   source: REPLAY   sim clock   run ▾  🔔  AR/EN  ☾ │
├ honesty strip (collapsible to a permanent chip) ──────────────────────────────────┤
│ rail │                  main canvas (screen-specific)                  │ inspector │
│ (nav)│                                                                 │ (context) │
├──────┴─────────────────────────────────────────────────────────────────┴──────────┤
│ Time Machine dock (scrubber, event markers, branches), on map and incident screens │
└───────────────────────────────────────────────────────────────────────────────────┘
```
Everything in the shell is bilingual with full RTL mirroring. The Fidelity badge and honesty chip cannot be removed.

### 13.4 Map engine

A GPU map on a local Cartesian coordinate system, offline, with a procedurally drawn basemap (terrain tint, district polygons, green corridors).

| Layer | Rendering |
|---|---|
| Districts | Polygons with labels, optional extrusion, tinted by land use |
| Pipes | Path layer; width by diameter; color by selectable metric (pressure gradient, velocity, headloss, age); animated flow along the path |
| Nodes | Scatter layer; glow and size from pressure status and demand |
| Sensors | Icons with quality ring and status glyph |
| Pumps, tanks, valves | Stateful icons (on, off, standby, fault suspected) |
| Residual heatmap | Interpolated detector residuals |
| Twin truth | Leak location, true pressure, fault markers (toggle, clearly tinted) |
| Incident halo | Pulsing ripple at suspected location, with top-3 candidate pipes ranked |
| Isolation preview | Valve set and affected zones highlighted before an action is chosen |
| Domain layers | Contributed by each adapter's `ui_manifest` (electricity feeders, cooling loops later) |

Views: **2.5D map** (default), **Schematic** (SVG hydraulic diagram for engineers), and an **optional 3D Capital view** (react-three-fiber: instanced buildings generated from district polygons and land use, day and night lighting, flow pulses visible through a translucent ground plane). The 3D view is an atmospheric presentation layer. It never replaces the 2.5D map as the working view.

Tools: fly-to incident, picking with hover cards carrying evidence chips, mini-map, ruler, before/after swipe compare, layer panel, legend that updates with the selected metric.

Performance tactics: typed-array binary buffers for geometry and per-tick values, tick batching, Web Workers for series processing, instancing, level of detail by zoom.

### 13.5 Screens

| # | Screen | Purpose and key content |
|---|---|---|
| 1 | **Command Center** | Network confidence index, active incidents and highest severity, unserved water now and at risk, data-quality summary, stream source, mini map, incident list, a "next best action" card with its cost range, domain tiles (Water live; Electricity and Cooling shown as architecture-ready) |
| 2 | **Twin Map** | Full map with inspector and Time Machine. Operator view versus twin truth toggle |
| 3 | **Scenario Lab** | Gallery of 28 presets with expected behavior preview, a composer where faults are placed by dragging on a timeline, schema-validated fields, run queue, side-by-side run comparison |
| 4 | **Data Quality Observatory** | Sensor-by-time quality matrix, per-sensor drill-down, RTU group view, maintenance recommendations, confidence index trend, discrepancy monitor |
| 5 | **Incident Center and Case File** | Lifecycle board; case file with timeline, residual small multiples, diagnosis rules fired, localization map with top-k, impact summary, action history, operator feedback, report export |
| 6 | **Decision Studio** | Action cards with P10 to P90 fans, cost-of-waiting curve, decision map showing where the recommendation flips, tornado sensitivity, break-even gauge, what-if sliders recomputed from the cached grid, before and after comparison, constraint controls |
| 7 | **Evidence Explorer** | Interactive provenance graph, node detail, label legend, reproducibility panel with "re-run and verify" |
| 8 | **Evaluation Lab** | Detector and policy leaderboard, detection delay distributions, false alerts per week, localization hit rates, failure-case gallery, split and leakage disclosure |
| 9 | **Assumptions Manager** | Assumption table with distributions, sources and verified flags, version diff, sensitivity rank, warnings for unverified inputs |
| 10 | **Asset Registry** | Assets and sensors, criticality, maintenance history (empty at F1) |
| 11 | **Domains and Fidelity** | Domain cards, Fidelity ladder explanation, import wizard with validation report for `.inp` files |
| 12 | **Executive Brief** | One printable page of large type: situation, exposure ranges, top decisions, assumption sensitivity. Includes a templated briefing mode |
| 13 | **Economics Lab** | Deployment ROI as a parametric what-if with break-even incident frequency and permanent assumption warning |
| 14 | **Sensor Placement Lab** | Candidate sensor sets, measured detection-delay and localization gains, ranked locations |
| 15 | **System Health** | Workers, queue depth, run durations, detector latency |

Every screen defines loading, empty and error states. Empty states invite an action ("Run a scenario to see the network respond"). Errors say what happened and how to fix it, with no apologies.

### 13.6 Signature interactions

1. **Time Machine.** A scrubber across the whole run with event markers (fault start in twin truth, watch, alert, acknowledgement, action), brush-to-zoom, and a **Branch** button that forks the timeline at any moment into a what-if branch shown as a ghosted line.
2. **Why this number.** Any number chip opens a slide-over with value, unit, label, formula, inputs (each with its own label), sources, assumption versions, and a mini provenance graph.
3. **Operator view versus twin truth.** One toggle shows what the system *knows* versus what is *true*, exposing blind spots and misses.
4. **Case file assembly.** When an incident opens, the case file builds itself in order (evidence, diagnosis, location, impact, cost, decision) as analysis jobs finish, with progress visible.
5. **Decision map.** Two-axis heatmap of the most influential assumptions, colored by the best action, with the current assumption marked, so the user sees how far they are from a flip.
6. **Swipe compare.** Drag across the map to compare "do nothing" against "act" for the same seed.
7. **Command palette** (Ctrl+K): jump to sensor, pipe, incident, scenario, or run a preset.
8. **Wall mode.** A large-display mode with oversized type, auto-cycling views, no pointer dependency, for control-room walls and ACUD presentations.

### 13.7 Data visualization rules

uPlot for streaming time series and ECharts for rich charts. Uncertainty is drawn as bands and fans, never as a single line. One axis per chart unless a dual axis is essential and labeled. Units always visible. Numbers use tabular figures and locale formatting, with an option for Arabic-Indic digits. Charts carry evidence labels. Residual plots show the threshold and the persistence window.

### 13.8 Accessibility and internationalization

Arabic and English with complete RTL mirroring, reviewed Arabic copy, AA contrast, full keyboard navigation with visible focus, ARIA live regions for incidents, spoken map summaries ("2 open incidents, highest severity high, in the residential district"), reduced-motion support, scalable text, 44 px touch targets for tablets. Units switchable (m head or bar or psi; m3/h or L/s).

### 13.9 Responsive behavior

Desktop-first at 1920 by 1080, a 4K wall mode, tablet for field supervisors, and a read-only mobile incident view.

### 13.10 Copy and voice

Plain, active, sentence case, no filler. A button says what happens ("Run scenario", "Acknowledge incident", "Export report"). An action keeps its name through the flow. Examples: empty Alerts screen: "No incidents. All residuals are within expected range." Error: "The scenario could not start because pipe P_0999 does not exist. Pick a pipe from the map." Honesty chip: "Simulated data, advisory only."

### 13.11 Frontend architecture

```
frontend/src/
  app/            shell, routing, providers, i18n, theme
  features/       command-center, map, scenario-lab, quality, incidents,
                  decision-studio, evidence, evaluation, assumptions, assets,
                  domains, executive, economics, placement, health
  map-engine/     layers, camera, picking, workers, binary buffers
  ui/             design system components, tokens, icons, chips
  data/           api client (generated), ws client, stores (ring buffers), selectors
  lib/            units, formatters, a11y helpers
```
State: TanStack Query for server state, Zustand for UI state, ring-buffer stores for streaming series, selectors feeding map layers. Types generated from OpenAPI. Testing: Vitest, Playwright end-to-end, visual regression snapshots in both themes and both directions, axe accessibility checks, Storybook for the component inventory.

Component inventory (minimum): `FidelityBadge`, `StreamSourcePill`, `EvidenceChip`, `NumberWithEvidence`, `StatusGlyph`, `TimeMachine`, `LayerPanel`, `IncidentCard`, `ActionCard`, `FanChart`, `DecisionMap`, `TornadoChart`, `ProvenanceGraph`, `SensorMatrix`, `AssumptionEditor`, `CommandPalette`, `WallModeShell`, `BranchCompare`.

### 13.12 Process for the implementer (design discipline)

1. Before writing UI code, produce a short design plan: tokens, type roles, layout concept with ASCII wireframes for the Command Center and Twin Map.
2. Review the plan against this brief and against generic defaults (templated card grids, one soft shadow everywhere, decorative gradients, all-caps eyebrows, numbered markers on non-sequences). Revise anything that reads as a default and note why.
3. Build the shell and the map engine first, because the living network is the identity. Screenshot in both themes and both text directions. Critique, then remove one decorative element.
4. Keep boldness in the map and the Time Machine. Everything else stays disciplined.

---

# PART IV: ENGINEERING, FUTURE DOMAINS AND DELIVERY

## 14. Repository layout (monorepo)

```
utilityguard/
├─ README.md   CLAUDE.md   docs/   contracts/   assumptions/   data/ (git-ignored: runs, private)
├─ platform/                       # L2 core, domain-agnostic
│  ├─ ug_core/     entities, time model, scenario engine, evidence kernel, registry, event bus ports
│  ├─ ug_intel/    quality, expectation, detectors, diagnosis, incidents, cost, decision, evaluation
│  ├─ ug_api/      FastAPI app, WebSocket hub, jobs, reports
│  ├─ ug_cli/      `ug` command: run, reproduce, eval, import, export
│  └─ tests/       unit, property, golden, contract, conformance
├─ domains/
│  ├─ water/       ✔ implemented (network providers, WNTR solver, faults, measurement, actions)
│  ├─ electricity/ ○ adapter skeleton + conformance tests (Section 18)
│  └─ cooling/     ○ adapter skeleton + conformance tests (Section 19)
├─ frontend/       React app (Section 13.11)
├─ eval/           experiment configs, split definitions, result notebooks, benchmark loaders
├─ deploy/         docker-compose.yml (profiles: core, redis, postgres), Dockerfiles, Makefile
└─ .github/workflows/  ci.yml (lint, types, tests, contract drift, e2e, visual)
```

Rule: `platform/` MUST NOT import from `domains/`. Domains register through entry points. A lint rule enforces this.

`CLAUDE.md` at the repo root restates the Honesty Rules, the layer dependency rule, the contract policy and the milestone gates so every Claude Code session starts with them.

---

## 15. Evaluation and validation plan

Principle: separate what is *demonstrated on benchmark data*, what is *simulated*, what is *statistically estimated*, and what is *assumed*. The Evaluation Lab reports each in its own section.

### 15.1 Tracks

| Track | Data | Valid claims |
|---|---|---|
| T1: Benchmark leak detection | BattLeDIM L-Town (2018 historical, 2019 evaluation, EPANET model, SCADA, leak labels). Verify exact event counts and label files from the dataset package before use | Event-level recall, delay, false alerts, localization on a public benchmark that is itself model-generated |
| T2: Synthetic fault detection | Capital twin scenarios with held-out fault parameters | Detection and diagnosis performance on simulated faults only. Never field validation |
| T3: Fault differentiation | Leak versus sensor fault versus demand change versus pump issue scenarios | Diagnosis accuracy, confusion matrix, rate of `unknown` |
| T4: Consequence analysis | Identical incidents with and without action | Hydraulic KPI differences, conditional on the simulator |
| T5: Decision comparison | Policies on identical scenarios, costs and constraints | Regret, win frequency, tail exposure, flip points |
| T6: Financial robustness | Perturbed assumptions and cost regimes | Stability of the recommendation |
| T7: Explainability and reproducibility | Independent re-computation | Every reported number reproduced from its manifest |
| T8: Optional run-to-failure experiment | A separate public equipment dataset (for example a bearing run-to-failure set) | Only a standalone RUL experiment on that equipment. Never merged with the water twin or claimed for pumps |

### 15.2 Splits and leakage control

- Temporal splits only: train on earlier periods, validate on later, test on a final untouched period. For BattLeDIM, train on 2018 and test on 2019.
- For synthetic scenarios: separate **scenario families** and **fault parameter ranges** across train, validation and test. No test scenario shares seed, fault location or magnitude bucket with training.
- Thresholds and persistence windows are tuned on validation only. The test set is used once per reported configuration, with the number of test evaluations logged.
- Normalization and baselines are fit on training only.
- A **split and leakage disclosure** panel lists, for every reported metric, what was used to fit, tune and test.

### 15.3 Metrics

Event-level recall; detection delay (median, P90); false alerts per simulated week on fault-free and demand-change scenarios; diagnosis accuracy with confusion matrix and `unknown` rate; localization hit@1, hit@3 and distance error; early-warning lead time on gradual faults; unserved water avoided against the strongest baseline at equal false-alarm rate; policy cost, regret and tail exposure; calibration only where a defined probability exists, with reliability curves.

Uncertainty: bootstrap over events and scenario seeds for intervals. Failure cases are listed explicitly in the UI and the report.

**The single headline KPI:** *unserved water avoided compared with the strongest baseline detector at the same false-alarm rate*, reported with its interval and its conditions.

### 15.4 Mandatory baselines

Fixed thresholds (D1), residual CUSUM (D2), multivariate residual detector (D3), reactive policy, threshold-alert policy, and fixed-interval inspection policy.

---

## 16. Testing strategy

| Level | What |
|---|---|
| Unit | Every module. Network validation, demand layers, fault injectors, quality checks, cost arithmetic |
| Property-based (hypothesis) | Conservation laws (mass balance), cost lines nonnegative and non-double-counted, schema round trips, grouping merge and split invariants |
| Golden determinism | Same manifest yields identical hashes within defined tolerances |
| Contract | Schemas, OpenAPI drift, WebSocket envelope, generated TypeScript types |
| Conformance | Every domain adapter passes the adapter suite |
| Scenario regression | The 28 presets run in CI at reduced duration and compare key outcomes |
| Evaluation smoke | Small sweep must meet minimum thresholds or CI fails |
| Frontend | Vitest components, Playwright journeys (run a scenario, open an incident, open Why this number, switch language and theme), axe accessibility, visual regression in four combinations of theme and direction |
| Performance | Tick latency, map frame time on a reference scene, analysis duration, with budgets from Section 4.8 |
| Security and hygiene | Dependency audit, secret scan, license check |

---

## 17. DevOps and delivery

- **One command:** `make up` starts the whole stack with Docker Compose. `make dev` runs locally without Docker. `make demo` loads prebuilt runs so the demo works instantly and fully offline.
- Compose profiles: `core` (api, worker, frontend), `redis` (stream bus adapter), `postgres` (relational store), `observability` (metrics and tracing).
- `ug` CLI: `ug run <scenario>`, `ug reproduce <manifest>`, `ug eval <config>`, `ug import-network <file.inp>`, `ug export-report <incident>`, `ug doctor` (environment and API checks, including the WNTR signatures used).
- CI on every push: ruff, mypy, pytest, contract drift, ESLint, tsc, Vitest, Playwright, visual regression, build images. Release notes generated from conventional commits. Semantic versions for contracts.
- Demo Mode ships prebuilt runs and a scripted tour so the system is demonstrable without waiting on simulations.

---

## 18. Domain 2: Electricity (designed in, built after Water)

**Goal:** prove the platform is genuinely multi-utility with a real second domain and real cross-domain scenarios.

| Aspect | Design |
|---|---|
| Assets | HV/MV substations, transformers, MV feeders, ring main units, switchgear, normally-open tie switches, loads per zone, optional rooftop solar and storage |
| Sensors | Voltage, current, active and reactive power, transformer oil and winding temperature, breaker status, smart-meter aggregates |
| Solver | Steady-state AC power flow with a time-series loop. Candidate: pandapower (verify license, API and availability). Network generator mirrors the district structure of the water twin so cross-domain scenarios align |
| Expectation model | Forecast load and generation, fault-free power flow, residuals on voltage and power |
| Faults | Transformer overload and accelerated thermal aging (custom degradation, `ASSUMPTION`, referencing a loading guide such as IEEE C57.91, verify), feeder trip, line fault, voltage sag, CT or VT sensor drift, stuck breaker status, load surge (heatwave air conditioning), solar intermittency |
| Detectors | Residual and CUSUM on voltage profile, transformer thermal-model residual, flow-balance consistency across feeders, supervised diagnosis, all behind the same `Detector` interface |
| Localization | Signature matrix over candidate lines and transformers, same method as water |
| Impact KPIs | Unserved energy (kWh), customers interrupted, reliability indices in the style of SAIDI and SAIFI, voltage violations, transformer loss of life estimate (modeled), energy losses |
| Actions | Feeder reconfiguration via tie switches, load transfer, demand response, transformer swap or maintenance, temporary generation |
| Costs | Value of lost load (`ASSUMPTION`), repair and replacement, energy losses, penalties only if contractual |
| Validation | Standard public test feeders and benchmark networks (for example IEEE test feeders, CIGRE benchmark; verify availability) for solver validation. Fault detection validated on simulated faults only. Public transformer failure data is scarce, so no calibrated failure probabilities are claimed |
| UI | New map layers (feeders by loading and voltage, substations, ties), electrical-specific panels, from the adapter's `ui_manifest` |
| Cross-domain | Feeder supplies pump station, so an electrical fault yields a water pump outage scenario input (`F-POWER`) with both domains' impacts and a combined cost view |

Exit criteria: adapter passes conformance, 10 electricity scenarios run through the unchanged core pipeline, one cross-domain scenario (feeder trip leads to pump outage leads to pressure loss) shows combined evidence and cost.

---

## 19. Domain 3: District Cooling (designed in, built after Electricity)

| Aspect | Design |
|---|---|
| Assets | Chillers, cooling towers, chilled-water pumps, primary and secondary loops, thermal energy storage, heat exchangers at building energy transfer stations, valves |
| Sensors | Supply and return temperature, flow, differential pressure, chiller power, tower fan status, storage temperature profile, ambient temperature |
| Solver | Hydraulics for the chilled-water network can reuse a pipe-network solver. The thermal side is a custom model: energy balance, chiller COP curves versus load and ambient conditions, effectiveness-NTU heat exchangers, storage stratification as a simple multi-node model. Document all approximations |
| Faults | Chiller fouling (COP degradation, custom model), refrigerant charge loss (capacity drop), cooling-tower fan fault, heat-exchanger fouling (low delta-T syndrome), pump faults, stuck valve, chilled-water leak, temperature sensor drift, storage sensor faults |
| Detectors | Energy balance residuals, kW per ton against an expectation curve, delta-T monitors, same interface as other domains |
| Impact KPIs | Unmet cooling load (kWh thermal), supply temperature violations, kW per ton, plant energy, makeup water |
| Actions | Stage another chiller, shift load to storage, adjust setpoints, clean or service heat exchangers, isolate a leaking section |
| Costs | Energy, water makeup, maintenance, comfort or penalty cost (`ASSUMPTION`) |
| Validation | A public chiller fault dataset exists (the ASHRAE RP-1043 chiller fault data is a candidate, verify availability and terms) and can validate chiller fault detection on real lab measurements of one chiller. Network-level behavior remains simulator-only |
| Cross-domain | Chillers draw from electricity feeders and makeup water from the water network. A **compound heatwave scenario** raises cooling load, electricity peak and water demand together and is the flagship multi-utility demonstration |

Exit criteria: conformance passed, chiller-fault validation on the public dataset reported honestly, the compound heatwave scenario runs end to end across all three domains.

---

## 20. From synthetic to real: calibration and live integration (F2, F3)

### 20.1 Data to request from ACUD (checklist for the first meeting)

Network GIS and asset register (pipes, diameters, materials, age, valves, tanks, pump stations); pump and chiller curves and equipment specifications; SCADA tag list and sensor metadata; historical SCADA for pressure, flow, tank levels (at least several months, including known events); leak, burst and repair logs with dates and locations; demand patterns by district and aggregated billing data; tariffs and unit costs (water production, electricity, repair, crew rates); contracts and penalty clauses; zone criticality list; maintenance records; the existing smart-city platform interfaces and any ETAP or SCADA export formats. Ask what format each comes in and what confidentiality terms apply.

### 20.2 Calibration workflow (F1 to F2)

1. Import topology (`InpFileProvider` or `GeoJsonProvider`), validate connectivity and units.
2. Calibrate demand patterns and pipe roughness against historical pressure and flow by bounded least squares on residuals. Verify the calibration utilities available in the installed WNTR version or implement our own with documented bounds.
3. Hold out a later period. Report pressure and flow error per sensor on the held-out period.
4. Re-estimate residual sigmas, re-tune detector thresholds on validation, re-run the evaluation suite on historical events if labels exist.
5. Upgrade the Fidelity badge to F2 only when the held-out error report passes agreed thresholds. Evidence labels switch to `OBSERVED` where real measurements are shown.

### 20.3 Live integration (F2 to F3)

Source adapters behind the telemetry port: OPC UA client, MQTT subscriber, Modbus gateway reader, REST and CSV drop. Requirements: **read-only** data path, no write path to control systems, network segmentation, tag dictionary with unit mapping, timestamp synchronization and skew checks, backpressure handling, replay of recorded live data through the same pipeline for regression testing. The stream source indicator changes from `REPLAY` to `LIVE`. All existing quality, detection, and evidence logic is unchanged.

---

## 21. Roadmap and milestones

Build order, not scope reduction. Each milestone ends with a working demo, all checks passing, and a short report of known limits.

| M | Name | Deliverables | Acceptance checks |
|---|---|---|---|
| M0 | Foundations | Repo, CI, `CLAUDE.md`, contracts and generated types, design plan for the UI (tokens, wireframes), Docker, `ug` CLI, mock dataset and mock stream in the final formats | Contract tests green. `make up` serves an empty shell with the Fidelity badge and banner. `ug doctor` verifies WNTR API signatures |
| M1 | Twin core | Procedural capital network and validation, demand model, hydraulics with PDD, all fault injectors, piecewise gradual faults, run store, manifest, determinism | Normal week runs cleanly. Same seed gives identical hashes. Leak lowers pressure near its location. Chunk-size convergence report written |
| M2 | Telemetry, stream and map | Measurement model, replay player with control, WebSocket hub, shell, map engine v1 (2.5D, animated flow, sensors, truth toggle), Scenario Lab basic | Drift, stuck, dropout visible in telemetry and absent in truth. Map holds 60 fps on reference scene. Seek and speed work |
| M3 | Quality, detection, incidents | Q01 to Q12, expectation with forecast error, D1 to D3, diagnosis, signature-matrix localization, incident manager, Alerts, Quality Observatory, Case File | Zero incidents on normal, holiday, heatwave, Ramadan over 10 seeds. Leaks detected with reported delay. Drift diagnosed as sensor fault. Ambiguous cases return `unknown` |
| M4 | Impact, cost, decision, evidence | Design grid runner, cost engine, sampling and sensitivity, decision engine, evidence kernel, Decision Studio, Evidence Explorer, reports, before and after | Every displayed number opens a complete evidence trail. Changing an assumption can flip the ranking and shows the flip point. Negative benefit case works. `ug reproduce` verifies a report |
| M5 | Evaluation and ML | D4 to D6, evaluation harness, BattLeDIM track T1, policy comparison T5, Evaluation Lab, failure gallery, leakage disclosure | Reports with intervals and explicit conditions. Strongest baseline is always shown. Test set used once per configuration |
| M6 | Experience layer | Time Machine with branching, 3D Capital view, Wall mode, Executive Brief, command palette, notification center, Economics Lab, Sensor Placement Lab, AR/EN and RTL polish, Day theme | Accessibility audit passes. Visual regression stable in four theme and direction combinations. Demo script runs end to end |
| M7 | Hardening | Performance tuning, security hygiene, docs, Demo Mode, packaging, final regression | Budgets met. CI green. Fresh clone to running demo in one command |
| P2 | Electricity | Section 18 | Section 18 exit criteria |
| P3 | Cooling | Section 19 | Section 19 exit criteria |
| P4 | Calibration and live | Section 20 | Held-out error report, Fidelity upgrade to F2 |

Critical path for scientific credibility: M0, M1, M3, M4, M5. M2 and M6 interface work can run in parallel with them.

---

## 22. Team and ownership (two engineers, both using Claude Code)

| | **A: Engine** | **B: Intelligence and Product** |
|---|---|---|
| Owns | `domains/water`, solver, faults, measurement model, impact runner, cost and decision engines, evidence kernel, later electricity and cooling solvers | `platform/ug_intel` quality, detectors, diagnosis, localization, incidents, evaluation harness, `ug_api` stream and REST, the whole `frontend/` |
| Contracts | Co-owned. Changes need both reviews | Co-owned |

Working agreements: contracts and mock data first (M0). Weekly integration demo of the full path. Short-lived branches, reviews on every PR, both run the full CI locally before merging. After M4, A helps with frontend screens (Decision Studio, Evidence Explorer). Each person keeps a decision log (`docs/adr/`) for non-obvious choices.

---

## 23. Risk register

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | Presenting F1 as a real replica of the capital | Credibility loss with ACUD | Fidelity badge, banner, scripted wording, F2 data request in the first meeting |
| 2 | Synthetic faults make detection look easier than reality | Overclaim | Forecast error, model mismatch, held-out parameters, BattLeDIM track, explicit disclosure |
| 3 | Circular decision evaluation | Misleading savings | Held-out cost regimes, perturbed hydraulics, every losing case shown |
| 4 | Uncertain assumptions drive ROI | Misleading finance | Ranges, break-even, sensitivity, permanent warnings, no default presented as finding |
| 5 | WNTR limits (pump degradation, sensor faults, piecewise leaks) | Technical blockers | Custom layers documented as approximations, `ug doctor` checks APIs early |
| 6 | Simulation too slow for interaction | Poor demo | Precompute runs, design-grid interpolation, background analysis, Demo Mode |
| 7 | Visual ambition outruns evidence | Weak science behind a strong look | Evaluation track on the critical path, 3D as optional layer, review of the design plan against this spec |
| 8 | Breadth (three domains, many screens) | Unfinished core | Milestone gates, conformance tests, domains after the water core passes M5 |
| 9 | Contract drift between two people | Integration pain | Generated types, CI drift check, weekly integration demo |
| 10 | Explanations sound right but are wrong | Loss of trust | Fixed templates only, no LLM in calculations, numeric reproducibility test |
| 11 | Safety misuse | Real-world harm | Advisory-only banner, no write path, human approval, audit log |
| 12 | Existing commercial overlap with ACUD's platforms | Weak differentiation | Position as evaluation and decision layer, validate need in the first ACUD conversation |

---

## 24. Definition of done (whole project)

1. All milestones M0 to M7 pass their acceptance checks, and CI is green.
2. Any displayed number can be traced to sources, formulas and assumption versions, and `ug reproduce` verifies the report.
3. The Evaluation Lab reports the headline KPI, with the strongest baseline, intervals and conditions, plus a failure-case gallery and leakage disclosure.
4. The Fidelity badge, stream-source indicator and honesty strip are present everywhere, including exports.
5. Arabic and English with full RTL, both themes, AA accessibility, keyboard-complete.
6. Offline demo from a fresh clone with one command, including Demo Mode and the scripted tour.
7. A documented "what this does not prove" page.
8. Domain conformance suite exists and Electricity and Cooling skeletons pass it, so adding a domain is a plugin task.

---

# APPENDICES

## Appendix A: assumptions file (format and placeholders)

All values below are **placeholders** to show the format. None is a real price or measured value. Replace with sourced values and mark `verified: true` only when a source exists.

```yaml
set_id: v1
parent: null
note: "Placeholder assumptions for the F1 twin (public layout, synthetic hydraulics). Not ACUD data."
assumptions:
  water_production_cost:
    unit: EGP/m3
    distribution: {type: triangular, min: 5.0, mode: 8.0, max: 12.0}
    source_note: "Placeholder"
    verified: false
  unserved_water_penalty:
    unit: EGP/m3
    distribution: {type: triangular, min: 0.0, mode: 15.0, max: 60.0}
    source_note: "Placeholder; can be zero if no penalty applies"
    verified: false
  electricity_price:
    unit: EGP/kWh
    distribution: {type: triangular, min: 1.0, mode: 2.0, max: 3.5}
    verified: false
  inspection_cost:
    unit: EGP
    distribution: {type: triangular, min: 2000, mode: 4000, max: 8000}
    verified: false
  repair_cost_planned:
    unit: EGP
    distribution: {type: triangular, min: 10000, mode: 25000, max: 60000}
    verified: false
  repair_cost_emergency:
    unit: EGP
    distribution: {type: triangular, min: 20000, mode: 45000, max: 120000}
    verified: false
  crew_response_hours:
    unit: h
    distribution: {type: triangular, min: 2, mode: 6, max: 18}
    verified: false
  repair_duration_hours:
    unit: h
    distribution: {type: triangular, min: 4, mode: 10, max: 30}
    verified: false
  intervention_effectiveness:
    unit: fraction
    distribution: {type: triangular, min: 0.7, mode: 0.95, max: 1.0}
    verified: false
  holiday_gov_demand_factor:
    unit: fraction
    distribution: {type: triangular, min: 0.45, mode: 0.6, max: 0.8}
    verified: false
  heatwave_demand_multiplier:
    unit: fraction
    distribution: {type: triangular, min: 1.1, mode: 1.25, max: 1.45}
    verified: false
  demand_forecast_error_sigma_pct:
    unit: percent
    distribution: {type: triangular, min: 3, mode: 6, max: 12}
    verified: false
  min_service_pressure:
    unit: m
    distribution: {type: triangular, min: 12, mode: 15, max: 20}
    verified: false
```

## Appendix B: Claude Code operating prompts

**Root `CLAUDE.md` (paste at the repo root):**

```
You are building UtilityGuard Twin from docs/UtilityGuard_Master_Spec.md. That file is the source of truth.
Rules:
1. Follow the Honesty Rules (Section 2) always. Ask before changing them.
2. Respect the layer dependency rule: platform/ never imports domains/.
3. Change contracts only through versioned schema updates and regenerate types.
4. Build milestone by milestone (Section 21). Do not start the next milestone until acceptance checks pass.
5. Verify every external API (WNTR, libraries) by introspection or docs before use. Never guess signatures.
6. Every displayed number must be created with an evidence record. No LLM in calculations.
7. Before UI code, write the design plan (tokens, wireframes), review it against the spec and against generic defaults, then build, screenshot, critique.
8. After each milestone print: what works, what is approximated, what is not proven.
```

**Per-milestone kickoff template:**

```
Implement milestone M<N> from Section 21 of the master spec.
First print a checklist of tasks, the APIs you will verify, and the tests you will write.
Then implement. Run all tests and the acceptance checks. Start the app and verify visually where relevant.
Finish with a summary: working features, approximations introduced, known limitations, and files changed.
Do not proceed to M<N+1>.
```

## Appendix C: executive demo script (about 12 minutes)

1. Open Command Center in Wall mode. State the Fidelity level and that data is simulated.
2. Show the living network at normal operation. Explain truth versus telemetry.
3. Launch `heatwave`. Show demand rising and no alert, and explain why.
4. Launch `leak_gradual_medium`. Watch the residual trend; the system moves to `watch` and then opens an incident.
5. Toggle twin truth: compare where the leak is with where the system points.
6. Open the Case File: evidence, diagnosis rules, top-3 candidate pipes.
7. Open Decision Studio: cost of waiting, ranked actions, break-even, decision map.
8. Open Why this number on the headline cost and walk the provenance graph.
9. Branch the timeline, compare do-nothing against act, side by side.
10. Open the Evaluation Lab: headline KPI against the strongest baseline, including where we lose.
11. Open Domains: show architecture readiness for Electricity and Cooling and the compound heatwave scenario as the roadmap.
12. Close with the Fidelity ladder and the data request for ACUD to move from F1 to F2.

## Appendix D: initial architecture decision records to write

ADR-001 truth versus telemetry separation. ADR-002 replay-first stream with precomputed runs. ADR-003 design-grid interpolation for Monte Carlo. ADR-004 domain adapter interface and registry. ADR-005 Parquet plus DuckDB for time series. ADR-006 evidence kernel and provenance DAG. ADR-007 map engine and offline basemap. ADR-008 no LLM in the calculation path. ADR-009 fidelity ladder and labeling. ADR-010 piecewise gradual-fault simulation and its error bounds.

## Appendix E: glossary

**DMA:** district metered area. **PDD:** pressure-driven demand. **Twin truth:** simulator's physical state, hidden from detectors. **Telemetry:** simulated sensor readings with errors. **Residual:** measured minus expected, normalized. **CUSUM:** cumulative sum change detector. **Signature matrix:** precomputed sensor response to a reference fault at each candidate location. **Fidelity ladder:** F0 to F3 scale of tie to a real system. **Evidence label:** category of origin attached to every number. **Design grid:** precomputed hydraulic outcomes over delay, size and action. **Break-even:** parameter value at which two actions cost the same. **CVaR:** mean cost in the worst tail of outcomes. **Decision map:** heatmap showing the best action across two uncertain assumptions.
