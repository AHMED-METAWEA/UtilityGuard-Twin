"""D-04 measurement acceptance: deterministic sensor simulation, never truth payloads."""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from solver_fixtures import START, STEP, demand, line, pumped_loop
from ug_core.ports import MeasurementPort
from ug_core.rng import SeedStreams
from ug_core.telemetry import TelemetrySeries
from ug_core.timebase import Timebase
from ug_core.truth import TruthEvent, TruthSeries
from ug_intel.quality import assess
from ug_water.network.model import Network, Pipe, Sensor, Valve, Zone
from ug_water.solver import simulate
from ug_water.telemetry.measurement import WaterMeasurement, rtu_group
from ug_water.telemetry.readings import to_readings
from ug_water.telemetry.whatif import SensorWhatIf, as_faults

ROOT = Path(__file__).resolve().parents[3]
ZERO = {
    "base_dropout_per_tick": 0.0,
    **{
        k: {"noise_sigma": 0.0, "noise_fraction": 0.0}
        for k in ("pressure", "flow", "level")
    },
}


def network() -> Network:
    return replace(
        pumped_loop(),
        sensors=(
            Sensor("a", "pressure", "j1"),
            Sensor("b", "flow", "p1"),
            Sensor("c", "level", "t1"),
        ),
        sensor_sets={"all": ("a", "b", "c"), "one": ("a",)},
    )


def truth(ticks: int = 48, step: int = STEP) -> TruthSeries:
    return TruthSeries(
        Timebase(START, step, ticks),
        {
            "pressure:j1": [20 + k / 10 for k in range(ticks)],
            "flowrate:p1": [0.012345] * ticks,
            "level:t1": [3.12345] * ticks,
        },
        (TruthEvent("private", "j1", 0),),
    )


def validator(name: str, definition: str | None = None) -> Draft202012Validator:
    schemas = [
        json.loads(p.read_text()) for p in (ROOT / "contracts/v1").glob("*.schema.json")
    ]
    registry: Registry[Any] = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas
    )
    schema = next(s for s in schemas if s["$id"].endswith(f"/{name}.schema.json"))
    if definition:
        schema = {"$ref": schema["$id"] + f"#/$defs/{definition}"}
    return Draft202012Validator(schema, registry=registry)


def test_payload_contract_delivery_quality_and_no_hidden_fields() -> None:
    net, physical = network(), truth()
    disabled = as_faults([SensorWhatIf("a", "disable", 0)], STEP, 48)
    series, delays = WaterMeasurement(net, "all", disabled).measure_with_delivery(
        physical, SeedStreams(1)
    )
    quality = assess(
        series,
        {"a": "pressure", "b": "flow", "c": "level"},
        {"a": 0.01, "b": 0.01, "c": 0.001},
        {s: (-100, 100) for s in series.readings},
        delays,
    )
    rows = to_readings(series, net, delays, quality)
    assert rows[0]["value"] is None and rows[0]["quality"]["status"] == "bad"
    check = validator("telemetry-reading")
    for row in rows:
        check.validate(row)
        expected = physical.timebase.time_at(row["tick"]) + timedelta(
            seconds=delays[row["sensor_id"]][row["tick"]]
        )
        assert row["delivered_at"] == expected.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert row["label"] == "SENSOR_SIM"
        assert set(row) == {
            "schema_version",
            "tick",
            "sensor_id",
            "value",
            "unit",
            "label",
            "delivered_at",
            "quality",
        }
    assert [(r["tick"], r["sensor_id"]) for r in rows] == [
        (t, s) for t in range(48) for s in ("a", "b", "c")
    ]
    bare = to_readings(series, net)
    assert all("delivered_at" not in row and "quality" not in row for row in bare)
    for row in bare:
        check.validate(row)
    assert type(series) is TelemetrySeries
    assert not hasattr(series, "events") and not hasattr(series, "channels")


