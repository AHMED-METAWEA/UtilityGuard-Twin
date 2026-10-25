# PROGRESS
Current phase: A1. Waves 0 and 1 are merged. **Wave 2 is delivered as four open pull requests (#16 to #19) and the lead has stopped at the usage check the owner asked for.** Wave 3 does not start until the owner says "continue".
Last session: 2026-10-25 (lead agent Claude Code)

Done:
- **Phase A0 closed** (PR #2; tag `phase-A0` on `506e578`, pushed, D-009). `freebuff/` is reference only (D-001).
- **A1 Wave 0:** T-A1-001 skeleton (PR #4). **Wave 1:** #6 to #15, all merged by the owner (core types, CI, WNTR manifest, adapter and import lint, ADR stubs and assumptions, contracts v1 approved with conditions, Spec 12.2 update, label test, records). Details in `docs/reviews/` and `docs/audit/DECISIONS.md` D-009 to D-013.
- **A1 Wave 2 (this session):** every card was built in its own worktree, cross-reviewed, and checked in a fresh clone with `make install install-dev && make ci`. None is merged. The owner's first task, the conformance test, is #17.

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
