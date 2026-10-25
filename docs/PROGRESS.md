# PROGRESS
Current phase: A1. Wave 1: PRs #6, #7, #8 and #9 are merged; #10, #11, #12 (approved with conditions), #13, #14 and #15 are open. **Wave 2 does not start until the owner confirms that all Wave 1 PRs are merged.**
Last session: 2026-10-25 (lead agent Claude Code)

Done:
- **Phase A0 closed** (merged by the owner, PR #2; tag `phase-A0` on `506e578`, pushed after the owner's OK, D-009). Baseline `baseline-freebuf`; `freebuff/` is reference only (D-001).
- **A1 Wave 0:** T-A1-001 skeleton merged (PR #4).
- **A1 Wave 1, all seven cards have a pull request.** The owner merged #6, #7, #8 and #9. The lead merges nothing. After #9 merged before #10, the lead rebased #10, #11 and #12 onto `dev` (only #10 conflicted, in `domains/water/pyproject.toml`; both sides kept), re-ran `make ci` in a fresh clone for each, and pushed with `--force-with-lease` on the lead's own branches.

| PR | Card | Owner | What | Review rounds (defects found and fixed) | Tests |
|---|---|---|---|---|---|
| #6 (merged) | Spec change | lead | nine evidence labels in Spec section 2; `fault_tag_hidden` only in `truth.parquet` | owner-requested | n/a |
| #7 (merged) | T-A1-006 CI | Codex | `make ci`, pinned dev tools, GitHub Actions; one lead fix commit (D-013) | lead review, hosted CI passes | 4 |
| #8 (merged) | T-A1-003 core types | lead | evidence labels, truth and telemetry as unrelated types, `Timebase`, canonical `Manifest` hash, seed streams | 2 rounds: 6 then 2 | 59 |
| #9 (merged) | T-A1-008 WNTR manifest | lead | 49 WNTR symbols checked by introspection; `--check` in `make ci` | 2 rounds: 2 then 1 | 22 |
| #10 | T-A1-005 adapter | lead | `DomainAdapter`, registry, conformance suite, import lint | 2 rounds: 4 then 3 | 110 unit, 8 conformance + 12 expected failures |
| #11 | T-A1-012 ADR and assumptions | lead | ADR stubs 001-010, strict assumptions loader, `assumptions/v1.yaml` | 2 rounds: 3 then 2 | 127 unit (with #8) |
| #12 | T-A1-002 contracts v1 | lead | 7 JSON Schemas, 19 examples, 67 rejected cases | 2 rounds: 5 then 4 | 680 contract |
| #14 | Spec 12.2 update | lead | the tick example and text match the stricter tick payload (owner's condition on #12); stacked on #12 | n/a | 1 test replaced |
| #15 | label test | lead | the Spec label table must equal the code labels (promised in #8) | n/a | 1 test tightened |

  #10 and #11 were stacked on #8 and are now rebased onto `dev`. #14 is stacked on #12.
- Every combination was checked in a fresh clone with `make install install-dev && make ci` over the CI branch. Two combined runs caught real problems that single-branch checks missed (a platform test importing a domain package; unused `type: ignore` comments under the repository's mypy settings). Both are fixed.
- Records: D-009 to D-013 in `docs/audit/DECISIONS.md`; card statuses in `docs/COLLAB_PLAN.md`.

What works: the core types enforce the Honesty Rules by structure (a value cannot exist without a known label; truth and telemetry are different types; the manifest hash ignores order and the interpreter's hash seed). Domains plug in through one interface and a registry, and a lint fails if `platform/` imports a domain. The WNTR calls the code may use are checked against the installed library. Contracts reject truth fields, missing stream sources, mislabelled money and unknown faults, each shown by a rejected example.

What is approximated: the word lists and the currency list in the contracts are best-effort (a grammar plus words, not proof); the source note of a verified assumption is checked for hygiene only; the lint cannot see a module name built at run time; the WNTR manifest was verified on WNTR 1.5.0 only.

What is not proven: the code that produces a contract payload (`Manifest.to_dict()` against `run-manifest`, and so on) is not yet tested against the schemas; no TypeScript types exist yet (T-A1-007); `ug doctor` does not exist (T-A1-009); nothing runs end to end. **The fixes made after review round 2 have had no third review** (D-012); the A1 exit-gate review must cover them.

Next:
1. Owner merges the rest, in this order: #10, #11, #12 (approved with conditions), #14 (stacked on #12), #15, #13. #13 may need a small update after the merges.
2. **Conditions the owner set on #12:** (a) update Spec 12.2 to the stricter tick payload: done, PR #14; (b) the test that `to_dict()` outputs validate against the schemas is the **first Wave 2 task** (card T-A1-002b, needs #8, #11 and #12 merged); (c) the four main decisions of #12 explained in plain words: done in the lead's report to the owner.
3. **Wave 2 does not start until the owner confirms that all Wave 1 PRs are merged.** Then: first T-A1-002b (Claude), together with Codex T-A1-004 (honesty tests) and T-A1-007 (TypeScript types; the schemas use relative references and the pinned generator was verified to work offline), and Claude T-A1-010 (shell). Small follow-up after #10: T-A1-008b, `WaterAdapter.health_checks()` wired to the WNTR check so `ug doctor` can reach it through the registry. Then Wave 3 (Codex T-A1-009 `ug` CLI, T-A1-011 deploy) and Wave 4 (T-A1-013 gate).

Blockers / human actions pending:
- Merge #10, #11, #12, #14, #15, #13 (see Next). #12 is approved by the owner with the conditions above.
- Branch protection on `dev` and `main` (owner action). Once #7 is merged, the `ci` check can be made required.
- Optional: GitHub "keep my email private" setting (COLLAB_PLAN Q4); delete the stale scratch-repo trust entry in `~/.codex/config.toml`.

Decisions since last session: D-009 to D-013 in `docs/audit/DECISIONS.md`. Default Codex reasoning effort stays `medium` (raised for T2 reviews).

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6, and the decision list in PR #12.

Spend so far: two long lead sessions (setup and Wave 0; Wave 1). Codex: 7 small runs earlier, 1 CI implementation run, and 10 adversarial review rounds in Wave 1 (two per lead card).
