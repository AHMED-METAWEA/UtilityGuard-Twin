# COLLAB_PLAN: Phase A0 and A1 task cards, pilot, bootstrap

**Author:** Claude Code (lead). **Status:** draft v1, awaiting human approval. **Date:** 2026-10-25.
Protocol: `docs/COLLABORATION.md`. Shared rules: `AGENTS.md`. Phases: `docs/ADOPTION_PLAN.md` section 9. Milestones: Master Spec section 21.
Tiers: **T0** trivial (CI/check only); **T1** normal (other agent reviews, finding log); **T2** honesty/physics-critical (adversarial review + Appendix E checklist + human glance).
Task cards below are the source of truth; when work starts, each is copied to `docs/tasks/<ID>.md` (status field there).

---

## 1. Repository bootstrap (approved by the human and executed 2026-10-25; this section records what was done)

### 1.1 State found before execution
- Local folder was not a git repo. Remote `https://github.com/AHMED-METAWEA/UtilityGuard-Twin` (public) had one "Initial commit" on `main` (8d22e89): `.gitignore` (GitHub Python template) and `README.md`. No tags, no other branches.
- `gh` was not logged in and no `~/.ssh` keys existed, but the system git config (`/opt/homebrew/etc/gitconfig`) uses the macOS keychain helper, which held a working GitHub credential: `git push --dry-run` succeeded, so `main`, the tag and `dev` were pushed with it. `gh` (needed for pull requests) was authenticated separately by device-code login.

### 1.1a Result
- `main` and `dev` at `debfd51` ("chore: import freebuf baseline"), pushed; tag `baseline-freebuf` -> `debfd51`, pushed. 79 files tracked under `freebuff/` (80 in the commit with `.gitignore`); `freebuff/frontend/src/lib/{api,types}.ts` tracked; nothing untracked-and-unignored left under `freebuff/`.
- Scanned before publishing (the repository is public): no secret-like strings, no local paths or personal identifiers in the staged baseline; the one binary (`screenshots/dashboard.png`, 700 KB) was viewed and shows only the app UI.

### 1.2 Placement of `freebuff/` (recommended)
Keep `freebuff/` in place and commit it unchanged as the baseline; tag `baseline-freebuf`. A0 and A1 work happens inside `freebuff/`. Phase A2 restructures with `git mv` per Adoption Plan section 8, by one agent, others frozen. Reasons: root-file collisions (`README.md`, `Makefile`, `.gitignore`, `docs/`), "pin behavior before moving", and the tag stays a clean diff reference. Cost: Adoption Plan paths are `freebuff/...` until A2.

### 1.3 Commands (run in this order after `gh auth login`)
```bash
cd ~/Desktop/UtilityGuard-Twin
git init -b main
git remote add origin https://github.com/AHMED-METAWEA/UtilityGuard-Twin.git
git fetch origin
git reset origin/main               # adopt the existing Initial commit, keep working files
git restore .gitignore README.md    # reset shows them deleted; restore the remote copies
```
Appended to root `.gitignore` BEFORE the baseline commit. The remote template contains `lib/`, which silently dropped `freebuff/frontend/src/lib/api.ts` and `types.ts` (confirmed with `git check-ignore -v`; it was the only wrongly ignored source path). The template already ignores `.venv` and `*.egg-info/`, so only three lines were needed:
```
!freebuff/frontend/src/lib/
.DS_Store
freebuff/.freebuff/
```
Baseline commit (only `.gitignore` and `freebuff/`; docs go on a later branch so the tag is pristine):
```bash
git add .gitignore freebuff
git ls-files freebuff | wc -l          # compare with: find freebuff -type f -not -path '*/.venv/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -not -name '*.pyc' -not -name '*.log' -not -name '.DS_Store' -not -name '*.db' -not -path '*.egg-info/*' -not -path '*/.freebuff/*' -not -path '*/.pytest_cache/*' -not -path '*/dist/*' | wc -l
git ls-files freebuff | grep -E '\.venv|node_modules|\.db$|\.log$|egg-info' ; echo "expect: nothing above"
git ls-files freebuff | grep 'src/lib/'            # expect api.ts and types.ts
git commit -m "chore: import freebuf baseline"      # plus trailers (Agent: claude-code + tooling attribution)
git tag baseline-freebuf
git push -u origin main --tags                      # human OK + auth required
```
Files excluded from the baseline by ignore rules (nothing deleted from disk; recorded in `docs/audit/DECISIONS.md`): `freebuff/.venv` (390 MB), `freebuff/frontend/node_modules` (83 MB), `*.log`, `freebuff/data/utilityguard.db`, `backend/*.egg-info`, `freebuff/.freebuff/`, `.DS_Store`.

