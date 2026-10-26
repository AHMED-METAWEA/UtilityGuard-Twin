# B1 Wave 2: state at the usage-limit stop (2026-10-26)

**Waiting for the owner (Tier 2, all green, reviews logged):** #45 T-B1-010 (plus the G2 ruling: may docs hold aggregate OSM numbers?), #47 T-B1-020 run store (adds D1 deps), #49 T-B1-016 hydraulics (2 rounds done), #50 T-B1-012 demand (adds assumptions/demand_v1.yaml). Also the overlay ruling for T-B1-013 (options A, B, C). Merged this wave by the lead under D-018 with the safety net: #46 records, #48 T-B1-011b PRV fix, #51 T-B1-019 presets.

**Branches not yet in a PR:**
- `codex/b1-ug-run` (T-B1-021 `ug run`, Codex + lead fixes, green, local only): an integration of #47, #49, #50, #51 plus the card. Next: after those merge, merge `dev` into it, review the diff (lead mutation run), open the PR (Tier 1).
- `claude/b1-osm-provider` (T-B1-013 part 1, pushed): see `T-B1-013.md`.
- `codex/b1-validation` (T-B1-014, Codex run `butxpcb6z` was still running at the stop; nothing committed): next, read `scratchpad/codex-b1-014-last.md`, commit Codex's work, review, decide on tuning the procedural network if it fails validation.

**Codex tokens (from the `codex exec` logs):** Wave 1 152,478. Wave 2: T-B1-012 81,234; T-B1-020 90,062; T-B1-011b 64,976; T-B1-020 fix 68,408; T-B1-012 fix 125,892; T-B1-019 50,524; T-B1-021 89,702 = 570,798 (T-B1-014 not counted yet). Total 723,276. Plugin reviews report no tokens.

**Resume first:** the T-B1-014 result; then the owner's merges and rulings; then T-B1-021's PR; then T-B1-013 part 2; then T-B1-017 (faults) and T-B1-018 (chunking). Record this state in `docs/PROGRESS.md` in the next records PR.
