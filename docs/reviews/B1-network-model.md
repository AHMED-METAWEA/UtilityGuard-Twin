# Review log: the water network model (B1, prerequisite of T-B1-011 and T-B1-013)

Author: Claude Code (lead). Reviewer: Codex (`review`, read-only, 2026-10-26). Tier: T1.

| Round | Severity | Finding | Decision | Fixed in |
|---|---|---|---|---|
| 1 | S2 | F1 provenance accepted `topology = PUBLIC_GEOMETRY`, and the test fixture used it: inferred pipe connections would carry the label of public geometry, although only the street geometry is public (AGENTS.md, T-B1-013). | Accepted, reproduced with a failing test. `topology` is always `ASSUMPTION`; `coordinates` keep `PUBLIC_GEOMETRY` for F1. | this PR, second commit |
| 1 | S2 | A one-point pump curve with zero flow constructed, but WNTR's `HeadPump.get_head_curve_coefficients()` divides by `Q[0]**2` for one-point curves. | Accepted, reproduced with a failing test; WNTR's source read (one point: Q > 0 needed; two points: distinct flows; three or more: `log(Q[1]/Q[-1])`, already safe under the increasing-flow rule). A one-point curve now needs a positive flow; a zero-flow shut-off point stays allowed in multi-point curves. | this PR, second commit |

The fixes were not reviewed a second time (T1).
