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
- **Applied:** Master Spec sections 1.4 and 5.1 rewritten in PR #3: F1 geometry carries provenance and the `PUBLIC_GEOMETRY` label; the procedural generator becomes the F0 fallback and test fixture; the F1 provider is `OsmCapitalProvider` (Phase B1, after a geometry feasibility test). Banner text: `Fidelity F1: Public capital layout, inferred pipes, synthetic hydraulics`.
- **Added by the lead, for the owner's confirmation in PR #3:** the badge states the level of the network actually loaded and never claims a higher one, so the A1 shell shows `No network loaded` until a network exists.
- **Still open (one line):** Spec section 2 lists eight evidence labels, `AGENTS.md` nine (adds `PUBLIC_GEOMETRY`). Recommended: add `PUBLIC_GEOMETRY` to Spec section 2. Card T-A1-003 assumes nine.

### D-006: Language convention (2026-10-25)
- English for all code, identifiers, scenario and fault names, data schemas, contracts, tests, documentation and the default UI. Arabic is a UI translation (i18n with full RTL) added later, as Master Spec section 13 describes, and never appears in identifiers, schemas, data keys or scenario names. Ideas taken from non-English sources are translated into English naming first. Rule added to `AGENTS.md`.

### D-007: Dependencies approved for Phase A1 (2026-10-25)
- Approved once by the owner: the packages Master Spec section 4.7 names. Python: pydantic v2, FastAPI, uvicorn, numpy, WNTR, PyYAML, jsonschema, pytest, hypothesis, ruff, mypy. Frontend: React 18, TypeScript, Vite, Vitest, Testing Library, and the type generator below. Versions are pinned exactly through lockfiles. Anything else asks first.
- Type generator, named before installation (card T-A1-007): `json-schema-to-typescript@16.0.0`, MIT licence, published 2026-08-28, not deprecated, Node >=16 (this machine runs 22.15.1), single maintainer, 8 runtime dependencies (lodash, js-yaml, minimist, prettier, tinyglobby, @apidevtools/json-schema-ref-parser, @types/lodash, @types/json-schema), registry integrity `sha512-Ah6kK4q6SjlMzWBH1eNOQkdRh5Qhr5T/RCFwfjQqWZA7UDW+N47A8wfyoiN0L884s4L4bAEI54IjIuN3/u0B/A==` (the lockfile entry must match). Looked up read-only on 2026-10-25; nothing installed yet.

### D-008: Merge and release process (2026-10-25)
- The owner reviews and merges every pull request, pushes phase tags, and sets branch protection on `dev` and `main`. Agents open PRs, report the link and stop. A phase tag is created locally by the lead after the owner's merge, and pushed only after the owner says so. Rule added to `AGENTS.md` and `COLLABORATION.md`.

## Reuse log (REUSE and ADAPT only)

No reuse has been decided yet. Candidates and likely verdicts are in `ADOPTION_PLAN.md` section 8. A line is added here, in the same PR that brings the code in, with: date, source file and lines in `freebuff/`, what was reused, verdict (REUSE or ADAPT), target path, tests added (including golden tests for the reused behavior), reviewer, and why it is better than writing it new.

| Date | Source (`freebuff/`) | What | Verdict | Target | Tests | Reviewer | Why |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
