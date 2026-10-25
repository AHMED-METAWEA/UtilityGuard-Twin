# INVENTORY: the reference baseline `freebuff/` (short)

Phase A0 deliverable, 2026-10-25. Purpose: say what the reference contains and how to run it, so we can take reuse decisions. It is not an audit. Details and evidence: `PITFALLS.md` (traps, measurements), `codex_inventory_raw.md` (Codex's exhaustive run log), `codex_audit_raw.md` (Codex's independent read-only audit).

## What it is
- Generated earlier by a different AI agent (freebuf) from a smaller prompt. Imported unmodified under `freebuff/`, git tag `baseline-freebuf` (commit `debfd51`). 79 files tracked. Reference only, no authority (`ADOPTION_PLAN.md` section 0).
- Backend (`freebuff/backend`): about 5.6k lines of Python in 20 app modules plus 7 test files and a conftest: `network` (hypothetical grid, about 40 junctions, 1 reservoir, 1 tank, duty pump plus 1 standby, 1 PRV), `scenarios` (schema, 9 presets, WNTR runner, sensor simulation), `quality`, `detect` (baseline, rule-based detector, diagnosis), `alerts`, `impact`, `finance` (+ `assumptions.yaml`), `decision`, `evidence`, `eval`, `store` (SQLite), `main.py` (REST and WebSocket).
- Frontend (`freebuff/frontend`): React 18, Vite, TypeScript, Recharts, SVG map; one page (`Dashboard.tsx`) and 9 components. No frontend test runner.
- Other: `Makefile`, `docker-compose.yml`, its own README and 6 docs in `freebuff/docs/`, `data/eval_report.json`, one screenshot.

## Presets (9)
`normal`, `holiday`, `heatwave`, `leak_gradual`, `leak_sudden`, `sensor_drift`, `sensor_stuck`, `pump_outage`, `leak_plus_sensor_drift`. No Ramadan preset.

## Earlier milestones, by source presence (Codex, reviewed by the lead)
All four (M1 twin/stream/map, M2 quality/detection/alerts, M3 impact/cost/decision/evidence, M4 extras/evaluation) are **partial**: the main modules exist; the Evaluation page, an explicit before/after view and a standalone drift monitor do not. Presence is not correctness; see `PITFALLS.md`.

## How to run it as a reference (do not run it inside the new build)
```bash
python3.11 -m venv freebuff/.venv
freebuff/.venv/bin/python -m pip install -e "freebuff/backend[dev]"      # needs network once
cd freebuff/backend && ../.venv/bin/python -m pytest -q                  # 34 passed in about 2.5 to 3.3 minutes
cd freebuff/frontend && npm install && npm run build                     # builds; npm reports 2 audit notices (1 moderate, 1 high)
docker compose -f freebuff/docker-compose.yml config                     # parses; not started or built in A0
```
`.venv` and `node_modules` are not in git. The shipped venv has stale script shebangs (created under a different folder); use `python -m ...`.

## Measured
- Tests: 34 passed, 0 failed (lead and Codex, independently).
- Determinism: identical output hash for all 9 presets across two separate processes, same machine. Not tested across machines.
- Runtime: 3.3 to 7.8 s per 48 h scenario; 11.4 s for a 7-day normal run.
- Physics checks that held: leak orifice law exact against the solver; mass conserved to 0.05 % on the fault-free run; all 43 WNTR symbols the code uses exist in 1.5.0 with matching signatures.

## Versions
Python 3.11.7 (Codex also installed it on 3.12.4). WNTR 1.5.0 (declared `>=1.5,<1.6`). numpy 2.4.6, pandas 3.1.0, pydantic 2.14.1, FastAPI 0.159 to 0.162 depending on the install (declared `>=0.110`, unpinned: fresh installs do not resolve identically). No backend lockfile; the frontend has `package-lock.json`. Node v22.15.1, npm 10.9.2, Docker Compose v5.3.1.

## Not covered (by design or not run)
The frontend was not audited by the lead (Codex reports on it in `codex_audit_raw.md`, not reproduced). The baseline's own evaluation script was not run (its committed `eval_report.md` agrees with our measurements). `docker compose up` was not run. Behavior on another operating system or CPU was not tested.