### 1.4 Branches and worktrees
```
main   phase gates only, tagged        dev   integration, PRs only (created from main after the baseline push)
claude/<phase>-<topic>                 codex/<phase>-<topic>
```
Done: `dev` created and pushed. `claude/a0-docs-setup` was created in the main clone (not a worktree), because the setup files were untracked there; it carries `CLAUDE.md`, `AGENTS.md`, `.codex/`, `docs/` into a PR to `dev`. The A0 worktrees below are created after that PR merges, so they contain the task cards.
```bash
mkdir -p ~/Desktop/UG-wt
git worktree add -b claude/a0-audit      ~/Desktop/UG-wt/claude-a0-audit      dev
git worktree add -b codex/a0-inventory   ~/Desktop/UG-wt/codex-a0-inventory   dev
git worktree add -b codex/a0-audit-p1    ~/Desktop/UG-wt/codex-a0-audit-p1    dev
```
The setup files currently sit untracked in the main clone. They are copied into `claude/a0-docs-setup`, committed there, and PR'd into `dev` (squash). Each worktree needs its own `.venv` (use `python3.11`; baseline venv is 3.11.7, system `python3` here is 3.12.4) and, for Codex, a trust entry in the user's `~/.codex/config.toml`.
GitHub branch protection on `dev` and `main` (PR required, no force push) if the plan allows; otherwise enforced by discipline.

---

## 2. Phase and milestone mapping

| Adoption phase | Spec milestone | Covers |
|---|---|---|
| A0 Baseline and audit | precedes M0 | Evidence about the baseline; no code change |
| A1 Stabilize | part of M0 | Contracts and generated types, make/Docker, banner and badge, S0/S1 fixes, golden and truth-leak tests |
| A2 Restructure | rest of M0 | `platform/` + `domains/water`, `DomainAdapter`, import-rule lint, `ug` CLI, CI |
| B1 to B7 | M1 to M7 | Per Adoption Plan section 9 (cards written when the previous gate passes) |

Sequencing note: Spec M0 lists the UI design plan and `ug doctor`; the Adoption Plan places them in B2 and A2. This plan follows the Adoption Plan. Critical path for credibility (Spec section 21): M0, M1, M3, M4, M5.

---

## 3. Phase A0 cards (Exit gate: INVENTORY, AUDIT, DECISIONS, MAPPING exist, measured numbers recorded, human reviewed)

### T-A0-001: Import the baseline and tag it
Status: **done 2026-10-25** (baseline commit `debfd51`, tag `baseline-freebuf`; all acceptance checks below passed locally and on the remote, including the GitHub tree listing showing both `src/lib` files)
Owner: claude   Reviewer: codex   Tier: T0
Branch: `main` (human-approved baseline exception; first commit)   Phase: A0   Spec refs: Adoption Plan section 3
**Goal:** `baseline-freebuf` tag exists locally and on the remote and points at an unmodified copy of `freebuff/` minus ignored artifacts.
**Context:** `lib/` ignore rule trap (1.3). Reviewer only checks the file list, not content.
**Allowed:** root `.gitignore`; git operations in 1.3. **Forbidden:** any edit inside `freebuff/`.
**Contracts touched:** none.
**Acceptance:**
- `git tag -l baseline-freebuf` prints the tag; `git ls-remote --tags origin baseline-freebuf` prints it after the approved push.
- Tracked-file count equals the on-disk count of non-ignored files (command in 1.3).
- `git ls-files freebuff | grep -E '\.venv|node_modules|\.db$|\.log$|egg-info'` is empty; `git ls-files freebuff | grep -c 'src/lib/'` prints `2`.
- `git diff --stat baseline-freebuf -- freebuff` is empty at the start of every later A0 task.
**Budget:** 1 short session. **Escalate if:** tracked count differs, any secret-looking file is tracked, push is rejected.

