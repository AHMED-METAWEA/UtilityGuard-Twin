# Baseline inventory — T-A0-002

## Inventory

OBSERVED on 2026-10-25 in the initially clean `codex/a0-inventory` worktree. All measured counts, timings and versions below are OBSERVED; milestone completeness is MODEL assessment from the cited source. This is a synthetic, hypothetical utility twin, with no ACUD operator data or field validation. No other audit documents were read. No code changes, commits, pushes, or Docker starts/builds were made.

`git ls-files | wc -l` printed `94` before these deliverables were created. Counts cover tracked files, excluding installed environments and generated output. `wc -l` counts newline bytes, not semantic source lines; the tracked PNG contributes 2083 newline bytes and the newline-free TypeScript build-info file contributes zero.

The counts were run with Python grouping the output of `git ls-files`, then invoking `subprocess.run(['wc', '-l', *files])` for each top-level group and each immediate `freebuff/backend/app` module. Root files were grouped separately.

| Top-level group | Tracked files | `wc -l` total |
|---|---:|---:|
| Root files | 4 | 333 |
| `.codex/` | 1 | 17 |
| `docs/` | 10 | 2632 |
| `freebuff/` | 79 | 14940 |

| Baseline tree | Tracked files | `wc -l` total | Contents observed from tracked paths |
|---|---:|---:|---|
| `freebuff/` root | 4 | 227 | Ignore rules, Makefile, README, Compose |
| `freebuff/backend/` | 44 | 5767 | FastAPI application, scenario/network/analysis modules, tests, packaging, Dockerfile |
| `freebuff/frontend/` | 23 | 5887 | React dashboard and components, API/types, styles, Vite/TypeScript/nginx configuration, lockfile, Dockerfile |
| `freebuff/docs/` | 6 | 395 | Tracked baseline documentation paths; contents not used for this inventory |
| `freebuff/data/` | 1 | 581 | Tracked evaluation JSON; contents not used as current test evidence |
| `freebuff/screenshots/` | 1 | 2083 | PNG; raw newline count, not source lines |

Backend application total: `5121` newline counts. Actual per-file `wc -l` output follows; empty package initializers are included. The sensor implementation is in `scenarios/runner.py`; `sensors/__init__.py` is empty.

```text
backend/app/(app root)
       0 freebuff/backend/app/__init__.py
      71 freebuff/backend/app/analysis.py
     122 freebuff/backend/app/config.py
     469 freebuff/backend/app/main.py
     662 total

backend/app/alerts
       0 freebuff/backend/app/alerts/__init__.py
     146 freebuff/backend/app/alerts/manager.py
     146 total

backend/app/decision
       0 freebuff/backend/app/decision/__init__.py
     348 freebuff/backend/app/decision/engine.py
     348 total

backend/app/detect
       0 freebuff/backend/app/detect/__init__.py
      40 freebuff/backend/app/detect/baseline.py
     202 freebuff/backend/app/detect/detector.py
     342 freebuff/backend/app/detect/diagnose.py
     584 total

backend/app/eval
       0 freebuff/backend/app/eval/__init__.py
     226 freebuff/backend/app/eval/metrics.py
     433 freebuff/backend/app/eval/run.py
     659 total

backend/app/evidence
       0 freebuff/backend/app/evidence/__init__.py
     222 freebuff/backend/app/evidence/builder.py
     222 total

backend/app/finance
       0 freebuff/backend/app/finance/__init__.py
     108 freebuff/backend/app/finance/assumptions.yaml
     262 freebuff/backend/app/finance/engine.py
     370 total

backend/app/impact
       0 freebuff/backend/app/impact/__init__.py
     353 freebuff/backend/app/impact/runner.py
     353 total

backend/app/network
       0 freebuff/backend/app/network/__init__.py
     439 freebuff/backend/app/network/builder.py
      82 freebuff/backend/app/network/zones.py
     521 total

backend/app/quality
       0 freebuff/backend/app/quality/__init__.py
     212 freebuff/backend/app/quality/checks.py
     212 total

backend/app/scenarios
       0 freebuff/backend/app/scenarios/__init__.py
     101 freebuff/backend/app/scenarios/library.py
     541 freebuff/backend/app/scenarios/runner.py
     171 freebuff/backend/app/scenarios/schema.py
     813 total

backend/app/sensors
       0 freebuff/backend/app/sensors/__init__.py

backend/app/store
       0 freebuff/backend/app/store/__init__.py
     231 freebuff/backend/app/store/db.py
     231 total

```

External URL/CDN search (executed):

```sh
rg -n -i 'https?://|fonts\.(googleapis|gstatic)|cdn|unpkg|cdnjs|@import|url\(' freebuff/frontend/index.html freebuff/frontend/src
```

