"""Real short hydraulic fixtures plus explicit structural counterexamples."""

from dataclasses import FrozenInstanceError, replace

import pytest
from ug_water.network.model import Junction, Pipe, Pump, Valve
from ug_water.network.validation import (
    NetworkInvalid,
    load_config,
    require_valid,
    validate_network,
)
from validation_helpers import line, with_tank

SHORT = 1 / 144  # ten minutes, including three report ticks
NAMES = {
    "junction_reachability",
    "junction_degree",
    "tank_connectivity",
    "prv_pressure_zone",
    "solves",
    "min_pressure_at_peak",
    "min_pressure_any_time",
    "max_velocity",
    "tank_starvation",
    "tank_pinned_full",
    "delivered_share",
}


def run(network, **kwargs):
    return validate_network(network, seed=1, horizon_days=SHORT, **kwargs)


def check(report, name):
    return next(c for c in report.checks if c.name == name)


def test_passes_labels_frozen_and_deterministic():
    report = run(with_tank(5))
    assert report.passed
    assert report == run(with_tank(5))
    assert {c.name for c in report.checks} == NAMES
    assert all(c.label == "CALCULATED" for c in report.checks)
    assert all(
        c.threshold_label == "ASSUMPTION"
        for c in report.checks
        if c.threshold is not None
    )
    assert check(report, "delivered_share").value == pytest.approx(1, abs=1e-6)
    with pytest.raises(FrozenInstanceError):
        report.passed = False
    with pytest.raises(FrozenInstanceError):
        report.checks[0].value = -1
    assert require_valid(line(), seed=1, horizon_days=SHORT).passed


@pytest.mark.parametrize(
    "head,name", [(12, "min_pressure_at_peak"), (5, "min_pressure_any_time")]
)
def test_pressure_fail_and_pass(head, name):
    assert check(run(line(head)), name).passed is False
    assert check(run(line(40)), name).passed is True
    assert "j1" in check(run(line(head)), name).detail
    assert "tick" in check(run(line(head)), name).detail


def test_velocity_fail_and_pass():
    assert check(run(line(100, 0.04)), "max_velocity").passed is False
    assert check(run(line()), "max_velocity").passed is True


@pytest.mark.parametrize(
    "level,name", [(0, "tank_starvation"), (10, "tank_pinned_full")]
)
def test_tank_fail_and_pass(level, name):
    assert check(run(with_tank(level)), name).passed is False
    assert check(run(with_tank(5)), name).passed is True


def test_structural_failures_skip_without_simulating(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("structural failures must not simulate")

    monkeypatch.setattr("ug_water.network.validation.simulate", forbidden)
    network = line()
    isolated = replace(
        network, junctions=(*network.junctions, Junction("j2", 2, 0, 0, 0.01, "z1"))
    )
    report = run(isolated)
    assert check(report, "junction_reachability").passed is False
    assert check(report, "junction_degree").passed is False
    assert check(report, "solves").passed is None
    assert {c.name for c in report.checks} == NAMES
    assert "structural failure" in check(report, "solves").detail
    with pytest.raises(NetworkInvalid, match="junction_reachability.*junction_degree"):
        require_valid(isolated, seed=1, horizon_days=SHORT)
    # An island with nonzero degree still fails reachability.
    island = replace(
        isolated,
        junctions=(*isolated.junctions, Junction("j3", 3, 0, 0, 0, "z1")),
        pipes=(*isolated.pipes, Pipe("island", "j2", "j3", 1, 0.5, 140, "submain")),
    )
    assert check(run(island), "junction_degree").passed is True
    assert check(run(island), "junction_reachability").passed is False
    tank = with_tank(5)
    disconnected = replace(tank, pipes=network.pipes)
    assert check(run(disconnected), "tank_connectivity").passed is False


def test_prv_bypass_and_pump_valve_undirected_reachability():
    network = line()
    network = replace(
        network,
        junctions=(*network.junctions, Junction("j2", 2, 0, 0, 0.01, "z1")),
        valves=(Valve("prv", "j1", "j2", 0.3, "prv", 25),),
    )
    assert check(run(network), "prv_pressure_zone").passed is True
    bypass = replace(
        network,
        pipes=(*network.pipes, Pipe("bypass", "r1", "j2", 1, 0.5, 140, "submain")),
    )
    assert check(run(bypass), "prv_pressure_zone").passed is False
    # Structural traversal includes pumps, and ignores link direction/status.
    pump = Pump("pump", "j1", "r1", "station", "standby", ((0.01, 10),), 0.8)
    reversed_pump = replace(network, pipes=(), pumps=(pump,))
    assert check(run(reversed_pump), "junction_reachability").passed is True
    second_source = replace(
        network,
        reservoirs=(*network.reservoirs, replace(network.reservoirs[0], id="r2")),
        pipes=(*network.pipes, Pipe("second", "r2", "j2", 1, 0.5, 140, "submain")),
    )
    assert check(run(second_source), "prv_pressure_zone").passed is False


def test_config_changes_outcome():
    config = load_config()
    assert check(run(line(12)), "min_pressure_at_peak").passed is False
    config["min_pressure_m"] = 11
    assert check(run(line(12), config=config), "min_pressure_at_peak").passed is True
    assert load_config()["min_pressure_m"] == 15


@pytest.mark.parametrize(
    "key,value",
    [
        ("label", "OBSERVED"),
        ("min_pressure_m", float("nan")),
        ("tank_margin_m", -1),
        ("pinned_full_share", 2),
        ("solves", False),
        ("max_unreachable_junctions", 1),
    ],
)
def test_reject_invalid_config(key, value):
    config = load_config()
    config[key] = value
    with pytest.raises(ValueError):
        run(line(), config=config)


@pytest.mark.parametrize("horizon", [0, -1, float("inf"), 0.001])
def test_reject_invalid_horizon(horizon):
    with pytest.raises(ValueError, match="horizon_days"):
        validate_network(line(), seed=1, horizon_days=horizon)


def test_a_check_that_cannot_be_evaluated_is_not_a_pass() -> None:
    """Lead review: a network without demand cannot show its pressures at peak; the report
    must not pass on checks it could not evaluate."""
    net = line()
    net = replace(net, junctions=(replace(net.junctions[0], base_demand=0.0),))
    report = run(net)
    pressure = {c.name: c for c in report.checks}["min_pressure_at_peak"]
    assert pressure.passed is None and report.passed is False