### T-A0-002: Inventory and test-run summary
Status: ready after T-A0-001   Owner: codex   Reviewer: claude   Tier: T1
Branch: `codex/a0-inventory`   Phase: A0   Spec refs: Adoption Plan sections 6.6, 7 (INVENTORY.md)
**Goal:** `docs/audit/INVENTORY.md` states, from commands run in a fresh worktree, what the baseline contains and what runs.
**Allowed:** `docs/audit/INVENTORY.md`, `docs/progress/codex.md`, files created inside the worktree's ignored `.venv`/`node_modules`. **Forbidden:** everything else, especially `freebuff/**` source and tests. Network may be enabled for the install step only (`-c 'sandbox_workspace_write.network_access=true'`), then off.
**Required content (5 sections):** `## Inventory` (tree summary, `wc -l` per module, `git ls-files | wc -l`); `## Milestone status` (earlier M1 to M4 per Adoption Plan section 1: exists / partial / missing, with file evidence; list presets present: normal, holiday, heatwave, leak_gradual, leak_sudden, sensor_drift, sensor_stuck, pump_outage, leak_plus_sensor_drift as observed by the lead; note absent Ramadan preset); `## How to run` (commands that actually worked, from a fresh clone, Python 3.11 and also whether it installs on 3.12); `## Test results` (pytest and frontend build output summary: counts passed/failed, exact command, duration); `## Versions` (Python, WNTR, Node, FastAPI, pydantic, numpy, pandas, React, Vite; pinned or not). Also record Adoption 6.6: `docker compose config`, does `make up` build, any CDN or external URL in `frontend/`, README command check.
**Acceptance (runnable):**
- `grep -cE '^## (Inventory|Milestone status|How to run|Test results|Versions)$' docs/audit/INVENTORY.md` prints `5`.
- Lead re-runs `cd freebuff/backend && ../.venv/bin/python -m pytest -q 2>&1 | tail -3` in its own env; passed/failed counts equal the file's.
- `git diff --stat dev -- freebuff` is empty (nothing in the baseline changed).
**Budget:** 1 to 2 sessions. **Escalate if:** baseline does not install, tests cannot run, or any secret appears in the tree.

### T-A0-003: Codex independent read-only audit (pilot P1, Codex side)
Status: ready after T-A0-001   Owner: codex   Reviewer: claude   Tier: T1
Branch: `codex/a0-audit-p1` (output file only)   Phase: A0   Spec refs: Adoption Plan section 6
**Goal:** `docs/audit/codex_audit_raw.md`: independent findings against the 6.1 to 6.6 checklist, without seeing the lead's audit.
**Command (run by the human or lead from the worktree; model reasoning raised for this task):**
```bash
codex exec -s read-only -c 'model_reasoning_effort="high"' -C ~/Desktop/UG-wt/codex-a0-audit-p1 \
  -o ~/Desktop/UG-wt/codex-a0-audit-p1/docs/audit/codex_audit_raw.md "$(cat docs/tasks/T-A0-003.prompt.md)"
```
Prompt (stored in `docs/tasks/T-A0-003.prompt.md`): audit `freebuff/` against `docs/ADOPTION_PLAN.md` section 6 and the Honesty Rules in `AGENTS.md`; do not edit files; do not read `docs/audit/AUDIT.md` or any lead audit; output a table `ID | Area | Finding | Severity (S0 to S3) | Evidence (file:line) | Verdict | Target phase`, one subsection per 6.1 to 6.6, and a top-10; mark any item you could not verify because the sandbox prevented running code as `NOT_VERIFIED`.
**Allowed:** the single output file. **Forbidden:** all source edits; reading lead audit files.
**Acceptance:**
- `grep -cE '^#+ .*6\.[1-6]' docs/audit/codex_audit_raw.md` is at least `6`.
- Every finding row has `file:line` or is marked `NOT_VERIFIED`; severity is one of S0 to S3 (`awk` check in the review log).
- Lead samples 10 cited `file:line` locations; hit rate is recorded as a pilot metric.
**Budget:** 1 run. **Escalate if:** the sandbox prevents reading `freebuff/`, or the final message is truncated or the run exhausts the usage budget (split by checklist area and re-run, one `-o` file per area).