def test_repeatability_permutation_independence_and_port() -> None:
    net, physical = network(), truth(100)
    faults = [
        {"type": "sensor_noise_growth", "sensor_id": "a", "start_hour": 0, "factor": 3},
        {"type": "sensor_offset", "sensor_id": "a", "start_hour": 0.1, "magnitude": 2},
        {
            "type": "sensor_drift",
            "sensor_id": "a",
            "start_hour": 0.1,
            "drift_per_hour": 0.5,
        },
        {
            "type": "sensor_stuck",
            "sensor_id": "a",
            "start_hour": 1,
            "duration_hours": 1,
        },
        {
            "type": "sensor_dropout",
            "sensor_id": "a",
            "start_hour": 2,
            "duration_hours": 1,
            "probability": 0.5,
        },
    ]
    model: MeasurementPort = WaterMeasurement(net, "all", faults)
    first = model.measure(physical, SeedStreams(7))
    assert first == model.measure(physical, SeedStreams(7))
    assert first == WaterMeasurement(net, "all", list(reversed(faults))).measure(
        physical, SeedStreams(7)
    )
    baseline, delays = WaterMeasurement(net, "all").measure_with_delivery(
        physical, SeedStreams(7)
    )
    modified, other_delays = WaterMeasurement(net, "all", faults).measure_with_delivery(
        physical, SeedStreams(7)
    )
    assert delays == other_delays
    assert modified.readings["a"] != baseline.readings["a"]
    for sensor in ("b", "c"):
        assert baseline.readings[sensor] == modified.readings[sensor]
    assert (
        WaterMeasurement(net, "one", faults)
        .measure(physical, SeedStreams(7))
        .readings["a"]
        == first.readings["a"]
    )
    assert first == WaterMeasurement(net, "all", faults).measure(
        replace(physical, events=()), SeedStreams(7)
    )


def test_onset_non_aligned_drift_and_stage_order() -> None:
    physical = TruthSeries(Timebase(START, STEP, 30), {"pressure:j1": [20.0] * 30})
    h = 0.1  # 1.2 ticks: the first affected reading is tick 2, with 0.8 tick elapsed.
    faults = [
        {
            "type": "sensor_drift",
            "sensor_id": "a",
            "start_hour": h,
            "drift_per_hour": 6.0,
        }
    ]
    result = WaterMeasurement(network(), "one", faults, ZERO).measure(
        physical, SeedStreams(1)
    )
    onset = math.ceil(h * 3600 / STEP)
    assert result.readings["a"][:onset] == (20.0,) * onset
    assert result.readings["a"][onset] == pytest.approx(20.4)
    assert result.readings["a"][onset + 1] - result.readings["a"][
        onset
    ] == pytest.approx(0.5)
    faults += [
        {"type": "sensor_offset", "sensor_id": "a", "start_hour": h, "magnitude": 2.0},
        {
            "type": "sensor_stuck",
            "sensor_id": "a",
            "start_hour": h,
            "duration_hours": 0.2,
        },
    ]
    held = (
        WaterMeasurement(network(), "one", faults, ZERO)
        .measure(physical, SeedStreams(1))
        .readings["a"]
    )
    assert held[onset:4] == (22.4, 22.4)
    assert held[4] == pytest.approx(23.4)  # half-open stuck window ended at hour .3


@pytest.mark.parametrize("mode", ["disable", "stuck", "drift"])
def test_whatifs_to_end_are_contract_faults_and_do_not_change_truth(mode: str) -> None:
    net, physical = network(), truth(48)
    before, net_before = physical.content_hash(), net.content_hash()
    item = SensorWhatIf("a", mode, 5, 0.6 if mode == "drift" else None)
    with pytest.raises(FrozenInstanceError):
        item.from_tick = 6  # type: ignore[misc]
    faults = as_faults([item], STEP, 48)
    validator("scenario-config", faults[0]["type"]).validate(faults[0])
    assert faults[0]["start_hour"] == 5 * STEP / 3600
    if mode != "drift":
        assert faults[0]["duration_hours"] == 43 * STEP / 3600
    series = WaterMeasurement(net, "all", faults, ZERO).measure(
        physical, SeedStreams(1)
    )
    baseline = WaterMeasurement(net, "all", config=ZERO).measure(
        physical, SeedStreams(1)
    )
    assert series.readings["a"][:5] == baseline.readings["a"][:5]
    if mode == "disable":
        assert series.readings["a"][5:] == (None,) * 43
    elif mode == "stuck":
        assert series.readings["a"][5:] == (baseline.readings["a"][5],) * 43
    else:
        for tick in range(5, 48):
            assert series.readings["a"][tick] == pytest.approx(
                baseline.readings["a"][tick] + (tick - 5) * 0.05
            )
    assert physical.content_hash() == before and net.content_hash() == net_before


@pytest.mark.parametrize("step", [1, 7, 60, 300, 900, 3600])
def test_whatif_start_round_trips_without_a_late_tick(step: int) -> None:
    # Includes tick 25 at step 300, whose float hour conversion can round upward.
    count = 600
    physical = TruthSeries(
        Timebase(START, step, count), {"pressure:j1": [20.0] * count}
    )
    for tick in (0, 1, 5, 25, 101, 287, 599):
        faults = as_faults([SensorWhatIf("a", "disable", tick)], step, count)
        values = (
            WaterMeasurement(network(), "one", faults, ZERO)
            .measure(physical, SeedStreams(1))
            .readings["a"]
        )
        assert values[:tick] == (20.0,) * tick
        assert values[tick:] == (None,) * (count - tick)


