"""Publication, reproducibility and corruption rejection for immutable runs."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from ug_core.canonical import canonical_json
from ug_core.manifest import Manifest
from ug_core.store import RunStore, StoreError
from ug_core.store.layout import run_id
from ug_core.store.truth_bundle import write_truth
from ug_core.timebase import Timebase
from ug_core.truth import TruthEvent, TruthSeries


def manifest():
    return Manifest(
        config={"faults": ["b", "a"]},
        seed=7,
        versions={"solver": "1"},
        unordered=("faults",),
    )


def series(value=30.0, reverse=False):
    channels = {"pressure:j1": [value] * 4, "flow:j2": [2.0] * 4}
    events = (TruthEvent("leak", "j1", 1, 3), TruthEvent("burst", "j1", 2))
    return TruthSeries(
        Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 4),
        dict(reversed(list(channels.items()))) if reverse else channels,
        tuple(reversed(events)) if reverse else events,
    )


def draft(store, value=30.0, reverse=False):
    run = store.new(manifest())
    write_truth(run, series(value, reverse))
    store.write_table(
        run,
        "expectation",
        pa.table(
            {
                "tick": [3, 1, 2, 0, 1],
                "sensor_id": ["b", "b", "a", "a", "a"],
                "expected_value": [3.0, 1.0, 2.0, 0.0, 4.0],
                "sigma": [0.1] * 5,
            }
        ),
    )
    return run


def test_repeat_is_verified_noop_and_changed_output_is_error(tmp_path):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    path = tmp_path / identifier
    before = {
        p.name: (p.stat().st_ino, p.stat().st_mtime_ns, p.read_bytes())
        for p in path.iterdir()
    }
    first = store.verify(identifier)
    assert store.write(draft(store, reverse=True)) == identifier
    assert store.verify(identifier).output_hashes == first.output_hashes
    assert {
        p.name: (p.stat().st_ino, p.stat().st_mtime_ns, p.read_bytes())
        for p in path.iterdir()
    } == before
    assert (path / "manifest.json").read_text() == canonical_json(first.to_dict())
    with pytest.raises(
        StoreError,
        match="same manifest, different outputs: the run is not deterministic; truth",
    ):
        store.write(draft(store, value=31.0))
    assert {p.name for p in tmp_path.iterdir()} == {identifier}


def test_unordered_manifest_key_has_same_identity():
    other = Manifest(
        config={"faults": ["a", "b"]},
        seed=7,
        versions={"solver": "1"},
        unordered=("faults",),
    )
    assert run_id(manifest()) == run_id(other)


def test_separate_processes_hash_the_same_content(tmp_path):
    script = """