### T-A0-004: Lead audit part 1, simulation and determinism (pilot P1, Claude side)
Status: ready after T-A0-001   Owner: claude   Reviewer: codex   Tier: T2
Branch: `claude/a0-audit`   Phase: A0   Spec refs: Adoption Plan 6.1, 6.2; Spec 4.1 P2, 5, 4.9
**Goal:** Findings and measured numbers for network, scenario schema, WNTR usage and determinism, written into `docs/audit/AUDIT.md` (section "Simulation") and `docs/audit/audit_part1_evidence.md`.
**Allowed:** `docs/audit/**`, `docs/progress/claude-code.md`; running (not editing) baseline code. **Forbidden:** edits under `freebuff/`.
**Required measurements:**
1. Determinism: run the same preset and seed twice, hash truth series, telemetry and incidents; record equal/unequal.
2. Runtime of a 48 h run; peak-demand minimum pressure; 7-day normal run tank behavior if feasible.
3. Every `wntr.*` symbol used in `freebuff/backend/app` listed with introspection proof against the installed WNTR 1.5.0 (`python -c "import wntr,inspect; ..."`), including the simulator choice and pressure-driven demand with leaks.
4. Leak split-node correctness and gradual-leak chunk hand-over: present, absent or untested; chunk-size convergence check exists or is noted missing.
**Acceptance:**
- Every checklist item in 6.1 and 6.2 has a row in `AUDIT.md` (a finding or an explicit `OK` with evidence); `grep -cE '^\| A0-S[0-9]+ \|' docs/audit/AUDIT.md` counts the Simulation rows; each row has the 7 columns.
- Items 1 to 3 each have a command and its output in `audit_part1_evidence.md`; item 4 has a verdict.
- Codex spot-check (review): 5 findings reproduced from their `file:line` or command.
**Budget:** 2 sessions. **Escalate if:** WNTR cannot do what the code assumes, or the baseline is largely unusable (human decision, no rebuild started).

### T-A0-005: Lead audit part 2, honesty, detection, finance, decision, evidence (pilot P1, Claude side)
Status: ready after T-A0-001   Owner: claude   Reviewer: codex   Tier: T2
Branch: `claude/a0-audit`   Phase: A0   Spec refs: Adoption Plan 6.3 to 6.5; Honesty Rules; Spec 2, 6, 7, 9, 10
**Goal:** Findings and measured numbers for truth/telemetry separation, labels, quality and detection, impact/finance/decision/evidence, in `AUDIT.md` (section "Honesty and intelligence") and `docs/audit/audit_part2_evidence.md`.
**Allowed / Forbidden:** as T-A0-004.
**Required measurements:**
1. Truth trace: every place truth or fault tags are read (`grep -rn "truth" freebuff/backend --include=*.py`) and whether each reaches the API, a WebSocket tick or a detector input. Note: sensor logic appears to sit in `scenarios/runner.py` while `sensors/` is empty; judge the coupling.
2. False alarms: incident count for `normal`, `holiday`, `heatwave` over 5 seeds (15 cells); record the table.
3. Labels: which displayed numbers have no evidence label; invented probabilities; any LLM in a calculation path; double counting in money lines; negative benefit representable; Monte Carlo labeling.
4. Detector thresholds configurable; diagnosis returns `unknown` for ambiguous cases (`leak_plus_sensor_drift`).
**Acceptance:**
- `audit_part2_evidence.md` contains the 15-cell false-alarm table and the `grep` output for item 1.
- Each S0/S1 finding has `file:line` evidence or a reproducing command.
- Codex spot-check: 5 findings reproduced, including at least one S0 if any exists.
**Budget:** 2 sessions. **Escalate if:** an S0 shows truth reaching the operator view (record immediately in PROGRESS.md blockers).

