# AGENTS.md: UtilityGuard Twin (shared rules for all coding agents)

Read by Codex directly. Claude Code imports it from `CLAUDE.md` (`@AGENTS.md`). Shared rules live ONLY here; `CLAUDE.md` holds Claude Code specifics. Keep this file under 32 KB.

## Project
Simulation-driven virtual utility twin of a capital-scale city (client context: ACUD, New Administrative Capital of Egypt). Water first; electricity and district cooling later as plugins.
- Target system: `docs/UtilityGuard_Master_Spec.md`
- Phases and the reference-baseline stance (`freebuff/` is reference only; build to the spec): `docs/ADOPTION_PLAN.md`
- Two-agent protocol (roles, branches, reviews): `docs/COLLABORATION.md`; concrete task cards: `docs/COLLAB_PLAN.md`
- Current state: `docs/PROGRESS.md`; your assignment: the task card in `docs/tasks/`

There is NO ACUD data. The layout comes from public sources, pipes are inferred, hydraulics are synthetic (fidelity F1). Never present the twin as a survey of a real network.

## Document authority (highest first)
1. Honesty Rules (below)
2. Master Spec
3. Adoption Plan and the assigned task card
4. Existing code in `freebuff/`: reference only, no authority. It was generated earlier by a different AI agent (freebuf). Take ideas from it; never depend on it or shape the architecture around it.

## Honesty Rules (never weaken; ask the human before changing)
- Every displayed number carries an evidence label: OBSERVED, BENCHMARK, PUBLIC_GEOMETRY, SIMULATION, SENSOR_SIM, MODEL, ASSUMPTION, CALCULATED, INSUFFICIENT_EVIDENCE.
- Truth is separate from telemetry. Detectors, the stream and the operator view never receive twin truth or hidden fault tags.
- No invented probabilities of real-world events. Use explicit assumptions, scenario-conditional values, or break-even thresholds.
- No LLM in any calculation path. Explanations come from fixed templates over structured evidence.
- Deterministic: the same manifest (config, seed, versions) gives the same output.
- Savings and ROI are "model-estimated, conditional on assumptions". Negative net benefit must be representable.
- Synthetic-fault results are never described as field validation.
- Advisory only. No write path to real equipment. A human approves every action.
- A permanent honesty banner, a Fidelity badge, and the stream-source indicator (REPLAY, SIMULATED, LIVE) appear where relevant.

## Architecture rules
- `platform/` never imports from `domains/`. Domains plug in through the `DomainAdapter` interface.
- Data crossing module boundaries uses versioned, schema-validated contracts in `contracts/`. Contract changes need the lead agent (Claude Code) and the human, and types must be regenerated.
- Everything is deterministic given a manifest (config, seed, versions).
- Offline-first: no CDN assets or external APIs at runtime.
- Verify every external API (WNTR and others) by introspecting the installed version or reading its documentation. Never guess signatures.

## Reference-baseline rules (build to the spec, reuse selectively)
- `freebuff/` (git tag `baseline-freebuf`) is a **reference**, not the foundation. Do not edit, move or delete anything in it; do not import from it. The new structure (`platform/`, `domains/water/`, `contracts/`, `assumptions/`, ...) is built fresh at the repo root following the Master Spec (section 14).
- Reuse a piece of `freebuff/` only if it passes review (Adoption Plan section 6 checklist) and is better than writing it new. Verdicts are REUSE, ADAPT, REFERENCE, AVOID (Adoption Plan section 4). Record every REUSE or ADAPT (source file, what was reused, why) in `docs/audit/DECISIONS.md` in the same PR that brings it in.
- Known pitfalls of the reference are listed in `docs/audit/PITFALLS.md`. New code must not repeat them, and each has a test in Phase A1.
- Golden (characterization) tests only for pieces we reuse (Adoption Plan Appendix A). Do not pin behavior that `PITFALLS.md` marks as a defect.
- Do not audit `freebuff/` line by line. Read it only to take a reuse decision.
- Small reversible steps; commit after each green step; never rewrite published history.
- List files in `docs/audit/DECISIONS.md` before any deletion, and get approval.
- `platform/` is a plain folder, not a Python package (a package named `platform` would shadow the standard library). Install `ug_core`, `ug_intel`, `ug_api`, `ug_cli` individually.

