# Demo runbook: recorded runs, backup, restore, serve

The demo runs no simulation. The runs are recorded once (`make demo-record`), packed into one archive for backup (`make demo-pack`), restored on the demo machine (`make demo-restore ARCHIVE=...`) and served by `ug_api` together with the built frontend (`make demo-serve`).

## Record once (about 2.5 min on the 8 GB Mac, one step at a time)
`make demo-record` records `normal_week`, `leak_sudden`, `leak_gradual_medium`, `burst_main`, `pump_outage_standby` and `fire_flow_event` (procedural network, seed 1, standard tier, 48 h, 5-minute ticks), then exports each view bundle into `var/demo-runs/views` (git-ignored). Nothing else heavy should run at the same time. Peak memory per step goes to `var/demo-runs/memory.tsv`.

Measured on 2026-10-28 (macOS `time -l`, maximum resident set size):

| scenario | run peak MB | export peak MB |
|---|---|---|
| normal_week | 1011 | 907 |
| leak_sudden | 1006 | 896 |
| leak_gradual_medium | 918 | 902 |
| burst_main | 981 | 904 |
| pump_outage_standby | 979 | 892 |
| fire_flow_event | 980 | 892 |

The export first peaked at 3.5 GB: `engine._truth` copied the whole flow matrix once per link and every column view kept its copy alive. It now indexes the ticks once, and the expectation keeps only the sensors' channels. The physics is unchanged: the exported bundle is byte-identical before and after.

## Backup and restore
- `make demo-pack` verifies the bundles, writes `SHA256SUMS` and packs them into `var/demo-runs.tar.gz` (about 4.6 MB, 1,122 files; same bundles give the same archive).
- `make demo-restore ARCHIVE=/path/demo-runs.tar.gz` refuses absolute or `..` paths, links and bad checksums, verifies every bundle, then replaces `var/demo-runs/views`.
- `make demo-verify` loads every bundle through the API's own `RunStore` (every file validated against its contract, no unexpected file) and prints one line per run.

## Serve at demo time
`cd frontend && npm run build` once, then `make demo-serve` (one process: the API serves `/api` and the built frontend on http://127.0.0.1:8080). Runtime memory: `ug_api` physical footprint 296 MB after loading all six runs (the first load of a run validates it, about 5 s; later requests take a few ms), plus the browser tab.

## Known limits (2026-10-28)
- The app shows the first recorded run only (no run picker yet).
- Detection false alarm: every run, the baseline included, shows one incident at tick 295 (R_D2_CUSUM on all sensors). Cause: the expectation is open-loop (its own tank controls), so it drifts from the real run after day 1. Fix planned (D-05b): anchor the expectation to the observed tank levels. Until then the incidents are not shown as detections in the demo.
- No decision file is exported for the fault runs yet.