### T-A0-006: Reconcile and write AUDIT, DECISIONS, MAPPING
Status: ready after T-A0-002..005   Owner: claude   Reviewer: codex   Tier: T2
Branch: `claude/a0-audit`   Phase: A0   Spec refs: Adoption Plan sections 4, 7, 8
**Goal:** The four deliverables exist, with the union of both audits and a recorded verdict per module.
**Allowed:** `docs/audit/AUDIT.md`, `DECISIONS.md`, `MAPPING.md`, `docs/reviews/T-A0-006.md`, `docs/PROGRESS.md`. **Forbidden:** `freebuff/**`.
**Content:** `AUDIT.md` table `ID | Area | Finding | Severity | Evidence | Verdict | Target phase | Found by (claude/codex/both)` plus top-10 and measured numbers; `DECISIONS.md` verdict per module (KEEP/REFACTOR/FIX/REWRITE/DROP) with reasons, the ignore-rule exclusions from 1.3, and any proposed deletions (none executed); `MAPPING.md` old to target paths, corrected from Adoption Plan section 8 (include `app/analysis.py`, `app/config.py`, `app/eval/*`, which the plan does not map).
**Acceptance:**
- All four files exist; `AUDIT.md` header has the 8 columns; top-10 present; measured numbers for determinism, 48 h runtime, 15-cell false alarms, truth-trace result.
- `docs/reviews/T-A0-006.md` logs the Codex spot-check of the top-10 (reproduced / not reproduced) and the pilot P1 comparison (found by only one agent).
- **Exit gate:** human approves A0; phase A1 starts after that.
**Budget:** 1 session. **Escalate if:** audit recommends REWRITE of a module or a rebuild (human decides).

---

## 4. Phase A1 cards (Exit gate per Adoption Plan: tests green, determinism verified, truth leak impossible and proven by a test, zero incidents on normal/holiday/heatwave over 5 seeds, no S0 or S1 left)
Cards for specific S0/S1 fixes cannot be written before the A0 audit. T-A1-004 is a template instantiated per finding ID after the A0 gate. Work happens inside `freebuff/`; paths below are relative to the repo root.

### T-A1-001: Golden (characterization) test harness (pilot P2)
Status: ready after A0 gate   Owner: codex   Reviewer: claude   Tier: T1
Branch: `codex/a1-golden-tests`   Phase: A1   Spec refs: Adoption Plan Appendix A
**Goal:** Behavior of correct modules is pinned by golden tests, so A2 moves are provable.
**Allowed:** `freebuff/backend/tests/golden/**`, `freebuff/backend/tests/test_golden.py`, `freebuff/backend/tests/conftest.py` (additive). **Forbidden:** `freebuff/backend/app/**`. If the app lacks a hook to run a preset at reduced duration, stop and request it from the lead.
**Content:** presets `normal`, `holiday`, `heatwave`, `leak_gradual`, `leak_sudden`, `sensor_drift`, `pump_outage` (also `sensor_stuck`, `leak_plus_sensor_drift` if cheap); fixed seed, reduced duration; snapshot = hash of ground-truth series with stated tolerance, hash of telemetry, incident list (type, location, first tick), top-line cost numbers from a fixed assumption set. Exclude anything `AUDIT.md` marks as a defect (list exclusions in the handoff).
**Acceptance:**
- `cd freebuff/backend && ../.venv/bin/python -m pytest -q -k golden` passes.
- Mutation check recorded in the handoff: changing one demand constant in a throwaway copy makes at least one golden test fail.
- Golden files change only in a commit titled `test(golden): update ... because ...`.
**Budget:** 2 sessions. **Escalate if:** runs are non-deterministic (that is an A0/S0 finding, not a test problem).

