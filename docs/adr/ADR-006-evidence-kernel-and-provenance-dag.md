# ADR-006: Evidence kernel and provenance DAG

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 10, principle P5; AGENTS.md Honesty Rules.

## Position taken in the Master Spec
- Every derived value is created together with its provenance record; evidence is not reconstructed later.
- An evidence record carries value, unit, one of nine labels, formula, inputs and provenance (10.1). The provenance graph is a directed acyclic graph; a result shows a weakest-link marker when any upstream node is an `ASSUMPTION` (10.2).
- Explanations come from fixed, reviewed, versioned templates (10.3).

## Where it is built
T-A1-003 (`EvidenceLabel`, `Evidenced`), T-A1-002 (evidence record schema), T-A1-012 (assumption ids of the form `as_<name>@<set>`); the kernel itself in Spec milestone M4.

## To settle when this ADR is completed
- Where evidence records are stored and how the provenance DAG is queried by the Evidence Explorer.
- The complete evidence id scheme beyond assumptions.
