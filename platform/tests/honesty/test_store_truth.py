"""Store truth boundary: privileged writer, restricted reader and clean outputs."""

import ast
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from honesty_support import ROOT, forbidden_property, imports, truth_violations
from ug_core.manifest import Manifest
from ug_core.store import RunReader, RunStore, StoreError
from ug_core.store.truth_bundle import write_truth
from ug_core.timebase import Timebase
from ug_core.truth import TruthEvent, TruthSeries

STORE = ROOT / "platform/ug_core/src/ug_core/store"


def test_only_privileged_bundle_module_may_import_truth():
    paths = sorted(STORE.glob("*.py"))
    assert len(paths) == 6
    privileged = STORE / "truth_bundle.py"
    assert truth_violations(privileged.read_text(), any_truth_import=True)
    for path in paths:
        if path != privileged:
            assert not truth_violations(path.read_text(), any_truth_import=True), path


def test_consumer_outputs_and_reader_have_no_privileged_properties(tmp_path):
    store = RunStore(tmp_path)
    run = store.new(Manifest(config={}, seed=7, versions={"test": "1"}))
    write_truth(
        run,
        TruthSeries(
            Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 2),
            {"pressure:j1": [30.0, 20.0]},
            (TruthEvent("leak", "j1", 1),),
        ),
    )
    for name in ("telemetry", "expectation", "quality", "detector_test"):
        data = {"tick": [1, 0], "value": [20.0, 30.0]}
        if not name.startswith("detector_"):
            data["sensor_id"] = ["a", "a"]
        store.write_table(run, name, pa.table(data))
    identifier = store.write(run)
    reader = store.open(identifier)
    files = sorted((tmp_path / identifier).glob("*.parquet"))
    assert len(files) == 5
    for path in files:
        if path.stem == "truth":
            assert "fault_tag_hidden" in pq.read_table(path).column_names
        else:
            table = pq.read_table(path)
            assert "fault_tag_hidden" not in table.column_names
            assert not any(forbidden_property(name) for name in table.column_names)
            rows = reader.read_table(path.stem)
            assert rows and not any(forbidden_property(name) for name in rows[0])
    for target in (RunReader, reader):
        assert not any(forbidden_property(name) for name in dir(target))
    for name in ("truth", "truth_backup", "detector_truth"):
        with pytest.raises(StoreError, match="restricted table"):
            reader.read_table(name)


def test_platform_has_no_domain_or_reference_imports():
    paths = [
        path for src in (ROOT / "platform").glob("*/src") for path in src.rglob("*.py")
    ]
    assert paths
    for path in paths:
        for node, target in imports(ast.parse(path.read_text())):
            assert target.split(".")[0] not in {"domains", "ug_water", "freebuff"}, (
                path,
                node.lineno,
                target,
            )


def test_consumer_writer_refuses_schema_truth_smuggling(tmp_path):
    for carrier in ("schema", "field", "nested", "case", "nested_metadata"):
        store = RunStore(tmp_path / "runs")
        run = store.new(Manifest(config={}, seed=7, versions={"test": "1"}))
        table = pa.table({"tick": [0], "sensor_id": ["a"]})
        if carrier == "schema":
            table = table.replace_schema_metadata({b"hidden": b"truth"})
        elif carrier == "field":
            table = pa.table(
                {"tick": [0], "sensor_id": ["a"]},
                schema=pa.schema(
                    [
                        pa.field("tick", pa.int64(), metadata={b"note": b"truth"}),
                        pa.field("sensor_id", pa.string()),
                    ]
                ),
            )
        else:
            child = pa.field(
                "value" if carrier == "nested_metadata" else "Fault_Tag_Hidden",
                pa.float64(),
                metadata={b"note": b"truth"} if carrier == "nested_metadata" else None,
            )
            if carrier == "case":
                table = pa.table(
                    {"tick": [0], "sensor_id": ["a"], "Fault_Tag_Hidden": [None]}
                )
            else:
                schema = pa.schema(
                    list(table.schema)
                    + [pa.field("support", pa.list_(pa.struct([child])))]
                )
                table = pa.table(
                    {"tick": [0], "sensor_id": ["a"], "support": [None]}, schema=schema
                )
        with pytest.raises(StoreError):
            store.write_table(run, "expectation", table)
        assert not run._tables
        assert not store.root.exists()
