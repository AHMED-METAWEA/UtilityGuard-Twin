# PITFALLS: what the reference baseline got wrong, and ideas worth keeping

Status: Phase A0 deliverable (2026-10-25), for human review. Source: lead measurements on the unmodified baseline (tag `baseline-freebuf`, `debfd51`), Python 3.11.7, with the dependency versions the baseline shipped with (WNTR 1.5.0, numpy 2.4.6, pandas 3.1.0), plus the independent Codex read-only audit (`codex_audit_raw.md`, same folder). The measuring scripts were run from a scratch folder and are not committed; each row names the command or file and line so it can be redone. `freebuff/` is a REFERENCE: nothing here is a to-do against it. It is a list of ideas worth keeping and traps the new system must be built to avoid, and each trap gets a test in Phase A1 or in the B-phase that builds the affected part.
Every row is labelled **L** (reproduced by the lead, command in the evidence column) or **C** (reported by Codex only, not reproduced). Severity is provisional (Adoption Plan section 4 scale), meaning "how bad this would be in the new system".

## 1. Baseline facts (measured)
- 34 tests, all pass (2 min 29 s). 9 presets. About 5.6k lines of Python; network of about 40 junctions; one duty pump plus a standby; one tank.
- Determinism: the SHA-256 of truth, baseline and readings is identical for all 9 presets across two separate processes (same machine). Not tested across machines.
- Runtime: 3.3 to 7.8 s for a 48 h scenario. 7-day normal run: 11.4 s; tank 1.94 to 7.19 m of 1.0 to 7.5 m, drifting +0.04 m/day.
- Mass balance with a forward-difference storage term: median 0.005 %, max 0.05 % on the fault-free run (WNTR conserves mass).
- Leak orifice law `Cd*A*sqrt(2gh)`: 0.00 % error against the solver at 4 ticks.
- 43 WNTR symbols the code uses all exist with matching signatures in 1.5.0 (`Junction.add_leak(wn, area, discharge_coeff=0.75, start_time=None, end_time=None)`; `demand_model='PDD'` reads back as `'PDA'`).
- Its own `eval_report.md` agrees with every number I measured (latencies, alert ticks) and honestly reports leak localization 0/2 top-1 and 0/2 top-3.

## 2. Ideas worth keeping (candidates, each needs review at time of use and a line in DECISIONS.md)
1. Whole scenario simulated once, stream replays stored series, WNTR never in the stream loop (matches Spec 4.5).
2. Leak by splitting the pipe at its midpoint and attaching `add_leak` to the new junction; orifice law verified (section 1). Reuse the idea or the function after review.
3. Sensor layer behaviours: dropout gives `None` (not zero); stuck holds the first stuck value; drift is additive. Needs per-sensor RNG streams (see P-12).
4. Cost lines: one quantity x one unit price, with formula, unit and label per line; triangular Monte Carlo with fixed seed; closed-form break-even stated as a threshold, "not an estimated probability"; sensitivity with bisection for the flip value; advisory and "conditional on assumptions" wording. Good shape, to be rebuilt on the Spec's design grid.
5. Quality-check family (stuck window, rate spike, neighbour drift, tank mass balance over a window) and rule-based diagnosis that returns `unknown` and uses `weak/moderate/strong`, never a percent.
6. Canonical-JSON run hash with values rounded to 6 digits.
7. Honest copy: banner text, `disclaimer` fields, `labels` dict per payload, notes that results are on simulated faults.

