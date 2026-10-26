"""CALCULATED local week-scale regression timings; all input is SIMULATION/F1."""

from datetime import UTC, datetime
from time import perf_counter

import pyarrow as pa
from ug_core.manifest import Manifest
from ug_core.store import RunStore
from ug_core.store.truth_bundle import write_truth
from ug_core.timebase import Timebase
from ug_core.truth import TruthEvent, TruthSeries


def benchmark_week(root):
    store = RunStore(root)
    run = store.new(
        Manifest(
            config={
                "fidelity": "F1",
                "source": "SIMULATED",
                "junctions": 260,
                "ticks": 2016,
            },
            seed=42,
            versions={"store": "1"},
        )
    )
    axis = Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 2016)
    values = [float(30 + tick % 7) for tick in axis.ticks()]
    simulation = TruthSeries(
        axis,
        {
            f"{quantity}:j{element:03}": values
            for element in range(260)
            for quantity in ("pressure", "demand", "head", "flow")
        },
        (TruthEvent("leak", "j001", 100, 120),),
    )
    # A week-sized consumer table makes the window query representative too.
    expectation = pa.table(
        {
            "tick": list(axis.ticks()),
            "sensor_id": ["s1"] * 2016,
            "expected_value": values,
        }
    )
    start = perf_counter()
    write_truth(run, simulation)
    store.write_table(run, "expectation", expectation)
    assembled = perf_counter()
    identifier = store.write(run)
    written = perf_counter()
    store.verify(identifier)
    verified = perf_counter()
    reader = store.open(identifier)
    opened = perf_counter()
    rows = reader.read_table("expectation", ticks=(100, 102))
    read = perf_counter()
    assert [row["tick"] for row in rows] == [100, 101]
    return {
        "assembly": assembled - start,
        "publish": written - assembled,
        "write": written - start,
        "verify": verified - written,
        "open": opened - verified,
        "window_read": read - opened,
    }


def test_week_scale_performance(tmp_path):
    timings = benchmark_week(tmp_path)
    print("CALCULATED seconds (SIMULATION/F1):", timings)
    assert timings["write"] < 20, timings
    assert timings["verify"] < 15, timings
    assert timings["window_read"] < 1, timings
