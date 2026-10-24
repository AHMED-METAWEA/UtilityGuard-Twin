# Acceptance checks

Recorded on 2026-10-22, Python 3.11, WNTR 1.5.0, Node 20, macOS.

## Commands

```bash
cd backend && ../.venv/bin/python -m pytest -q          # 34 passed
cd backend && ../.venv/bin/python -m app.eval.run --with-decisions
make build                                               # tsc + vite build
make start                                               # http://127.0.0.1:8000
```

## M1 — virtual network and deterministic simulation

- Network: 41 nodes (36 grid junctions + 4 process junctions + tank), 60 pipes, 3 isolation valves, PRV, duty/standby pumps; 12 sensors (8 pressure, 3 flow, 1 level).
- 48 h normal run completes in ~6 s. `truth.ticks == 576`, 577 timestamps, finite pressures and demands.
- Same config + seed produces identical `output_hash` and readings; changing the seed changes readings but not physics.
- Leak run lowers pressure near the leak and raises tank outflow; baseline has zero leak flow.
- Sensor faults change readings only: stuck P02 is constant for 6 h while truth pressure moves; drift P05 diverges while truth equals baseline.

## M2 — replayed stream and API

- `POST /api/runs?wait=true` returns `ready` with hash, seed and runtime.
- WebSocket `/ws/runs/{id}` sends tick 0 immediately, then tick 1 at +5 simulated minutes; `pause`, `resume`, `speed` and `jump` are honoured.
- REST: truth, readings, quality, incidents, evidence and analysis endpoints all return labelled payloads.
- UI: permanent banner and footer; play/pause, scrub, speed, map, charts, sensor table render without console errors.

## M3 — data-quality layer

- Status values are `ok | suspect | bad`; score is bounded to [0,1].
- Fault-free run: 0 bad readings, suspect readings < 2% of all samples.
- Stuck sensor: 40+ ticks flagged `stuck`/`stuck_persistent` and marked `bad`; no other sensor is marked bad in the same window.
- Drift: P05 flagged `drift_vs_neighbors` for 20+ ticks late in the run; P06 is not.

## M4 — detection, diagnosis, incidents

- Fault-free presets (`normal`, `holiday`, `heatwave`): zero incidents, zero alert ticks.
- Detection: 6/6 declared fault scenarios detected; mean latency 72 simulated minutes in the evaluation.
- Leak: high severity, candidate pipe list present, residual evidence shows falling pressure and rising tank outflow.
- Sensor drift/stuck: `sensor_fault` at the correct sensor; physics unaffected.
- Pump outage: single `pump_issue` incident at PUMP_1; recovery transient does not open a second incident.
- Combined leak + sensor drift: two incidents (sensor fault and leak), i.e. the ambiguity is surfaced rather than hidden.
- Leak localisation is **not** demonstrated: 0/2 top-1 and 0/2 top-3. This is reported in the UI and evaluation.

## M5 — costs and decision support

- Every cost line equals quantity × unit price; line sums equal total cost; variant averaging is unit tested.
- Monte Carlo is seeded and reproducible; P10 ≤ P50 ≤ P90.
- Break-even uses fixed costs when the fault is absent; the "never pays off" branch is tested.
- Decision output includes recommended action, feasible set, constraints, sensitivity with ranking flips, cost context and an advisory-only notice.
- Leak decision examples: repair-isolate recommended with mean cost ≈ 10.4k CU vs monitor ≈ 29.9k CU; savings labelled CALCULATED and conditional on ASSUMPTIONs.

## M6 — evidence trail

- Incident evidence contains 30+ records; every record has a valid label, formula, inputs, sources and explanation.
- Labels used include MODEL, SENSOR_SIM, SIMULATION, ASSUMPTION, CALCULATED.
- Reproducibility record includes run id, seed, network/detector/assumption versions and recompute instructions.

## M7 — evaluation

- `docs/eval_report.md` regenerated from the same code path; determinism re-check passed.
- Fault-free incidents 0; alert-tick fraction 0.00%.
- Decision sanity check runs WNTR continuations and reports costs/constraints.

## Not verified / limitations

- No real utility data, no field validation, no probability calibration.
- Pressure-only leak localisation is weak on this looped grid; see README and the evaluation report.
- Isolation is modelled by reducing leak area, not by graph/valve operations.
- Screenshot capture initially failed while the preview webview was not compositing; after a reload and viewport resize it worked (see `screenshots/dashboard.png`). Functionality was verified with accessibility snapshots and DOM assertions.
- Docker images were not built in this session.
