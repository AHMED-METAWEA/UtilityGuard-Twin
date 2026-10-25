# ADR-003: Design-grid interpolation for Monte Carlo

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 4.5 (second key decision), 9.

## Position taken in the Master Spec
- Monte Carlo cost analysis must not re-run the hydraulic solver for each sample.
- Hydraulic outcomes come from a small design-of-experiments grid (delay, leak size, action) computed once per incident. Samples vary the economic assumptions and interpolate the hydraulic outcomes across the grid.
- Results are "model-estimated, conditional on assumptions"; negative net benefit must be representable.

## Where it is built
Spec milestone M4 (design grid runner, cost engine, sampling and sensitivity).

## To settle when this ADR is completed
- Grid resolution and interpolation method, and how the interpolation error is bounded and reported.
- How a recommendation always carries its sensitivity analysis.
