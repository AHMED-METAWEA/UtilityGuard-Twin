# Handoff: demo work, state on 2026-10-28 night (lead)

Plan: `docs/DEMO_PLAN.md`; freeze Fri 30 Oct; demo Mon 2 Nov. Mac has 8 GB: at most 2 heavy jobs, single-threaded maths, Playwright `--workers=1`. Safety net: `~/Desktop/UG-wt/tools/safety.sh dev`.

## Open PRs (owner merges, in this order)
1. #79 D-03 review fixes (#76 was merged at its first head; gate-valve outage, order-free failover).
2. #78 W-01 baseline in the app (rebased on dev, #74 commits dropped; mergeable, ci/audit/container green).
3. #80 W-02 recorded demo runs (stacked on #78 + #79): `make demo-record|demo-pack|demo-verify|demo-restore|demo-serve`, `docs/DEMO_RUNBOOK.md`; engine memory fix (bundles byte-identical).

## Recorded runs
In `~/Desktop/UG-wt/claude-demo-w02/var/demo-runs/` (views + `memory.tsv`) and `var/demo-runs.tar.gz` (4.6 MB). Peaks 0.9-1.0 GB per step.

## Next (critical path)
1. D-05b (lead, detection, Opus high): every run, the baseline included, raises one incident at tick 295 (R_D2_CUSUM on all sensors). Cause: the expectation is open-loop (own tank-level pump controls) and drifts after day 1 (level residual sd 0.045 m day 1 vs 1.27 m day 2). Design: anchor the expectation to observed tank levels (re-initialise tank levels from the latest valid level readings every hour) or drive the pumps from the observed state; then re-record and require zero incidents on normal_week and one on each fault run near its onset.
2. W-03: run picker (Runs screen / shell), incidents panel and decision for fault runs (decision.json is not exported yet).
3. Offline proof against `make demo-serve`; R-01 rehearsal script.
4. Worktree cleanup (owner's OK).
