# ADR-010: Piecewise gradual-fault simulation and its error bounds

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 5.3, risk table (WNTR limits).

## Position taken in the Master Spec
- Gradual faults are simulated piecewise. The run is divided into chunks (default 30 minutes), fault parameters are updated per chunk, and tank levels and pump states are handed off between chunks.
- A convergence test compares chunk sizes, and the approximation error is reported in `docs/approximations.md`. The approach is a documented approximation, not exact physics.

## Where it is built
Spec milestone M1 (piecewise gradual faults, chunk-size convergence report); `ug_water.wntr_api` (T-A1-008) pins the WNTR calls it will use.

## To settle when this ADR is completed
- How the error bound is computed and what tolerance counts as converged.
- Which WNTR features are used for leaks and pump states, verified against the installed version before use.
