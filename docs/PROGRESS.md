# PROGRESS
Current phase: **B1 (Spec M1), Waves 2 and 3.** Merged in B1: T-B1-001 to 005, 010, 011 (+011b), 012, 015, 016, 020, 021; in review: T-B1-013 (#53, Tier 2) and T-B1-014 (#54, Tier 1); in progress: T-B1-019 (run part); not started: T-B1-017, 018, 022, 030. Owner rulings of 2026-10-27: G2 allows aggregate OSM numbers with the attribution; the district overlay is option A (schematic around the Wikidata anchor).
Last session: 2026-10-26 (lead agent Claude Code)

## Phase B1, state on 2026-10-27
- The owner merged #45 (T-B1-010), #47 (T-B1-020), #49 (T-B1-016), #50 (T-B1-012). The lead merged #48 (T-B1-011b), #51 (T-B1-019 data part) and #52 (T-B1-021 `ug run`) under D-018; after each merge a fresh clone of `dev` passed `make ci` and hosted CI on `dev` was green.
- T-B1-014 (network validation, Codex) is finished and in review (#54). The procedural network fails `min_pressure_any_time`, `max_velocity` and `tank_pinned_full` on seeds 1 to 3: tuning it (and calibrating the OSM network's demand rates and pipe sizes) is a lead card before T-B1-022.
- T-B1-013 (OSM provider) is in review (#53): all tiers build on the cached extract (lite 250 junctions, standard 799, full 6,020; aggregate numbers, © OpenStreetMap contributors, ODbL).

**Tokens (Codex from the `codex exec` logs; the lead from its context counter, approximate):**

| Wave | Codex implementation | Lead (Claude) |
|---|---|---|
| 1 | 152,478 | about 230,000 |
| 2 and 3 to date | 657,861 (T-B1-012 81,234; 020 90,062; 011b 64,976; 020 fix 68,408; 012 fix 125,892; 019 50,524; 021 89,702; 014 87,063) | about 580,000 |
| Total | 810,339 | about 810,000 |

Plugin reviews (Codex adversarial) report no tokens.

## Phase B1, Wave 2 (started 2026-10-26)
The owner merged #39 (T-B1-005) and #40 (T-B1-004) and said continue: the Codex lanes start first and run while the lead works; the lead stops only for Tier 2 merges (batched), `main` or tags, new dependencies, deletions, breaking contracts `v1` or the Honesty Rules, money, or the usage limit. Interfaces fixed before the lanes started: D-024.

| Card | Who | Branch | State |
|---|---|---|---|
| T-B1-020 run store | Codex (Tier 2, high effort) | `codex/b1-run-store` | running; the lead's first commit adds the D1 pins (`pyarrow==26.0.0`, `duckdb==1.5.6`) |
| T-B1-012 demand model | Codex (Tier 2, high effort) | `codex/b1-demand` | running |
| T-B1-010 `ug fetch-geometry` | lead | `claude/b1-fetch-geometry`, #45 | round 1 fixed; inside-box lengths, `make ci`, round 2 next |
| T-B1-016 hydraulics | lead | `claude/b1-hydraulics` | next |
| T-B1-013 OSM provider | lead | `claude/b1-osm-provider` | after T-B1-016 |

**Codex tokens (running tally, from the `codex exec` logs):** Wave 1 implementation 152,478. Wave 2: T-B1-020 and T-B1-012 running (added when they finish). Plugin reviews report no tokens.

## Phase B1, Wave 1 (2026-10-26)
Owner decisions applied: G1 to G3, D1 to D3 (D-023 in PR #39); the owner merged #37 and #38 and added card T-B1-005. Work split from now on (owner, 2026-10-26): Codex takes every card that needs no lead judgment (run store, API, stream and replay plumbing, frontend screens from the design plan, tests, CI, docs, tooling), up to two lanes, medium effort unless Tier 2; the lead keeps physics and fault injection, solver integration, detection, cost and decision, evidence, contracts and UI direction.

| PR | Card | Author | State | Review log |
|---|---|---|---|---|
| #40 | T-B1-004 dev and CI environments install what the container ships | Codex | open, the owner merges (dependency handling) | `docs/reviews/T-B1-004.md` |
| #39 | T-B1-005 F1 badge and notice for the hybrid geometry | Claude | open, the owner merges (Tier 2, Master Spec text) | `docs/reviews/T-B1-005.md` (2 rounds) |
| #41 | T-B1-015 WNTR manifest for B1 (81 symbols) and AST guard | Codex | merged by the lead (`2f5cf0f`) | `docs/reviews/T-B1-015.md` |
| #42 | network model (prerequisite of T-B1-011 and T-B1-013) | Claude | merged by the lead (`ee1d5b5`) | `docs/reviews/B1-network-model.md` |
| #43 | T-B1-011 procedural F0 network | Codex | merged by the lead (`cbcfbf6`) | `docs/reviews/T-B1-011.md` |
| #45 | T-B1-010 `ug fetch-geometry` and the coverage report | Claude | open, **in review**; round 1 found 4 S1 and 2 S2, all fixed in local commit `7dc05fc` (not pushed, so the PR still shows `8ce72cd`); round 2 not run; the owner merges (Tier 2) | `docs/reviews/T-B1-010.md` (round 1, in commit `7dc05fc`) |

After every lead merge: a fresh clone of `dev` passed `make ci` and hosted CI on `dev` (jobs `ci`, `container`, `audit`) was green.

**Codex usage (tokens, from the `codex exec` logs):**

| Run | Tokens |
|---|---|
| T-B1-004 implementation | 42,260 |
| T-B1-015 implementation | 49,705 |
| T-B1-011 implementation | 60,513 |
| **Wave 1 implementation total** | **152,478** |

Review runs go through the Codex plugin, which does not report tokens. This wave ran 4: T-B1-005 rounds 1 and 2, the network model (T1), T-B1-010 round 1 (`review-mvp83i3y-9y29f9`, finished, 2 min 26 s). **No Codex job is running** at the stop.

**T-B1-010 at the stop (branch `claude/b1-fetch-geometry`, worktree `~/Desktop/UG-wt/claude-b1-fetch-geometry`):**
- Fixed in `7dc05fc` (local; lint, format, mypy and `make test-unit` green, 1,290 unit tests; 97 geometry tests; 37 of 38 mutations of the new checks caught, the survivor is equivalent): (1) S1 the cache must be git-ignored or outside any repository, symbolic links resolved, the default is `data/geometry` at the repository top; (2) S1 the area file holds no OSM-derived geometry: a Wikidata anchor (Q19588497, CC0), a search half-width, a margin, landmark names; the study box is placed at fetch time from the landmarks and stored only in the cache; (3) S1 empty or partial answers are failures; (4) S1 `verify_extract` checks the whole provenance, the saved queries against the current templates, the boxes, timestamps, endpoint and extract hash; (5) S2 a same-snapshot folder is repaired when corrupt or foreign; (6) S2 every mapped-feature field has its own label, `km` is `CALCULATED`.
- Live result: the live fetch of the new design finished after the stop (exit 0, OSM timestamp 2026-10-26T12:39:20Z, cache only): all 9 landmarks found, study box 23.4 km by 16.4 km (382 km2; its coordinates are derived from OSM positions and stay in the cache, G2); built drivable roads 2,736.1 km, 11,727 junctions, 0.996 of the length in the largest component (the feasibility box gave 2,887.7 km, 12,451 and 0.977: a different box, the comparison is not yet written up).
- Not done: the fresh-clone `make ci` of `7dc05fc`; the push to #45; the write-up of the live numbers in the PR and the review log; Codex round 2; the PR description update. Not yet decided: whether the merged feasibility report, which still states the old box as a record of the test, should be left as it is (no code reads it).

**Findings worth keeping:** the first live geometry fetch (old box) reproduced the feasibility numbers exactly; the procedural F0 demand densities are far below urban values (T-B1-012 and T-B1-014 must set the scale); setuptools 84.0.0 pins the build backend until 84.1.0 is 14 days old (2026-11-02); an outside account opened issue #44 on this public repository ("Question about Codex instruction checks in external worktrees"), untouched, left to the owner.

**Exact next step (when the owner says continue):** in `~/Desktop/UG-wt/claude-b1-fetch-geometry`, (1) read `data/geometry/capital/2026-10-26T12-39-20Z/report.md` and add the numbers for the new box to the PR description and the review log, explaining the change from the feasibility numbers (a different box); (2) a fresh clone of `dev` plus the branch passes `make install install-dev && make ci`; (3) push to #45 and wait for hosted CI; (4) Codex adversarial review round 2 (the last round for Tier 2), fix test-first, log it in `docs/reviews/T-B1-010.md`, put fixes after round 2 on the D-016 list; (5) finish this records PR (Tier 0, merge under D-018 plus the safety net), print the Wave 1 usage check and pause. Then the owner merges #39, #40 and #45 and Wave 2 opens: Codex lanes T-B1-020 (run store, Tier 2) and T-B1-012 (demand model, Tier 2), the lead T-B1-013 (OSM provider) and T-B1-016 (hydraulics).

## Phase B1 (Spec M1): plan stage, 2026-10-26
- **Small tasks first** (owner's order): T-B1-001, a CI job `container` that builds the image and checks the running container (hardening and smoke), merged as #36 (`bf6c32f`) after a Codex T1 review and eight container mutations; it ran the image on Linux x86_64 for the first time. T-B1-002, the Python dependency audit (PR #37, waiting for the owner because it changes dependency handling): a standard-library script reads PyPI's advisory data; its first run found 12 advisories in the development environment (pip 23.2.1, setuptools 65.5.0 from Python 3.11's venv) and 8 in the image (pip 24.0, setuptools 79.0.1 from the base image); the PR fixes them (pip 26.2.1 in `make install`, setuptools removed, no packaging tools in the image) and the audit is clean afterwards. Every chosen dependency was already clean.
- **Geometry feasibility test** (T-B1-003, `docs/audit/B1_GEOMETRY_FEASIBILITY.md`): OSM's street layout of the capital is strong (2,888 km of drivable roads, 12,451 junctions, 97.7% connected, plus 1,103 km under construction); districts, land use, buildings and names are weak; the water network is absent. Proposal: OSM streets plus a hand-made district overlay labelled `ASSUMPTION`; OSM data stays in a git-ignored cache (ODbL).
- **B1 plan**: `docs/COLLAB_PLAN.md` section 4b, 18 cards in waves 0 to 4, with the decisions the owner takes first (G1 to G3 geometry and licence; D1 `pyarrow==26.0.0` and `duckdb==1.5.6`; D2 `networkx==3.6.1`; D3 PR #37).
- **Found and not fixed** (now card T-B1-004): the development and CI environments resolve `fastapi` 0.143.5 while the container ships 0.143.0; package builds fetch the newest `setuptools`.
- **Next step:** the owner approves or changes the plan and takes decisions G1 to G3 and D1 to D3; then Wave 1 (T-B1-004, 010, 011, 015).

## A1 exit gate, T-A1-013: CLOSED 2026-10-26
**Closure:** the owner explicitly approved #31 (contracts `v1` tightened in place) and, as a one-time authorization, the gate merge. #31 was squash-merged as `7d06056`; `docs/reviews/T-A1-013.md` was updated to show no S0 or S1 open (`eb817f9`); PR #34 merged `dev` into `main` with a **merge commit** `daf6634` (parents `debfd51`, the baseline import, and `eb817f9`); the annotated tag `phase-A1` points at `daf6634` and is pushed. After each merge a fresh clone of the merged branch passed `make ci` and hosted CI was green (`main` at `daf6634` included). `dev` is one merge commit behind `main` with no content difference. Recorded as D-022.
Full log: `docs/reviews/T-A1-013.md` (findings, decisions, fixing PRs, the lead's runs, the Spec M0 criteria one by one).

- **Fresh clone of `dev`**: `make install install-dev` exit 0; `make ci` exit 0 (1,155 unit, 870 contract, 283 frontend, 202 honesty with 11 of 11 mutations caught, 35 water, 2 browser tests, 8 adapter-conformance passes and 12 expected failures until M1 to M4); `make up` serves the shell (healthy container, `make smoke` 5 of 5, a real Chromium shows the notice, the badge `No network loaded` and `REPLAY no stream connected`, every request to the same origin); `ug doctor` exits 0 and exits 1 on an edited WNTR manifest; the import rule fails when `platform/` imports a domain. Hosted CI on `dev` is green at `fd012b1`.
- **Codex adversarial review since `phase-A0`**, 2 rounds, 4 runs: 8 findings (1 S1, 6 S2, 1 S3), all reproduced with failing tests and fixed. None in the code only the lead had reviewed (`ug_api`, the container, `grammar.py`) or in the second-round fixes of #24.
- **Fixed and merged by the lead (#30, Tier 1)**: `ug doctor` now checks that every reference target is a schema, and follows references inside targets; a number that overflows to infinity (`1e9999`) is refused by the contract test loader and by the doctor.
- **Fixed and merged with the owner's explicit approval (#31, Tier 2, contract change, `7d06056`)**: the S1 (`{"value":100,"unit":"EGP","label":"SENSOR_SIM"}` was a valid telemetry reading and a valid tick reading) and its siblings (the same hole in evidence records labelled SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY; `INSUFFICIENT_EVIDENCE` carrying numeric estimates). The fix puts the code's fail-closed unit vocabulary into the contract. It tightens `v1` in place, which the contracts README forbids unless the owner approves (no `v1` payload is produced or stored yet).
- **Spec M0 not fully met**: the UI design plan (tokens, wireframes) is B2 by the Adoption Plan; the mock dataset and mock stream are partial (valid example payloads exist; no stream player or server); the shell does not import the generated TypeScript types yet.
- **Decisions taken by the owner**: (1) #31 approved, `v1` tightened in place, no `v2`; (2) the gate approved: the lead merged `dev` into `main` with a merge commit and pushed `phase-A1` under a one-time authorization (the standing rule D-018 is unchanged: no `main`, no tags for the lead); (3) B1 starts at the plan stage only.
- **Not reviewed a third time (D-016, D-021)**: the transitive reference walk (#30), the evidence-record rule and the `FNU`/`FTU` atoms (#31), plus the earlier list.
- **Follow-ups decided 2026-10-26**: a CI job that builds the image and runs the smoke script, and a Python dependency audit job, are the two small tasks that open B1; the shell importing the generated types and the mock stream go to B2.

## Wave 3 state (2026-10-26)
The "Done", "Next" and usage lines further down are the Wave 2 record; this section supersedes their status.

Owner decisions applied this wave: T-A1-002c approved; frontend packages, the `legacy-peer-deps` workaround and `actions/setup-node@v7` accepted; corrected T-A1-011 acceptance text accepted; Playwright accepted as a pinned dev dependency (`@playwright/test` 1.64.0). **New standing rule D-018 (2026-10-26): the lead may squash-merge Tier 0 and Tier 1 PRs into `dev` when hosted CI is green, the cross-review is logged and the PR touches no contracts, assumptions, Honesty Rules text, Master Spec, dependencies or deletions; never Tier 2, `main` or tags.**

| PR | Card | Author | State | Cross-review (log in `docs/reviews/`) |
|---|---|---|---|---|
| #21 | fix: offline check ignores type declarations | Claude | merged by the owner | tests in the PR |
| #23 | T-A1-008b water adapter health check | Claude | merged by the owner | Codex T1 after the merge: no defects (`T-A1-008b.md`) |
| #25 | T-A1-009 `ug` CLI, `ug doctor` | Codex | merged by the owner | lead: 29 mutations, 3 test gaps closed (`T-A1-009.md`) |
| #18 | T-A1-004 honesty tests and mutation runner | Codex | merged by the owner after two rebases (conflicts in `docs/progress/codex.md`, both sections kept) and one lead fixture commit | `T-A1-004.md` |
| #24 | T-A1-002c objects refuse what the contracts refuse | Claude | merged by the owner | Codex adversarial, 2 rounds, 5 findings fixed; no third round (`T-A1-002c.md`) |
| #26 | T-A1-011 health API, Docker Compose, `make up` | Codex | merged by the owner after three rebases | lead: run in Docker, 14 smoke and 29 API mutations (`T-A1-011.md`) |
| #22 | Wave 3 plan | Claude | merged by the owner | docs only |
| #27 | T-A1-014 browser test | Claude | merged by the owner (Tier 1 but adds a dependency) | Codex T1: no defects (`T-A1-014.md`) |
| records PR | review logs, D-018, D-019, this state | Claude | Tier 0 | none needed |

Hosted CI on `dev` was green after the last four merges (#18, #24, #26, #22); I did not check it after #21, #23 and #25.

Codex jobs: none running at the end. Finished this wave: the CLI run, the deploy run, two adversarial reviews of #24, two T1 reviews (#23 after its merge, #27). The idle Codex broker processes left by earlier worktrees were stopped at the end of this session.

What works: `ug_core` objects refuse what the contracts refuse (the gaps are closed, one by-design gap remains); the money rule is fail-closed (a SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY value needs a unit from `grammar.PHYSICAL_UNIT_ATOMS`); `ug doctor` checks Python, domains and their health hooks, every contract schema offline, node and docker; `make up` serves the shell and `/api/health` from one origin in a hardened container; a real Chromium confirms the shell requests nothing from another origin and that the Content-Security-Policy stops fetch, image, stylesheet, script, frame, WebSocket, EventSource and beacon attempts (in #27, not yet merged).

What is approximated: the currency spelling reader is best-effort (the unit vocabulary is the real guard for the four simulator labels; other labels may carry any unit token); the container is not firewalled, only the shell CSP and the smoke gate check offline behaviour; base images are pinned by digest (read 2026-10-25) and do not update themselves.

What is not proven: the second-round fixes of #24 had no third Codex round, and #25 and #26 were reviewed by the lead only (D-016, and T-A1-013 must cover them); the browser test runs in Chromium only; Docker was run on macOS arm64 only, not on a Linux runner; Codex's two T1 reviews could not run the code (read-only sandbox), so they are reading reviews.

Decision for the owner (open since #24): keep the fail-closed unit vocabulary (D-019), or ask the lead to remove it and keep only the spelling reader.

**Exact next step:** superseded by the section "A1 exit gate" above.

Usage check for Wave 3: Codex implementation runs 2 (CLI, deploy), adversarial reviews 2 (both rounds of #24), T1 reviews 2 (#23, #27); the lead applied more than 150 mutation runs locally; no money was spent; new dependencies are `fastapi` and `uvicorn` (hash-pinned, releases at least 14 days old) and `@playwright/test` 1.64.0 (exact pin, audit clean); Docker images and a Chromium build were downloaded. The lead's token counter read 14.60 million remaining when it stopped for the usage limit and 14.97 million after this task: it was reset when the date changed, so I cannot give a combined figure.

Done:
- **Phase A0 closed** (PR #2; tag `phase-A0` on `506e578`, pushed, D-009). `freebuff/` is reference only (D-001).
- **A1 Wave 0:** T-A1-001 skeleton (PR #4). **Wave 1:** #6 to #15, all merged by the owner (core types, CI, WNTR manifest, adapter and import lint, ADR stubs and assumptions, contracts v1 approved with conditions, Spec 12.2 update, label test, records). Details in `docs/reviews/` and `docs/audit/DECISIONS.md` D-009 to D-013.
- **A1 Wave 2 (this session):** every card was built in its own worktree, cross-reviewed, and checked in a fresh clone with `make install install-dev && make ci`. The owner merged all of them except #18 (left open for a docs conflict, resolved in Wave 3). The owner's first task, the conformance test, is #17.

| PR | Card | Author | What | Reviews (by the other agent) | Tests |
|---|---|---|---|---|---|
| #17 | T-A1-002b | Claude | the code's outputs validate against the schemas; 23 gaps listed by signature | Codex, 2 rounds (4 then 1 weakness) | 180 in the file |
| #16 | T-A1-007 | Codex | TypeScript types from contracts v1 and a drift check | Claude: 1 finding, fixed | drift check, 2 mutations |
| #18 | T-A1-004 | Codex | honesty tests and an 11-mutation runner (in `make ci`) | Claude: 25 mutations, 4 gaps then 1 | 202 |
| #19 | T-A1-010 | Claude | shell: honesty notice, Fidelity badge, stream-source indicator | Codex, 2 rounds (4 then 3 findings) | 269 |

  #16 and #18 both append to `docs/progress/codex.md`: whichever merges second needs a trivial rebase (keep both sections). #16 and #19 add the same three `.gitignore` lines (identical, they merge cleanly).
- A merge preview of the four branches on `dev` has exactly that one conflict; every branch passes `make ci` alone.
- Records: review logs for every reviewed task in `docs/reviews/` (findings, decisions, fixes); D-014 to D-016 in `docs/audit/DECISIONS.md`; follow-up card T-A1-002c; the deploy card's acceptance text corrected.

What works: the code's payloads for the manifest, assumption set and telemetry rows validate against the contracts (and the places where the code is looser are written down and tested for staleness); TypeScript types are generated offline from the schemas and a drift check fails when they differ; the honesty suite fails when truth reaches the operator side, a number is unlabelled, money is mislabelled, a hash or random stream loses its determinism, NaN becomes zero, or a write-capable control library appears, and a runner proves it by applying 11 mutations; the shell shows the notice, the badge and the stream source in every state and survives failures, with a strict Content-Security-Policy on the built page and a build-time offline check.

What is approximated: the shell and the offline check cannot prove that a real browser makes no request (no browser test; Playwright is not on the approved list); the word and currency lists in the contracts are best-effort; the scanners understand literal syntax only; the frontend lockfile was generated with `legacy-peer-deps` because of an npm 10.9.2 crash (D-014).

What is not proven: the 23 gaps (the code accepts what the contract rejects: id and unit grammars, the money label on `Evidenced`, commit and hash formats) stay open until T-A1-002c; the generated types are not yet imported by the shell; `ug doctor` and the water adapter health check (T-A1-008b) do not exist; there is no API or Docker deployment yet (Wave 3). **Fixes made after review round 2 have had no third review (D-016); T-A1-013 must cover them.**

Next:
1. Owner reviews and merges #17, #16, #18, #19 (suggested order; #16 before #18 so the shared `codex.md` conflict is resolved once by the lead), then this records PR.
2. **Usage check (below), then pause.** When the owner says "continue": Wave 3. Codex: T-A1-009 (`ug` CLI and `ug doctor`) and T-A1-011 (deploy, with the corrected acceptance text); Claude: T-A1-008b (water adapter health check) first, because 009 needs it, and T-A1-002c if the owner approves it. Then Wave 4: T-A1-013 (gate review).
3. Decisions for the owner: approve T-A1-002c (closing the 23 gaps, a T2 change to `ug_core`); accept the frontend dependency set and the npm workaround (D-014).

Blockers / human actions pending:
- Merge the Wave 2 pull requests and this records PR.
- Branch protection on `dev` and `main` (owner action; the `ci` check exists since #7).
- Optional: GitHub "keep my email private" setting (COLLAB_PLAN Q4); delete the stale scratch-repo trust entry in `~/.codex/config.toml`.

Decisions since last session: D-014 (dependencies and tooling), D-015 (acceptance texts that could not be met), D-016 (unreviewed round-2 fixes, running list).

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6.

Usage check for Wave 2 (what I can measure):
- Codex implementation runs: 3 (T-A1-007: 44,780 tokens; T-A1-004: 82,187; T-A1-004 fixes: 55,480; total 182,447). Codex review runs: 4 adversarial reviews of the lead's cards (T-A1-002b twice, T-A1-010 twice), about 5 minutes each; the plugin does not report their tokens.
- Lead: about 0.31 million tokens of the 15 million budget (14.99 to 14.69 million remaining), about 2 percent, plus over a hundred local mutation runs of test suites (a few seconds each, no cost).
- Review: every card that Codex reviewed needed both rounds and round 2 found something new each time, so plan two rounds per Tier-2 card in Wave 3.
- No money was spent; nothing outside the approved dependency list was installed; Codex ran offline.