## Working agreement
- Work only on your assigned task card. Stay inside its "allowed files". Do not edit paths owned by the other agent (ownership map in `docs/COLLABORATION.md` section 7).
- Use your own git worktree and branch (`claude/<phase>-<topic>` or `codex/<phase>-<topic>`) created from `dev`. Worktrees live outside the repo under `~/Desktop/UG-wt/<agent>-<topic>`. Never commit directly to `main` or `dev`; open a pull request into `dev`.
- Conventional commits (`feat`, `fix`, `test`, `refactor`, `docs`, `chore`), one logical change each, tests green at each commit. Add the trailer `Agent: codex` (or `Agent: claude-code`); keep any attribution line your own tooling adds.
- Author, tester and reviewer are different agents. Never mark your own work as reviewed.
- Write a handoff note in the PR description and in `docs/progress/<agent>.md`, where `<agent>` is `claude-code` or `codex` (template in `docs/COLLABORATION.md` Appendix D). If it is not in the repo, the other agent has not seen it. Never name any file `CLAUDE.md` or `AGENTS.md` in any letter case outside the repo root: on macOS they are auto-loaded as instructions.
- Treat review findings as hypotheses: reproduce with a failing test or a `file:line` citation before acting. Two review rounds maximum, then escalate.
- Keep reads narrow (`git ls-files`, `wc -l`, `grep`); never read the whole repository.
- Never commit secrets, credentials, `.venv`, `node_modules`, databases or large data files.

## Stop and ask the human before
Changing Honesty Rules or contracts; deleting or rewriting a module; adding heavy, paid or license-sensitive dependencies; anything that costs money; destructive git commands (`reset --hard`, `clean -fd`, force push); pushing to the remote or merging to `main`; a library that cannot do what the spec assumes; usage limits close to exhausted; any edit or deletion inside `freebuff/`; a reuse candidate that touches truth, evidence labels or cost logic when you are unsure it is safe.

## Definition of done (every task)
- Acceptance tests in the task card pass; CI is green once CI exists.
- The Honesty checklist (`docs/COLLABORATION.md` Appendix E) is ticked in the PR.
- Handoff note written; cross-review logged in `docs/reviews/<task-id>.md` for T1 and T2 tasks.
- `docs/PROGRESS.md` is updated by the lead after merge.

## Commands (keep up to date as they come into existence)
- The new structure has no commands yet. They are added in Phase A1 (task cards T-A1-001, T-A1-006, T-A1-009, T-A1-011 in `docs/COLLAB_PLAN.md`):
  - Backend tests: `make test-backend`
  - Frontend checks: `make test-frontend`
  - Run locally: `make dev`    Run with Docker: `make up`
  - Same checks as CI: `make ci`
  - Environment check: `ug doctor`
- `freebuff/` commands (for reference reading only, never part of the build): `cd freebuff/backend && ../.venv/bin/python -m pytest -q`

## Notes for Codex specifically
- Reviews and audits are read-only: report findings with severity (S0 to S3), evidence (`file:line`) and a suggested fix; do not edit files. Scripted audit form: `codex exec -s read-only -C <worktree> -o <output.md> "<prompt>"`.
- Implementations: keep the diff small and focused, add tests that failed before the change, and list anything you were unsure about in the handoff note.
- Prefer the repository's existing patterns and tools over introducing new ones.
- Verified for Codex CLI 0.164: approval policy accepts only `on-request` or `never`; sandbox modes are `read-only`, `workspace-write`, `danger-full-access`. Never use `danger-full-access` or `--dangerously-bypass-approvals-and-sandbox` on the host.
- `workspace-write` also allows writes to `/tmp` and `$TMPDIR`. Network is off by default (`.codex/config.toml`); a task card that needs installs must say so, and network is enabled for that run only.
- `.codex/config.toml` loads only when the project path is trusted in the user's `~/.codex/config.toml`. Each worktree path may need its own trust entry; ask the human, do not edit user-level config.
- Run `/codex:rescue`-style write tasks only in a dedicated worktree with no uncommitted work. It edits the working tree and does not commit.
