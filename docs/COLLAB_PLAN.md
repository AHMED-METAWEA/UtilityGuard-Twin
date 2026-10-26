# COLLAB_PLAN: Phase A0 and A1 task cards, pilot, bootstrap record

**Author:** Claude Code (lead). **Status:** v2.1, 2026-10-25: owner decisions recorded (`docs/audit/DECISIONS.md` D-005 to D-008). **Date:** 2026-10-25.
Stance: `freebuff/` is a reference; the target is the Master Spec built fresh (`docs/audit/DECISIONS.md` D-001). Phases: `docs/ADOPTION_PLAN.md` section 9. Protocol: `docs/COLLABORATION.md`. Shared rules: `AGENTS.md`. Milestones: Master Spec section 21.
Tiers: **T0** trivial (CI/check only); **T1** normal (other agent reviews, finding log); **T2** honesty/physics-critical (adversarial review + Appendix E checklist + human glance).
Task cards below are the source of truth; when work starts, each is copied to `docs/tasks/<ID>.md` (status field there).

---

## 1. Repository bootstrap (executed 2026-10-25; this section is the record)

### 1.1 State found before execution
- Local folder was not a git repo. Remote `https://github.com/AHMED-METAWEA/UtilityGuard-Twin` (public) had one "Initial commit" on `main` (8d22e89): `.gitignore` (GitHub Python template) and `README.md`. No tags, no other branches.
- `gh` was not logged in and no `~/.ssh` keys existed, but the system git config uses the macOS keychain helper, which held a working GitHub credential: `git push --dry-run` succeeded, so `main`, the tag and `dev` were pushed with it. `gh` (needed for pull requests) was authenticated by device-code login.

### 1.2 Result
- `main` and `dev` at `debfd51` ("chore: import freebuf baseline"), tag `baseline-freebuf` -> `debfd51`, all pushed. 79 files tracked under `freebuff/`; `freebuff/frontend/src/lib/{api,types}.ts` tracked; nothing untracked-and-unignored left under `freebuff/`.
- The remote's `.gitignore` template ignores every `lib/` directory. Appended before the baseline commit: `!freebuff/frontend/src/lib/`, `.DS_Store`, `freebuff/.freebuff/`.
- Excluded from git by ignore rules (left on disk, nothing deleted; recorded in `docs/audit/DECISIONS.md` D-002): `.venv`, `frontend/node_modules`, `frontend/dist`, `*.log`, `data/utilityguard.db`, `backend/*.egg-info`, `backend/.pytest_cache`, `.freebuff/`, `.DS_Store`.
- Public-repo hygiene scan of all refs and all blobs: clean (`DECISIONS.md` D-004).

### 1.3 Placement of `freebuff/` (decided)
`freebuff/` stays at the repo root as a **reference**, unmodified, and is never edited, moved or deleted by either agent. The new structure is built beside it at the root (Master Spec section 14). Original plan (adopt in place, restructure in A2) is superseded by D-001.

### 1.4 Branches and worktrees
```
main   phase gates only, tagged        dev   integration, PRs only
claude/<phase>-<topic>                 codex/<phase>-<topic>
```
Worktrees live in `~/Desktop/UG-wt/<agent>-<topic>`, each with its own `.venv` (use `python3.11`) and, for Codex, a trust entry in the user's `~/.codex/config.toml` (Codex adds one itself when launched with `-C <dir>`; only point it at repositories we control).
Branch protection on `dev` and `main` is not set (checked read-only). The human applies it in GitHub settings if the plan allows (PR required, no force push); otherwise it is enforced by discipline. The owner merges every pull request and pushes phase tags; agents open PRs, report the link and stop (`DECISIONS.md` D-008).

---

## 2. Phase and milestone mapping

| Phase | Spec milestone | Covers |
|---|---|---|
| A0 Reference inventory and reuse decisions | precedes M0 | Short inventory, pitfalls list, decisions; no code in the new structure |
| A1 Foundation | M0 | Structure per Spec section 14, contracts and generated types, core types, honesty tests, CI, `ug doctor`, shell with banner and badge, ADR stubs |
| A2 | retired | Reused pieces are ported inside B1 |
| B1 to B7 | M1 to M7 | Per Adoption Plan section 9 (cards written when the previous gate passes) |

