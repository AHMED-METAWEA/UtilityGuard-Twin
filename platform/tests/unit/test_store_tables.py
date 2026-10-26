"""Schema, content hashing, windows and privileged bundle rules."""

import hashlib
from datetime import UTC, datetime

import pyarrow as pa
import pytest
from test_store_run import draft, manifest, series
from ug_core.canonical import canonical_json
from ug_core.store import RunStore, StoreError
from ug_core.store.hashing import table_hash
from ug_core.store.tables import prepare
from ug_core.store.truth_bundle import read_truth, write_truth
from ug_core.timebase import Timebase
from ug_core.truth import TruthEvent, TruthSeries


def test_hash_is_canonical_content_not_file_bytes():
    table = prepare(
        "expectation",
        pa.table(
            {"tick": [1, 0], "sensor_id": ["b", "a"], "value": [1.23456789, -0.0]}
        ),
    )
    payload = {
        "columns": [[f.name, str(f.type), f.nullable] for f in table.schema],
        "key": ["tick", "sensor_id"],
        "label": "MODEL",
        "rows": [[0, "a", 0], [1, "b", 1.234568]],
    }
    digest = table_hash(table, ("tick", "sensor_id"))
    assert digest == hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    reordered = prepare(
        "expectation",
        pa.table({"tick": [0, 1], "sensor_id": ["a", "b"], "value": [0.0, 1.234568]}),
    )
    assert table_hash(reordered, ("tick", "sensor_id")) == digest
    changed_type = prepare(
        "expectation",
        pa.table({"tick": [0, 1], "sensor_id": ["a", "b"], "value": [0, 1]}),
    )
    same_values_float = prepare(
        "expectation",
        pa.table({"tick": [0, 1], "sensor_id": ["a", "b"], "value": [0.0, 1.0]}),
    )
    assert table_hash(changed_type, ("tick", "sensor_id")) != table_hash(
        same_values_float, ("tick", "sensor_id")
    )


def test_events_exact_element_window_overlap_and_no_event(tmp_path):
    store = RunStore(tmp_path)
    run = store.new(manifest())
    timebase = Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 4)
    write_truth(
        run,
        TruthSeries(
            timebase,
            {
                "pressure:j1": [30.0] * 4,
                "flow:j1": [2.0] * 4,
                "pressure:j10": [31.0] * 4,
                "flow:zone:j1": [3.0] * 4,
            },
            (TruthEvent("leak", "j1", 1, 3), TruthEvent("burst", "j1", 2)),
        ),
    )
    identifier = store.write(run)
    table = read_truth(store, identifier)
    assert table.schema.metadata == {b"label": b"SIMULATION"}
    assert [(f.name, str(f.type), f.nullable) for f in table.schema] == [
        ("tick", "int64", False),
        ("element_id", "string", False),
        ("quantity", "string", False),
        ("value", "double", False),
        ("fault_tag_hidden", "string", True),
    ]
    rows = table.to_pylist()
    assert len(rows) == 16
    for row in rows:
        expected = (
            [None, "leak", "burst+leak", "burst"][row["tick"]]
            if row["element_id"] == "j1"
            else None
        )
        assert row["fault_tag_hidden"] == expected
    assert {r["element_id"] for r in rows} == {"j1", "j10", "zone:j1"}
    # Explicit no-event fixture, including the previously tagged element.
    other = RunStore(tmp_path / "no_events")
    run = other.new(manifest())
    write_truth(run, TruthSeries(timebase, {"pressure:j1": [30.0] * 4}))
    assert all(
        r["fault_tag_hidden"] is None
        for r in read_truth(other, other.write(run)).to_pylist()
    )


@pytest.mark.parametrize("channel", ["pressure", ":j1", "pressure:", ""])
def test_invalid_channels_are_rejected_before_any_write(tmp_path, channel):
    store = RunStore(tmp_path / "runs")
    run = store.new(manifest())
    with pytest.raises(StoreError, match="quantity:element_id"):
        write_truth(run, TruthSeries(series().timebase, {channel: [1.0] * 4}))
    assert not store.root.exists()


@pytest.mark.parametrize(
    "name", ["truth", "TRUTH", "truth_backup", "detector_truth", "untruthful"]
)
def test_consumer_reader_and_writer_refuse_all_truth_names(tmp_path, name):
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    with pytest.raises(StoreError, match="restricted table"):
        store.open(identifier).read_table(name)
    with pytest.raises(StoreError, match="restricted table"):
        store.write_table(store.new(manifest()), name, pa.table({"tick": [0]}))


@pytest.mark.parametrize(
    "column",
    [
        "fault_tag_hidden",
        "faultTag",
        "Ground_Truth",
        "hidden_value",
        "injected_fault",
        "channels",
        "events",
        "target",
        "parameters",
    ],
)
def test_consumer_writer_refuses_privileged_columns(tmp_path, column):
    store = RunStore(tmp_path / "runs")
    with pytest.raises(StoreError, match="restricted column"):
        store.write_table(
            store.new(manifest()),
            "expectation",
            pa.table({"tick": [0], "sensor_id": ["a"], column: [1.0]}),
        )
    assert not store.root.exists()


