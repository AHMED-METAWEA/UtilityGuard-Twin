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

### D-005 (open): meaning of fidelity F1 and the banner wording
- Spec 1.4 and 5.1 define F1 as capital-inspired with all geometry hypothetical; `AGENTS.md`, the earlier `CLAUDE.md` and this plan's G01 describe F1 as real public layout with inferred pipes (`OsmCapitalProvider`, B1, after a geometry feasibility test). Until the human rules, the weaker Spec 1.4 text is used for the badge (stricter reading, `COLLABORATION.md` section 9).

## Reuse log (REUSE and ADAPT only)

No reuse has been decided yet. Candidates and likely verdicts are in `ADOPTION_PLAN.md` section 8. A line is added here, in the same PR that brings the code in, with: date, source file and lines in `freebuff/`, what was reused, verdict (REUSE or ADAPT), target path, tests added (including golden tests for the reused behavior), reviewer, and why it is better than writing it new.

| Date | Source (`freebuff/`) | What | Verdict | Target | Tests | Reviewer | Why |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