Spec M0 lists the UI design plan; the Adoption Plan places it in B2. This plan follows the Adoption Plan: A1 ships only a minimal shell. Critical path for credibility (Spec section 21): M0, M1, M3, M4, M5.

---

## 3. Phase A0 cards (Exit gate: `INVENTORY.md`, `PITFALLS.md`, `DECISIONS.md` exist and the human has reviewed them)

| ID | Goal | Owner / Reviewer | Tier | Status and evidence |
|---|---|---|---|---|
| T-A0-001 | Import the baseline unmodified and tag it | claude / codex | T0 | **Done.** Tag `baseline-freebuf` -> `debfd51` on the remote; tracked count equals the on-disk count; `git diff baseline-freebuf -- freebuff` empty; both `src/lib` files tracked (checked on the remote tree) |
| T-A0-002 | Inventory and test-run summary of `freebuff/` (network on for installs only) | codex / claude | T1 | **Done.** `docs/audit/codex_inventory_raw.md`. Lead re-ran the backend tests (34 passed) and checked presets and versions: they match. Short version: `INVENTORY.md` |
| T-A0-003 | Independent read-only audit against the Section 6 checklist (pilot P1, Codex side) | codex / claude | T1 | **Done.** `docs/audit/codex_audit_raw.md` (104 lines). Lead reproduced 3 of 3 sampled claims |
| T-A0-004 | Lead inventory, measurements and pitfalls (pilot P1, Claude side) | claude / codex | T2 | **Done.** `PITFALLS.md` (19 pitfalls, labelled lead-reproduced or Codex-only), `INVENTORY.md` |
| T-A0-005 | Record the stance change and the reuse register; update the plan documents | claude / human | T2 | **In this PR.** `DECISIONS.md` (D-001 to D-005), `ADOPTION_PLAN.md` v2.0, `AGENTS.md`, `CLAUDE.md`, `COLLABORATION.md`, this file |

The earlier cards T-A0-004 to T-A0-006 (deep audit, AUDIT/MAPPING deliverables) were dropped by D-001. Exit: the human reviews and merges this PR; then `dev` is merged to `main` and tagged `phase-A0`.

---

## 4. Phase A1 cards: Foundation (Spec M0)

Everything is built fresh at the repo root; nothing is imported from `freebuff/`. Dependencies are limited to those named in Master Spec section 4.7 (see open question 3); any other package needs approval. Each card lists its pitfall IDs from `docs/audit/PITFALLS.md`. Python 3.11, package folders per Spec section 14; `platform/` is **not** a Python package (D-003).

**Order:** 001 first (single agent). Then, in parallel where owners differ: Claude 002, 003, 005, 008, 012; Codex 006 (after 001), 007 (after 002), 004 (after 002 and 003), 009 (after 001 and 008). Claude 010, then Codex 011. Then 013.

