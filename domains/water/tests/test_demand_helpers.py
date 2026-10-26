"""Shared deterministic demand test cases (no runtime dependency on test helpers)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from ug_core.assumptions import load_assumptions, parse_assumptions
from ug_core.timebase import Timebase
from ug_water.demand import DemandCalendar, DemandModel
from ug_water.network.model import Network
from ug_water.network.procedural import ProceduralCapitalProvider

ROOT = Path(__file__).resolve().parents[3]
ASSUMPTIONS = ROOT / "assumptions/demand_v1.yaml"
START = datetime(2026, 2, 28, 22, tzinfo=UTC)  # March 1 midnight at UTC+2.
GOLDEN_TIMEBASE = Timebase(START, 300, 7 * 24 * 12)
GOLDEN_CALENDAR = DemandCalendar(
    holidays=frozenset({date(2026, 3, 2)}),
    ramadan=frozenset({date(2026, 3, d) for d in (4, 5, 6)}),
)


@lru_cache(maxsize=1)
def network() -> Network:
    return ProceduralCapitalProvider().build(1)


def model(**modes: float) -> DemandModel:
    if not modes:
        return DemandModel.from_file(ASSUMPTIONS)
    data = load_assumptions(ASSUMPTIONS).to_dict()
    for name, value in modes.items():
        data["assumptions"][name]["distribution"] = {
            "type": "triangular",
            "min": value,
            "mode": value,
            "max": value,
        }
    return DemandModel(parse_assumptions(data))


def expectation(
    demand: DemandModel, tb: Timebase, cal: DemandCalendar
) -> NDArray[np.float64]:
    net = network()
    profiles = {z.id: demand.multipliers(z.land_use, tb, cal) for z in net.zones}
    return np.column_stack([j.base_demand * profiles[j.zone] for j in net.junctions])


def print_summary() -> None:
    """Regenerate the acceptance report, without changing any golden constants."""
    from datetime import timedelta
    from time import perf_counter

    start = perf_counter()
    net = ProceduralCapitalProvider().build(1)
    demand = DemandModel.from_file(ASSUMPTIONS)
    loaded = perf_counter()
    truth = demand.truth(net, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    truth_done = perf_counter()
    forecast = demand.forecast(net, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    end = perf_counter()
    print("Synthetic F0 procedural network; not ACUD data; parameters ASSUMPTION.")
    print(
        f"NumPy {np.__version__}; CALCULATED build seconds: load+network={loaded - start:.6f}, "
        f"truth={truth_done - loaded:.6f}, forecast={end - truth_done:.6f}, total={end - start:.6f}"
    )
    print(
        "local date | SIMULATION L/s mean min max | MODEL L/s mean min max | peak local SIMULATION/MODEL"
    )
    for day in range(7):
        rows, peaks = [], []
        for series in (truth, forecast):
            values = series.total_m3s()[day * 288 : (day + 1) * 288] * 1000
            rows.append(f"{values.mean():.6f} {values.min():.6f} {values.max():.6f}")
            peak = int(np.argmax(values))
            peaks.append(f"{peak // 12:02d}:{peak % 12 * 5:02d}")
        local_date = (GOLDEN_TIMEBASE.start + timedelta(hours=2, days=day)).date()
        print(f"{local_date} | {rows[0]} | {rows[1]} | {peaks[0]}/{peaks[1]}")
    print("SIMULATION truth hash:", truth.content_hash())
    print("MODEL forecast hash:", forecast.content_hash())
    long = Timebase(GOLDEN_TIMEBASE.start, 300, 28 * 288)
    expected = expectation(demand, long, GOLDEN_CALENDAR)
    print(
        "CALCULATED 4-week seed=7 residual statistics vs ASSUMPTION targets: "
        "noise SD=.04 phi=.75; forecast SD=.06 phi=.85"
    )
    print("zone | truth SD phi | forecast SD phi")
    truth_long = demand.truth(net, long, 7, GOLDEN_CALENDAR)
    forecast_long = demand.forecast(net, long, 7, GOLDEN_CALENDAR)
    for zone in net.zones:
        column = next(
            i
            for i, j in enumerate(net.junctions)
            if j.zone == zone.id and j.base_demand > 0
        )
        rows = []
        for series in (truth_long, forecast_long):
            residual = series.values[:, column] / expected[:, column] - 1
            rows.append(
                f"{np.std(residual):.6f} {np.corrcoef(residual[:-1], residual[1:])[0, 1]:.6f}"
            )
        print(f"{zone.id} | {rows[0]} | {rows[1]}")


if __name__ == "__main__":
    print_summary()
