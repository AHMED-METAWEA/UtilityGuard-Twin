"""Cross-process determinism and explicit one-week regression hashes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import pytest
from test_demand_helpers import (
    GOLDEN_CALENDAR,
    GOLDEN_TIMEBASE,
    ROOT,
    assert_same_series,
    model,
    network,
)

# Regenerate with the exact case in test_golden_hashes using content_hash().
# Update only for a reviewed, intentional model/assumption/numeric change, with
# before/after results and rationale in the handoff; never to hide a regression.
GOLDEN_TRUTH = "12e2527e5952dedec3c3f60a0065cda7ede829dfaee61606e9debec4504043f5"
GOLDEN_FORECAST = "80f179c3211a8d712509ae2498d71ad0385e4bef7de5ff83049c93014aba5beb"


@pytest.mark.parametrize("path", ["truth", "forecast"])
def test_golden_hashes(path: str) -> None:
    generate = getattr(model(), path)
    result = generate(network(), GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    assert result.content_hash() == (
        GOLDEN_TRUTH if path == "truth" else GOLDEN_FORECAST
    )


@pytest.mark.parametrize("path", ["truth", "forecast"])
def test_repeated_calls_seeds_and_separate_process(path: str, tmp_path: Path) -> None:
    generate = getattr(model(), path)
    first = generate(network(), GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    expected = first.content_hash()
    assert_same_series(generate(network(), GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR), first)
    assert (
        generate(network(), GOLDEN_TIMEBASE, 8, GOLDEN_CALENDAR).content_hash()
        != expected
    )
    code = f"""
from datetime import UTC, date, datetime
from ug_core.timebase import Timebase
from ug_water.demand import DemandModel, DemandCalendar
from ug_water.network.procedural import ProceduralCapitalProvider
model = DemandModel.from_file({str(ROOT / "assumptions/demand_v1.yaml")!r})
calendar = DemandCalendar(holidays=frozenset({{date(2026,3,2)}}), ramadan=frozenset(date(2026,3,d) for d in (4,5,6)))
series = model.{path}(ProceduralCapitalProvider().build(1), Timebase(datetime(2026,2,28,22,tzinfo=UTC),300,2016),7,calendar)
print(series.content_hash())
"""
    env = {**os.environ, "PYTHONHASHSEED": "391"}
    # Different CWD also proves no dependence on the caller's working directory.
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert process.stdout.strip() == expected


def test_week_build_performance() -> None:
    demand = model()
    net = network()
    start = perf_counter()
    demand.truth(net, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    demand.forecast(net, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    elapsed = perf_counter() - start
    assert elapsed < 2, f"combined truth and forecast build: {elapsed:.3f}s"
