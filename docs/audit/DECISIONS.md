# DECISIONS

Every change of stance, every reuse from `freebuff/`, and every proposed deletion is recorded here with a reason. Nothing is deleted without approval. Honesty Rules and contracts are never changed through this file.

## Decisions

### D-001: `freebuff/` is a reference, not the foundation (2026-10-25)
- **Decision:** `freebuff/` is kept as a reference to see what was tried, take ideas from, and learn which traps to avoid. The target is the Master Spec, built fresh at the repo root (`platform/`, `domains/water/`, `contracts/`, `assumptions/`, ...). We do not depend on `freebuff/`, shape the architecture around it, or preserve its structure or behavior. A piece is reused only if it passes review and is better than writing it new; each reuse is logged in the reuse log below.
- **Replaces:** the v1.0 stance "adopt the existing code, audit it, fix it in place, restructure in A2".
- **Reasons:**
  1. Direction from the human owner: the goal is a better system than freebuf produced.
  2. Evidence from the A0 inventory (`PITFALLS.md`): the baseline has S0 defects in exactly the areas the Honesty Rules protect (truth reaching decisions, fault onset one tick late, non-deterministic fault order, a short ramp producing no leak, both pumps closed on a standby switch, false-alarm results true only by construction, mislabelled and unused assumptions). Fixing in place would first require pinning the behavior of code we then change.
  3. Structure: flat `backend/app` modules, one hypothetical F0 grid, no contracts, no adapter interface, a different stream envelope. The Spec's architecture (platform/domains split, evidence kernel, design grid, manifest) is a different shape, so "restructure" would amount to a rewrite.
  4. Cost: a deep line-by-line audit of code we may not use wastes usage on two limited subscriptions.
- **What was good and stays available as ideas:** see `PITFALLS.md` section 2 (leak by pipe split, orifice law, cost-line shape, break-even wording, `unknown` diagnosis and strength labels, canonical-JSON hash).
- **Consequences:** phases revised (A0 = short inventory and reuse decisions; A1 = foundation built fresh; A2 retired; reused pieces are ported inside B1); golden tests only for reused pieces; task cards rewritten; `ADOPTION_PLAN.md`, `AGENTS.md`, `CLAUDE.md`, `COLLABORATION.md`, `COLLAB_PLAN.md` updated in the same PR.
- **Approved by:** the human owner, 2026-10-25 (revised phase list approved before the files were changed).

### D-002: Baseline import and ignore rules (2026-10-25)
- `freebuff/` was committed unmodified (`debfd51`) and tagged `baseline-freebuf`. It stays at the repo root as reference and is not edited, moved or deleted.
- Left on disk but excluded from git by ignore rules (nothing deleted): `.venv`, `frontend/node_modules`, `frontend/dist`, `*.log`, `data/utilityguard.db`, `backend/*.egg-info`, `backend/.pytest_cache`, `.freebuff/`, `.DS_Store`.
- The remote's Python-template `.gitignore` ignored every `lib/` directory, which would have dropped `freebuff/frontend/src/lib/`; re-included explicitly (`!freebuff/frontend/src/lib/`).
- **Files proposed for deletion:** none.

### D-003: `platform/` is not a Python package (2026-10-25)
- A top-level package named `platform` would shadow the standard-library module. `platform/` is a plain folder; `ug_core`, `ug_intel`, `ug_api` and `ug_cli` are installed individually. Approved by the human owner.

