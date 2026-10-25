# ADR-009: Fidelity ladder and labeling

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 1.4, 2, 5.1; `docs/audit/DECISIONS.md` D-005.

## Position taken in the Master Spec
- Four levels: F0 generic synthetic (fallback for tests), F1 public layout with synthetic hydraulics (what is built now), F2 calibrated with ACUD data, F3 live-synced.
- A permanent Fidelity badge states the level of the network actually loaded and never claims a higher level. F1 is not ACUD's network and not a survey of it.
- Public geometry is labelled `PUBLIC_GEOMETRY` and carries provenance; inferred pipe routes, sizes, demands and equipment are `ASSUMPTION`.

## Where it is built
T-A1-010 (badge in the shell), T-A1-003 (`PUBLIC_GEOMETRY` in `EvidenceLabel`); the F1 provider in Phase B1.

## To settle when this ADR is completed
- The geometry feasibility test and the choice of public sources (Phase B1).
- What data swap and re-calibration take the twin from F1 to F2.
