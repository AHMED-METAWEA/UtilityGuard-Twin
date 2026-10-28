# Handoff: demo work, state on 2026-10-28 evening (lead)

Plan of record: `docs/DEMO_PLAN.md`. Feature freeze Fri 30 Oct; demo Mon 2 Nov ("best partial version").
Load limits (owner): at most 2 heavy jobs; `OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1`; Playwright `--workers=1`; check `vm_stat` before launching. `make demo-baseline` peaks at 3.6 GB: run it alone. A fault run peaks at about 1 GB.
Safety net: `~/Desktop/UG-wt/tools/safety.sh dev` (installs like CI, then `make ci`).

## Open PRs (owner merges)
| PR | What | State |
|---|---|---|
| #74 | D-07 API | container fixed (validation loaded on first use; the image has no jsonschema/contracts); ci, audit, container green; mergeable |
| #76 | D-03 faults | Codex review: 2 S1 + 6 S2 fixed (outage through a lossless gate valve, order-free failover), 3 S2 accepted; `docs/reviews/D-03.md` |
| #78 | W-01 baseline in the app | contains #74 (merge #74 first); review + mutation in `docs/reviews/W-01.md`; lead changes: offline gate allows fetch only in `src/app/api.ts` (`app-api-*.js`), RunStore cache by stat signature, Command Center recorded mode |
| #77 | this handoff | Tier 0 |

## Next
1. After #74, #76 and #78 merge: export the five fault scenarios as bundles (`ug run <preset> --duration-hours 48` + `ug export`, one at a time) into `var/demo-runs/views`; Scenario Lab and Runs screen list them (W-02 card: run picker in the shell, incidents and decision for fault runs).
2. Command Center recorded mode shows only map + readings: add KPIs computed from the bundle (CALCULATED) and the incident panel from `incidents.json`.
3. Offline proof (W-01b): Playwright offline run against the built app + API with the baseline bundle; R-01 rehearsal script (`docs/DEMO_SCRIPT.md`).
4. Worktree cleanup (73 worktrees, 22 GB): owner's OK needed.

## How to see the baseline
`cd ~/Desktop/UG-wt/codex-demo-w01 && make demo-baseline && UG_RUNS_DIR=var/demo-runs/views .venv/bin/python -m ug_api` and, in another terminal, `cd frontend && npm run build && npx vite preview`; open the printed URL (`#/` and `#/map`). The first load validates the bundle (about 5 s).