Result: no matches (exit 1); there are no literal HTTP(S) URLs, CDN names, CSS imports or CSS URL references matching that search in these paths. A deliberately broader preliminary search, `rg -n -i 'https?://|fonts|cdn|unpkg|cdnjs' ...`, also matched the following local `fontSize` declarations (false positives, listed exhaustively):

```text
freebuff/frontend/src/components/Charts.tsx:33:  fontSize: 12,
freebuff/frontend/src/components/Charts.tsx:52:            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
freebuff/frontend/src/components/Charts.tsx:53:            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} domain={[0, 8]} />
freebuff/frontend/src/components/Charts.tsx:66:            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
freebuff/frontend/src/components/Charts.tsx:67:            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} unit={sensorUnit} />
freebuff/frontend/src/components/Charts.tsx:80:            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
freebuff/frontend/src/components/Charts.tsx:81:            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} unit="σ" domain={[residualLow, residualHigh]} />
freebuff/frontend/src/components/Charts.tsx:98:            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
freebuff/frontend/src/components/Charts.tsx:99:            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} unit=" L/s" />
freebuff/frontend/src/components/Charts.tsx:101:            <Legend wrapperStyle={{ fontSize: 11 }} />
```

Additional search `rg -n 'external|https?:|@import|url\(' freebuff/frontend/index.html freebuff/frontend/src` found exactly one hit:

```text
freebuff/frontend/src/lib/api.ts:70:  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
```

This selects a protocol, not an external host. Line 71 constructs the WebSocket URL using `window.location.host`. `styles.css:17` names Inter and system fallback fonts without a font download. The Vite configuration contains localhost development proxies (`vite.config.ts:11-12`), outside the requested `index.html`/`src` search. No browser runtime or offline-container test was performed.

## Milestone status

These assessments describe source presence and visible omissions, not full milestone acceptance or production correctness. Paths below are relative to `freebuff/`.

| Earlier milestone | Status | File evidence and limits |
|---|---|---|
| M1 Twin, stream, map | partial | `backend/app/network/builder.py:171` builds the hypothetical WNTR model; lines 226-229 define only two pumps total (duty and standby), rather than the requested two plus standby. `scenarios/library.py:20`, `scenarios/runner.py:227` (pipe split), `:339` (simulation), `:461` (sensor layer); `main.py:221` (REST run creation), `:382` (WebSocket); `frontend/src/components/NetworkMap.tsx`, `Playback.tsx`, `ScenarioLab.tsx`, and `pages/Dashboard.tsx:474` wire the map/playback/lab. No Ramadan preset. Source presence does not prove hydraulic fidelity or truth separation. |
| M2 Quality, detection, alerts | partial | `backend/app/quality/checks.py:70`, `detect/detector.py:49`, `detect/diagnose.py:143` and `:259` (candidate pipes), `alerts/manager.py:36` implement quality, residual detection, diagnosis/localization and incident grouping. UI integration is in `frontend/src/pages/Dashboard.tsx:500` and `:559`, plus `SensorTable.tsx` and `IncidentPanel.tsx:128`. Dedicated Alerts/Data-quality pages are absent from the inspected frontend tree and Dashboard tab list (`:24-31`); these functions are dashboard panels. |
| M3 Impact, cost, decision, evidence | partial | `backend/app/impact/runner.py:168`, `finance/assumptions.yaml`, `finance/engine.py:223-246` (triangular Monte Carlo percentiles), `decision/engine.py:26-37` (actions), `:45` (break-even), `:106` (sensitivity), `evidence/builder.py:43`; UI panels `IncidentPanel.tsx`, `DecisionPanel.tsx` and `pages/Dashboard.tsx:559-586`. Impact uses a configurable crew response time (`impact/runner.py:187`), default 3 h (`assumptions.yaml:53-59`), not an explicit 6/24/72 h delay comparison. A dedicated “Why this number?” drawer was not found in the inspected frontend source search; evidence is presented in panels. |
| M4 Extras and evaluation | partial | `backend/app/alerts/manager.py:36` groups incidents; `backend/app/eval/run.py:343` and `:392` provide evaluation/CLI, and tracked `data/eval_report.json`/`docs/eval_report.md` exist. Evaluation was NOT_RUN in this task. No Evaluation tab/page, explicit before/after view, or standalone drift monitor was found in the tracked tree/Dashboard tab list and targeted source search. Sensor fault injection and quality checks are present, but do not establish a dedicated drift monitor. Optional PDF export and sensor placement optimization were not found; `pages/Dashboard.tsx:652` explicitly describes fixed placement. |

Presets read directly from `backend/app/scenarios/library.py:20-72`:

```text
normal
holiday
heatwave
leak_gradual
leak_sudden
sensor_drift
sensor_stuck
pump_outage
leak_plus_sensor_drift
```

