# PROGRESS
Current phase: A0 (inventory and reuse decisions written; awaiting human review of PR `claude/a0-reference-stance`)
Last session: 2026-10-25 (lead agent Claude Code)

Done:
- Repository bootstrapped and baseline published (T-A0-001): `main` and `dev` at `debfd51`, tag `baseline-freebuf`, `freebuff/` imported unmodified (79 files). PR #1 (setup docs, two-agent protocol) merged into `dev`.
- **Stance changed (D-001):** `freebuff/` is a reference only; the target is the Master Spec built fresh; reuse is selective and logged. Revised phases: A0 = short inventory and reuse decisions; A1 = foundation (Spec M0) built fresh; A2 retired; reused pieces ported inside B1. `platform/` is not a Python package (D-003).
- A0 deliverables written: `docs/audit/INVENTORY.md` (short), `PITFALLS.md` (19 pitfalls, lead-reproduced or Codex-only, plus pilot P1 result), `DECISIONS.md` (D-001 to D-005, empty reuse log), Codex evidence (`codex_audit_raw.md`, `codex_inventory_raw.md`, `docs/progress/codex.md`).
- Plan documents updated for the new stance: `docs/ADOPTION_PLAN.md` v2.0, `AGENTS.md`, `CLAUDE.md`, `docs/COLLABORATION.md` v1.1, `docs/COLLAB_PLAN.md` v2 (13 foundation cards T-A1-001..013), notice on superseded prompts in `docs/prompts/PROMPTS.md`.
- Public repository hygiene scan over every ref and blob: clean (D-004).
- Codex verified earlier (codex-cli 0.164.0, plugin 1.0.6, review gate off); `/codex:rescue` behavior recorded in `docs/progress/claude-code.md`.

Next:
1. Human reviews and merges the PR (not merged by the lead).
2. Merge `dev` to `main`, tag `phase-A0` (human approval).
3. Phase A1: start with T-A1-001 (repository skeleton), then the cards in the order given in `docs/COLLAB_PLAN.md` section 4. Print a plan and wait for approval before A1 starts (CLAUDE.md).

Blockers / human actions pending:
- Review and merge the PR.
- Rule on the F1 wording (D-005); it only blocks the final banner text in T-A1-010.
- Approve the A1 dependency list (`docs/COLLAB_PLAN.md` section 6, Q3).
- Optional: branch protection on `dev` and `main` (GitHub settings); GitHub "keep my email private" setting (Q4); delete the stale scratch-repo trust entry Codex added to `~/.codex/config.toml`.

Decisions since last session: D-001 to D-005 in `docs/audit/DECISIONS.md`. Default Codex reasoning effort stays `medium`.

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6.

Spend so far: 1 long lead session (setup, bootstrap, measurements, stance change); Codex: 6 small runs (config key check, rescue write test, read-only control, project-config banner check, inventory run, independent audit run).
