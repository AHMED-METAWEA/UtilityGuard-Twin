# PROGRESS
Current phase: A1. Wave 1 is delivered as open pull requests. Waiting for the owner's reviews and merges. Wave 2 does not start until the owner says "continue" (usage check first).
Last session: 2026-10-25 (lead agent Claude Code)

Done:
- **Phase A0 closed** (merged by the owner, PR #2; tag `phase-A0` on `506e578`, pushed after the owner's OK, D-009). Baseline `baseline-freebuf`; `freebuff/` is reference only (D-001).
- **A1 Wave 0:** T-A1-001 skeleton merged (PR #4).
- **A1 Wave 1, all seven cards have a pull request. None is merged. The lead did not merge anything.**

| PR | Card | Owner | What | Review rounds (defects found and fixed) | Tests |
|---|---|---|---|---|---|
| #6 | Spec change | lead | nine evidence labels in Spec section 2; `fault_tag_hidden` only in `truth.parquet` | owner-requested | n/a |
| #7 | T-A1-006 CI | Codex | `make ci`, pinned dev tools, GitHub Actions; one lead fix commit (D-013) | lead review, hosted CI passes | 4 |
| #8 | T-A1-003 core types | lead | evidence labels, truth and telemetry as unrelated types, `Timebase`, canonical `Manifest` hash, seed streams | 2 rounds: 6 then 2 | 59 |
| #9 | T-A1-008 WNTR manifest | lead | 49 WNTR symbols checked by introspection; `--check` in `make ci` | 2 rounds: 2 then 1 | 22 |
| #10 | T-A1-005 adapter | lead | `DomainAdapter`, registry, conformance suite, import lint | 2 rounds: 4 then 3 | 110 unit, 8 conformance + 12 expected failures |
| #11 | T-A1-012 ADR and assumptions | lead | ADR stubs 001-010, strict assumptions loader, `assumptions/v1.yaml` | 2 rounds: 3 then 2 | 127 unit (with #8) |
| #12 | T-A1-002 contracts v1 | lead | 7 JSON Schemas, 19 examples, 67 rejected cases | 2 rounds: 5 then 4 | 680 contract |

  #10 and #11 are stacked on #8 (they reuse its types), and say so in their descriptions.
- Every combination was checked in a fresh clone with `make install install-dev && make ci` over the CI branch. Two combined runs caught real problems that single-branch checks missed (a platform test importing a domain package; unused `type: ignore` comments under the repository's mypy settings). Both are fixed.
- Records: D-009 to D-013 in `docs/audit/DECISIONS.md`; card statuses in `docs/COLLAB_PLAN.md`.

What works: the core types enforce the Honesty Rules by structure (a value cannot exist without a known label; truth and telemetry are different types; the manifest hash ignores order and the interpreter's hash seed). Domains plug in through one interface and a registry, and a lint fails if `platform/` imports a domain. The WNTR calls the code may use are checked against the installed library. Contracts reject truth fields, missing stream sources, mislabelled money and unknown faults, each shown by a rejected example.

What is approximated: the word lists and the currency list in the contracts are best-effort (a grammar plus words, not proof); the source note of a verified assumption is checked for hygiene only; the lint cannot see a module name built at run time; the WNTR manifest was verified on WNTR 1.5.0 only.

What is not proven: the code that produces a contract payload (`Manifest.to_dict()` against `run-manifest`, and so on) is not yet tested against the schemas; no TypeScript types exist yet (T-A1-007); `ug doctor` does not exist (T-A1-009); nothing runs end to end. **The fixes made after review round 2 have had no third review** (D-012); the A1 exit-gate review must cover them.

Next:
1. Owner reviews and merges, in this order: #6, #7, #8, #10, #11, #9, #12 (needs sign-off), then this records PR. `domains/water/pyproject.toml` conflicts between #9 and #10 (two hunks); the lead rebases whichever merges second. Small follow-up after #9 and #10: T-A1-008b, `WaterAdapter.health_checks()` wired to the WNTR check, so `ug doctor` can reach it through the registry. Another follow-up after #8, #11 and #12: tests that the code's `to_dict()` outputs validate against the schemas.
2. Pause for the usage check (owner's rule). When the owner says continue: Wave 2: Codex T-A1-004 (honesty tests) and T-A1-007 (TypeScript types; the schemas now use relative references, and the pinned generator was verified to work offline), Claude T-A1-010 (shell). Then Wave 3 (Codex T-A1-009 `ug` CLI, T-A1-011 deploy) and Wave 4 (T-A1-013 gate).

Blockers / human actions pending:
- Review and merge the pull requests above. #12 is a contracts change and needs the owner's sign-off on the eight decisions listed in its description.
- Branch protection on `dev` and `main` (owner action). Once #7 is merged, the `ci` check can be made required.
- Optional: GitHub "keep my email private" setting (COLLAB_PLAN Q4); delete the stale scratch-repo trust entry in `~/.codex/config.toml`.

Decisions since last session: D-009 to D-013 in `docs/audit/DECISIONS.md`. Default Codex reasoning effort stays `medium` (raised for T2 reviews).

Open questions for the human: see `docs/COLLAB_PLAN.md` section 6, and the decision list in PR #12.

Spend so far: two long lead sessions (setup and Wave 0; Wave 1). Codex: 7 small runs earlier, 1 CI implementation run, and 10 adversarial review rounds in Wave 1 (two per lead card).
