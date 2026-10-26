# ADR-001: Truth versus telemetry separation

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 4.1 (P1), 11.2, 7; AGENTS.md Honesty Rules.

## Position taken in the Master Spec
- The twin holds physical truth. Sensors produce telemetry derived from truth plus error. Detectors only ever see telemetry (P1).
- Truth is exposed only to the evaluation harness and the optional "twin truth" toggle in the UI. The stream, the quality checks, the detectors and the operator view never receive truth or hidden fault tags.
- Truth is stored apart from telemetry; hidden fault tags exist only in the truth file (11.2).

## Where it is built
T-A1-003 (`TruthSeries` and `TelemetrySeries` as unrelated types, `MeasurementPort`), T-A1-002 (telemetry and stream schemas have no truth or fault-tag field), T-A1-004 (honesty tests).

## To settle when this ADR is completed
- How the "twin truth" toggle is gated so that it cannot reach a recorded export.
- Which modules may import `ug_core.truth` (today: measurement models and the evaluation harness) and how that list is enforced.
