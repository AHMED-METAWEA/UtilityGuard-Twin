"""D-05a forecast-only expectation and D-04 -> D2 integration on solver fixtures."""

from __future__ import annotations

from dataclasses import replace

import pytest
from solver_fixtures import demand, line, pumped_loop
from ug_core.evidence import EvidenceLabel
from ug_core.numeric import round_for_hash
from ug_core.rng import SeedStreams
from ug_intel.detect.cusum import detect
from ug_intel.detect.incident import incident_from
from ug_intel.quality import assess
from ug_water.demand.model import DemandSeries
from ug_water.network.model import Network, Sensor
from ug_water.solver import simulate
from ug_water.telemetry.expectation import expected_readings
from ug_water.telemetry.measurement import WaterMeasurement


def forecast(net: Network, ticks: int = 576) -> DemandSeries:
    base = demand(net, ticks)
    return DemandSeries(
        base.timebase, base.junction_ids, base.values, EvidenceLabel.MODEL, "0" * 64
    )


def test_expectation_refuses_simulation_before_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = line(45)

    def forbidden(*args, **kwargs):
        pytest.fail("SIMULATION demand must be rejected before any solver call")

    monkeypatch.setattr("ug_water.telemetry.expectation.simulate", forbidden)
    with pytest.raises(ValueError, match="MODEL"):
        expected_readings(
            net, "all", replace(forecast(net), label=EvidenceLabel.SIMULATION)
        )


def test_noise_free_channel_mapping_all_kinds_and_sensor_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = replace(
        pumped_loop(),
        sensors=(
            Sensor("p", "pressure", "j1"),
            Sensor("f", "flow", "p1"),
            Sensor("l", "level", "t1"),
        ),
        sensor_sets={"all": ("p", "f", "l"), "one": ("f",)},
    )
    model = forecast(net, 48)
    run = simulate(net, model)
    physical = run.truth
    # Compare the mapping exactly against one solver result; independent solver
    # runs use the project's canonical numeric precision (round_for_hash).
    monkeypatch.setattr("ug_water.telemetry.expectation.simulate", lambda *args: run)
    expected = expected_readings(net, "all", model)
    assert expected == {
        "p": tuple(physical.channels["pressure:j1"]),
        "f": tuple(1000 * v for v in physical.channels["flowrate:p1"]),
        "l": tuple(physical.channels["level:t1"]),
    }
    assert expected_readings(net, "one", model) == {"f": expected["f"]}
    assert expected_readings(net, "all", model) == expected
    monkeypatch.undo()
    repeated = expected_readings(net, "all", model)
    assert {s: tuple(map(round_for_hash, vs)) for s, vs in repeated.items()} == {
        s: tuple(map(round_for_hash, vs)) for s, vs in expected.items()
    }
    zero = {
        "base_dropout_per_tick": 0,
        **{
            k: {"noise_sigma": 0, "noise_fraction": 0}
            for k in ("pressure", "flow", "level")
        },
    }
    measured = WaterMeasurement(net, "all", config=zero).measure(
        physical, SeedStreams(1)
    )
    for sensor, quantum in (("p", 0.01), ("f", 0.01), ("l", 0.001)):
        assert measured.readings[sensor] == pytest.approx(
            expected[sensor], abs=quantum / 2 + 1e-12
        )
    with pytest.raises(ValueError, match="sensor set"):
        expected_readings(net, "absent", model)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_clean_two_days_no_incident(seed: int) -> None:
    net = replace(
        line(45),
        sensors=(Sensor("p", "pressure", "j1"), Sensor("f", "flow", "p1")),
        sensor_sets={"all": ("p", "f")},
    )
    model = forecast(net)
    expected = expected_readings(net, "all", model)
    physical = simulate(net, model).truth
    telemetry, delays = WaterMeasurement(net, "all").measure_with_delivery(
        physical, SeedStreams(seed)
    )
    kinds, quanta = {"p": "pressure", "f": "flow"}, {"p": 0.01, "f": 0.01}
    quality = assess(
        telemetry, kinds, quanta, {"p": (0, 100), "f": (-100, 100)}, delays, expected
    )
    result = detect(telemetry.readings, expected, quality, quanta)
    assert all(s.alarm_tick is None for s in result.sensors.values())
    assert (
        incident_from(result, kinds, quality, "run-1", {"p": "z1", "f": "z1"}) is None
    )
