"""Local calendar, known factors and truth-only event/fire windows."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from test_demand_helpers import GOLDEN_TIMEBASE, START, model, network
from ug_core.timebase import Timebase
from ug_water.demand import DemandCalendar, FireFlow, SpecialEvent


@pytest.mark.parametrize("kind", [SpecialEvent, FireFlow])
def test_window_and_value_validation(kind: type[SpecialEvent] | type[FireFlow]) -> None:
    start = datetime(2026, 3, 1)
    for end in (start, start - timedelta(hours=1)):
        with pytest.raises(ValueError, match="after start"):
            kind("some_id", start, end, 1)
    with pytest.raises(ValueError, match="naive local"):
        kind("some_id", start.replace(tzinfo=UTC), start + timedelta(hours=1), 1)
    for bad in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="positive|finite"):
            kind("some_id", start, start + timedelta(hours=1), bad)


def test_calendar_freezes_inputs_and_rejects_datetimes_as_dates() -> None:
    dates = {date(2026, 3, 1)}
    cal = DemandCalendar(holidays=dates)  # type: ignore[arg-type]
    dates.clear()
    assert cal.holidays == frozenset({date(2026, 3, 1)})
    with pytest.raises(ValueError, match="local dates"):
        DemandCalendar(ramadan=frozenset({datetime(2026, 3, 1)}))
    with pytest.raises(ValueError, match="SpecialEvent"):
        DemandCalendar(events=("bad",))  # type: ignore[arg-type]


def test_friday_saturday_and_fixed_offset_boundary() -> None:
    demand = model(noise_sigma=0, forecast_sigma=0)
    for day in range(2, 9):  # Monday through Sunday, March 2026.
        local_day = date(2026, 3, day)
        # 23:00 UTC preceding day is 01:00 local on this date.
        tb = Timebase(datetime(2026, 3, day, tzinfo=UTC) - timedelta(hours=1), 300, 1)
        actual = demand.forecast(network(), tb, 7, DemandCalendar())
        for i, junction in enumerate(network().junctions):
            land = next(z.land_use for z in network().zones if z.id == junction.zone)
            base = (
                junction.base_demand
                * demand.pattern(land)[1]
                * demand.parameter("demand_season_m03")
            )
            weekend = (
                demand.parameter(f"demand_weekend_{land}")
                if local_day.weekday() in (4, 5)
                else 1
            )
            assert actual.values[0, i] == pytest.approx(base * weekend)
    thursday = Timebase(datetime(2026, 3, 5, 23, tzinfo=UTC), 300, 1)
    shifted = demand.multipliers("government", thursday, DemandCalendar())[0]
    unshifted = model(utc_offset_hours=0).multipliers(
        "government", thursday, DemandCalendar()
    )[0]
    assert shifted == pytest.approx(
        demand.pattern("government")[1]
        * demand.parameter("demand_weekend_government")
        * demand.parameter("demand_season_m03")
    )
    assert unshifted == pytest.approx(
        demand.pattern("government")[23] * demand.parameter("demand_season_m03")
    )


def test_holiday_government_drops_sharply_residential_rises_and_all_factors_apply() -> (
    None
):
    tb = Timebase(datetime(2026, 3, 1, 22, tzinfo=UTC), 300, 288)  # Monday
    demand = model()
    holiday = DemandCalendar(holidays=frozenset({date(2026, 3, 2)}))
    for generate in (demand.truth, demand.forecast):
        normal = generate(network(), tb, 7, DemandCalendar()).values
        changed = generate(network(), tb, 7, holiday).values
        for i, junction in enumerate(network().junctions):
            land = next(z.land_use for z in network().zones if z.id == junction.zone)
            np.testing.assert_allclose(
                changed[:, i], normal[:, i] * demand.parameter(f"demand_holiday_{land}")
            )
            if land == "government" and junction.base_demand > 0:
                assert np.all(changed[:, i] < normal[:, i] * 0.5)
            if land == "residential" and junction.base_demand > 0:
                assert np.all(changed[:, i] > normal[:, i])
    for land in {z.land_use for z in network().zones}:
        ordinary = demand.multipliers(land, tb, DemandCalendar())
        heat = demand.multipliers(land, tb, replace(holiday, heatwave=holiday.holidays))
        np.testing.assert_allclose(
            heat / ordinary,
            demand.parameter(f"demand_holiday_{land}")
            * demand.parameter(f"demand_heatwave_{land}"),
        )


@pytest.mark.parametrize("iftar", [17, 18, 20])
def test_ramadan_peak_moves_with_iftar(iftar: int) -> None:
    demand = model(iftar_hour_local=iftar)
    tb = Timebase(START, 300, 288)
    for generate in (demand.truth, demand.forecast):
        normal = generate(network(), tb, 7, DemandCalendar()).total_m3s()
        ramadan = generate(
            network(), tb, 7, DemandCalendar(ramadan=frozenset({date(2026, 3, 1)}))
        ).total_m3s()
        normal_hour = int(np.argmax(normal)) / 12
        ramadan_hour = int(np.argmax(ramadan)) / 12
        assert iftar <= ramadan_hour <= iftar + 2
        assert not iftar <= normal_hour <= iftar + 2


def test_event_truth_only_zone_and_half_open_window() -> None:
    demand = model()
    net = network()
    start, end = datetime(2026, 3, 1, 10), datetime(2026, 3, 1, 12)
    cal = DemandCalendar(events=(SpecialEvent(net.zones[0].id, start, end, 2),))
    normal = demand.truth(net, GOLDEN_TIMEBASE, 7, DemandCalendar()).values
    changed = demand.truth(net, GOLDEN_TIMEBASE, 7, cal).values
    expected = normal.copy()
    columns = [i for i, j in enumerate(net.junctions) if j.zone == net.zones[0].id]
    expected[120:144, columns] *= 2  # Local midnight start, 12 samples/hour.
    np.testing.assert_array_equal(changed, expected)
    np.testing.assert_array_equal(
        demand.forecast(net, GOLDEN_TIMEBASE, 7, cal).values,
        demand.forecast(net, GOLDEN_TIMEBASE, 7, DemandCalendar()).values,
    )


def test_fire_adds_exact_flow_and_forecast_is_unaffected() -> None:
    demand = model()
    net = network()
    start, end = datetime(2026, 3, 1, 10), datetime(2026, 3, 1, 12)
    cal = DemandCalendar(fire_flows=(FireFlow(net.junctions[3].id, start, end, 0.025),))
    normal = demand.truth(net, GOLDEN_TIMEBASE, 7, DemandCalendar())
    changed = demand.truth(net, GOLDEN_TIMEBASE, 7, cal)
    delta = np.zeros_like(normal.values)
    delta[120:144, 3] = 0.025
    np.testing.assert_allclose(
        changed.values - normal.values, delta, rtol=0, atol=1e-17
    )
    np.testing.assert_array_equal(changed.values[:120], normal.values[:120])
    np.testing.assert_array_equal(changed.values[144:], normal.values[144:])
    assert (
        demand.forecast(net, GOLDEN_TIMEBASE, 7, cal).content_hash()
        == demand.forecast(net, GOLDEN_TIMEBASE, 7, DemandCalendar()).content_hash()
    )


def test_overlapping_events_multiply_fires_add_order_independently() -> None:
    net = network()
    start, end = datetime(2026, 3, 1), datetime(2026, 3, 1, 1)
    events = (
        SpecialEvent(net.junctions[0].zone, start, end, 2),
        SpecialEvent(net.junctions[0].zone, start, end, 3),
    )
    fires = (
        FireFlow(net.junctions[0].id, start, end, 0.01),
        FireFlow(net.junctions[0].id, start, end, 0.02),
    )
    tb = Timebase(START, 300, 1)
    demand = model()
    empty = demand.truth(net, tb, 7, DemandCalendar()).values
    cal = DemandCalendar(events=events, fire_flows=fires)
    result = demand.truth(net, tb, 7, cal)
    assert result.values[0, 0] == pytest.approx(empty[0, 0] * 6 + 0.03)
    assert (
        result.content_hash()
        == demand.truth(
            net, tb, 7, DemandCalendar(events=events[::-1], fire_flows=fires[::-1])
        ).content_hash()
    )
