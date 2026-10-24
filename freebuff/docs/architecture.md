# Architecture

## Data flow

```
ScenarioConfig (ASSUMPTION)
      │
      ▼
WNTR run ──► TruthSeries (SIMULATION) ──┬──► baseline run (fault-free, SIMULATION)
      │                                 │
      │                                 ▼
      │                     sensor layer: noise, drift, stuck, dropout (SENSOR_SIM)
      │                                 │
      │                                 ▼
      │                     quality layer: ok/suspect/bad + score + flags (MODEL)
      │                                 │
      │                                 ▼
      │                     detector: residuals in sensor sigmas, persistence + CUSUM (MODEL)
      │                                 │
      │                                 ▼
      │                     diagnosis rules: pump → leak → sensor → demand → unknown (MODEL)
      │                                 │
      │                                 ▼
      │                     incident grouping (MODEL)
      │                                 │
      └──────────────► stored run bundle ─┴──► REST + WebSocket replay
                                                 │
                                                 ▼
                                    decision engine (on demand):
                                    WNTR continuation for each action
                                    + cost lines + Monte Carlo + break-even
```

The whole scenario is simulated once when the run is created. The WebSocket only replays stored frames; it never calls WNTR. That makes the stream deterministic and cheap, and keeps "real-time" honest: it is a replay.

## Key modules

| Module | Responsibility |
| --- | --- |
| `network/builder.py` | Hypothetical 6×6 grid behind a `NetworkProvider` protocol, plus description used by UI and diagnosis |
| `network/zones.py` | Zone demand curves (ASSUMPTION) |
| `scenarios/schema.py` | Pydantic scenario contract, validation, canonical form for hashing |
| `scenarios/runner.py` | Chunked WNTR simulation, baseline run, sensor layer, output hash |
| `quality/checks.py` | Range, stuck, rate-spike, neighbour-drift, tank mass-balance checks |
| `detect/baseline.py` | Expected values from the fault-free run, residual in noise sigmas |
| `detect/detector.py` | Persistence/CUSUM detection, per-sensor state, confidence |
| `detect/diagnose.py` | Rule precedence, candidate pipe ranking, severity |
| `alerts/manager.py` | Incident grouping, merge rules, alert tick map |
| `finance/engine.py` | Assumptions, cost lines, triangular Monte Carlo, sensitivity helpers |
| `impact/runner.py` | WNTR continuation from an incident tick, with tank carry-over |
| `decision/engine.py` | Option ranking, constraints, break-even, sensitivity, advisory text |
| `evidence/builder.py` | Evidence records for incident and decision numbers |
| `eval/` | Evaluation of detection, false alarms, localisation, quality, decisions |
| `store/db.py` | SQLite metadata + zlib-compressed JSON blobs |

## Determinism

- Each run has a fixed integer seed used by the sensor noise and Monte Carlo sampling.
- Scenario configs are canonicalised (sorted faults, fixed key order) and hashed with SHA-256.
- WNTR runs with fixed timesteps and chunk boundaries derived deterministically from the config.
- The evaluation re-runs a preset and asserts the hash is unchanged.

## Why chunking?

WNTR models a leak as a constant area. A gradual leak changes area over time, so the runner splits the timeline at fault boundaries and at hourly steps during a ramp, then carries the tank level into the next chunk. Hydraulics inside each chunk are solved normally. The approximation is documented in `scenario_schema.md`.

## Separation of truth and measurement

The detector and quality layer take only `readings` (SENSOR_SIM) and the baseline expectation. Ground truth is used to build the baseline and for evaluation only. The UI's truth overlay is explicitly labelled and off by default.

## Honesty constraints in code

- `evidence/builder.py` asserts that every label is one of the six allowed values.
- No probability is estimated anywhere; the decision engine computes break-even thresholds from cost differences.
- Missing data is `null`/`INSUFFICIENT_EVIDENCE` rather than interpolated.
- The permanent banner and footer are rendered by the app shell, not toggled by state.
