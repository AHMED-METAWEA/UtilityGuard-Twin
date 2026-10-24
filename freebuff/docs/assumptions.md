# Assumptions and thresholds

Everything in this table is either an explicit assumption or a documented rule threshold. None of it is measured field data. Prices live in `backend/app/finance/assumptions.yaml` and are editable from the UI (`PUT /api/assumptions`); the other values are in `backend/app/config.py`.

## Prices and operational assumptions (CU = placeholder currency units)

| Key | Value | Range used for sampling | Unit |
| --- | ---: | --- | --- |
| `water_price_per_m3` | 1.20 | 0.40 – 4.00 | CU/m³ |
| `unserved_water_penalty_per_m3` | 8.00 | 2.00 – 30.00 | CU/m³ |
| `electricity_price_per_kwh` | 0.25 | 0.08 – 0.60 | CU/kWh |
| `inspection_cost` | 900 | 300 – 3000 | CU/inspection |
| `repair_cost_planned` | 6000 | 2000 – 20000 | CU/repair |
| `repair_cost_emergency` | 18000 | 6000 – 60000 | CU/repair |
| `crew_response_hours` | 3.0 | 0.5 – 12.0 | h |
| `repair_duration_hours` | 6.0 | 1.0 – 24.0 | h |
| `inspection_duration_hours` | 1.0 | 0.25 – 4.0 | h |
| `intervention_effectiveness` | 0.90 | 0.60 – 1.00 | fraction |
| `low_pressure_threshold_m` | 15.0 | 5.0 – 25.0 | m |
| `max_unserved_m3` | 150 | 0 – 1000 | m³ per horizon |
| `decision_horizon_hours` | 72 | 6 – 72 | h |
| `monte_carlo_samples` | 300 | 100 – 1000 | samples |

Currency is deliberately abstract. The values are obvious placeholders and must not be presented as tariffs or contractor quotes.

## Network assumptions

- Reservoir base head 8 m; tank elevation 66 m, initial level 4 m, diameter 14 m, min/max level 1.0/7.5 m.
- PRV setting 35 m at the tank outlet; PDD required pressure 20 m, exponent 0.5.
- Zone peak demands (L/s): gov 10, com 22, res 26, shaped by stated hourly curves.
- PIPE_17 is a smaller local distributor (DN80) by design; all other grid pipes are DN150. Three edges are TCV isolation valves.
- Sensor noise (1σ): pressure 0.12 m, flow 0.8 L/s (0.6 for F03), tank level 0.01 m.
- Pump efficiency for energy: 75%; leak discharge coefficient 0.75.

## Quality layer

| Check | Rule | Effect |
| --- | --- | --- |
| `missing` | `null` reading | bad, score 0 |
| `out_of_range` | outside stated physical range | bad |
| `stuck` | range ≤ ε over 6 ticks (pressure 0.01 m, flow 0.05 L/s, level 0.002 m) | suspect, then `stuck_persistent` after 12 ticks → bad |
| `rate_spike` | > 3 m, 12 L/s or 0.15 m per 5 min | suspect |
| `drift_vs_neighbors` | local pressure residual > 3.5σ from neighbour median **and** |z| ≥ 2σ | suspect |
| `deviation_from_baseline` | |z| > 3σ | small penalty |
| `mass_balance` | 30-min tank level change differs from F01−F02 by > max(0.04 m, 35%) | suspect |

Scores start at 1.0 and subtract fixed penalties; ≥ 0.8 is `ok`, 0.45–0.8 is `suspect`, below 0.45 is `bad`. The score is a transparent rule output, not a probability.

## Detector

| Parameter | Value | Meaning |
| --- | ---: | --- |
| `watch_threshold` | 2.5σ | deviation worth watching |
| `alert_threshold` | 4.0σ | deviation worth alerting |
| `persistence_ticks` | 3 | consecutive ticks above watch before alert |
| `cusum_drift` | 0.75σ | CUSUM slack |
| `cusum_threshold` | 15σ | CUSUM alarm (must be corroborated by a current ≥2.5σ deviation) |
| `cluster_distance_m` | 220 | pressure sensors considered nearby |
| `leak_min_sensors` | 2 | minimum clustered pressure sensors for a leak |
| `group_window_ticks` | 12 | incident merge window (1 h) |

Degraded sensors are down-weighted in detection (0.5× for suspect, 0.25× for bad) but a bad reading can still trigger a sensor-integrity finding (stuck/out-of-range).

## Decision options

| Diagnosis | Options |
| --- | --- |
| leak | monitor, inspect then repair, isolate and repair now |
| pump issue | monitor, inspect, switch standby pump |
| sensor fault | monitor, inspect |
| demand change | monitor |
| unknown | monitor, inspect |

Impacts are WNTR continuations from the incident tick for the decision horizon. Leak-size low/mid/high variants are 0.5×/1×/2× of the model-estimated area. Isolation reduces the leak to 20% until repair completes. Costs are summed over variants with equal weights; Monte Carlo samples triangular price ranges and leak variants.

## Break-even

```
p* = (action_cost_absent − monitor_cost_absent)
     / [(monitor_cost_present − monitor_cost_absent) − (action_cost_present − action_cost_absent)]
```

If the denominator is non-positive, the action never pays off in this model and no threshold is shown. A repair is charged its planned cost even when no fault is present; otherwise repairing would look free in the no-fault state and the threshold would collapse to zero.
