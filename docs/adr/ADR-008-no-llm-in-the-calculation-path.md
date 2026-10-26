# ADR-008: No LLM in the calculation path

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: AGENTS.md Honesty Rules; Master Spec 10.3, 4.7.

## Position taken in the Master Spec
- No language model is used in any calculation path. Explanations come from fixed templates over structured evidence.
- SHAP is allowed for model attribution only and is never presented as a physical root cause.

## Where it is built
The rule is stated in `AGENTS.md`; the honesty tests of T-A1-004 are where it becomes checkable.

## To settle when this ADR is completed
- How the rule is checked mechanically (for example a test that no module on a calculation path imports a language-model client).
- Where a language model may be used at all (development tooling, outside the calculation path).