### D-004: Public repository hygiene check (2026-10-25)
- Scanned every blob reachable from every ref of the public GitHub repository (fresh mirror clone: `main`, `dev`, the docs branch, the PR ref, the tag; 81 unique files, 1.38 MB): no private-key blocks, cloud or GitHub or Slack or Google or OpenAI-style keys, JWTs, credentials in URLs, secret-like assignments, email addresses, local user paths or IP addresses in file contents; the only high-entropy hits were code identifiers. The one binary (`freebuff/screenshots/dashboard.png`) was viewed and has no embedded text metadata (chunks: IHDR, IDAT, IEND, iCCP only).
- Known and accepted: the commit author email (the owner's GitHub account email) appears in git commit metadata, including the "Initial commit" GitHub created from the owner's account. History is not rewritten. See `COLLAB_PLAN.md` section 6 for the optional no-reply address setting.
- Not covered by the scan: GitHub repository settings and secrets (none are used), and anything on the owner's machine outside the repository.

### D-005: Meaning of fidelity F1 and the banner wording (2026-10-25, resolved by the owner)
- **Ruling (owner):** F1 is the real public layout of the capital (real districts and roads from public sources, inferred pipes, synthetic hydraulics). It is not ACUD's network and not a survey of it.
- **Applied:** Master Spec sections 1.4 and 5.1 rewritten in PR #3 (merged 2026-10-25): F1 geometry carries provenance and the `PUBLIC_GEOMETRY` label; the procedural generator becomes the F0 fallback and test fixture; the F1 provider is `OsmCapitalProvider` (Phase B1, after a geometry feasibility test). Banner text: `Fidelity F1: Public capital layout, inferred pipes, synthetic hydraulics`.
- **Added by the lead in PR #3 (merged without change, so recorded as accepted):** the badge states the level of the network actually loaded and never claims a higher one, so the A1 shell shows `No network loaded` until a network exists.
- **Still open (one line):** Spec section 2 lists eight evidence labels, `AGENTS.md` nine (adds `PUBLIC_GEOMETRY`). Recommended: add `PUBLIC_GEOMETRY` to Spec section 2. Card T-A1-003 assumes nine.

### D-006: Language convention (2026-10-25)
- English for all code, identifiers, scenario and fault names, data schemas, contracts, tests, documentation and the default UI. Arabic is a UI translation (i18n with full RTL) added later, as Master Spec section 13 describes, and never appears in identifiers, schemas, data keys or scenario names. Ideas taken from non-English sources are translated into English naming first. Rule added to `AGENTS.md`.

### D-007: Dependencies approved for Phase A1 (2026-10-25)
- Approved once by the owner: the packages Master Spec section 4.7 names. Python: pydantic v2, FastAPI, uvicorn, numpy, WNTR, PyYAML, jsonschema, pytest, hypothesis, ruff, mypy. Frontend: React 18, TypeScript, Vite, Vitest, Testing Library, and the type generator below. Versions are pinned exactly through lockfiles. Anything else asks first.
- Type generator, named before installation (card T-A1-007): `json-schema-to-typescript@16.0.0`, MIT licence, published 2026-08-28, not deprecated, Node >=16 (this machine runs 22.15.1), single maintainer, 8 runtime dependencies (lodash, js-yaml, minimist, prettier, tinyglobby, @apidevtools/json-schema-ref-parser, @types/lodash, @types/json-schema), registry integrity `sha512-Ah6kK4q6SjlMzWBH1eNOQkdRh5Qhr5T/RCFwfjQqWZA7UDW+N47A8wfyoiN0L884s4L4bAEI54IjIuN3/u0B/A==` (the lockfile entry must match). Looked up read-only on 2026-10-25; nothing installed yet.

### D-008: Merge and release process (2026-10-25)
- The owner reviews and merges every pull request, pushes phase tags, and sets branch protection on `dev` and `main`. Agents open PRs, report the link and stop. A phase tag is created locally by the lead after the owner's merge, and pushed only after the owner says so. Rule added to `AGENTS.md` and `COLLABORATION.md`. **Partly replaced by D-018 (2026-10-26):** the lead may now merge Tier 0 and Tier 1 PRs into `dev` under conditions; everything else in this entry stands.

### D-009: Owner answers to the open questions (2026-10-25)
- The phase-A0 tag push is approved (done: `phase-A0` is on the remote at the merge commit `506e578`). The build backend `setuptools>=68` is accepted. The badge guard is accepted: the Fidelity badge shows the level of the network actually loaded (`No network loaded` in A1). `PUBLIC_GEOMETRY` is added to Master Spec section 2 so it lists nine labels, and the Spec section 11.2 line is fixed so `fault_tag_hidden` lives only in `truth.parquet` (both in PR #6, open). The owner sets branch protection.

### D-010: WNTR API manifest (T-A1-008): method adapted, no freebuff code copied
- The A0 inventory verified 43 WNTR symbols by introspection of WNTR 1.5.0. The manifest (PR #9) applies the same method to an explicit, reviewed list of 49 symbols (14 callables with signatures, 29 attributes of a probe network, 6 simulation result columns) and covers every WNTR name the freebuff code used (checked by grep). The logic lives in `ug_water.wntr_api`, not in `platform/`, so `ug doctor` reaches it through the domain adapter without breaking the import rule. No freebuff source was copied, so the reuse log below stays empty.

### D-011: Additions and deviations in Wave 1 that need the owner's acceptance
- **PR #10 (adapter):** an optional `HasHealthChecks` hook outside the Spec's `DomainAdapter` interface, so `ug doctor` can ask a domain about its environment.
- **PR #12 (contracts), listed in its description:** the tick payload gains required labels, formula references and versions; the evidence record gains an optional `kind` and a `reason` for `INSUFFICIENT_EVIDENCE`; v1 specifies the `tick` frame only; fault parameter names are the lead's reading of Spec 5.4; hand-written schemas are the source of truth in A1 (Spec 12 says generated from pydantic); units and keys are closed grammars. The owner approved #12 with three conditions: update Spec 12.2 to the stricter tick payload (PR #14), make the test that `to_dict()` outputs validate against the schemas the first Wave 2 task (card T-A1-002b), and have the four main decisions explained in plain words. Wave 2 does not start until the owner confirms that all Wave 1 PRs are merged.
- **PR #11 (assumptions):** `verified: true` is checked for hygiene only (a human reviews each verified entry); a structured source field would be a Spec change, left to the owner.

### D-012: What the two-round review limit produced in Wave 1
- Every Wave 1 card by the lead needed both Codex adversarial rounds, and round 2 found new defects each time: core types 6 then 2, adapter 4 then 3, WNTR manifest 2 then 1, assumptions 3 then 2, contracts 5 then 4. Each finding was reproduced before it was fixed, with the regression test written first. The fixes made after round 2 have **not** had a third review (the limit is two). The A1 exit-gate review (T-A1-013) must review exactly this code again. Hits per round suggest budgeting two review rounds per T2 card from the start.

### D-013: A lead fix inside a Codex pull request
- The new import lint (PR #10) found that `platform/tests/unit/test_smoke.py` in Codex's CI pull request (#7) imported `ug_water`, which the architecture rule forbids. The lead's original review of #7 missed it. The lead added one commit to #7 (marked `Agent: claude-code`, with a PR comment) rather than leaving the combination broken. Precedent: a fix to a Codex branch before merge is allowed when a check the lead owns finds the problem, and it is announced on the pull request.

### D-014: Frontend and tooling dependencies added in Wave 2 (approved list, exact pins)
- **Frontend (PR #19), the Master Spec 4.7 list:** react and react-dom 18.3.1, typescript 6.0.3, vite 8.3.4, vitest 5.0.3, jsdom 29.1.1, @testing-library/react 16.3.3 and @testing-library/dom 10.4.2, @types/react 18.3.31 and @types/react-dom 18.3.7. All at least 14 days old, MIT except TypeScript (Apache-2.0), none deprecated. 122 packages in the tree, all from registry.npmjs.org with integrity hashes, `npm audit`: 0 vulnerabilities. `frontend/.npmrc`: `ignore-scripts=true` and `legacy-peer-deps=true`. The second is needed because npm 10.9.2 crashes ("reading 'edgesOut'") on the vitest peer graph; `npm ci` from the lockfile works without it. jsdom is held at 29.x because 30 needs Node 22.22 and this machine has 22.15. No router library: hash routes (react-router is not on the approved list).
- **Type generator (PR #16), D-007:** `json-schema-to-typescript@16.0.0` in its own tool folder `scripts/types/` (15 packages, 0 vulnerabilities, integrity equal to the approved value), kept out of the app's dependency tree. Installed by the lead with `--ignore-scripts` because Codex has no network.
- **CI (PR #19):** `actions/setup-node@v7` (GitHub-owned) added to the workflow so the frontend and type checks run on the hosted runner; Node 22.
- **`.gitignore`:** `node_modules/`, `frontend/dist/`, `*.tsbuildinfo` (the Python template does not cover Node).

### D-015: Acceptance texts that could not be met as written
- **T-A1-011:** the card required `curl localhost/ | grep "Fidelity F1"`. The shell is rendered by JavaScript, so the served HTML holds no badge text, and the badge correctly says `No network loaded` until a network is loaded (D-005). The card now checks the title, the Content-Security-Policy tag and the strings in the bundle.
- **T-A1-010:** the card's grep for external URLs in `frontend/dist` prints nothing only because React's bundle puts its one inert message string on a line that also holds `w3.org`. The gate is `frontend/scripts/check-offline.mjs` (browser-like URL normalisation, exact namespace exemptions, and a strict Content-Security-Policy on the built page).
- **T-A1-007:** the card put the generator in `frontend/package.json`; it lives in `scripts/types/` instead so the two Wave 2 cards (007 and 010) did not edit the same package file and lockfile.

### D-016: Code fixed after review round 2 and not reviewed again (running list)
- Wave 1: core types (#8), WNTR manifest (#9), adapter and import lint (#10), assumptions (#11), contracts (#12).
- Wave 2: conformance tests (#17), honesty suite (#18, the stream-independence test and mutation), shell (#19). Every one of these cards needed both rounds and found something new in the second. T-A1-013 (the A1 gate review) must review exactly this code, and `docs/reviews/` has one log per task listing the findings.
- Wave 3: contract-gap closure (#24: the second-round fixes, i.e. the fail-closed physical-unit rule and the `asd_` evidence-id namespace, had tests and mutation runs but no third Codex round); the CLI and deploy cards (#25, #26) were reviewed by the lead only (Codex authored them). T-A1-013 must cover these too.

### D-017: Owner approvals of 2026-10-25 (end of Wave 2)
- T-A1-002c (close the 23 gaps between code and contracts) is approved. The frontend dependency set, the `legacy-peer-deps` workaround and `actions/setup-node@v7` are approved (D-014). The corrected T-A1-011 acceptance text is approved (D-015).
- **Playwright is approved as a pinned dev dependency, for one browser test** in Wave 3 (card T-A1-014): `@playwright/test` 1.64.0 (Apache-2.0, published 2026-10-07). The card states the exact name, version, its one runtime dependency and the browser download before installation, as the owner required. Anything else asks first.
- Lesson: a merge preview must run `make ci` on the merged result, not only look for conflicts. `dev` was red for a short time after #16 and #19 were merged together (generated types quoting "WebSocket" tripped the offline check); fixed by PR #21.

### D-018: Standing merge rule for the lead agent (2026-10-26, owner)
- Replaces "agents never merge" (D-008) for this case only. The lead agent (Claude Code) may **squash-merge a pull request into `dev` itself** when ALL of these hold: hosted CI is green; the cross-review is logged in `docs/reviews/`; the PR is Tier 0 or Tier 1; and it does not touch `contracts/`, `assumptions/`, the Honesty Rules text, the Master Spec, dependencies, or deletions.
- The lead may NOT merge Tier 2 PRs, anything into `main`, or push tags: it lists them for the owner. It never bypasses a red or pending check and never force-pushes `dev`.
- Safety net after every merge the lead makes: pull `dev`, run `make ci` in a fresh clone of `dev` (not the working tree), and confirm hosted CI on `dev` is green. If either fails the lead stops merging at once, does not push to `dev`, opens a revert or fix PR and reports. One PR at a time; verify before the next.
- The records PR that carries this decision is Tier 0 and the lead may merge it once it is green. Codex does not merge (the owner's text names the lead only). Rule written into `AGENTS.md` (Working agreement) and `COLLABORATION.md` (5.2, 5.3, 7 step INTEGRATE, and a short section).

### D-019: Decisions taken in Wave 3 (2026-10-25 and 2026-10-26)
- **Fail-closed money rule (PR #24, Tier 2).** Reading currency spellings was bypassed in every Codex round (`E-G-P/m3`, `CAD`, then `CAD.m^-3`). A value labelled SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY must therefore carry a unit built from `ug_core.grammar.PHYSICAL_UNIT_ATOMS` (with metric prefixes and exponents), or it is refused; a new physical unit is added there in a reviewed change. This is stricter than the contract for those four labels (the contract text already says the code catches what its recogniser does not list); no contract file changed. The owner merged #24 with this rule in place; if the owner prefers the spelling reader alone, the lead removes the vocabulary check. A currency in no list at all and a lenient label (ASSUMPTION, OBSERVED, ...) is still not recognised by spelling.
- **Evidence ids.** A long assumption-set id or name gives a shortened evidence id `asd_<name start>-<32 hex digest>`; natural ids start `as_`, so the two namespaces cannot collide.
- **Deployment (PR #26).** Base images `node:22-slim` and `python:3.11-slim` are pinned by digest (the multi-architecture index digests read on 2026-10-25); they do not receive security updates until someone changes the digest. Runtime dependencies `fastapi 0.143.0` and `uvicorn 0.54.0` (and transitive packages) are installed with `--require-hashes` from `deploy/requirements-api.lock`. The container is hardened (non-root uid 10001, read-only root, `cap_drop: ALL`, loopback-only port) but not firewalled: offline behaviour is checked by the shell CSP and the smoke gate, not enforced by the network.
- **Browser test (PR #27).** `@playwright/test` 1.64.0 was installed as approved in D-017 (exact pin, `npm audit` 0 vulnerabilities, three packages added); Chromium (about 100 MB) is downloaded into the user cache, and hosted CI installs it with `--with-deps`. Because it adds a dependency, the lead does not merge it (D-018).
- **Process.** Codex cannot commit from its sandbox, so the lead commits reviewed Codex work with the `Agent: codex` trailer. The lead added tests where a mutation survived (CLI: the `FAIL` prefix, a repeated schema `$id`, an unresolvable `$dynamicRef`; deploy: the launcher defaults). Mistake to correct: the commit message of the CLI commit says 28 of 29 mutations were caught by Codex's tests; the right number is 25 (the PR text was corrected; the merged commit is not rewritten).
- Lesson: after each owner merge the open PRs that append to `docs/progress/codex.md` conflict again (three rebases this wave, always keep both sections). Each agent's handoff could go to its own file per task to stop this; proposed, not changed.

## Reuse log (REUSE and ADAPT only)

No reuse has been decided yet. Candidates and likely verdicts are in `ADOPTION_PLAN.md` section 8. A line is added here, in the same PR that brings the code in, with: date, source file and lines in `freebuff/`, what was reused, verdict (REUSE or ADAPT), target path, tests added (including golden tests for the reused behavior), reviewer, and why it is better than writing it new.

| Date | Source (`freebuff/`) | What | Verdict | Target | Tests | Reviewer | Why |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
