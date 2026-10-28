# Handoff: demo work, state on 2026-10-28 (lead)

Plan of record: `docs/DEMO_PLAN.md`. Feature freeze Fri 30 Oct; demo Mon 2 Nov ("best partial version").
Load limits (owner): at most 2 heavy jobs (Codex lanes, full pytest, Playwright, fresh-clone make ci, long sims); `OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1`; Playwright `--workers=1`; check `vm_stat`/`ps` before launching. The Mac has 8 GB; a vitest run timed out at 457 s while swapping (passes in 3 s alone).

## Dev
Head 3ccedd6 (#65-#69, #71, #72 merged). Safety net: fresh-clone `make ci` EXIT=0 (`~/Desktop/UG-wt/tools/safety.sh dev`, it runs `make install install-dev frontend-install` first) and hosted ci success.

## Open PRs (all for the owner)
| PR | What | State |
|---|---|---|
| #70 | D-05a detection (Tier 2) | rebased onto dev (D-04 commits dropped, newer test_quality.py kept); 3,527 tests; ci/audit/container green: mergeable |
| #73 | D-02 OSM calibration (Tier 2) | 2-day validation passed (33.7/30.5 m, 2.23 m/s) |
| #74 | D-07 API (Tier 2) | lead review + 2 mutations caught |
| #75 | U-02 Command Center (Tier 1, owner merges: lead edited two shell tests) | 376 tests, Playwright 4 passed |
| #76 | D-03 faults (Tier 2) | 434 water tests; Codex adversarial review running -> `tools/D-03.review.md`; log it in `docs/reviews/D-03.md` |

## Running
- Codex W-01 in `~/Desktop/UG-wt/codex-demo-w01` (branch `codex/demo-w01-baseline`, = #74 + #70 merged locally): `ug export`, `make demo-baseline`, app loads the bundle with REPLAY. Card `tools/W-01.prompt.md`; result `tools/W-01.result.md`. Rebase onto dev once #70/#74 merge.

## Next
1. D-03 review -> fix S0/S1, log review.
2. W-01 result: review (Tier 2: truth walk on the bundle, mutation), commit, PR.
3. Five scenarios as bundles (leak_sudden, leak_gradual_medium, burst_main, pump_outage_standby, fire_flow_event) via `ug export` once D-03 + W-01 merge; Scenario Lab lists them.
4. W-01 offline proof (Playwright offline run against the built app + API), R-01 rehearsal script.
5. Worktree cleanup (73 worktrees, 22 GB disk): needs the owner's OK.
