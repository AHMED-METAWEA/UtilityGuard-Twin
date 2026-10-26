# PROGRESS
Current phase: A1. Waves 0 to 3 are built and **every Wave 3 pull request except #27 is merged into `dev` by the owner**. Open: #27 (browser test, adds the Playwright dependency, so the owner merges it under D-018) and the records PR. Wave 4 (T-A1-013, the A1 gate review) does not start without the owner's go-ahead.
Last session: 2026-10-26 (lead agent Claude Code)

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
| #27 | T-A1-014 browser test | Claude | **open**; Tier 1 but adds a dependency, so the owner merges it | Codex T1: no defects (`T-A1-014.md`) |
| records PR | review logs, D-018, D-019, this state | Claude | Tier 0 | none needed |

Hosted CI on `dev` was green after the last four merges (#18, #24, #26, #22); I did not check it after #21, #23 and #25.

Codex jobs: none running at the end. Finished this wave: the CLI run, the deploy run, two adversarial reviews of #24, two T1 reviews (#23 after its merge, #27). The idle Codex broker processes left by earlier worktrees were stopped at the end of this session.

What works: `ug_core` objects refuse what the contracts refuse (the gaps are closed, one by-design gap remains); the money rule is fail-closed (a SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY value needs a unit from `grammar.PHYSICAL_UNIT_ATOMS`); `ug doctor` checks Python, domains and their health hooks, every contract schema offline, node and docker; `make up` serves the shell and `/api/health` from one origin in a hardened container; a real Chromium confirms the shell requests nothing from another origin and that the Content-Security-Policy stops fetch, image, stylesheet, script, frame, WebSocket, EventSource and beacon attempts (in #27, not yet merged).

What is approximated: the currency spelling reader is best-effort (the unit vocabulary is the real guard for the four simulator labels; other labels may carry any unit token); the container is not firewalled, only the shell CSP and the smoke gate check offline behaviour; base images are pinned by digest (read 2026-10-25) and do not update themselves.

What is not proven: the second-round fixes of #24 had no third Codex round, and #25 and #26 were reviewed by the lead only (D-016, and T-A1-013 must cover them); the browser test runs in Chromium only; Docker was run on macOS arm64 only, not on a Linux runner; Codex's two T1 reviews could not run the code (read-only sandbox), so they are reading reviews.

Decision for the owner (open since #24): keep the fail-closed unit vocabulary (D-019), or ask the lead to remove it and keep only the spelling reader.

**Exact next step:** (1) owner: merge #27 (it adds `@playwright/test` 1.64.0); (2) owner: say "continue" to start Wave 4, T-A1-013 (the A1 gate review of everything above; it needs Codex and a full usage budget); (3) optional proposal: one handoff file per task instead of one `docs/progress/codex.md`, which conflicted on every merge this wave (D-019).

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
