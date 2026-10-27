"""Demand invariants, input validation and deterministic arithmetic."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import yaml
from test_demand_helpers import (
    ASSUMPTIONS,
    GOLDEN_CALENDAR,
    GOLDEN_TIMEBASE,
    expectation,
    model,
    network,
)
from ug_core.assumptions import load_assumptions
from ug_core.canonical import canonical_json, sha256_hex
from ug_core.evidence import EvidenceLabel
from ug_core.numeric import round_for_hash
from ug_core.timebase import Timebase
from ug_water.demand import (
    DemandCalendar,
    DemandModel,
    DemandSeries,
    FireFlow,
    SpecialEvent,
)


@pytest.mark.parametrize("seed", [0, 7, 91, 1003])
@pytest.mark.parametrize(
    "calendar",
    [
        DemandCalendar(),
        GOLDEN_CALENDAR,
        DemandCalendar(heatwave=frozenset({date(2026, 3, d) for d in range(1, 8)})),
    ],
)
def test_positive_finite_properties(seed: int, calendar: DemandCalendar) -> None:
    demand = model()
    net = network()
    land_uses = {z.land_use for z in net.zones} | {"commercial", "industrial"}
    for land in land_uses:
        for ramadan in (False, True):
            pattern = demand.pattern(land, ramadan=ramadan)
            assert np.all(np.isfinite(pattern)) and np.all(pattern > 0)
            assert pattern.mean() == pytest.approx(1, abs=1e-15)
        multipliers = demand.multipliers(land, GOLDEN_TIMEBASE, calendar)
        assert np.all(np.isfinite(multipliers)) and np.all(multipliers > 0)
    for series in (
        demand.truth(net, GOLDEN_TIMEBASE, seed, calendar),
        demand.forecast(net, GOLDEN_TIMEBASE, seed, calendar),
    ):
        assert np.all(np.isfinite(series.values)) and np.all(series.values >= 0)
        assert series.values.shape == (2016, 260)
        np.testing.assert_array_equal(series.total_m3s(), series.values.sum(axis=1))


def test_labels_provenance_immutability_and_content_hash() -> None:
    demand = model()
    tb = Timebase(GOLDEN_TIMEBASE.start, 300, 2)
    truth = demand.truth(network(), tb, 7, DemandCalendar())
    forecast = demand.forecast(network(), tb, 7, DemandCalendar())
    assert truth.label is EvidenceLabel.SIMULATION
    assert forecast.label is EvidenceLabel.MODEL
    assert truth.assumption_set_hash == demand.assumptions.content_hash()
    assert all(
        a.label is EvidenceLabel.ASSUMPTION
        and not a.verified
        and "placeholder" in a.source_note.lower()
        for a in demand.assumptions.assumptions.values()
    )
    assert truth.junction_ids == tuple(sorted(j.id for j in network().junctions))
    for series in (truth, forecast):
        with pytest.raises(ValueError):
            series.values[0, 0] = 9
        with pytest.raises(ValueError):
            series.values.flags.writeable = True
        with pytest.raises(FrozenInstanceError):
            series.label = EvidenceLabel.MODEL  # type: ignore[misc]
    source = np.array(truth.values)
    detached = replace(truth, values=source)
    source[:] = 0
    np.testing.assert_array_equal(detached.values, truth.values)
    expected = sha256_hex(
        canonical_json(
            {
                "schema_version": "1",
                "timebase": tb.to_dict(),
                "junction_ids": truth.junction_ids,
                "unit": "m3/s",
                "values": [[round_for_hash(v) for v in row] for row in truth.values],
                "label": "SIMULATION",
                "assumption_set_hash": truth.assumption_set_hash,
            }
        )
    )
    assert truth.content_hash() == expected
    assert replace(truth, label=EvidenceLabel.MODEL).content_hash() != expected
    assert replace(truth, assumption_set_hash="a" * 64).content_hash() != expected
    assert replace(truth, values=truth.values + 0.00001).content_hash() != expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.001])
def test_series_rejects_nonfinite_negative(bad: float) -> None:
    tb = Timebase(GOLDEN_TIMEBASE.start, 300, 1)
    with pytest.raises(ValueError, match="finite and non-negative"):
        DemandSeries(tb, ("j1",), np.array([[bad]]), EvidenceLabel.MODEL, "a" * 64)


def test_series_guards_shape_ids_label_hash() -> None:
    valid = DemandSeries(
        Timebase(GOLDEN_TIMEBASE.start, 300, 1),
        ("j1",),
        np.array([[0.0]]),
        EvidenceLabel.MODEL,
        "a" * 64,
    )
    for changes, message in [
        ({"values": np.zeros((2, 1))}, "shape"),
        ({"junction_ids": ("z", "a")}, "sorted"),
        ({"label": EvidenceLabel.ASSUMPTION}, "label"),
        ({"assumption_set_hash": "bad"}, "SHA-256"),
    ]:
        with pytest.raises(ValueError, match=message):
            replace(valid, **changes)


def test_base_demands_not_rescaled_and_linear_interpolation_wraps() -> None:
    demand = model(noise_sigma=0, forecast_sigma=0)
    tb = Timebase(datetime(2026, 3, 1, 5, 30, tzinfo=UTC), 60, 1)  # 07:30 local
    normal = demand.pattern("residential")
    factor = (normal[7] + normal[8]) / 2 * demand.parameter("demand_season_m03")
    profile = demand.multipliers("residential", tb, DemandCalendar())
    assert profile[0] == pytest.approx(factor)
    late = Timebase(datetime(2026, 3, 1, 21, 30, tzinfo=UTC), 60, 1)
    assert demand.multipliers("residential", late, DemandCalendar())[
        0
    ] == pytest.approx(
        (normal[23] + normal[0]) / 2 * demand.parameter("demand_season_m03")
    )
    net = network()
    expected = expectation(demand, tb, DemandCalendar())
    for generate in (demand.truth, demand.forecast):
        np.testing.assert_array_equal(
            generate(net, tb, 7, DemandCalendar()).values, expected
        )
        scaled = replace(
            net,
            junctions=tuple(
                replace(j, base_demand=j.base_demand * 3) for j in net.junctions
            ),
        )
        np.testing.assert_allclose(
            generate(scaled, tb, 7, DemandCalendar()).values, expected * 3
        )


@pytest.mark.parametrize("month", range(1, 13))
def test_every_season_month(month: int) -> None:
    tb = Timebase(datetime(2026, month, 10, 10, tzinfo=UTC), 300, 1)
    demand = model()
    unity = model(**{f"demand_season_m{m:02d}": 1 for m in range(1, 13)})
    assert demand.multipliers("medical", tb, DemandCalendar())[0] == pytest.approx(
        unity.multipliers("medical", tb, DemandCalendar())[0]
        * demand.parameter(f"demand_season_m{month:02d}")
    )


@pytest.mark.parametrize("change", ["negative", "nan", "infinity", "missing", "unit"])
def test_invalid_assumption_copy(tmp_path: Path, change: str) -> None:
    data = yaml.safe_load(ASSUMPTIONS.read_text())
    name = "demand_diurnal_residential_h07"
    entry = data["assumptions"][name]
    if change == "missing":
        del data["assumptions"][name]
    elif change == "unit":
        entry["unit"] = "h"
    else:
        value = {"negative": -1, "nan": float("nan"), "infinity": float("inf")}[change]
        entry["distribution"] = dict(
            type="triangular", min=value, mode=value, max=value
        )
    copy = tmp_path / "demand_copy.yaml"
    copy.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="positive|finite|missing|unit"):
        DemandModel.from_file(copy).truth(
            network(), GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR
        )
    assert load_assumptions(ASSUMPTIONS).assumptions[name].distribution.mode > 0


def test_unknown_land_use_and_calendar_references() -> None:
    net = network()
    unknown = replace(
        net, zones=tuple(replace(z, land_use="unlisted") for z in net.zones)
    )
    with pytest.raises(ValueError, match="unknown land use 'unlisted'"):
        model().truth(unknown, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    start = datetime(2026, 3, 1)
    for cal, message in [
        (
            DemandCalendar(
                events=(
                    SpecialEvent("unknown_zone", start, start + timedelta(hours=1), 2),
                )
            ),
            "unknown zone",
        ),
        (
            DemandCalendar(
                fire_flows=(
                    FireFlow(
                        "unknown_junction", start, start + timedelta(hours=1), 0.01
                    ),
                )
            ),
            "unknown junction",
        ),
    ]:
        for generate in (model().truth, model().forecast):
            with pytest.raises(ValueError, match=message):
                generate(net, GOLDEN_TIMEBASE, 7, cal)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("noise_sigma", -0.1, "sigma"),
        ("forecast_sigma", -0.1, "sigma"),
        ("noise_phi", 1, "phi"),
        ("forecast_phi", -1, "phi"),
        ("utc_offset_hours", 24, "offset"),
        ("iftar_hour_local", 24, "iftar"),
    ],
)
def test_invalid_process_parameters(field: str, value: float, message: str) -> None:
    demand = model(**{field: value})
    with pytest.raises(ValueError, match=message):
        generate = demand.forecast if field.startswith("forecast") else demand.truth
        generate(network(), GOLDEN_TIMEBASE, 7, DemandCalendar())


def test_negative_stochastic_multiplier_raises_without_clipping() -> None:
    for generate in (model(noise_sigma=20).truth, model(forecast_sigma=20).forecast):
        with pytest.raises(ValueError, match="stochastic multipliers"):
            generate(network(), GOLDEN_TIMEBASE, 7, DemandCalendar())