### T-A1-002: Make targets and fresh-clone reliability
Status: ready after A0 gate   Owner: codex   Reviewer: claude   Tier: T1
Branch: `codex/a1-make-fresh-clone`   Phase: A1   Spec refs: Adoption Plan A1 task 2
**Goal:** `make test-backend`, `make test-frontend`, `make dev`, `make up` work from a fresh clone. The baseline Makefile has `test`, `dev` (prints instructions), `up`, but no frontend test target and no `test-backend`.
**Allowed:** root `Makefile` (thin shim to `freebuff/`), `freebuff/Makefile`, `freebuff/docker-compose.yml`, `freebuff/backend/Dockerfile`, `freebuff/frontend/package.json` scripts, `freebuff/README.md` command sections. **Forbidden:** `freebuff/backend/app/**`, `freebuff/frontend/src/**`. Adding a frontend test runner (Vitest) is a light dev dependency: ask the lead in the card comments before adding.
**Acceptance:**
- Fresh clone: `T=$(mktemp -d) && git clone <repo> $T/c && cd $T/c && git checkout <branch> && make install && make test-backend && make test-frontend` all exit 0. `test-frontend` = typecheck and build at minimum.
- `docker compose -f freebuff/docker-compose.yml config >/dev/null` exits 0; `make up` smoke documented (URL returns HTTP 200).
- `grep -RInE 'https?://(fonts\.|cdn|unpkg|cdnjs|ajax)' freebuff/frontend/index.html freebuff/frontend/src` is empty (offline-first).
**Budget:** 1 to 2 sessions. **Escalate if:** an install needs network at runtime or a heavy dependency.

### T-A1-003: Truth-leak regression test
Status: ready after T-A0-005   Owner: codex (test), claude (denylist spec)   Reviewer: claude   Tier: T2
Branch: `codex/a1-truth-leak-test`   Phase: A1   Spec refs: Honesty Rules; Spec 4.1 P1; Adoption Plan A1 exit gate
**Goal:** A test proves that REST responses, WebSocket ticks and detector inputs contain no truth fields or hidden fault tags.
**Allowed:** `freebuff/backend/tests/test_truth_leak.py`, `freebuff/backend/tests/truth_denylist.yaml` (Claude authors the denylist from the T-A0-005 trace). **Forbidden:** `freebuff/backend/app/**`.
**Acceptance:**
- `... pytest -q -k truth_leak` passes on a clean tree, and FAILS when a seeded mutation (a truth field added to one payload, in a throwaway copy) is applied; both outcomes are shown in the handoff.
- The test walks every route in the app's route table and every message type the stream emits; adding a new route without coverage fails the test.
**Budget:** 1 to 2 sessions. **Escalate if:** an actual leak is found (S0; Claude fixes under T-A1-004, test stays failing until then).

