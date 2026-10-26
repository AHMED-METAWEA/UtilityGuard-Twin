"""Controlled solver outputs verify reductions and unavailable-result handling."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from ug_water.network.model import Junction
from ug_water.network.validation import (
    NetworkInvalid,
    load_config,
    require_valid,
    validate_network,
)
from ug_water.solver import HydraulicsError
from validation_helpers import line, with_tank

SHORT = 1 / 144


def results(monkeypatch, channels):
    def simulate(network, demand):
        assert demand.timebase.n_ticks == 3
        assert demand.timebase.step_seconds == 300
        assert demand.timebase.iso_at(0) == "2027-03-04T22:00:00Z"
        assert demand.label.value == "SIMULATION"
        return SimpleNamespace(truth=SimpleNamespace(channels=channels))

    monkeypatch.setattr("ug_water.network.validation.simulate", simulate)


def checks(network):
    report = validate_network(network, seed=1, horizon_days=SHORT)
    return {c.name: c for c in report.checks}


def test_hydraulics_error_is_failed_check_and_named_exception(monkeypatch):
    def fail(*args):
        raise HydraulicsError("bad element p1 tick 2")

    monkeypatch.setattr("ug_water.network.validation.simulate", fail)
    report = checks(line())
    assert report["solves"].passed is False
    assert "p1 tick 2" in report["solves"].detail
    assert report["max_velocity"].passed is None
    assert report["delivered_share"].value is None
    with pytest.raises(NetworkInvalid, match="solves"):
        require_valid(line(), seed=1, horizon_days=SHORT)


def test_peak_requested_not_delivered_excludes_zero_base_nodes_and_integrates_volume(
    monkeypatch,
):
    from ug_water.demand.model import DemandModel

    original = DemandModel.truth

    def demand(self, network, timebase, seed, calendar):
        series = original(self, network, timebase, seed, calendar)
        assert seed == 1
        assert not calendar.events and not calendar.holidays and not calendar.ramadan
        return replace(series, values=np.array([[0, 1], [0, 3], [0, 2]], dtype=float))

    monkeypatch.setattr(DemandModel, "truth", demand)
    network = line()
    network = replace(
        network,
        junctions=(Junction("j0", 0, 0, 0, 0, "z1"), *network.junctions),
        pipes=(*network.pipes, replace(network.pipes[0], id="p0", end="j0")),
    )
    results(
        monkeypatch,
        {
            "pressure:j0": [-100] * 3,
            "pressure:j1": [9, 16, 20],
            "velocity:p0": [0] * 3,
            "velocity:p1": [-4, 1, 2],
            "demand:j0": [0] * 3,
            "demand:j1": [0.5, 1, 500],
        },
    )
    report = checks(network)
    assert report["min_pressure_at_peak"].value == 16
    assert "tick 1" in report["min_pressure_at_peak"].detail
    assert report["min_pressure_any_time"].value == 9
    assert report["min_pressure_any_time"].passed is False
    assert report["max_velocity"].value == 4
    assert "p1, tick 0" in report["max_velocity"].detail
    assert report["delivered_share"].value == 1.5 / 4
    assert report["delivered_share"].passed is None
    with pytest.raises(NetworkInvalid, match="min_pressure_any_time.*max_velocity"):
        require_valid(network, seed=1, horizon_days=SHORT)


def test_pressure_and_velocity_equality_pass_and_tank_margin_equality_fails(
    monkeypatch,
):
    channels = {
        "pressure:j1": [15, 15, 10],
        "velocity:p1": [3] * 3,
        "velocity:pt": [0] * 3,
        "demand:j1": [0.01] * 3,
        "level:t1": [0.05, 5, 5],
    }
    results(monkeypatch, channels)
    report = checks(with_tank(5))
    assert report["min_pressure_any_time"].passed is True
    assert report["max_velocity"].passed is True
    assert report["tank_starvation"].passed is False
    assert report["tank_pinned_full"].passed is True
    # Share is over all ticks, not a requirement for consecutive ticks.
    channels["level:t1"] = [10, 5, 10]
    config = load_config()
    config["pinned_full_share"] = 2 / 3
    report = validate_network(with_tank(5), seed=1, horizon_days=SHORT, config=config)
    full = next(c for c in report.checks if c.name == "tank_pinned_full")
    assert full.value == pytest.approx(2 / 3, abs=1e-6)
    assert full.passed is False


def test_zero_demand_is_explicitly_unavailable_and_no_tanks_pass(monkeypatch):
    network = line()
    network = replace(
        network, junctions=(replace(network.junctions[0], base_demand=0),)
    )
    results(monkeypatch, {"velocity:p1": [0] * 3, "demand:j1": [0] * 3})
    report = checks(network)
    assert report["min_pressure_at_peak"].value is None
    assert report["delivered_share"].value is None
    assert report["tank_starvation"].passed is True


def test_delivered_share_is_informational_even_when_zero(monkeypatch):
    results(
        monkeypatch,
        {"pressure:j1": [20] * 3, "velocity:p1": [0] * 3, "demand:j1": [0] * 3},
    )
    report = validate_network(line(), seed=1, horizon_days=SHORT)
    assert report.passed
    share = next(c for c in report.checks if c.name == "delivered_share")
    assert share.value == 0
    assert share.passed is None