Ramadan preset: missing from this dictionary. No preset simulation claims are inferred from the README or prior evaluation artifacts.

## How to run

Commands ran from this worktree unless a directory is shown. Only baseline-declared dependencies and their transitive dependencies were installed. Logs and temporary configuration were kept under `/tmp`; source/build environments were kept in ignored folders. Network was used for installation, not application runtime.

Python installation:

```sh
python3.11 -m venv freebuff/.venv
DIST_EXTRA_CONFIG=/tmp/ug-a0-egg-info.cfg PIP_CACHE_DIR=/tmp/ug-a0-pip-cache freebuff/.venv/bin/pip install -e "freebuff/backend[dev]"
```

Both completed with exit 0. The pip command was initially attempted before venv creation finished and returned exit 127; it was rerun after creation completed and succeeded. `/tmp/ug-a0-egg-info.cfg` was created with the following contents, redirecting editable-install metadata into the allowed ignored environment rather than creating `backend/*.egg-info`:

```ini
[egg_info]
egg_base = <worktree>/freebuff/.venv
```

Python compatibility installation:

```sh
python3.12 -m venv /tmp/ug-a0-python312
DIST_EXTRA_CONFIG=/tmp/ug-a0-egg-info.cfg PIP_CACHE_DIR=/tmp/ug-a0-pip-cache /tmp/ug-a0-python312/bin/pip install -e "freebuff/backend[dev]"
```

Both completed with exit 0. Python 3.12 tests/import validation: NOT_RUN; successful installation alone is not runtime compatibility evidence. The temporary environment was retained; nothing was deleted.

Frontend installation (exit 0):

```sh
cd freebuff/frontend && npm_config_cache=/tmp/ug-a0-npm-cache npm_config_package_lock=false npm install
```

Disabling lockfile writes preserves the tracked baseline lockfile. The installed dependency versions are observations of this run, not a claim that an unmodified default `npm install` would leave tracked files unchanged.

Frontend build: the exact in-place `cd freebuff/frontend && npm run build` is NOT_RUN because `tsc -b` writes tracked `tsconfig.tsbuildinfo`. Instead, every tracked frontend file was copied unchanged into `freebuff/frontend/node_modules/.inventory-build/` using `shutil.copy2`; that directory's `node_modules` symlinks to `..` to use the installed dependencies. No tracked source was edited. The command actually run was:

```sh
cd freebuff/frontend/node_modules/.inventory-build && /usr/bin/time -p npm run build
```

This completed with exit 0. Outputs are in the mirror's `dist/`. It verifies the unchanged source build in a different directory, not the requested exact in-place workflow. A preliminary attempt to establish write protection with `sandbox-exec -p '…' /usr/bin/true` failed with exit 71 (`sandbox_apply: Operation not permitted`); the mirror avoids relying on unavailable nested sandboxing.

Compose parse (exit 0):

```sh
docker compose -f freebuff/docker-compose.yml config
```

Parsed backend/frontend build contexts, backend data bind mount, backend healthcheck, ports and dependency. `make up` expands to `docker compose up --build` (`freebuff/Makefile:33-34`): it requests builds by source inspection only. Docker Compose `up` and `build`, including offline startup: NOT_RUN, explicitly forbidden. No claim that containers start or work offline.

Every shell command in `freebuff/README.md` (README assumes the `freebuff/` working directory):

| README line | Command | Ran? / result |
|---:|---|---|
| 32 | `make install` | NOT_RUN wrapper: uses unqualified `python3`, editable metadata and writable lockfile. Explicit Python 3.11 venv/editable installation and protected npm installation above succeeded. |
| 33 | `make start` | NOT_RUN: builds in place, then starts a persistent server. Build tested in isolated mirror only. |
| 41 | `make backend` | NOT_RUN: persistent hot-reload server; this task used tests, not interactive servers. |
| 42 | `make frontend` | NOT_RUN: persistent Vite dev server; this task used a production build. |
| 48 | `make up` | NOT_RUN: explicitly forbidden container startup/build. Target inspected, Compose config parsed. |
| 54 | `make test` | NOT_RUN wrapper; its pytest equivalent was run directly with the requested `-q` flag; see Test results. |
| 55 | `make eval` | NOT_RUN: default evaluation CLI overwrites tracked report files (`backend/app/eval/run.py:411-416`), outside allowed edits. |

Opening `http://127.0.0.1:8000` (README line 36): NOT_RUN, no server/browser session requested. README line 89 and its API table list HTTP methods/routes; these are interface descriptions, not shell commands. README scenario instructions and historical performance claims are not independent verification.

Other Adoption 6.6 checks: endpoint contract conformance, scalable storage, manifests, full honesty-label coverage, truth separation, licenses and a secret scan were NOT_RUN as audits; this inventory does not certify them. `tsc -b` ran as part of the mirror build; a separate linter is not declared in `frontend/package.json`. No additional audit files were read.

