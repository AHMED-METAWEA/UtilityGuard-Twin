#!/usr/bin/env bash
# All mutations run in disposable copies; editable installs must not hide them.
# Usage: scripts/mutation_check.sh — clean suite plus ten mutations, all must be caught.
set -euo pipefail
repo=$(git rev-parse --show-toplevel)
python="$repo/.venv/bin/python"
workspace=$(mktemp -d "${TMPDIR:-/tmp}/ug-honesty.XXXXXXXX")
trap 'rm -rf "$workspace"' EXIT
export PYTHONDONTWRITEBYTECODE=1

# Include tracked files and untracked, non-ignored deliverables before committing.
"$python" - "$repo" "$workspace/original" <<'PY'
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo, destination = map(Path, sys.argv[1:])
names = subprocess.check_output(
    ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=repo
).split(b"\0")
for name in sorted(set(names) - {b""}):
    relative = Path(os.fsdecode(name))
    source, target = repo / relative, destination / relative
    if not source.is_file():
        raise SystemExit(f"Cannot copy repository file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
PY

select_copy() {
    copy=$1
    export PYTHONPATH="$copy/platform/ug_core/src:$copy/platform/ug_intel/src:$copy/platform/ug_api/src:$copy/platform/ug_cli/src:$copy/domains/water/src${PYTHONPATH:+:$PYTHONPATH}"
    cd "$copy"
    "$python" - "$copy" <<'PY'
import sys
from pathlib import Path
import ug_core

location = Path(ug_core.__file__).resolve()
print(f"Source binding: {location}")
if not location.is_relative_to(Path(sys.argv[1]).resolve()):
    raise SystemExit("ABORT: ug_core is outside the copy; mutations would be invisible")
PY
}

select_copy "$workspace/original"
if ! "$python" -m pytest platform/tests/honesty -q > "$workspace/clean.log" 2>&1; then
    cat "$workspace/clean.log"
    echo 'ABORT: clean honesty suite failed'
    exit 1
fi
echo 'CLEAN PASS'

caught=0
missed=0
for mutation in truth_import truth_payload nan_to_zero unordered_manifest stream_source money_label exact_tick manifest_seed_dropped evidence_valueless_allowed telemetry_label_simulation; do
    copy="$workspace/$mutation"
    "$python" - "$workspace/original" "$copy" <<'PY'
import shutil
import sys
shutil.copytree(sys.argv[1], sys.argv[2])
PY
    select_copy "$copy"
    "$python" - "$mutation" <<'PY'
import ast
import compileall
import json
import sys
from pathlib import Path

mutation = sys.argv[1]
touched = []

def write(path, text):
    path = Path(path)
    before = path.read_text() if path.exists() else None
    if before == text:
        raise SystemExit(f"ABORT: mutation {mutation} did not change {path}")
    path.write_text(text)
    touched.append(path)

def edit_json(path, change):
    path = Path(path)
    value = json.loads(path.read_text())
    before = json.dumps(value, sort_keys=True)
    change(value)
    if json.dumps(value, sort_keys=True) == before:
        raise SystemExit(f"ABORT: JSON mutation {mutation} made no change to {path}")
    write(path, json.dumps(value, indent=2) + "\n")

def replace_once(path, old, new):
    path = Path(path)
    source = path.read_text()
    if source.count(old) != 1:
        raise SystemExit(f"ABORT: mutation {mutation}: expected one anchor in {path}")
    write(path, source.replace(old, new, 1))

core = Path("platform/ug_core/src/ug_core")
if mutation == "truth_import":
    write("platform/ug_intel/src/ug_intel/leak.py", "from ug_core.truth import TruthSeries\n")
elif mutation == "truth_payload":
    edit_json("contracts/v1/telemetry-reading.schema.json",
              lambda obj: obj["properties"].update(truth_value={"type": "number"}))
    edit_json("contracts/examples/telemetry-reading/pressure_suspect.json",
              lambda obj: obj.update(truth_value=30.9))
elif mutation == "nan_to_zero":
    path = core / "numeric.py"
    source = path.read_text()
    function = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "finite")
    raises = [n for n in ast.walk(function) if isinstance(n, ast.Raise)
              and isinstance(n.exc, ast.Call)
              and ast.unparse(n.exc.func) == "NonFiniteError"]
    if len(raises) != 1:
        raise SystemExit("ABORT: finite() must have exactly one NonFiniteError raise")
    node = raises[0]
    lines = source.splitlines(keepends=True)
    old = "".join(lines[node.lineno - 1:node.end_lineno])
    indent = " " * node.col_offset
    # Keep infinity rejection; specifically simulate the reference NaN-to-zero bug.
    new = (f"{indent}if math.isnan(number):\n{indent}    return 0.0\n" + old)
    replace_once(path, old, new)
elif mutation == "unordered_manifest":
    replace_once(core / "manifest.py",
                 "config[key] = sorted(items, key=canonical_json)",
                 "config[key] = list(items)")
elif mutation == "stream_source":
    edit_json("contracts/examples/stream-envelope/tick_replay_with_suspect_sensor.json",
              lambda obj: obj["payload"].pop("stream_source"))
elif mutation == "money_label":
    edit_json("contracts/examples/evidence-record/cost_24h.json",
              lambda obj: obj.update(label="SIMULATION"))
elif mutation == "exact_tick":
    path = core / "timebase.py"
    source = path.read_text()
    function = next(n for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.FunctionDef) and n.name == "tick_at_offset")
    guard = next(n for n in function.body if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "remainder != 0")
    lines = source.splitlines(keepends=True)
    old = "".join(lines[guard.lineno - 1:guard.end_lineno])
    replace_once(path, old, " " * guard.col_offset + "steps = round(seconds / self.step_seconds)\n")
elif mutation == "manifest_seed_dropped":
    replace_once(core / "manifest.py", '            "seed": self.seed,\n', '')
    replace_once(core / "manifest.py",
                 '{"config": thaw(self.config), "seed": self.seed}',
                 '{"config": thaw(self.config)}')
elif mutation == "evidence_valueless_allowed":
    replace_once(core / "evidence.py", "elif self.value is None:",
                 "elif self.value is None and False:")
elif mutation == "telemetry_label_simulation":
    edit_json("contracts/examples/telemetry-reading/pressure_suspect.json",
              lambda obj: obj.update(label="SIMULATION"))
else:
    raise SystemExit(f"ABORT: unknown mutation {mutation}")

# A syntactically broken mutation is a harness failure, never a caught bug.
for path in touched:
    if path.suffix == ".py":
        if not compileall.compile_file(str(path), quiet=1, force=True):
            raise SystemExit(f"ABORT: invalid Python mutation in {path}")
    elif path.suffix == ".json":
        json.loads(path.read_text())
if not touched:
    raise SystemExit(f"ABORT: mutation {mutation} touched nothing")
PY
    status=0
    "$python" -m pytest platform/tests/honesty -q > "$workspace/$mutation.log" 2>&1 || status=$?
    if [[ "$status" -eq 1 ]]; then
        echo "CAUGHT $mutation"
        caught=$((caught + 1))
    elif [[ "$status" -eq 0 ]]; then
        echo "MISSED $mutation"
        missed=$((missed + 1))
    else
        cat "$workspace/$mutation.log"
        echo "ABORT: $mutation failed to run tests (pytest exit $status)"
        exit 1
    fi
done
echo "Summary: clean PASS; $caught CAUGHT; $missed MISSED; 10 mutations"
[[ "$caught" -eq 10 && "$missed" -eq 0 ]]
