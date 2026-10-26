# UtilityGuard Twin: Prompts for Claude Code

**Place at:** `docs/prompts/PROMPTS.md`
Copy one prompt at a time into Claude Code, started in the repository root. Run them in order. Use a fresh session per prompt.

> **Superseded in part (2026-10-25, `docs/audit/DECISIONS.md` D-001).** `freebuff/` is now a reference baseline, not code to adopt, audit in depth, fix in place or restructure. **Prompts 1, 2, 3 and 4 below describe the old plan and must not be used.** Phase A0 is done; Phase A1 is run from the task cards in `docs/COLLAB_PLAN.md` section 4 (one card per session), and later phases from `docs/ADOPTION_PLAN.md` section 9 with Prompt 5. Prompts 0, 5, 6 and 7 still apply, with "existing code" read as "the reference in `freebuff/`". The text of Prompts 1 to 4 is kept unchanged for history.

---

## Prompt 0: Connect and verify the repository (run once, 2 minutes)

```
Check that this folder is the git repository root and is connected to the remote.
1. Run: git rev-parse --show-toplevel; git remote -v; git status --short | head -20; git log --oneline | head -5; git tag.
2. Confirm that CLAUDE.md exists at the root and that docs/UtilityGuard_Master_Spec.md, docs/ADOPTION_PLAN.md and docs/prompts/PROMPTS.md exist.
3. If the tag baseline-freebuf does not exist, tell me and stop. Do not create tags or commits yourself.
4. Create docs/PROGRESS.md from the template in docs/ADOPTION_PLAN.md section 3 if it does not exist, and docs/audit/ if missing. Do not commit.
5. Print a 5-line summary of what you found. Do not read any source code yet.
```

---

## Prompt 1: Phase A0, adopt and audit (no code changes)

```
You are adopting an existing codebase that was generated earlier by a different AI coding agent (freebuf). It is unverified. Do not trust it, do not rewrite it, and do not change any source code in this session.

Read, in this order: CLAUDE.md, docs/PROGRESS.md, docs/ADOPTION_PLAN.md (sections 0 to 8 and Phase A0 only), and docs/UtilityGuard_Master_Spec.md sections 1 to 2 (vision, fidelity ladder, honesty rules) and section 21 (milestones). Read the rest of the Master Spec only when a specific audit item needs it.

Goal: produce a truthful audit of the existing code against the Master Spec and the Honesty Rules, and recommend what to keep, fix, refactor, rewrite or drop.

Method (keep token use low):
1. Inventory first. Use git ls-files, wc -l, and a directory summary. Do not read every file. Identify which of the earlier milestones M1 to M4 (see ADOPTION_PLAN section 1) actually exist.
2. Set up and run: install dependencies, run backend tests (quietly), run the frontend build, try make up or the documented start command. Record what works and what fails, with the exact error.
3. Measure, do not guess: determinism (run the same seeded scenario twice and compare output hashes), run time of a 48 h scenario, false alarms on normal, holiday and heatwave over 5 seeds if the detector exists.
4. Verify external APIs: introspect the installed WNTR version and confirm every WNTR function the code calls actually exists and is used with correct arguments (leak creation, pipe splitting, pressure-driven demand, pump outage, controls).
5. Search for the S0 risks specifically: where twin truth or hidden fault tags are read and whether they can reach telemetry, the stream or detectors; numbers displayed without an evidence label; invented probabilities; any LLM call in a calculation path; missing honesty banner; non-seeded randomness.
6. Read in full only the highest-risk files (simulation runner, sensor layer, detector, finance engine, stream/main). Skim the rest by grep and structure.
7. Apply the per-area checklist in ADOPTION_PLAN section 6 and the gap list in section 5.

Deliverables (write to docs/audit/, no source changes):
- INVENTORY.md
- AUDIT.md with columns: ID | Area | Finding | Severity (S0 to S3) | Evidence (file:line or command output) | Verdict (KEEP, FIX, REFACTOR, REWRITE, DROP) | Target phase
- DECISIONS.md (every REWRITE or DROP needs a reason; list files you propose to delete, delete nothing)
- MAPPING.md (old module to target location, per ADOPTION_PLAN section 8, corrected to what really exists)

Finish by printing: (a) which milestones really exist and how well they work, (b) the 10 most serious findings, (c) your honest recommendation: continue with this code, or rebuild parts, with the cost of each, (d) the proposed task list for Phase A1 in priority order. Update docs/PROGRESS.md. Do not commit; I will review first.
```

---

## Prompt 2: Review and correct specific old files (use during A1, one module at a time)

```
Review these existing files against the Master Spec and Honesty Rules and fix what is wrong: <list of files or a module name>.

Process:
1. Read only those files and their direct tests.
2. If no characterization test pins the current correct behavior, write one first.
3. List the problems you find (severity S0 to S3) before changing anything, and wait for my approval if any fix changes a contract or removes behavior.
4. Fix in small steps. Each fix gets a test that fails before and passes after. Run the tests after every step.
5. Verify every library call by introspection or documentation, never from memory.
6. Update docs/audit/AUDIT.md statuses and docs/PROGRESS.md. Commit after each green step with a clear message.
Do not touch other modules. Do not rewrite wholesale unless AUDIT.md marks this module REWRITE and I approved it.
```

