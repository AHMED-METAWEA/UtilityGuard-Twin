# contracts/

Versioned JSON Schemas for data that crosses module boundaries (Master Spec principle P3: contracts before code). Created in task T-A1-002. **A contract change needs the lead agent and the owner, and the generated TypeScript types must be regenerated.**

## Layout
- `v1/`: the schemas (JSON Schema draft 2020-12). Every payload requires `"schema_version": "1"`. `$id` values are identifiers only (the host `utilityguard.invalid` never resolves); nothing is fetched at run time.
- `examples/<schema>/`: valid payloads. Every file must validate.
- `invalid/<schema>/`: one file per rejection reason, named after the reason. Every file must be rejected, and `platform/tests/contract/test_contracts.py` checks it is rejected **for that reason** and no other.

## Schemas
| File | Payload | Spec |
|---|---|---|
| `scenario-config.schema.json` | Scenario configuration with the fault catalogue | 12.3, 5.4 |
| `run-manifest.schema.json` | Everything needed to reproduce a run (the shape of `ug_core.Manifest.to_dict()`) | 10.4 |
| `telemetry-reading.schema.json` | One sensor reading at one tick | 11.2, 12.2 |
| `stream-envelope.schema.json` | WebSocket frame; version 1 specifies `tick` | 12.2 |
| `evidence-record.schema.json` | A displayed number with its label, formula and inputs | 10.1 |
| `assumption-set.schema.json` | A versioned set of assumptions | 11.1, Appendix A |
| `incident.schema.json` | An incident with hypothesis, support and location | 8, 11.1 |
| `network-view.schema.json` | The network as the map draws it: structure and geometry in local metres, no state, no fault | 13, DEMO_PLAN D-01 |
| `time-series.schema.json` | A plotted series (sensor, expectation, residual, forecast); never SIMULATION, so truth cannot travel in it | 12.2, DEMO_PLAN D-01 |
| `decision-comparison.schema.json` | Options compared by expected cost, worst case (p90), regret and break-even; advisory; every number an evidence record | 9.4, DEMO_PLAN D-01 |
| `whatif-request.schema.json` | Operator sensor what-if (disable, stuck, drift): telemetry only | DEMO_PLAN D-01 |
| `common.schema.json` | Shared definitions: labels, identifiers, timestamps, quality | 2 |

## Rules baked into the schemas
- **Closed objects.** `additionalProperties: false` (or `unevaluatedProperties: false`) everywhere. A test fails if an object is open by omission.
- **No truth in telemetry.** `telemetry-reading` and `stream-envelope` have no truth, fault-tag or hidden field, and a test fails if one is ever declared (pitfalls P-01, P-02). Hidden fault tags live in the truth bundle only (Spec 11.2).
- **Stream source.** Every `tick` requires `stream_source` in `REPLAY|SIMULATED|LIVE` (P-04).
- **Labels.** Every displayable number carries a `label` from the nine evidence labels. Telemetry readings may only be `SENSOR_SIM`, `OBSERVED` or `BENCHMARK`.
- **Keys are data too.** Names in operator-visible maps follow a closed grammar: residual names are upper-case sensor tokens (`P05`, `SPE`), detector ids are lower-case (`d2`), versions are `<name>_v<number>` (`d2_v1`), formula and template ids end in `.v<number>`. Words that name truth, hidden state, injected faults, probabilities or percent confidence are refused inside them. This is a grammar plus a word list, not proof: code checks the names against the sensors of the run.
- **Units are one ASCII token** (`m`, `L/s`, `kWh`, `EGP/m3`): no spaces and no letters outside A-Z and a-z, so look-alike letters cannot disguise a currency.
- **Derived numbers name their derivation.** A data-quality score is `CALCULATED` and names its formula (`formula_ref`); so does the network confidence index; a detector output is `MODEL` and carries the detector `version`.
- **Evidence.** `INSUFFICIENT_EVIDENCE` if and only if the value is `null` (and then a `reason` is given); an input of a calculation is never `INSUFFICIENT_EVIDENCE`; `CALCULATED` needs a formula and at least one input.
- **Money** (the record and each of its inputs): a unit that looks like a currency must be spelled exactly `EGP` or `EGP/<m3|kWh|MWh|kW|h|day|month|year>`; money is never `SIMULATION`, `MODEL`, `SENSOR_SIM` or `PUBLIC_GEOMETRY` (P-14); a money value is a JSON number, never formatted text; a cost (`kind: cost`) is an amount in `EGP` and is `CALCULATED` (or `INSUFFICIENT_EVIDENCE`). The currency recogniser lists common codes and words; a currency it does not list is caught by the evidence kernel in code, the second line of defence.
- **A sensor reports a physical quantity** (`telemetry-reading`, and the readings of a `tick` frame): the `unit` is `common.schema.json#/$defs/physical_unit`, one ASCII token built only from the known physical units, so money, however it is spelled, can never be labelled as sensor output. The list of units is `ug_core.grammar.PHYSICAL_UNIT_ATOMS`; a new physical unit is added there and the pattern is regenerated (a test keeps them equal). The same holds for an evidence record (and each of its inputs) labelled `SIMULATION`, `MODEL`, `SENSOR_SIM` or `PUBLIC_GEOMETRY`: its unit, when present, is a `physical_unit`. `INSUFFICIENT_EVIDENCE` carries no `value` and no `uncertainty` estimate.
- **No invented probabilities.** No `probability` or percent-confidence field exists, except the dropout fault's `probability`, which is an input of the scenario, not a claim about the world. Incidents carry a rule-based `support` strength.
- **Faults.** `type` must be one of the 14 catalogue types (an unknown type is rejected, P-18); each type has its own required parameters.

## Tests that guard the schemas
`platform/tests/contract/` holds three kinds: structure and rejected-for-the-right-reason tests (`test_contracts.py`), regression tests for holes found in review (`test_contract_hardening.py`), and a type-flip fuzz (`test_contract_fuzz.py`) that swaps every value of every example for a value of another type and fails if the schema starts accepting something that is not on a reviewed allowlist. Schema mutations that no test notices are treated as test bugs.

## What a schema cannot check
JSON Schema checks shape and ranges. These need code and are checked elsewhere: that a fault refers to an element that exists and fits the horizon (scenario validation against a network), that `min <= mode <= max` in an assumption (the loader), and that a verified assumption names a real source (a human review). JSON has no `NaN` or infinity: the tests load every file with a strict parser that rejects them.

## Changing a contract
1. Open a task card and get the owner's sign-off.
2. A change that old payloads would not survive is a new version directory (`v2/`), never an edit of `v1/`. (Exception, A1 gate round 1, T-A1-013: the sensor-unit and `INSUFFICIENT_EVIDENCE` rules above tighten `v1` in place, because no `v1` payload is produced, stored or exchanged yet; the owner approves this exception by merging that change.)
3. Add a valid example and an invalid file for it; regenerate the TypeScript types (T-A1-007).
4. Run `make test-contracts`.