## Test results

Backend test command (exit 0):

```sh
export PYTHONPYCACHEPREFIX=<worktree>/freebuff/.venv/pycache
export UTILITYGUARD_DATA_DIR=<worktree>/freebuff/.venv/runtime-data
export MPLCONFIGDIR=<worktree>/freebuff/.venv/matplotlib
export PYTEST_ADDOPTS='-o cache_dir=<worktree>/freebuff/.venv/pytest-cache'
cd freebuff/backend && /usr/bin/time -p ../.venv/bin/python -m pytest -q
```

Result: **34 passed, 0 failed, 0 skipped, 0 errors**, 1 warning. Wall duration: **195.32 s** (user 176.33 s, sys 3.77 s), measured around the requested pytest invocation. The baseline already configures `addopts = "-q"`, so the additional command-line `-q` suppresses the textual count/duration summary. The pass count was counted from the 34 dots on the complete `[100%]` progress line, not copied from historical docs. No per-test skip/fail/error markers appeared; exit was 0. `/usr/bin/time` provides duration rather than a pytest-internal duration.

```text
..................................                                       [100%]
=============================== warnings summary ===============================
../.venv/lib/python3.11/site-packages/fastapi/testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
real 195.32
user 176.33
sys 3.77
```

No undeclared replacement dependency was installed. The environment variables route caches/runtime data into the ignored venv; test fixture databases use pytest temporary paths. A separate import check also successfully imported numpy, pandas, WNTR and FastAPI in the Python 3.11 environment.

Frontend install: 105 packages added, 106 audited, 24 s reported by npm; exit 0. npm reported 2 vulnerabilities (1 moderate, 1 high), and a Recharts 2.x deprecation. No audit fix or upgrade was run.

Frontend build command and location are documented above. `npm run build` invokes `tsc -b && vite build`: exit 0, 840 modules transformed, Vite reported 1.94 s, `/usr/bin/time -p` reported real 5.43 s (user 9.27 s, sys 0.71 s). Output: `dist/index.html` 0.40 kB, CSS 14.52 kB, JS 574.91 kB; gzip 0.27 / 3.65 / 165.74 kB respectively. Warning: a minified chunk exceeds 500 kB. Frontend automated tests: NOT_RUN; no test script is declared. Production build success is not browser functional validation.

`freebuff/.venv/bin/pip check`: exit 0, `No broken requirements found.` Python 3.12 backend tests: NOT_RUN (optional installation check only).

Card acceptance checks are recorded in the handoff. Lead rerun in a separate environment: NOT_RUN by Codex; requires the assigned reviewer.

## Versions

Values below were obtained using `python --version`, `importlib.metadata.version`, `node --version`, `npm --version`, installed frontend package JSON, and `docker compose version`.

| Tool/package | Python 3.11 environment / frontend | Python 3.12 compatibility install | Declaration / pinning |
|---|---|---|---|
| Python | 3.11.7 | 3.12.4 | `requires-python = ">=3.11"`; no exact pin |
| WNTR | 1.5.0 | 1.5.0 | `>=1.5,<1.6`, bounded range, not exact |
| FastAPI | 0.162.0 | 0.162.0 | `>=0.110`, not exact |
| pydantic | 2.14.1 | 2.14.1 | `>=2.6`, not exact |
| numpy | 2.4.6 | 2.5.4 | `>=1.24`, not exact |
| pandas | 3.1.0 | 3.1.0 | `>=2.0`, not exact |
| pytest | 9.1.1 | 9.1.1 | dev extra `>=8.0`, not exact |
| Node | v22.15.1 | n/a | README says Node >=18; no exact package.json engine pin |
| npm | 10.9.2 | n/a | No package-manager version pin in inspected package.json |
| React | 18.3.1 | n/a | `^18.3.1`, range; tracked npm lockfile exists |
| Vite | 5.4.21 | n/a | `^5.3.3`, range; tracked npm lockfile exists |
| TypeScript | 5.9.3 | n/a | `^5.5.3`, range; tracked npm lockfile exists |
| Recharts | 2.15.4 | n/a | `^2.12.7`, range; tracked npm lockfile exists |
| Docker Compose | v5.3.1 | n/a | Observed CLI, no exact pin in inspected Compose file |

`git ls-files '*lock*'` returned only `freebuff/frontend/package-lock.json`; there is no tracked backend lockfile. Python resolutions differ between interpreters (numpy above; also networkx 3.6.1 versus 3.7 and scipy 1.17.1 versus 1.18.1 in pip output). Fresh installs are therefore not guaranteed to resolve identical versions. The successful builds/tests here apply to the observed environment, not all allowed dependency versions.
