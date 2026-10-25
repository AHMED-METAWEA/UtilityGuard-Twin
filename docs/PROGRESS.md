# PROGRESS
Current phase: A0 (inventory and reuse decisions written; PR #2 awaiting the owner's merge; A1 not started)
Last session: 2026-10-25 (lead agent Claude Code)

Done:
- Repository bootstrapped and baseline published (T-A0-001): `main` and `dev` at `debfd51`, tag `baseline-freebuf`, `freebuff/` imported unmodified (79 files). PR #1 (setup docs, two-agent protocol) merged into `dev`.
- **Stance changed (D-001):** `freebuff/` is a reference only; the target is the Master Spec built fresh; reuse is selective and logged. Revised phases: A0 = short inventory and reuse decisions; A1 = foundation (Spec M0) built fresh; A2 retired; reused pieces ported inside B1. `platform/` is not a Python package (D-003).
- A0 deliverables written: `docs/audit/INVENTORY.md` (short), `PITFALLS.md` (19 pitfalls, lead-reproduced or Codex-only, plus pilot P1 result), `DECISIONS.md` (D-001 to D-005, empty reuse log), Codex evidence (`codex_audit_raw.md`, `codex_inventory_raw.md`, `docs/progress/codex.md`).
- Plan documents updated for the new stance: `docs/ADOPTION_PLAN.md` v2.0, `AGENTS.md`, `CLAUDE.md`, `docs/COLLABORATION.md` v1.1, `docs/COLLAB_PLAN.md` v2 (13 foundation cards T-A1-001..013), notice on superseded prompts in `docs/prompts/PROMPTS.md`.
- Public repository hygiene scan over every ref and blob: clean (D-004).
- Codex verified earlier (codex-cli 0.164.0, plugin 1.0.6, review gate off); `/codex:rescue` behavior recorded in `docs/progress/claude-code.md`.

Next:
1. Owner reviews and merges PR #2 (reference-baseline stance, A0 deliverables), then PR #3 (Spec: F1 definition) and the records PR that carries this update.
2. After PR #2 is merged: the lead creates the local tag `phase-A0` on the merge commit on `dev` and asks before pushing it (owner rule, D-008).
3. Phase A1 does not start until the owner says go. The A1 plan (13 foundation cards, parallel lanes with Codex, merge waves) is printed in the session and in `docs/COLLAB_PLAN.md` section 4.

Blockers / human actions pending:
- Merge PR #2, PR #3 and the records PR; say "go" for A1.
- Set branch protection on `dev` and `main` (owner action; not set at last check).
- One-line answer: add `PUBLIC_GEOMETRY` to Master Spec section 2 (the Spec lists eight evidence labels, `AGENTS.md` nine). Recommended yes.
- Optional: GitHub "keep my email private" setting (COLLAB_PLAN Q4); delete the stale scratch-repo trust entry in `~/.codex/config.toml`.

Decisions since last session: D-001 to D-008 in `docs/audit/DECISIONS.md`: owner ruling on F1 (real public layout), English-only naming with Arabic as a later UI translation, A1 dependency list approved (type generator pinned to `json-schema-to-typescript@16.0.0`), and the owner merges all PRs and pushes tags. Default Codex reasoning effort stays `medium`.

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6.

Spend so far: 1 long lead session (setup, bootstrap, measurements, stance change); Codex: 6 small runs (config key check, rescue write test, read-only control, project-config banner check, inventory run, independent audit run).