### T-A1-001: Repository skeleton and packaging
Status: **done 2026-10-25** (PR #4 merged; verified from a fresh clone; Codex review: no actionable defects)   Owner: claude   Reviewer: codex   Tier: T1   Branch: `claude/a1-skeleton`   Spec refs: section 14, 4.7
**Goal:** The directory structure of Spec section 14 exists and installs, with `platform/` a plain folder.
**Allowed:** root `Makefile`, root `README.md`, `platform/**`, `domains/**`, `contracts/` (placeholder), `assumptions/` (placeholder), `docs/adr/`, `deploy/`, `.github/`, `frontend/` (placeholder), `scripts/`. **Forbidden:** `freebuff/**`, other `docs/**`, `AGENTS.md`.
**Acceptance:**
- `make install` exits 0 from a fresh clone (Python 3.11): creates `.venv`, installs `ug_core`, `ug_intel`, `ug_api`, `ug_cli` and the water package individually (editable).
- `.venv/bin/python -c "import ug_core, ug_intel, ug_api, ug_cli, ug_water; print('ok')"` prints `ok`.
- `.venv/bin/python -c "import platform, pathlib; assert pathlib.Path(platform.__file__).name == 'platform.py'"` exits 0 (the standard library is not shadowed); `test ! -e platform/__init__.py`.
- `python scripts/check_layout.py` exits 0 and fails when a directory of Spec section 14 is missing.
**Budget:** 1 session. **Escalate if:** the package layout needs a decision that Spec section 14 does not cover (record an ADR).

### T-A1-002: Contracts v1 (JSON Schema)
Status: **merged (PR #12)**, approved by the owner with three conditions, all met: Spec 12.2 updated (PR #14, merged), the conformance test (T-A1-002b, PR #17), the four main decisions explained   Owner: claude   Reviewer: codex   Tier: T2   Branch: `claude/a1-contracts`   Spec refs: sections 11, 12, 2
**Goal:** Versioned, schema-validated contracts for scenario config, run manifest, telemetry reading, stream envelope, evidence record, assumption and incident.
**Allowed:** `contracts/**`, `contracts/examples/**` (valid), `contracts/invalid/**` (one file per rejection reason), `platform/tests/contract/**`. **Forbidden:** anything else.
**Rules baked into the schemas:** every schema requires `schema_version`; `additionalProperties: false`; the telemetry and stream schemas have **no** truth or fault-tag fields (P-01, P-02); the stream envelope requires `stream_source` in `REPLAY|SIMULATED|LIVE` (P-04); every displayable number carries `label` from the nine evidence labels; cost objects require `label: CALCULATED` (P-14); unknown fault types are rejected (P-18).
**Acceptance:** `make test-contracts` passes: every file in `contracts/examples/` validates; every file in `contracts/invalid/` is rejected (names: `missing_schema_version`, `extra_field`, `truth_field_in_telemetry`, `unknown_label`, `unknown_fault_type`, `cost_labelled_simulation`, `missing_stream_source`).
**Budget:** 2 sessions. **Escalate if:** a Spec section 12 payload cannot be expressed without deviating (human decides).

### T-A1-002b: The code's outputs validate against the contracts
Status: **merged (PR #17)**   Owner: claude   Reviewer: codex   Tier: T1   Branch: `claude/a1-contract-conformance`   Spec refs: 12, 10.4
**Goal:** The schemas of `contracts/v1/` and the code that produces their payloads cannot drift apart. `ug_core.Manifest.to_dict()` validates against `run-manifest`; `AssumptionSet.to_dict()` (with `schema_version`) against `assumption-set`; `Evidenced` against `evidence-record` where a mapping exists; `TelemetrySeries` rows against `telemetry-reading`; `Timebase.to_dict()` and the label enums against `common`.
**Allowed:** `platform/tests/contract/test_code_matches_contracts.py` and, only if a payload cannot be produced yet, a small `to_payload()` helper in `platform/ug_core/**`. **Forbidden:** changing a schema (contract change, ask the owner).
**Acceptance:** `make test-contracts` passes with the new tests; a deliberate mutation (a renamed key in `Manifest.to_dict()`, an extra field, a label added to `EvidenceLabel`) makes a test fail. Anything the code cannot produce yet is listed in the PR as a gap, not hidden.
**Budget:** 1 session.

### T-A1-002c: Close the gaps between the code and the contracts
Status: **merged (PR #24)**; two Codex adversarial rounds (3 then 2 findings); the second-round fixes were not reviewed a third time (D-016); the fail-closed unit rule is recorded in D-019   Owner: claude   Reviewer: codex   Tier: T2   Branch: `claude/a1-contract-gaps`   Spec refs: 10.1, 11, 12
**Goal:** `Evidenced`, `Manifest`, `TelemetrySeries` and `AssumptionSet` refuse what the contracts reject, so the API can never build an invalid payload: the money label rule for `Evidenced` (an amount or a price is never SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY, a money value is a number, currencies are written `EGP`), the identifier and unit grammars, git commit format, `schema_version`, output hash format, repeated names, empty formula strings, and empty directly built assumption sets.
**Allowed:** `platform/ug_core/**`, the tests of those types, and `GAPS` in `platform/tests/contract/test_code_matches_contracts.py` (entries are removed, never added). **Forbidden:** changing a schema.
**Acceptance:** `GAPS` contains only the one by-design entry (`Manifest.config` is generic); `test_no_listed_gap_is_stale` and `test_no_unlisted_gap_between_the_code_and_the_contract` pass; `make ci` passes; the honesty suite and its mutation runner still pass.
**Budget:** 1 session.

### T-A1-003: Core types: truth and telemetry separate, evidence labels, manifest
Status: **merged (PR #8)**; core label test tightened to equality (PR #15, merged)   Owner: claude   Reviewer: codex   Tier: T2   Branch: `claude/a1-core-types`   Spec refs: 4.1 P1 and P2, 2, 10, 11
**Goal:** `ug_core` provides the types the rest of the system is built on, so the Honesty Rules are enforced by structure.
**Contents:** `EvidenceLabel` (exactly the nine labels); `Evidenced[T]` (value plus label plus evidence id; cannot be built without a label); `TruthSeries` and `TelemetrySeries` as unrelated types (no shared base; telemetry is created only through a measurement port); `Timebase` (ticks, timestep, time axis: what quality and detectors receive instead of truth, P-03); `Manifest` with a canonical order-independent hash (fault lists in canonical order, P-06) and a documented rounding policy; `finite()` that raises on NaN or infinity instead of returning zero (P-17); `SeedStreams`: named independent random streams derived from the manifest seed, so adding a fault or sensor never changes another stream's noise (P-12).
**Allowed:** `platform/ug_core/**`, `platform/tests/unit/**`. **Forbidden:** `freebuff/**`, contracts (T-A1-002).
**Acceptance:** `pytest platform/tests/unit/test_core_types.py -q` passes, including: `len(EvidenceLabel) == 9` and the names equal the Spec list; building `Evidenced` without a label raises; the manifest hash is equal for two fault lists in different order and differs when any value changes; `finite(float('nan'))` raises; stream `"a"` yields identical values with and without stream `"b"` drawn, and across two processes.
**Budget:** 2 sessions.

### T-A1-004: Honesty tests (written before the code they guard)
Status: **merged (PR #18)**; the lead added one fixture commit so it is green with or without T-A1-002c   Owner: codex (author, non-owner of the guarded modules)   Reviewer: claude   Tier: T2   Branch: `codex/a1-honesty-tests`   Pilot: **P2**   Spec refs: 2, 4.1, 16
**Goal:** A test suite that fails if any pitfall in `PITFALLS.md` is reintroduced in the structure.
**Allowed:** `platform/tests/honesty/**`, `scripts/mutation_check.sh`, `Makefile` target `test-honesty`. **Forbidden:** the modules under test.
**Tests (each names its pitfall ID in the docstring):** truth-leak structural (P-01, P-03): an AST import-graph test shows nothing under `platform/ug_intel/**` or the stream and operator parts of `platform/ug_api/**` imports `TruthSeries`, and their entry points are annotated with `Timebase` and `TelemetrySeries`; payload walker (P-01, P-02): no schema reachable from telemetry, stream or operator contracts has a property named like a `TruthSeries` field or a fault tag (the denylist is derived by introspection so it cannot drift); determinism (P-06): same manifest in two subprocesses gives the same hash, and permuted fault lists give the same canonical hash; label coverage and money labels (P-14): every displayable number in the contracts carries one of the nine labels and cost objects are `CALCULATED`; finite guard (P-17): no `ug_core` path turns NaN or infinity into zero; unknown ids and fault types rejected (P-18).
**Acceptance:** `make test-honesty` passes on the clean tree; `scripts/mutation_check.sh` exits 0, meaning it injected each of three mutations in a temporary copy (an import of `TruthSeries` in `ug_intel`; a truth field added to a telemetry example; a NaN-to-zero conversion) and the suite failed every time.
**Budget:** 2 sessions.

### T-A1-005: DomainAdapter, registry, conformance skeleton, import lint
Status: **merged (PR #10)**   Owner: claude   Reviewer: codex   Tier: T2   Branch: `claude/a1-adapter`   Spec refs: 4.6, 14
**Goal:** Domains plug in through one interface, and `platform/` can never import `domains/`.
**Allowed:** `platform/ug_core/adapter/**`, `platform/ug_core/registry.py` (both under the `src/ug_core/` layout of ADR-011), `platform/tests/conformance/**`, `domains/water/**` (adapter stub, its entry point and `ug-core` dependency only), `scripts/check_imports.py`, `mk/adapter.mk`, unit tests for the interface, registry and lint. **Forbidden:** other domains' logic.
**Acceptance:**
- `make lint-imports` exits 0 on the clean tree and non-zero after a scratch file in `platform/ug_intel/` adds `import ug_water` (mutation shown in the handoff).
- `.venv/bin/python -c "from ug_core.registry import discover; assert 'water' in discover()"` exits 0 (entry-point group `ug.domains`).
- `pytest platform/tests/conformance -q` passes with unimplemented adapter methods reported as strict xfail with a reason, and fails if an unimplemented method silently returns data.
**Budget:** 1 to 2 sessions.

### T-A1-006: CI workflow and `make ci`
Status: **merged (PR #7)** (hosted CI passed; the lead added one fix commit, see D-013)   Owner: codex   Reviewer: claude   Tier: T1   Branch: `codex/a1-ci`   Spec refs: 16, 17
**Goal:** One command (`make ci`) runs exactly what GitHub Actions runs.
**Allowed:** `.github/workflows/ci.yml`, `Makefile` (ci target), tool config in the package `pyproject.toml` files (ruff, mypy, pytest). **Forbidden:** source code of other cards.
**Acceptance:** `make ci` runs lint, type check, unit, contract, honesty, conformance, import-lint and (once 007 lands) contract-drift, and exits 0 locally; `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0; the first run on the PR is green (recorded in the handoff). Only GitHub-owned actions (checkout, setup-python, setup-node), pinned to a major version; no third-party actions.
**Budget:** 1 session.

### T-A1-007: TypeScript type generation and contract-drift check
Status: **merged (PR #16)**   Owner: codex   Reviewer: claude   Tier: T1   Branch: `codex/a1-ts-types`   Spec refs: 12, 16
**Allowed:** `frontend/src/generated/**`, `scripts/gen_types.*`, `scripts/check_contract_drift.sh`, `Makefile` (`gen-types`), `frontend/package.json` (one dev dependency, pinned exactly).
**Dependency (approved, `DECISIONS.md` D-007):** `json-schema-to-typescript@16.0.0` (MIT, published 2026-08-28, not deprecated, Node >=16, 8 runtime dependencies). Registry integrity `sha512-Ah6kK4q6SjlMzWBH1eNOQkdRh5Qhr5T/RCFwfjQqWZA7UDW+N47A8wfyoiN0L884s4L4bAEI54IjIuN3/u0B/A==`; the executor verifies that the lockfile entry matches before committing and runs `npm audit` on the result, reporting findings in the handoff. A different package or version needs the owner's approval.
**Acceptance:** `make gen-types && git diff --exit-code frontend/src/generated` exits 0 on a clean tree; editing one schema without regenerating makes `scripts/check_contract_drift.sh` exit non-zero (mutation shown in the handoff).
**Budget:** 1 session.

### T-A1-008: WNTR API manifest by introspection
Status: **merged (PR #9)** (two Codex adversarial rounds, 3 defects found and fixed, 22 tests). Follow-up card **T-A1-008b** below.   Owner: claude   Reviewer: codex   Tier: T1   Branch: `claude/a1-wntr-manifest`   Spec refs: 4.7, M0 (`ug doctor`)
**Goal:** A generated list of every WNTR symbol the new code may use, each with its signature in the installed version, so wrong API usage fails a check instead of a run. The introspection method is the one used in the A0 inventory; the 43 symbols verified there are the starting set (logged as ADAPT in `DECISIONS.md`).
**Allowed:** `domains/water/**/wntr_api_manifest.json`, `scripts/gen_wntr_manifest.py`, and (added during the work, D-010) `domains/water/src/ug_water/wntr_api.py` (the logic, so `ug doctor` reaches it through the adapter), `domains/water/tests/**`, `mk/wntr.mk`, the WNTR dependency in `domains/water/pyproject.toml`. **Forbidden:** solver code.
**Acceptance:** `python scripts/gen_wntr_manifest.py --check` exits 0 on the installed WNTR; the manifest records `wntr.__version__` and at least 40 symbols; renaming one symbol in a temporary copy makes `--check` exit non-zero naming it.
**Budget:** 1 session.

### T-A1-008b: The water adapter reports its environment health
Status: **merged (PR #23)**; Codex T1 review logged after the merge in `docs/reviews/T-A1-008b.md`   Owner: claude   Reviewer: codex   Tier: T1   Branch: `claude/a1-water-health`   Spec refs: 4.6, M0 (`ug doctor`)
**Goal:** `ug doctor` can ask a domain whether its environment is sound without `platform/` importing `domains/`: `WaterAdapter.health_checks()` (the optional `HasHealthChecks` hook of ADR-004) runs the WNTR manifest check.
**Allowed:** `domains/water/src/ug_water/adapter.py`, `domains/water/tests/test_adapter_health.py`. **Forbidden:** `platform/**`, the manifest itself.
**Acceptance:** `discover()["water"]` satisfies `HasHealthChecks`; `health_checks()` returns `HealthCheck` objects including `wntr_api_manifest` (ok, with the WNTR version and symbol count in the detail) and `wntr_version`; with a manifest edited in a temporary copy (a symbol renamed) the check is not ok and its detail names the symbol; the conformance suite and `make ci` still pass.
**Budget:** small.

### T-A1-014: Browser test: the built shell makes no outside request
Status: **PR #27 open** (Tier 1, but it adds the dependency approved in D-017, so the owner merges it under D-018)   Owner: claude   Reviewer: codex   Tier: T1   Branch: `claude/a1-browser-test`   Spec refs: P10 (offline-first), 16
**Dependency, stated before installing (as the owner required):** `@playwright/test` **1.64.0** (npm; Apache-2.0; published 2026-10-07; Node >=20; not deprecated). One runtime dependency, `playwright@1.64.0`, which depends on `playwright-core@1.64.0` (same licence and date); `fsevents` is an optional macOS-only extra. Installed in `frontend/` as an exact-pinned dev dependency, with `ignore-scripts=true` (`frontend/.npmrc`) and `npm audit` reported in the PR. **It also downloads a browser:** `npx playwright install chromium` fetches the Chromium build that matches 1.64.0 (about 150 to 200 MB) from Playwright's download host into the user cache (`~/Library/Caches/ms-playwright` on macOS), outside the repository; on the hosted runner CI uses `--with-deps` (apt packages for the browser). Nothing is downloaded at application run time; this is development tooling only.
**Goal:** Prove in a real browser what the static scan and the Content-Security-Policy only claim: the built shell makes no request to any other origin.
**Allowed:** `frontend/e2e/**`, `frontend/playwright.config.ts`, `frontend/package.json` and `package-lock.json` (the one dependency), `frontend/tsconfig.json` (include the test folder), `mk/browser.mk`, `.github/workflows/ci.yml` (one browser install step). **Forbidden:** shell behaviour (`frontend/src/**`).
**Behaviour (one spec file):** serve `frontend/dist` with `vite preview` on a loopback port; open the shell, visit every route; record every request, WebSocket and EventSource: all are same-origin and none is a WebSocket; the honesty notice, badge and stream source are visible; then inject a script that tries `fetch`, `new Image()`, a `<link rel=stylesheet>`, `WebSocket` and `navigator.sendBeacon` to an `.invalid` host and assert the browser reports a Content-Security-Policy violation for each and sends nothing.
**Acceptance:** `make test-browser` passes in a fresh clone (after `make browser-install`); mutating the page in a temporary copy (an `<img src="https://example.invalid/x">`, a font stylesheet link, a `fetch` of an outside URL in `main.tsx`) makes it fail naming the request; removing the CSP tag makes the injected-request step fail; `make ci` includes it; hosted CI passes.
**Budget:** 1 session.

### T-A1-009: `ug` CLI skeleton and `ug doctor`
Status: **merged (PR #25)** (lead review by running and mutating the code, see `docs/reviews/T-A1-009.md`)   Owner: codex   Reviewer: claude   Tier: T1   Branch: `codex/a1-ug-cli`   Spec refs: 14, M0
**Allowed:** `platform/ug_cli/**`, `platform/tests/unit/test_cli.py`. Standard library only (`argparse`); no new dependency.
**Behaviour:** `ug --version`; `ug doctor` checks Python version, WNTR version and every manifest symbol signature, that every file in `contracts/` is a valid JSON Schema, and (warning only) Node version; `run`, `reproduce`, `eval`, `import`, `export` exist as stubs that print "not implemented" and exit 2.
**Acceptance:** `.venv/bin/ug doctor` exits 0 here; with a manifest edited in a temporary copy it exits 1 and the message names the symbol; `ug doctor --json` prints valid JSON (`python -m json.tool` accepts it).
**Budget:** 1 session.

### T-A1-010: Shell skeleton: honesty banner, Fidelity badge, stream-source indicator
Status: **merged (PR #19)**; the offline check fix for the combination with #16 is PR #21   Owner: claude   Reviewer: codex   Tier: T2   Branch: `claude/a1-shell`   Spec refs: 1.4, 2 (rules 1 and 2), 13   Pitfalls: P-04, P-17
**Allowed:** `frontend/src/app/**`, `frontend/src/ui/**` (minimal tokens only), `frontend/index.html`, `frontend/package.json`, test config. Packages named in Spec section 4.7 only (React, TypeScript, Vite, Vitest, Testing Library). **Forbidden:** the full design system and map engine (B2).
**Behaviour:** permanent banner and Fidelity badge. The badge shows the level of the network actually loaded (Master Spec 1.4): `No network loaded` in A1, `Fidelity F0: Generic synthetic` for the procedural fallback, and `Fidelity F1: Public capital layout, inferred pipes, synthetic hydraulics` only for a network whose geometry carries `PUBLIC_GEOMETRY` provenance. The stream-source indicator reads `REPLAY|SIMULATED|LIVE` from the stream envelope type and defaults to `REPLAY`; loading and error states render the same banner. All UI strings are English and live in one module (no literals scattered through components), so the Arabic translation can be added later (`AGENTS.md` Language).
**Acceptance:** `make test-frontend` passes: a component test renders the shell at every route, in the loading state and in the error state, and asserts banner, badge text (`No network loaded` with no network; the F1 text only when the network declares F1 provenance) and indicator are present each time; `LIVE` is never shown unless the envelope says so; `grep -RIn "https\?://" frontend/index.html frontend/dist | grep -viE "localhost|127.0.0.1|w3.org"` prints nothing (offline-first).
**Budget:** 1 to 2 sessions.

### T-A1-011: Deploy: API skeleton, Docker Compose, `make up`
Status: **merged (PR #26)** (lead review, run in Docker, see `docs/reviews/T-A1-011.md`)   Owner: codex   Reviewer: claude   Tier: T1   Branch: `codex/a1-deploy`   Spec refs: 4.4, 17, M0
**Goal:** `make up` serves the built shell offline with a minimal API (`/api/health` returning version and the honesty disclaimer).
**Allowed:** `deploy/**`, `mk/deploy.mk` (the root Makefile is not edited; targets register through `mk/*.mk`), `platform/ug_api/**` (skeleton only; it never imports a domain). **Forbidden:** domain logic, `frontend/**` (owned by the shell card).
**Acceptance:** `docker compose -f deploy/docker-compose.yml config` exits 0; `make up` builds and serves the shell; `curl -s localhost:<documented port>/` returns the page whose `<title>` is `UtilityGuard Twin` and whose `Content-Security-Policy` meta tag is present, and the served bundle contains the strings `No network loaded` and the honesty statement (the shell is rendered by JavaScript, so the page text is not in the HTML); `curl -s localhost:<port>/api/health` returns JSON with `schema_version`, the version and the honesty disclaimer; `make down` stops it; the built image makes no external request at runtime (`frontend/scripts/check-offline.mjs` passes on the served files, and the page must keep working under its CSP, which allows only same-origin requests, so the API is served from the same origin).
**Budget:** 1 to 2 sessions.

### T-A1-012: ADR stubs and the `assumptions/` format
Status: **merged (PR #11)**   Owner: claude   Reviewer: codex   Tier: T1   Branch: `claude/a1-adr-assumptions`   Spec refs: Appendix A and D
**Allowed:** `docs/adr/**`, `assumptions/v1.yaml`, `platform/ug_core/assumptions.py` (under `src/ug_core/`), `platform/tests/unit/test_assumptions.py`, `platform/tests/unit/test_adr_stubs.py`, the `pyyaml` dependency of `ug_core`.
**Acceptance:** ten files `docs/adr/ADR-001-*.md` to `ADR-010-*.md` exist with the titles from Spec Appendix D; `pytest platform/tests/unit/test_assumptions.py -q` passes: `assumptions/v1.yaml` loads; every entry has unit, distribution, `verified` and `source_note`; a missing `verified`, `min > mode`, or an unknown key is rejected; all shipped values are `verified: false` placeholders.
**Budget:** 1 session.

### T-A1-013: A1 exit-gate review
Status: **closed 2026-10-26** (two Codex rounds, `docs/reviews/T-A1-013.md`; #31 merged `7d06056`; `dev` merged into `main` as `daf6634`, tag `phase-A1`; D-022)   Owner: codex (review) and claude (review of Codex PRs)   Reviewer: human   Tier: T2
**Command:** `/codex:adversarial-review --base phase-A0 --background truth or hidden fault tags reaching telemetry, the stream, detectors or decisions; nondeterminism; numbers displayed without an evidence label; invented probabilities; double counting in cost lines; contract drift; NaN converted to zero`
**Acceptance:** findings logged in `docs/reviews/T-A1-013.md` (severity, evidence, decision, fixing commit); no S0 or S1 open; from a fresh clone `make install && make ci` is green, `make up` serves the shell with badge and banner, `ug doctor` exits 0, `make test-honesty` and `scripts/mutation_check.sh` pass; the human approves, then `dev` merges to `main` with tag `phase-A1`.

---

## 5. Pilot and metrics (COLLABORATION section 11)

| Pilot | Cards | Result or what is compared |
|---|---|---|
| P1 independent look at the reference | T-A0-003 (Codex, read-only) and T-A0-004 (lead) | **Done** (`PITFALLS.md` section 4): found by both: truth reaching decisions, missing or wrong labels, missing honesty indicators; only by the lead (all measured): fault onset lag, false alarms under forecast error, localization 0/2, tank starvation, unused assumption, incident fragmentation; only by Codex (static reading): hidden faults in the operator tab, ramp producing no leak, fault-order nondeterminism, both pumps closed on standby switch, NaN to zero. 3 of 3 sampled Codex claims reproduced. The union was far more useful than either audit alone |
| P2 bounded implementation | T-A1-004 (Codex) | Rework rate on a clearly specified task |
| P3 cross-review | Claude reviews the P2 PR; Codex adversarially reviews T-A1-003 | Reviewer usefulness: accepted vs rejected findings |

Per-task metrics (fill at merge): findings by severity | accepted / rejected | rework rounds | tests added | CI first pass | rough usage (sessions, review runs).

| Task | Findings S0/S1/S2/S3 | Accepted/rejected | Rework rounds | Tests added | CI first pass | Usage |
|---|---|---|---|---|---|---|
| T-A0-002 + T-A0-003 (Codex runs) | n/a | 3 of 3 sampled claims reproduced | 0 | 0 | n/a | 2 Codex runs |
| (A1 rows filled during the pilot) | | | | | | |

After P3 the lead proposes changes to the ownership map in `docs/COLLABORATION.md` section 7; the human approves.

---

## 6. Open questions for the human
1. **F1 wording (D-005): RESOLVED.** Owner ruling: F1 is the real public layout of the capital with inferred pipes and synthetic hydraulics. The Spec change is PR #3 (merged). The `PUBLIC_GEOMETRY` line was approved by the owner and is PR #6 (open): Spec section 2 then lists nine labels.
2. **Branch protection** on `dev` and `main`: the owner sets it (D-009). With #7 merged, the `ci` check can be made required.
3. **Dependencies for A1: APPROVED (D-007).** The packages Master Spec section 4.7 names, plus `json-schema-to-typescript@16.0.0` (details in T-A1-007). Anything else asks first.
4. **Commit email.** Every commit, including the "Initial commit" GitHub created from your account, carries your GitHub account email in its metadata, which is public. History is not rewritten. Optional: turn on "Keep my email addresses private" in GitHub settings and set a no-reply address as `user.email` for new commits. I will not change git identity without your OK.
5. **Codex trust and effort.** Trust for the main clone is in place. Codex adds an entry for any directory it is launched in; a stale entry for a throwaway scratch repo exists in `~/.codex/config.toml` and can be deleted. Default reasoning effort stays `medium` (raised per run for T2 reviews).
