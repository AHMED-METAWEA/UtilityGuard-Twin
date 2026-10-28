#!/bin/sh
# Record the demo runs once, one at a time, and export their view bundles (no simulation at
# demo time). Peak memory of every step goes to var/demo-runs/memory.tsv (macOS `time -l`).
set -eu
export OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1
PY=${PY:-.venv/bin/python}
OUT=var/demo-runs
mkdir -p "$OUT"
printf 'scenario\tstep\tpeak_mb\tseconds\n' > "$OUT/memory.tsv"
measure() { # scenario step command...
  scenario=$1; step=$2; shift 2
  /usr/bin/time -l "$@" > "$OUT/last.out" 2> "$OUT/last.err" || { cat "$OUT/last.err" >&2; exit 1; }
  peak=$(awk '/maximum resident set size/ {printf "%d", $1 / 1048576}' "$OUT/last.err")
  secs=$(awk '/ real / {print $1}' "$OUT/last.err")
  printf '%s\t%s\t%s\t%s\n' "$scenario" "$step" "$peak" "$secs" >> "$OUT/memory.tsv"
}
for scenario in normal_week leak_sudden leak_gradual_medium burst_main pump_outage_standby fire_flow_event; do
  measure "$scenario" run "$PY" -m ug_cli run "$scenario" --network procedural --tier standard \
    --seed 1 --duration-hours 48 --store "$OUT/store"
  run_id=$(sed -n 's/^run_id: //p' "$OUT/last.out")
  measure "$scenario" export "$PY" -m ug_cli export "$run_id" --store "$OUT/store" --out "$OUT/views"
  echo "$scenario $run_id"
done
rm -f "$OUT/last.out" "$OUT/last.err"
column -t "$OUT/memory.tsv"