### T-A1-004: Fix one S0/S1 finding (template; one card per finding ID)
Status: template   Owner: claude (physics, honesty, truth separation) or codex (non-physics S1)   Reviewer: the other   Tier: T2 for S0, T1 for S1
Branch: `<agent>/a1-fix-<AUDIT-ID>`   Phase: A1
**Goal:** Finding `<AUDIT-ID>` is fixed with a test that fails before and passes after.
**Allowed:** only the files named in the finding's `Evidence` column plus their tests. **Acceptance:** the named test fails on `dev` and passes on the branch; golden tests unchanged unless the audit marked the behavior a defect (separate commit); Appendix E ticked in the PR. For S0 the reviewer runs `/codex:adversarial-review --base dev --background <focus text>` (Claude's change) or reads the diff and re-runs tests (Codex's change). **The first instance of this card is pilot P3 (Codex side).**

### T-A1-005: Exit-gate tests: no false alarms, determinism
Status: ready after T-A1-001   Owner: codex   Reviewer: claude   Tier: T2
Branch: `codex/a1-gate-tests`   Phase: A1   Spec refs: Adoption Plan A1 exit gate; Spec 21 M3 style check
**Allowed:** `freebuff/backend/tests/test_gate_false_alarms.py`, `test_gate_determinism.py`. **Forbidden:** app code.
**Acceptance:**
- `... pytest -q -k "no_false_alarm or determinism"` passes: zero incidents for `normal`, `holiday`, `heatwave` over 5 seeds; two runs of one manifest produce identical hashes of truth, telemetry and incidents.
- A deliberately loosened detector threshold in a throwaway copy makes the false-alarm test fail.
**Budget:** 1 session. **Escalate if:** the baseline cannot pass (S0/S1 fix cards, owner claude).

### T-A1-006: Extract contracts from pydantic models
Status: ready after A0 gate; **needs human sign-off before merge (contracts)**   Owner: claude   Reviewer: codex   Tier: T2
Branch: `claude/a1-contracts`   Phase: A1   Spec refs: Spec 12; Adoption Plan A1 task 4
**Goal:** Versioned JSON Schemas in `contracts/` for the baseline's API payloads, derived from `freebuff/backend/app` pydantic models.
**Allowed:** `contracts/**`, a small generator script under `freebuff/backend/scripts/`. **Forbidden:** changing payload shapes.
**Acceptance:** every schema carries `schema_version`; `... pytest -q -k contract` validates live API responses for each route against its schema; a payload with an extra undeclared field fails.
**Budget:** 1 to 2 sessions. **Escalate if:** the models have no clean mapping or payloads must change (human decides).

### T-A1-007: TypeScript type generation and contract-drift check
Status: ready after T-A1-006   Owner: codex   Reviewer: claude   Tier: T1
Branch: `codex/a1-ts-types`   Phase: A1   Spec refs: Adoption Plan A1 task 4
**Allowed:** `freebuff/frontend/src/lib/types.gen.ts`, `freebuff/frontend/package.json` scripts, `Makefile` targets, CI-ready script `scripts/check_contract_drift.sh`. A schema-to-TS generator is a light dev dependency: name the package and version in the card comments for lead approval.
**Acceptance:**
- `make gen-types && git diff --exit-code freebuff/frontend/src/lib/types.gen.ts` exits 0 on a clean tree.
- Editing one schema without regenerating makes `scripts/check_contract_drift.sh` exit non-zero.
**Budget:** 1 session.

### T-A1-008: Honesty banner, Fidelity badge, stream-source indicator
Status: ready after human ruling on F1 wording (section 6, Q1)   Owner: claude   Reviewer: codex   Tier: T2
Branch: `claude/a1-shell-honesty`   Phase: A1   Spec refs: Spec 1.4, 2 (rules 1 and 2), 13 shell
**Allowed:** `freebuff/frontend/src/App.tsx`, a new `freebuff/frontend/src/components/Shell*.tsx`, `freebuff/frontend/src/styles.css`. **Forbidden:** pages' data logic.
**Acceptance:** a component test renders every route and asserts the banner, the Fidelity badge text exactly as ruled in Q1, and the stream-source indicator (REPLAY, SIMULATED or LIVE) are present; exported reports (if any) carry the same text. If no frontend test runner exists, T-A1-002 adds Vitest first.
**Budget:** 1 session. **Escalate if:** badge wording cannot be stated truthfully for the current baseline network.

### T-A1-009: Evidence-label chip on every displayed number
Status: ready after T-A1-008   Owner: codex   Reviewer: claude   Tier: T2
Branch: `codex/a1-evidence-chips`   Phase: A1   Spec refs: Honesty Rules; Spec 2 rule 3, 10
**Allowed:** `freebuff/frontend/src/components/**`, `freebuff/frontend/src/pages/**`, `freebuff/frontend/src/lib/types.ts` (labels only). **Forbidden:** backend.
**Acceptance:** a test renders each page with fixture data and fails if any element marked as a numeric value lacks `data-evidence-label` with a value from the nine allowed labels; the convention (`<Value label="SIMULATION">`) is documented in `freebuff/docs/`; no hard-coded demo numbers (grep list in handoff).
**Budget:** 2 sessions. **Escalate if:** a backend number has no evidence record to label (S1 finding, backend fix card).

### T-A1-010: A1 exit-gate review
Status: ready after all A1 cards   Owner: codex (review) and claude (review of Codex PRs)   Reviewer: human   Tier: T2
Branch: none (review only)   Phase: A1
**Command:** `/codex:adversarial-review --base baseline-freebuf --background truth or hidden fault tags reaching telemetry, the stream or detectors; nondeterminism; numbers displayed without an evidence label; invented probabilities; double counting in cost lines; contract drift`
**Acceptance:** findings logged in `docs/reviews/T-A1-010.md` (severity, evidence, decision, fixing commit); no S0/S1 open; all A1 exit-gate conditions checked off in `docs/PROGRESS.md`; human approves, then `dev` merges to `main` with tag `phase-A1`.

---

## 5. Pilot and metrics (COLLABORATION section 11)

| Pilot | Cards | What is compared |
|---|---|---|
| P1 independent audit | T-A0-003 (Codex, read-only) vs T-A0-004/005 (Claude) | Findings found by only one agent (blind spots); `file:line` hit rate of each; NOT_VERIFIED share |
| P2 bounded implementation | T-A1-001 (Codex) | Rework rate on a clearly specified task |
| P3 cross-review | Claude reviews the P2 PR; Codex adversarially reviews the first T-A1-004 Claude fix | Reviewer usefulness: accepted vs rejected findings |

Per-task metrics (fill at merge): findings by severity | accepted / rejected | rework rounds | tests added | CI first pass (n/a until CI exists) | rough usage (sessions, review runs).

| Task | Findings S0/S1/S2/S3 | Accepted/rejected | Rework rounds | Tests added | CI first pass | Usage |
|---|---|---|---|---|---|---|
| (filled during the pilot) | | | | | | |

After P3 the lead proposes changes to the ownership map in `docs/COLLABORATION.md` section 7; the human approves.

---

## 6. Open questions for the human
Status after the human's blanket approval ("do all this") of the summary and its proposals:
1. **F1 wording conflict (blocks T-A1-008): STILL OPEN, provisional default applies.** Spec 1.4 and 5.1 define F1 as capital-inspired with all geometry hypothetical (`ProceduralCapitalProvider`, banner `Fidelity F1: Capital-inspired, synthetic hydraulics`). `CLAUDE.md`, `AGENTS.md`, Adoption Plan G01/G02 and COLLABORATION describe F1 as real capital layout from public sources with inferred pipes (`OsmCapitalProvider`, B1, behind a geometry feasibility test). Until the B1 feasibility test passes, the weaker Spec 1.4 wording is the only claim that is true, and COLLABORATION section 9 says the stricter reading applies until the human decides. So T-A1-008 uses the Spec 1.4 text unless the human rules otherwise. No document text was changed.
2. GitHub auth: DONE (keychain credential for git; `gh` device login for PRs). Branch protection on `dev` and `main` cannot be set from here and was not checked: the human applies it in GitHub settings if the plan allows (PR required, no force push); otherwise it is enforced by discipline.
3. Section 1.2 (freebuff in place) and 1.3/1.4: APPROVED and executed.
4. Codex trust for this project path: **OPEN, human action.** The lead did not edit `~/.codex/config.toml` (an automatic safeguard blocked changes to agent configuration, and the lead does not work around it). Until the entry exists, `.codex/config.toml` is ignored by Codex and user-level settings apply (reasoning effort `high`, which costs more usage). The human adds to `~/.codex/config.toml`:
   ```toml
   [projects."<absolute path of this clone>"]
   trust_level = "trusted"
   ```
   (or accepts the trust prompt on the first interactive `codex` run in this folder). Observed side effect: running `codex exec -C <dir>` or the plugin's `task --cwd <dir>` in a directory made Codex add `[projects."<dir>"] trust_level = "trusted"` to `~/.codex/config.toml` by itself (it did so for the throwaway scratch repo used for the rescue test; that entry points at a temp path and can be deleted). So worktrees where Codex is launched with `-C` are probably trusted automatically, but this means any directory Codex is pointed at gets its `.codex/config.toml` honored: only point Codex at repositories we control. Confirm with a no-flag `codex exec` banner in a worktree (`reasoning effort: medium` means the project config loaded).
5. Codex default effort `medium`: kept (per-run override to `high` for audits and T2).
6. Light dev dependencies for A1 (Vitest, a JSON-Schema-to-TS generator): still ask per card (name and version in the card comments).
7. **Filename collision: RESOLVED.** On macOS (case-insensitive) a file named `docs/progress/claude.md` was auto-loaded as a nested `CLAUDE.md`, i.e. as override-priority instructions. Renamed to `docs/progress/claude-code.md` (matches the `Agent: claude-code` trailer; `codex.md` unchanged) and all references in `AGENTS.md`, `CLAUDE.md`, `docs/COLLABORATION.md`, `docs/COLLAB_PLAN.md`, `docs/PROGRESS.md` updated. Rule for any agent log: never name a file `CLAUDE.md`, `AGENTS.md` or a case variant.
