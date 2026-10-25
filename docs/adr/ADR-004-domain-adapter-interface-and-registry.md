# ADR-004: Domain adapter interface and registry

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 4.6, 14; principle P4.

## Position taken in the Master Spec
- Water, electricity and cooling implement one `DomainAdapter` interface. The core never imports domain code.
- Adapters register through an entry-point registry (group `ug.domains`). Each adapter must pass the conformance suite in `platform/tests/conformance/` before it can be enabled.

## Where it is built
T-A1-005 (interface, `AdapterBase`, `ug_core.registry.discover`, conformance suite, `scripts/check_imports.py`). The optional `HasHealthChecks` hook for `ug doctor` is an addition to the Spec interface, kept outside `DomainAdapter` so plain adapters still conform.

## To settle when this ADR is completed
- The members of each component protocol (they are marker types until their milestone).
- Cross-domain effects through the `InterdependencyGraph` (Spec 4.6): explicit scenario inputs labelled `SIMULATION`, never imports.