@pytest.mark.parametrize("tick", [48, 49])
def test_whatif_outside_horizon_is_rejected(tick: int) -> None:
    with pytest.raises(ValueError):
        as_faults([SensorWhatIf("a", "disable", tick)], STEP, 48)


def test_units_and_decimal_half_even_quantization() -> None:
    values = WaterMeasurement(network(), "all", config=ZERO).measure(
        truth(), SeedStreams(1)
    )
    rows = to_readings(values, network())
    for row in rows:
        quantum = Decimal(".001" if row["sensor_id"] == "c" else ".01")
        assert Decimal(str(row["value"])) % quantum == 0
        assert row["unit"] == ("L/s" if row["sensor_id"] == "b" else "m")
    assert values.readings["b"][0] == 12.34
    physical = TruthSeries(
        Timebase(START, STEP, 4), {"pressure:j1": [1.005, 1.015, -1.005, -1.015]}
    )
    assert WaterMeasurement(network(), "one", config=ZERO).measure(
        physical, SeedStreams(1)
    ).readings["a"] == (1.0, 1.02, -1.0, -1.02)


@pytest.mark.parametrize(
    "element, expected",
    [
        ("j1", "z1"),
        ("p1", "z1"),
        ("p0", "z1"),
        ("source", "source"),
        ("pu1", "z1"),
        ("v1", "z1"),
        ("t1", "t1"),
    ],
)
def test_every_rtu_branch(element: str, expected: str) -> None:
    net = pumped_loop()
    # Cross-zone link proves START wins; r1 -> t1 proves the link-id fallback.
    net = replace(
        net,
        zones=(*net.zones, Zone("z2", "Other", "residential")),
        junctions=tuple(
            replace(j, zone="z2") if j.id == "j2" else j for j in net.junctions
        ),
        pipes=(*net.pipes, Pipe("source", "r1", "t1", 50, 0.3, 130, "transmission")),
        valves=(Valve("v1", "r1", "j2", 0.3, "isolation"),),
    )
    sensor = Sensor(
        "test",
        "level" if element == "t1" else "pressure" if element == "j1" else "flow",
        element,
    )
    assert rtu_group(sensor, net) == ("z2" if element == "v1" else expected)


def test_group_outage_missing_values_delays_and_recovery() -> None:
    net, physical = network(), truth()
    faults = [
        {
            "type": "comms_outage",
            "rtu_group": "z1",
            "start_hour": 0.1,
            "duration_hours": 0.2,
        }
    ]
    baseline, base_delays = WaterMeasurement(
        net, "all", config=ZERO
    ).measure_with_delivery(physical, SeedStreams(1))
    outage, delays = WaterMeasurement(net, "all", faults, ZERO).measure_with_delivery(
        physical, SeedStreams(1)
    )
    assert delays == base_delays
    for sensor in ("a", "b"):
        assert outage.readings[sensor][2:4] == (None, None)
        assert outage.readings[sensor][:2] == baseline.readings[sensor][:2]
        assert outage.readings[sensor][4:] == baseline.readings[sensor][4:]
    assert outage.readings["c"] == baseline.readings["c"]
    assert all(2 <= d <= 30 and d.is_integer() for ds in delays.values() for d in ds)
    assert WaterMeasurement(
        net, "all", config={**ZERO, "base_dropout_per_tick": 1}
    ).measure(physical, SeedStreams(1)).readings == {
        s: (None,) * 48 for s in ("a", "b", "c")
    }


def test_fixed_sensor_stream_draws_and_noise_growth() -> None:
    physical = truth(30)
    rng = SeedStreams(9).stream("measure.a")
    expected = []
    for tick in range(30):
        z = float(rng.standard_normal())
        rng.random()  # base dropout
        rng.random()  # fault dropout (drawn even without a fault)
        rng.integers(2, 31)  # whole-second delivery
        expected.append(
            float(
                (
                    Decimal(
                        str(
                            physical.channels["pressure:j1"][tick]
                            + 0.1 * z * (3 if tick >= 2 else 1)
                        )
                    )
                    / Decimal(".01")
                ).to_integral_value()
                * Decimal(".01")
            )
        )
    faults = [
        {
            "type": "sensor_noise_growth",
            "sensor_id": "a",
            "start_hour": 0.1,
            "factor": 3,
        }
    ]
    actual = WaterMeasurement(
        network(), "one", faults, {"base_dropout_per_tick": 0}
    ).measure(physical, SeedStreams(9))
    assert actual.readings["a"] == tuple(expected)