import json, sys
from datetime import UTC, datetime
from ug_core.manifest import Manifest
from ug_core.store import RunStore
from ug_core.store.truth_bundle import write_truth
from ug_core.timebase import Timebase
from ug_core.truth import TruthSeries
store = RunStore(sys.argv[1])
m = Manifest(config={}, seed=7, versions={"solver":"1"})
run = store.new(m)
channels = {k: [30.0, 31.0] for k in {"pressure:j1", "flow:j2"}}
write_truth(run, TruthSeries(Timebase(datetime(2026,1,1,tzinfo=UTC),300,2), channels))
identifier = store.write(run)
print(json.dumps([identifier, dict(store.verify(identifier).output_hashes)], sort_keys=True))
"""
    results = []
    for seed in ("1", "42"):
        completed = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=True,
            capture_output=True,
            text=True,
        )
        results.append(json.loads(completed.stdout))
    assert results[0] == results[1]
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "change",
    [
        "value",
        "delete",
        "extra",
        "hash",
        "seed",
        "rename",
        "unknown_field",
        "missing_hash",
    ],
)
def test_tampering_refused_by_verify_and_open(tmp_path, change):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    path = tmp_path / identifier
    if change == "value":
        table = pq.read_table(path / "truth.parquet")
        data = table.to_pydict()
        data["value"][0] += 1
        pq.write_table(pa.table(data, schema=table.schema), path / "truth.parquet")
    elif change == "delete":
        (path / "truth.parquet").unlink()
    elif change == "extra":
        pq.write_table(pa.table({"tick": [0]}), path / "unexpected.parquet")
    elif change == "rename":
        identifier = "run_" + "0" * 16
        path.rename(tmp_path / identifier)
    else:
        data = json.loads((path / "manifest.json").read_text())
        if change == "hash":
            data["output_hashes"]["truth"] = "0" * 64
        elif change == "seed":
            data["seed"] += 1
        elif change == "missing_hash":
            del data["output_hashes"]["truth"]
        else:
            data["unknown"] = "value"
        (path / "manifest.json").write_text(canonical_json(data))
    for action in (store.verify, store.open):
        with pytest.raises(StoreError):
            action(identifier)


def test_existing_corrupt_run_cannot_be_overwritten(tmp_path):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    path = tmp_path / identifier / "truth.parquet"
    path.write_bytes(b"damaged")
    with pytest.raises(StoreError):
        store.write(draft(store))
    assert path.read_bytes() == b"damaged"


def test_reader_rechecks_after_open(tmp_path):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    reader = store.open(identifier)
    (tmp_path / identifier / "expectation.parquet").unlink()
    with pytest.raises(StoreError, match="run changed after open"):
        reader.read_table("expectation")


def test_failed_atomic_publication_cleans_all_staging(tmp_path, monkeypatch):
    store = RunStore(tmp_path / "runs")
    run = draft(store)

    def fail(*args):
        raise OSError("injected replacement failure")

    monkeypatch.setattr("ug_core.store.run.os.replace", fail)
    with pytest.raises(StoreError, match="injected replacement failure"):
        store.write(run)
    assert list(store.root.iterdir()) == []


def test_failed_parquet_write_cleans_all_staging(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run = draft(store)

    def fail(*args):
        raise OSError("injected parquet failure")

    monkeypatch.setattr("ug_core.store.run.write_parquet", fail)
    with pytest.raises(StoreError, match="injected parquet failure"):
        store.write(run)
    assert list(tmp_path.iterdir()) == []


def test_simultaneous_publish_rechecks_winner(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run = draft(store)
    other_root = tmp_path / "other"
    other_store = RunStore(other_root)
    identifier = other_store.write(draft(other_store))
    original = os.replace

    def race(source, destination):
        original(other_root / identifier, destination)
        return original(source, destination)

    monkeypatch.setattr("ug_core.store.run.os.replace", race)
    assert store.write(run) == identifier
    assert len(list(tmp_path.glob(".run_*"))) == 0
    store.verify(identifier)


@pytest.mark.parametrize("name", ["../run_x", "run_ABC", "/etc/passwd"])
def test_invalid_run_paths_are_refused(tmp_path, name):
    with pytest.raises(StoreError, match="invalid run id"):
        RunStore(tmp_path).open(name)


def test_symlink_output_is_refused(tmp_path):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    path = tmp_path / identifier / "truth.parquet"
    saved = tmp_path / "saved.parquet"
    path.rename(saved)
    path.symlink_to(saved)
    with pytest.raises(StoreError, match="unsafe output"):
        store.open(identifier)


@pytest.mark.parametrize("changed_content", [False, True])
def test_reader_refuses_rewritten_file_after_open(tmp_path, changed_content):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    reader = store.open(identifier)
    path = tmp_path / identifier / "expectation.parquet"
    before = path.stat()
    table = pq.read_table(path)
    if changed_content:
        data = table.to_pydict()
        data["expected_value"][0] += 1
        table = pa.table(data, schema=table.schema)
    pq.write_table(table, path)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
    with pytest.raises(StoreError, match="^run changed after open$"):
        reader.read_table("expectation", ticks=(0, 1))


def test_hash_once_per_write_and_no_hash_per_read(tmp_path, monkeypatch):
    import ug_core.store.run as module

    original = module.table_hash
    calls = []

    def track(table, key):
        calls.append(key)
        return original(table, key)

    monkeypatch.setattr(module, "table_hash", track)
    store = RunStore(tmp_path)
    run = draft(store)
    assert len(calls) == 2
    identifier = store.write(run)
    assert len(calls) == 2
    reader = store.open(identifier)
    assert len(calls) == 4
    for _ in range(3):
        reader.read_table("expectation", ticks=(0, 1))
    assert len(calls) == 4

    # Cached content must own its buffers; callers can mutate numpy-backed Arrow.
    run = store.new(manifest())
    write_truth(run, series())
    source = np.array([1.0])
    store.write_table(run, "detector_x", pa.table({"tick": [0], "value": source}))
    source[0] = 99.0
    assert run._tables["detector_x"]["value"].to_pylist() == [1.0]


def test_reader_hashes_manifest_bytes_even_with_same_stat(tmp_path):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    reader = store.open(identifier)
    path = tmp_path / identifier / "manifest.json"
    before = path.stat()
    data = path.read_bytes()
    path.write_bytes(data.replace(b'"seed":7', b'"seed":8'))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    with pytest.raises(StoreError, match="^run changed after open$"):
        reader.read_table("expectation")