---

## Prompt 3: Phase A1, stabilize and fix S0 and S1

```
Phase A1 from docs/ADOPTION_PLAN.md. Read CLAUDE.md, docs/PROGRESS.md, docs/audit/AUDIT.md, docs/audit/DECISIONS.md, and ADOPTION_PLAN section 9 (Phase A1) and Appendix A.

First print a short plan: the order of the fixes (all S0 first, then S1), the characterization tests you will add, and what you will verify. Wait for my approval.

Then execute:
1. Characterization (golden) tests for correct behavior per Appendix A.
2. Make make test-backend, make test-frontend, make dev and make up work from a fresh clone.
3. Fix S0 findings, then S1. Each fix has a test that failed first.
4. Extract contracts from the existing pydantic models into contracts/ (JSON Schema) and generate TypeScript types. Add a CI check that fails on drift.
5. Add the honesty banner, evidence label chips and Fidelity badge where missing. Use the label set from the Master Spec section 2.
6. Add a test proving telemetry, WebSocket ticks and detector inputs contain no truth or hidden fault fields.

Commit after each green step. Stop at the Phase A1 exit gate (ADOPTION_PLAN section 9) and report: what works, what is approximated, what is not proven. Update docs/PROGRESS.md.
```

---

## Prompt 4: Phase A2, restructure to the target architecture

```
Phase A2 from docs/ADOPTION_PLAN.md. Read CLAUDE.md, docs/PROGRESS.md, docs/audit/MAPPING.md and ADOPTION_PLAN sections 8 and 9 (Phase A2). Read Master Spec sections 4.3, 4.6 and 14 for the target layout and the DomainAdapter interface.

Print a plan of the move sequence (small steps, tests green after each) and wait for my approval. Then:
1. Create platform/, domains/water/, contracts/, assumptions/, docs/adr/.
2. Move modules per MAPPING.md using git mv in small commits. Keep golden tests unchanged and passing.
3. Introduce the DomainAdapter interface and wrap the existing water code. Add the conformance test skeleton and a lint or test that fails if platform/ imports from domains/.
4. Add the ug CLI skeleton (ug doctor, ug run), GitHub Actions CI (lint, types, tests, contract drift), and update the Commands section of CLAUDE.md.
5. Create ADR stubs ADR-001 to ADR-010 (titles in Master Spec Appendix D).

Do not add features in this phase. Stop at the Phase A2 exit gate and report. Update docs/PROGRESS.md.
```

---

## Prompt 5: Generic phase kickoff (B1 to B7)

Replace `<PHASE>` with `B1`, `B2`, and so on.

```
Phase <PHASE> from docs/ADOPTION_PLAN.md section 9, which implements the matching milestone in docs/UtilityGuard_Master_Spec.md section 21.

Read CLAUDE.md, docs/PROGRESS.md, the Phase <PHASE> entry in ADOPTION_PLAN, the matching milestone row in Master Spec section 21, and only the Master Spec sections that the milestone references. Do not read the whole spec.

Step 1: print a checklist of tasks, the external APIs you will verify, the tests you will write, and the existing code you will build on (not rebuild). Wait for my approval.
Step 2: implement in small steps. Reuse existing modules. If an existing module is wrong, fix it and log the decision. For any UI work, first write the design plan (tokens, type roles, wireframes), review it against the Master Spec section 13 and against generic defaults, and show it to me before building.
Step 3: run all tests and the milestone acceptance checks. Start the app and verify visually where relevant.
Step 4: finish with a summary: working features, approximations introduced, known limits, files changed. Update docs/PROGRESS.md and commit. Do not start the next phase.

Phase-specific reminders:
- B1: do the geometry feasibility test first (ug fetch-geometry and the coverage report). If public map coverage of the capital is weak, report it and propose the manual-overlay fallback before building anything else.
- B2: the map engine is the identity of the product. Build the shell and map first.
- B3: false alarms on normal, holiday, heatwave and Ramadan over 10 seeds must be zero.
- B4: every displayed number must open a complete evidence trail.
- B5: use temporal splits, never tune on the test set, always show the strongest baseline.
```

---

## Prompt 6: Resume after an interrupted session

```
Resume work. Read CLAUDE.md and docs/PROGRESS.md only. Run git status and git log --oneline | head -10, then run the test suite quietly. Report the current phase, what is done, what is half-finished, and the next three steps. Do not change anything until I confirm.
```

---

## Prompt 7: Weekly integration check

```
Run an integration check. Start the full stack, run the presets normal, leak_gradual and sensor_drift end to end, and verify: no truth in the stream, labels on every displayed number, deterministic rerun hashes, zero incidents on normal, correct diagnosis on sensor_drift. Report pass or fail per check with evidence. Fix nothing; list failures with a suggested fix and severity.
```

---

## Notes for the human

- Run the prompts in order, one per fresh session. Review the output files before moving on.
- If the audit says the old code is mostly unusable, read the recommendation before deciding to rebuild.
- Each prompt asks for approval before big changes. That is intentional: it saves tokens by avoiding wrong work.
- Keep `docs/PROGRESS.md` honest. It is what makes a cheap resume possible.
