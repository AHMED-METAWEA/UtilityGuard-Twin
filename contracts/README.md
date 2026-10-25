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
| `common.schema.json` | Shared definitions: labels, identifiers, timestamps, quality | 2 |

## Rules baked into the schemas
- **Closed objects.** `additionalProperties: false` (or `unevaluatedProperties: false`) everywhere. A test fails if an object is open by omission.
- **No truth in telemetry.** `telemetry-reading` and `stream-envelope` have no truth, fault-tag or hidden field, and a test fails if one is ever declared (pitfalls P-01, P-02). Hidden fault tags live in the truth bundle only (Spec 11.2).
- **Stream source.** Every `tick` requires `stream_source` in `REPLAY|SIMULATED|LIVE` (P-04).
- **Labels.** Every displayable number carries a `label` from the nine evidence labels. Telemetry readings may only be `SENSOR_SIM`, `OBSERVED` or `BENCHMARK`.
- **Keys are data too.** Names in operator-visible maps (detector ids, residual names) may not name truth, hidden state, injected faults, probabilities or percent confidence (`operator_visible_key`), so they cannot ride in as keys.
- **Derived numbers name their derivation.** A data-quality score is `CALCULATED` and names its formula (`formula_ref`); so does the network confidence index; a detector output is `MODEL` and carries the detector `version`.
- **Evidence.** `INSUFFICIENT_EVIDENCE` if and only if the value is `null` (and then a `reason` is given); `CALCULATED` needs a formula and at least one input; a cost (`kind: cost`) is `CALCULATED` or `INSUFFICIENT_EVIDENCE`; an amount (`EGP`, `EGP/year`, `EGP/month`, `EGP/day`) is never `SIMULATION`, `MODEL`, `SENSOR_SIM` or `PUBLIC_GEOMETRY` (P-14); any unit that looks like a currency must be spelled exactly `EGP` or `EGP/<m3|kWh|MWh|kW|h|day|month|year>`; an input of a calculation is never `INSUFFICIENT_EVIDENCE`.
- **No invented probabilities.** No `probability` or percent-confidence field exists, except the dropout fault's `probability`, which is an input of the scenario, not a claim about the world. Incidents carry a rule-based `support` strength.
- **Faults.** `type` must be one of the 14 catalogue types (an unknown type is rejected, P-18); each type has its own required parameters.

## Tests that guard the schemas
`platform/tests/contract/` holds three kinds: structure and rejected-for-the-right-reason tests (`test_contracts.py`), regression tests for holes found in review (`test_contract_hardening.py`), and a type-flip fuzz (`test_contract_fuzz.py`) that swaps every value of every example for a value of another type and fails if the schema starts accepting something that is not on a reviewed allowlist. Schema mutations that no test notices are treated as test bugs.

## What a schema cannot check
JSON Schema checks shape and ranges. These need code and are checked elsewhere: that a fault refers to an element that exists and fits the horizon (scenario validation against a network), that `min <= mode <= max` in an assumption (the loader), and that a verified assumption names a real source (a human review). JSON has no `NaN` or infinity: the tests load every file with a strict parser that rejects them.

## Changing a contract
1. Open a task card and get the owner's sign-off.
2. A change that old payloads would not survive is a new version directory (`v2/`), never an edit of `v1/`.
3. Add a valid example and an invalid file for it; regenerate the TypeScript types (T-A1-007).
4. Run `make test-contracts`.
