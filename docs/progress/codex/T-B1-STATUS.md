## Handoff: T-B1-STATUS

- Done: added standard-library B1 card parsing, per-wave and total counts, owner-waiting and blocked sections, and deterministic Markdown output in `scripts/status.py`.
- Done: added `make status` through the existing `mk/*.mk` wildcard and generated `docs/STATUS.md`; no Makefile edit was needed.
- Done: added six offline tests covering section and heading boundaries, the first Status line, missing status, suffix IDs, classification, deterministic CLI output, open-PR overrides, owner/tier detection and GitHub failures.
- Verified by: `make lint typecheck test-unit` passed (ruff lint and format clean; mypy clean across 54 source files; 1,404 unit tests passed, 1 skipped because the sandbox denies loopback binding). Focused status tests passed (6). `make status` succeeded with the expected GitHub warning and plan-only fallback. `.venv/bin/python scripts/status.py` printed the real plan's counts; `--write /tmp/ug-b1-status-check.md` plus `cmp docs/STATUS.md /tmp/ug-b1-status-check.md` confirmed byte-identical output. `git diff --check` passed; `git status --short` showed only the five allowed new files.
- Not done / known limits: network is disabled; real GitHub success was not exercised. The prescribed list command is supplemented with `gh pr view <number> --json body` to detect owner-merge text in PR bodies. If any GitHub invocation fails, all GitHub supplementation is discarded and a warning is printed; plan statuses remain the fallback source. The prescribed list command uses gh's default limit of 30 open PRs.
- Contracts touched: no. No dependencies, runtime domain code, assumptions or reference-baseline code touched.
- Honesty checklist: ticked below; progress counts carry CALCULATED. This is a development progress report, not a twin or operator view.
- Risks the reviewer should focus on: status precedence, exact card-ID matching (including `b` suffixes), plan-only open-PR inference, and owner-waiting detection.
- Next step for the other agent: independently run the acceptance checks and record the Tier 1 cross-review in `docs/reviews/T-B1-STATUS.md`. No independent review is claimed here. Owner requested no commit; no commit, push or PR creation performed.

Honesty checklist (Appendix E):

- [x] Truth separation: no truth, telemetry or operator paths touched.
- [x] Evidence: report counts are CALCULATED from the plan and optional GitHub results; identifiers are source references.
- [x] Probabilities and assumptions: no event probabilities or model assumptions introduced.
- [x] Money: no cost or benefit calculations introduced.
- [x] Determinism: identical inputs produce byte-identical Markdown; tests cover file and stdout output, and PR-order independence.
- [x] No LLM in the calculation path.
- [x] Banner, Fidelity and stream source: not applicable to this development report; existing displays untouched.
- [x] External interface: installed `gh pr list --help` and `gh pr view --help` verified the flags and fields; subprocess calls tested with a fake.
- [x] Contracts: unchanged; no regeneration needed.
- [x] Synthetic results: no field-validation claims introduced.