## 3. Pitfalls the new system must be built to avoid
| ID | Sev | Pitfall | Evidence |
|---|---|---|---|
| P-01 | S0 | Truth reaches the decision path: when the F02 sensor reading is missing, the leak-size estimate uses twin truth. Corrupting truth changes the estimate (7.695 vs 0.400 cm2) only when F02 is missing. Continuations start from the true tank level. | L: `impact/runner.py:55-67,222`; counterfactual script. C-6.5-01 |
| P-02 | S0 | Hidden injected fault types, locations and timing are visible in the default operator tab, bypassing the truth toggle. | C-6.3-04 (frontend not audited by the lead) |
| P-03 | S1 | Truth object passed whole into the detector-side quality layer; only the time axis is read today, but nothing prevents more. Interface should carry a timebase, not truth. | L: `analysis.py:18`, `quality/checks.py:81,177` |
| P-04 | S0 | Truth endpoint `/api/runs/{id}/truth` is open to any caller (no role, no audit); stream frames carry no `stream_source` or `schema_version`. | L: `main.py:265`, `_frame` |
| P-05 | S0 | Every physical fault starts one tick (5 min) late (leak 144 -> 145; pump trip 216 -> 217; restore 264 -> 265) while sensor faults are exact: chunk row 0 is discarded, so the boundary tick keeps the pre-fault state. Detection-delay metrics inherit this. | L: onset script; `runner.py:157-174,406-410` |
| P-06 | S0 | A valid short gradual ramp (0.5 h) produces no leak; a second leak is silently dropped; two lists with the same canonical manifest run different leaks. | L: verify script. C-6.2-04, C-6.2-11 |
| P-07 | S0 | `switch_standby_pump` closes both pumps, so its cost is 174,812 vs 35,254 for monitor. | L: `impact/runner.py:138-147`; decision run. C-6.2-07 |
| P-08 | S1 | Detector expectation is the exact fault-free twin run told the holiday and heatwave settings, scaled by sensor noise only (no model-error term). Zero false alarms on normal, holiday, heatwave over 5 seeds (0/15 cells) is true by construction. With a 1 % demand-forecast error: 7 false "leak" incidents; 2 to 25 %: leak incidents every time. | L: false-alarm and forecast-error scripts |
| P-09 | S1 | Leak localization never hits: top-1 0/2 and top-3 0/2, yet the incident says `strength=strong`, `severity=high`; the impact simulation then puts the leak on the wrong pipe (PIPE_11 vs true PIPE_17; PIPE_47 in the leak-plus-drift case). | L: candidates script; baseline `eval_report.md` |
| P-10 | S1 | One root cause fragments into several incidents (a 1.0 cm2 leak gave 4, 0.5 cm2 gave 5). | L: decision script |
| P-11 | S1 | Decision output hardly depends on leak size: 0.5, 1.0 and 6.0 cm2 give monitor about 30k to 31k and repair about 10.2k to 10.3k; "monitor" always carries an emergency repair, so it cannot win and negative net benefit is not realised in practice. A sensor fault is charged a pipe repair. | L: decision script |
| P-12 | S2 | Sensor noise comes from one shared random stream, and dropout draws extra numbers only inside the fault window, so configuring one fault changes the noise of every other sensor. | L: `runner.py:473-515` read |
| P-13 | S1 | Editable assumption `intervention_effectiveness` (0.90) has zero references in code; isolation uses a hard-coded 0.2. Monte Carlo samples only 6 price ranges, not timing or effectiveness. Equal weights over leak-size variants are an undeclared probability assumption. No `verified` flag. | L: grep; `finance/engine.py:189,217,230`; `impact/runner.py:247` |
| P-14 | S2 | Money lines labelled `SIMULATION` although they multiply by an assumed price (should be CALCULATED with ASSUMPTION inputs). | L: `finance/engine.py:157-177`. C-6.5-12/13 |
| P-15 | S2 | The network is under-built for its own scenarios: pump flow saturates at 79 L/s and the tank starves in the no-fault heatwave (13 % of ticks), pump outage (7 %), sudden leak (11 %); reported flows stop balancing in that regime. | L: starvation and mass-balance scripts |
| P-16 | S2 | Gradual leak is a staircase by hourly chunks: volume 893 m3 vs 911 m3 at 5-minute chunks (-1.9 %); no convergence report. | L: convergence script |
| P-17 | S0 | NaN and infinities are silently converted to 0.0 by `_round`; missing analysis shown as healthy/normal; Fidelity and stream-source indicators absent. | C-6.2-12, C-6.4-06, C-6.6-06. L: `_round` read (`runner.py:133`) |
| P-18 | S2 | Unknown `sensor_id`/`pump_id` accepted by the schema and silently inert; no `schema_version`; valve ids pass pattern validation and fail at run time; hard-coded diagnosis thresholds; pump issue always names `PUMP_1`. | L: `schema.py`, `diagnose.py` read |
| P-19 | S3 | Installed venv relocation left stale shebangs (`pip` script points to an old path); unpinned dependencies (`>=`). | L |

## 4. Pilot P1 data (two independent audits of the same baseline)
- Found by both: truth/hidden data reaching decisions (P-01), missing evidence labels and mislabelled money lines, missing honesty indicators.
- Found only by the lead (all measured): P-05, P-08, P-09, P-10, P-11, P-12, P-13, P-15, P-16.
- Found only by Codex (static reading, no execution): P-02, P-06 (2 of 3 sub-claims), P-07, P-17 NaN-to-zero and missing-analysis-as-normal. Spot-check by the lead: 3 of 3 sampled Codex claims reproduced (P-06 ramp, P-06 ordering, P-07).
- Reading: neither audit alone was enough; each caught what the other missed. The union is the useful result, and it cost far less than a line-by-line review of code we may not keep.
