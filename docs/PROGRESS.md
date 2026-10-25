# PROGRESS
Current phase: A1. Waves 0 to 2 are merged by the owner except #18. **Wave 3 is built and in review as open pull requests (#18, #21 to #26) plus one local branch; the lead stopped early because the usage limit is almost reached (owner's instruction).** Wave 4 (T-A1-013, the gate) does not start without the owner's go-ahead.
Last session: 2026-10-25 (lead agent Claude Code)

## Wave 3 state (2026-10-25, written at the stop for the usage limit)
The "Done", "Next" and usage lines further down are the Wave 2 record; this section supersedes their status.

Owner decisions applied this wave: T-A1-002c approved; frontend packages, the `legacy-peer-deps` workaround and `actions/setup-node@v7` accepted; corrected T-A1-011 acceptance text accepted; Playwright accepted as a pinned dev dependency (`@playwright/test` 1.64.0).

| PR / branch | Card | Author | State | Evidence |
|---|---|---|---|---|
| #18 `codex/a1-honesty-tests` | T-A1-004 (Wave 2) | Codex | open; rebased onto `dev`, conflict in `docs/progress/codex.md` resolved keeping both sides; lead added commit `e706cce` (valid hex commit and SHA-256 values in the determinism fixtures, assertions unchanged) | green with and without #24 |
| #21 `claude/fix-offline-generated` | fix | Claude | open; **dev is red until it merges** (the offline check flagged the generated `.d.ts`) | tests added in the PR |
| #22 `claude/a1-wave3-plan` | plan, cards T-A1-008b and T-A1-014, D-017 | Claude | open; this records update is committed on it | docs only |
| #23 `claude/a1-water-health` (`fe68955`) | T-A1-008b | Claude | open; **no Codex review yet** | 13 tests; fresh clone `make ci` exit 0 |
| #24 `claude/a1-contract-gaps` (`d7afb1a`) | T-A1-002c | Claude | open; Tier 2, **two Codex rounds done** (3 then 2 findings, all reproduced and fixed test-first); the round-2 fixes have no third review | 1927 unit and contract tests; about 80 mutations; fresh clone `make ci` exit 0 alone and with #18 merged |
| #25 `codex/a1-ug-cli` (`7847b6f`) | T-A1-009 | Codex | open; stacked on #23 (contains its commit); lead-reviewed | 29 mutations: Codex's tests caught 25, the lead added tests for 3 real gaps, 1 is equivalent (`allow_nan`); fresh clone `make ci` exit 0 |
| #26 `codex/a1-deploy` (`e409b93`) | T-A1-011 | Codex | open; lead-reviewed and **run in Docker** | `make up` healthy, uid 10001, read-only root, loopback port; `make smoke` 5/5; 14 smoke-script mutations all fail it; 29 API mutations caught after the lead's added tests; fresh clone `make ci` exit 0 |
| `claude/a1-browser-test` (`38e269e`), **local only, not pushed, no PR** | T-A1-014 | Claude | committed; the test is green; hosted-CI install step missing | 2 browser tests pass; 21 mutations of the build or sources fail it as required; `npm audit` 0 vulnerabilities |

Codex jobs: none running. Finished: the CLI run (T-A1-009), the deploy run (task `bn9c2ft04`, T-A1-011), the two adversarial reviews of #24 (`b0hig3el2` round 1, `b79c2e7tu` round 2). Not started: Codex T1 reviews of #23 and of T-A1-014. Idle Codex `app-server-broker` processes from earlier worktrees are still alive (they are not jobs; they can be killed).

What works: `ug_core` objects refuse what the contracts refuse (the 23 gaps are closed, one by-design gap remains); the money rule is fail-closed (a SIMULATION, MODEL, SENSOR_SIM or PUBLIC_GEOMETRY value needs a unit from `grammar.PHYSICAL_UNIT_ATOMS`); `ug doctor` checks Python, domains and their health hooks, every contract schema offline, node and docker; `make up` serves the shell and `/api/health` from one origin in a hardened container; a real Chromium confirms the shell requests nothing from another origin and that the Content-Security-Policy stops fetch, image, stylesheet, script, frame, WebSocket, EventSource and beacon attempts.

What is approximated: the currency spelling reader is best-effort (the fail-closed unit vocabulary is the real guard for the four simulator labels); other labels may carry any unit token; the container is not firewalled, only the shell CSP and the smoke gate check offline behaviour; base images are pinned by digest (read 2026-10-25) and do not update themselves.

What is not proven: the round-2 fixes of #24 have had no third Codex round; #23 and the browser test have had no Codex review; the browser test is not yet in hosted CI; Docker was run on macOS arm64 Docker Desktop only, not on a Linux runner; `make ci` was verified in fresh clones that merged #21 locally, so hosted CI on every branch is red until #21 is merged.

**Decision for the owner (in #24):** the fail-closed physical-unit vocabulary is stricter than the contract for the four simulator labels (a new physical unit must first be added to `PHYSICAL_UNIT_ATOMS`). Keep it, or say so and the lead removes it and keeps only the spelling reader.

**Merge order:** #21 first. Then #23 before #25 (stacked). #24, #18, #26 and #22 in any order after #21 (a #18 and #24 merge needs no further change).

**Exact next step (when usage allows):**
1. Owner: merge #21, then the others in the order above.
2. Lead, `claude/a1-browser-test`: add the CI step `cd frontend && npm ci && npx playwright install --with-deps chromium` before `make ci` in `.github/workflows/ci.yml` (the card allows exactly that edit); in a fresh clone run `make install install-dev && make browser-install && make ci`; push the branch and open the PR; run the Codex T1 review of it.
3. Lead: Codex T1 review of #23 (`codex-companion.mjs review --base origin/dev --cwd ~/Desktop/UG-wt/claude-a1-water-health --wait`); at most 2 Codex runs at once.
4. Lead, records PR for Wave 3: `docs/reviews/T-A1-002c.md`, `T-A1-009.md`, `T-A1-011.md`, `T-A1-014.md` (and `T-A1-008b.md` after its review); D-018 in `docs/audit/DECISIONS.md` (the fail-closed unit rule, the digest pins, the Playwright dependency as installed, the round-2 fixes without a third review); update the `GAPS` wording of T-A1-002b in `docs/COLLAB_PLAN.md`; fix the commit message of `7847b6f`, which says 28 caught where 25 is right (the PR text is corrected).
5. Cleanup the lead started: Docker Desktop is running (container stopped; quit it from the menu if wanted); Chromium (about 100 MB) is in `~/Library/Caches/ms-playwright`.
6. Then stop at the Wave 3 gate; Wave 4 (T-A1-013) only on the owner's go-ahead.

Usage check for Wave 3 (what I can measure): Codex implementation runs 2 (CLI, deploy; tokens are in the run logs in the scratchpad), Codex adversarial reviews 2 (both rounds of #24, about 5 minutes each); the lead used roughly 0.4 million tokens in this session (14.89 to 14.60 million remaining) plus more than 150 local mutation runs; no money was spent; the new dependencies are `fastapi`, `uvicorn` (hash-pinned, at least 14 days old) and `@playwright/test` 1.64.0 (exact pin, audit clean); Docker images and the Chromium build were downloaded.

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