def test_nested_privileged_columns_rejected_even_if_null(tmp_path):
    store = RunStore(tmp_path)
    inferred = pa.table(
        {"tick": [0], "sensor_id": ["a"], "support": [{"hidden": 1.0}]}
    ).schema
    table = pa.table(
        {"tick": [0], "sensor_id": ["a"], "support": [None]}, schema=inferred
    )
    with pytest.raises(StoreError, match="restricted column"):
        store.write_table(store.new(manifest()), "expectation", table)


@pytest.mark.parametrize(
    "name",
    ["arbitrary", "analysis_incident", "detector_", "../telemetry", "detector_x/y"],
)
def test_unlisted_table_names_rejected(tmp_path, name):
    store = RunStore(tmp_path)
    with pytest.raises(StoreError, match="outside Spec"):
        store.write_table(store.new(manifest()), name, pa.table({"tick": [0]}))


def test_window_is_half_open_and_key_ordered_through_duckdb(tmp_path, monkeypatch):
    import ug_core.store.tables as tables

    original = tables.duckdb.connect
    calls = []

    def track(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(tables.duckdb, "connect", track)
    store = RunStore(tmp_path)
    identifier = store.write(draft(store))
    reader = store.open(identifier)
    rows = reader.read_table("expectation", ticks=(1, 3))
    assert [(r["tick"], r["sensor_id"], r["expected_value"]) for r in rows] == [
        (1, "a", 4.0),
        (1, "b", 1.0),
        (2, "a", 2.0),
    ]
    assert calls == [(":memory:",)]
    assert [(r["tick"], r["sensor_id"]) for r in reader.read_table("expectation")] == [
        (0, "a"),
        (1, "a"),
        (1, "b"),
        (2, "a"),
        (3, "b"),
    ]
    assert reader.read_table("expectation", ticks=(2, 2)) == []
    for ticks in ((-1, 3), (3, 1), (True, 3), (1.5, 3)):
        with pytest.raises(StoreError, match="window"):
            reader.read_table("expectation", ticks=ticks)
    with pytest.raises(StoreError, match="missing output"):
        reader.read_table("telemetry")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_never_written_or_replaced(tmp_path, value):
    store = RunStore(tmp_path / "runs")
    run = store.new(manifest())
    with pytest.raises(ValueError, match="finite"):
        TruthSeries(series().timebase, {"pressure:j1": [value] * 4})
    with pytest.raises(StoreError, match="finite"):
        store.write_table(
            run,
            "expectation",
            pa.table({"tick": [0], "sensor_id": ["a"], "value": [value]}),
        )
    assert not run._tables
    assert not store.root.exists()
    # Recheck at publication even if a caller tampers with the private draft.
    write_truth(run, series())
    table = run._tables["truth"]
    data = table.to_pydict()
    data["value"][0] = value
    run._tables["truth"] = pa.table(data, schema=table.schema)
    with pytest.raises(StoreError, match="finite"):
        store.write(run)
    assert not store.root.exists()


@pytest.mark.parametrize(
    "data",
    [
        {"tick": [0, 0], "sensor_id": ["a", "a"]},
        {"tick": [0], "sensor_id": [None]},
        {"tick": [-1], "sensor_id": ["a"]},
        {"tick": [0.0], "sensor_id": ["a"]},
    ],
)
def test_invalid_keys_rejected(tmp_path, data):
    with pytest.raises(StoreError):
        RunStore(tmp_path).write_table(
            RunStore(tmp_path).new(manifest()), "expectation", pa.table(data)
        )


def test_complete_draft_required_and_duplicate_outputs_rejected(tmp_path):
    store = RunStore(tmp_path / "runs")
    run = store.new(manifest())
    with pytest.raises(StoreError, match="required bundle"):
        store.write(run)
    assert not store.root.exists()
    write_truth(run, series())
    with pytest.raises(StoreError, match="duplicate output"):
        write_truth(run, series())


def test_numeric_detector_id_and_nested_float_hashing(tmp_path):
    store = RunStore(tmp_path)
    run = draft(store)
    store.write_table(
        run, "detector_1-v1", pa.table({"tick": [0], "residuals": [[1.23456789]]})
    )
    identifier = store.write(run)
    assert store.open(identifier).read_table("detector_1-v1") == [
        {"tick": 0, "residuals": [1.23456789]}
    ]
    left = prepare("detector_x", pa.table({"tick": [0], "residuals": [[1.23456789]]}))
    right = prepare("detector_x", pa.table({"tick": [0], "residuals": [[1.234568]]}))
    assert table_hash(left, ("tick",)) == table_hash(right, ("tick",))
