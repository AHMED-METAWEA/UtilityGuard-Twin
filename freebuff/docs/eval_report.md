# Evaluation report

Virtual utility twin. Hypothetical network, simulated data. These metrics describe this prototype on its own synthetic network only.

- Generated: 2026-10-22T12:23:59+00:00
- Engine: WNTR 1.5.0 (Python)
- Network: ugtwin-v1 · detector rules-v1

## Summary

| Metric | Value |
| --- | --- |
| Scenarios evaluated | 9 |
| Fault scenarios detected | 6/6 (100%) |
| Mean detection latency | 72 min |
| Leaks detected | 2/2 |
| Leak localisation top-1 | 0/2 |
| Leak candidate top-3 contains truth | 0/2 |
| Incidents on fault-free runs | 0 |
| Alert-tick fraction on fault-free runs | 0.00% |

## Per scenario

| Scenario | Faults | Incidents | Alert ticks | Expected | Detected | Latency | Location | Smoke |
| --- | --- | ---: | ---: | --- | --- | ---: | --- | --- |
| normal | none | 0 | 0 | — | — | — | — | — |
| holiday | none | 0 | 0 | — | — | — | — | — |
| heatwave | none | 0 | 0 | — | — | — | — | — |
| leak_gradual | declared | 1 | 397 | leak | yes | 195 min | pipe:PIPE_17 → pipe:PIPE_11 | top-1 False, top-3 False |
| leak_sudden | declared | 1 | 432 | leak | yes | 5 min | pipe:PIPE_17 → pipe:PIPE_11 | top-1 False, top-3 False |
| sensor_drift | declared | 1 | 435 | sensor_fault | yes | 90 min | P05 → P05 | quality coverage 100% |
| sensor_stuck | declared | 1 | 69 | sensor_fault | yes | 25 min | P02 → P02 | quality coverage 100% |
| pump_outage | declared | 1 | 298 | pump_issue | yes | 5 min | PUMP_1 → PUMP_1 | — |
| leak_plus_sensor_drift | declared | 2 | 434 | sensor_fault | yes | 110 min | P05 → P05 | quality coverage 100% |

## Data quality

| Scenario | Faulted sensor | Window ticks | Flagged | Bad | Suspect |
| --- | --- | ---: | ---: | ---: | ---: |
| normal | — | 0 | 0 | 0 | 0 |
| holiday | — | 0 | 0 | 0 | 0 |
| heatwave | — | 0 | 0 | 0 | 0 |
| leak_gradual | — | 0 | 0 | 0 | 0 |
| leak_sudden | — | 0 | 0 | 0 | 0 |
| sensor_drift | P05 | 457 | 457 | 0 | 440 |
| sensor_stuck | P02 | 73 | 73 | 67 | 0 |
| pump_outage | — | 0 | 0 | 0 | 0 |
| leak_plus_sensor_drift | P05 | 457 | 457 | 0 | 438 |

## Cost/decision sanity check

| Scenario | Recommended | Mean costs (CU) | Savings vs monitor | Constraints |
| --- | --- | --- | ---: | --- |
| leak_gradual | repair_isolate | monitor: 29,716, inspect: 11,849, repair_isolate: 10,436 | 19,280 | ok |
| leak_sudden | repair_isolate | monitor: 37,100, inspect: 11,990, repair_isolate: 10,603 | 26,497 | ok |

## Determinism

- First hash: `2669e0433d6f791bdb558666c5ba7948013b771696e4a8bbb3c5607436fc737c`
- Second hash: `2669e0433d6f791bdb558666c5ba7948013b771696e4a8bbb3c5607436fc737c`
- Identical: **True**

## What this evaluation does not prove

- It does not validate the detector against real utility data or real leak events.
- The synthetic fault set is small and authored by the same person as the detector.
- Localisation is scored against a deliberately chosen synthetic pipe, not a field repair record.
- No probability calibration is claimed; the decision engine reports break-even thresholds instead.