def test_stuck_values_raise_quality_after_a_full_window_and_then_recover() -> None:
    faults = [
        {
            "type": "sensor_stuck",
            "sensor_id": "a",
            "start_hour": 1.0,
            "duration_hours": 2.0,
        }
    ]
    values = WaterMeasurement(network(), "one", faults, ZERO).measure(
        truth(), SeedStreams(1)
    )
    quality = assess(values, {"a": "pressure"}, {"a": 0.01}, {"a": (0.0, 100.0)})["a"]
    assert all("Q04" not in q["flags"] for q in quality[:23])
    assert all("Q04" in q["flags"] for q in quality[23:36])
    assert all("Q04" not in q["flags"] for q in quality[36:])


def test_flow_noise_adds_absolute_fraction_in_litres_per_second() -> None:
    net = replace(network(), sensor_sets={"one": ("b",)})
    physical = TruthSeries(Timebase(START, STEP, 2), {"flowrate:p1": [-0.1, 0.1]})
    result = WaterMeasurement(net, "one", config={"base_dropout_per_tick": 0}).measure(
        physical, SeedStreams(12)
    )
    stream = SeedStreams(12).stream("measure.b")
    for tick, value in enumerate((-100.0, 100.0)):
        candidate = value + float(stream.standard_normal()) * (0.05 + 0.005 * 100.0)
        expected = float(
            (Decimal(str(candidate)) / Decimal(".01")).to_integral_value()
            * Decimal(".01")
        )
        assert result.readings["b"][tick] == expected
        stream.random()
        stream.random()
        stream.integers(2, 31)


def test_faults_with_same_sort_prefix_have_a_canonical_tiebreaker() -> None:
    faults = [
        {
            "type": "sensor_offset",
            "sensor_id": "a",
            "start_hour": 0.0,
            "magnitude": magnitude,
        }
        for magnitude in (1e16, -1e16, 1.0)
    ]
    model = WaterMeasurement(network(), "one", faults, ZERO)
    assert model.measure(truth(), SeedStreams(1)) == WaterMeasurement(
        network(), "one", faults[::-1], ZERO
    ).measure(truth(), SeedStreams(1))


@pytest.mark.parametrize(
    "config",
    [
        {"base_dropout_per_tick": -1},
        {"base_dropout_per_tick": 2},
        {"pressure": {"quantum": 0}},
        {"pressure": {"noise_sigma": float("nan")}},
        {"delivery_delay_s": [30, 2]},
        {"delivery_delay_s": [2.1, 2.9]},
        {"label": "OBSERVED"},
    ],
)
def test_invalid_measurement_config_is_rejected(config: dict) -> None:
    with pytest.raises(ValueError):
        WaterMeasurement(network(), "all", config=config)


@pytest.mark.parametrize(
    "delays", [{"a": [0.0]}, {"a": [0.0] * 47 + [float("nan")]}, {"a": [2.5] * 48}]
)
def test_invalid_delivery_metadata_is_rejected(delays: dict) -> None:
    values = WaterMeasurement(network(), "one", config=ZERO).measure(
        truth(), SeedStreams(1)
    )
    with pytest.raises(ValueError):
        to_readings(values, network(), delays)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_clean_two_days_and_drift_detection_with_solver_fixture(seed: int) -> None:
    net = replace(
        line(45), sensors=(Sensor("p", "pressure", "j1"),), sensor_sets={"all": ("p",)}
    )
    multipliers = [1 + 0.2 * math.sin(2 * math.pi * k / 288) for k in range(576)]
    physical = simulate(net, demand(net, 576, multipliers)).truth
    expected = {"p": physical.channels["pressure:j1"]}
    kinds, quanta, ranges = {"p": "pressure"}, {"p": 0.01}, {"p": (0.0, 100.0)}
    model = WaterMeasurement(net, "all")
    clean, delays = model.measure_with_delivery(physical, SeedStreams(seed))
    quality = assess(clean, kinds, quanta, ranges, delays, expected)
    assert not any({"Q04", "Q08"} & set(q["flags"]) for q in quality["p"])
    faults = as_faults([SensorWhatIf("p", "drift", 288, 0.5)], STEP, 576)
    drifted = WaterMeasurement(net, "all", faults).measure(physical, SeedStreams(seed))
    flags = assess(drifted, kinds, quanta, ranges, expected=expected)["p"]
    assert any("Q08" in q["flags"] for q in flags[288:361])


@pytest.mark.parametrize(
    "item",
    [
        lambda: SensorWhatIf("a", "other", 0),
        lambda: SensorWhatIf("a", "disable", -1),
        lambda: SensorWhatIf("a", "drift", 0),
        lambda: SensorWhatIf("a", "drift", 0, float("nan")),
    ],
)
def test_invalid_whatif_is_rejected(item: Any) -> None:
    with pytest.raises(ValueError):
        item()
