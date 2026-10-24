# PROGRESS
Current phase: A0 (setup and bootstrap done; A0 audit not started)
Last session: 2026-10-25 (setup, planning, repository bootstrap; lead agent Claude Code)

Done:
- Project documents placed: `CLAUDE.md`, `AGENTS.md`, `.codex/config.toml` at root; spec, adoption plan, collaboration protocol, collab plan in `docs/`; prompts in `docs/prompts/`; `docs/{progress,tasks,reviews,audit}` created.
- **Repository bootstrapped and baseline published (T-A0-001 done).** `main` and `dev` at `debfd51`; tag `baseline-freebuf` -> `debfd51`; all pushed to `AHMED-METAWEA/UtilityGuard-Twin` (public). 79 files tracked under `freebuff/`. The remote's `.gitignore` template ignored `lib/`, which would have dropped `freebuff/frontend/src/lib/`; fixed before the commit and verified on the remote tree. Secret/PII scan of the baseline was clean.
- Codex verified: codex-cli 0.164.0, plugin 1.0.6, ChatGPT login OK, review gate OFF. `/codex:rescue` writes the working tree and does not commit; without `--write` it is read-only. Config keys validated with `--strict-config`. Details: `docs/progress/claude-code.md`.
- `AGENTS.md` (shared rules), `CLAUDE.md` (`@AGENTS.md` plus Claude specifics), `.codex/config.toml` finalized.
- `docs/COLLAB_PLAN.md`: task cards T-A0-001..006 and T-A1-001..010, pilot P1 to P3, open questions with current status.
- Agent log renamed `docs/progress/claude-code.md` (the name `claude.md` was auto-loaded as instructions on macOS).
- Nothing inside `freebuff/` was changed. The setup files are on branch `claude/a0-docs-setup` for a pull request into `dev`.

Next:
1. Merge the docs-setup PR into `dev` (Codex review first, per COLLABORATION section 8).
2. Create the A0 worktrees under `~/Desktop/UG-wt/` from `dev` (`claude-a0-audit`, `codex-a0-inventory`, `codex-a0-audit-p1`).
3. Run T-A0-002 and T-A0-003 (Codex) in parallel with T-A0-004 and T-A0-005 (Claude), then T-A0-006. The A0 exit gate needs the human to review `docs/audit/*`.
(Per CLAUDE.md, a plan is printed and approved before the A0 audit starts.)

Blockers / human actions pending:
- Add the Codex trust entry for this project to `~/.codex/config.toml` (two lines in `docs/COLLAB_PLAN.md` section 6, Q4). The lead did not edit user-level agent config; until it exists, Codex ignores `.codex/config.toml` and uses user settings (effort `high`).
- Branch protection on `dev` and `main` (GitHub settings; PR required, no force push) if the plan allows. Not checked or set by the lead.
- Optional: delete the stale `[projects."/private/tmp/.../rescue-test"]` trust entry that Codex added to `~/.codex/config.toml` for the throwaway scratch repo.

Decisions since last session:
- `freebuff/` stays in place as the baseline until Phase A2 (approved).
- Branch model `main`, `dev`, `claude/*`, `codex/*` and worktree folder `~/Desktop/UG-wt/` (approved).
- Codex default reasoning effort `medium`; audits and T2 reviews raise it per run.
- F1 fidelity wording conflict (Spec 1.4/5.1 vs CLAUDE.md/Adoption Plan G01) remains an open human ruling; until decided, the weaker Spec 1.4 wording applies to the banner (COLLABORATION section 9, stricter reading). Blocks T-A1-008 only.
- Dev dependencies for A1 (Vitest, a JSON-Schema-to-TS generator) are asked per card.

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6 (Q1 F1 wording, Q4 Codex trust, branch protection).

Spend this phase: 1 Claude setup session plus execution of the approved bootstrap; 3 tiny Codex model calls (config key check, rescue write test, read-only control). Plugin setup and `codex doctor` make no model call.
