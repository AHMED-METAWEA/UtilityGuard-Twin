"""Hydraulic faults (card D-03): plans, WNTR changes and their effect in a run."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from solver_fixtures import STEP, demand, pumped_loop
from ug_water.network.model import LevelControl
from ug_water.solver import build_model, load_options, simulate
from ug_water.solver.faults import (
    GRADUAL_STEPS,
    FaultPlan,
    add_fire_flows,
    plan_faults,
)

TICKS = 37  # 3 h at 5 min


def leak(
    start_hour: float = 1.0, area: float = 2.0, **extra: object
) -> dict[str, object]:
    return {
        "type": "leak",
        "profile": "sudden",
        "start_hour": start_hour,
        "location": "pipe:p2",
        "final_area_cm2": area,
        **extra,
    }


def run(faults: list[dict[str, object]], net=None):
    net = net or pumped_loop()
    series = demand(net, TICKS)
    plan = plan_faults(faults, net, series.timebase)
    return simulate(net, add_fire_flows(series, plan), faults=plan).truth, plan


def channel(truth, name: str) -> np.ndarray:
    return np.asarray(truth.channels[name])


def test_a_fault_starts_at_the_first_tick_at_or_after_its_hour() -> None:
    net = pumped_loop()
    tb = demand(net, TICKS).timebase
    assert plan_faults([leak(start_hour=1.0)], net, tb).events[0].start_tick == 12
    assert plan_faults([leak(start_hour=1.01)], net, tb).events[0].start_tick == 13
    assert plan_faults([leak(start_hour=0)], net, tb).leaks[0].steps == ((0, 2e-4),)


@pytest.mark.parametrize(
    ("fault", "match"),
    [
        (leak(start_hour=3.0), "last tick"),
        ({**leak(), "location": "pipe:nope"}, "unknown pipe"),
        (
            {
                "type": "pump_outage",
                "start_hour": 1,
                "pump_id": "x",
                "duration_hours": 1,
            },
            "unknown pump",
        ),
        (
            {
                "type": "fire_flow",
                "start_hour": 1,
                "node": "node:x",
                "flow_l_s": 5,
                "duration_hours": 1,
            },
            "unknown junction",
        ),
        (
            {
                "type": "sensor_drift",
                "start_hour": 1,
                "sensor_id": "s",
                "drift_per_hour": 1,
            },
            "demo slice",
        ),
    ],
)
def test_faults_are_checked_against_the_network_and_the_horizon(fault, match) -> None:
    net = pumped_loop()
    with pytest.raises(ValueError, match=match):
        plan_faults([fault], net, demand(net, TICKS).timebase)


def test_two_leaks_on_one_pipe_are_refused() -> None:
    net = pumped_loop()
    with pytest.raises(ValueError, match="more than one leak"):
        plan_faults([leak(), leak(start_hour=2)], net, demand(net, TICKS).timebase)


def test_a_leak_needs_the_wntr_engine() -> None:
    net = pumped_loop()
    series = demand(net, TICKS)
    plan = plan_faults([leak()], net, series.timebase)
    with pytest.raises(ValueError, match="wntr engine"):
        build_model(net, series, replace(load_options(), engine="epanet"), plan)


def test_an_empty_plan_changes_nothing() -> None:
    net = pumped_loop()
    series = demand(net, TICKS)
    assert (
        simulate(net, series).content_hash()
        == simulate(net, series, faults=FaultPlan()).content_hash()
    )


def test_a_sudden_leak_flows_from_its_tick_and_is_a_hidden_event() -> None:
    truth, plan = run([leak()])
    flow = channel(truth, "leak:p2")
    assert np.all(flow[:12] == 0.0)
    assert np.all(flow[12:] > 1e-3)
    (event,) = truth.events
    assert (event.kind, event.target, event.start_tick, event.end_tick) == (
        "leak",
        "p2",
        12,
        None,
    )
    clean, _ = run([])
    # The leak lowers the pressure near it and its water comes through the network.
    assert channel(truth, "pressure:j3")[20] < channel(clean, "pressure:j3")[20]
    assert "leak:p2" not in clean.channels
    # The split pipe keeps its id (its upstream half); the hidden halves are not channels.
    assert not any("~" in name for name in truth.channels)


def test_a_burst_is_a_large_sudden_leak() -> None:
    burst = {
        "type": "burst",
        "start_hour": 1,
        "location": "pipe:p2",
        "final_area_cm2": 6.0,
    }
    truth, _ = run([burst])
    small, _ = run([leak(area=2.0)])
    assert channel(truth, "leak:p2")[20] > channel(small, "leak:p2")[20]
    assert truth.events[0].kind == "burst"


def test_a_gradual_leak_is_a_staircase_that_reaches_the_final_area() -> None:
    truth, plan = run([leak(profile="gradual", ramp_hours=1.0, area=2.0)])
    starts = [s for s, _ in plan.leaks[0].steps]
    assert starts == [3600, 4500, 5400, 6300]  # 1 h + k x 15 min
    assert sum(a for _, a in plan.leaks[0].steps) == pytest.approx(2e-4)
    flow = channel(truth, "leak:p2")
    assert np.all(np.diff(flow[12:]) >= -1e-6)
    assert (
        int((np.diff(flow[11:25]) > 5e-4).sum()) == GRADUAL_STEPS
    )  # one jump per step
    sudden, _ = run([leak(area=2.0)])
    assert flow[-1] == pytest.approx(channel(sudden, "leak:p2")[-1], rel=0.05)


def test_a_pump_outage_stops_the_pump_against_its_level_control() -> None:
    net = replace(
        pumped_loop(), controls=(LevelControl("ctl_pu1", "pu1", "t1", 5.5, 5.9),)
    )
    outage = {
        "type": "pump_outage",
        "start_hour": 1,
        "pump_id": "pu1",
        "duration_hours": 1,
    }
    truth, _ = run([outage], net)
    flow = channel(truth, "flowrate:pu1")
    assert flow[:12].max() > 1e-3  # the tank is below 5.5 m: the control runs the pump
    assert np.all(np.abs(flow[12:24]) < 1e-6)
    assert flow[24:].max() > 1e-3  # the control takes over again after the outage
    standby = channel(truth, "flowrate:pu2")
    assert np.all(np.abs(standby[:12]) < 1e-6)
    assert standby[12:24].max() > 1e-3  # failover: the station's standby runs
    assert np.all(np.abs(standby[24:]) < 1e-6)
    (event,) = truth.events
    assert (event.target, event.start_tick, event.end_tick) == ("pu1", 12, 24)


def test_a_pump_without_a_level_control_reopens_after_the_outage() -> None:
    outage = {
        "type": "pump_outage",
        "start_hour": 1,
        "pump_id": "pu1",
        "duration_hours": 0.5,
    }
    flow = channel(run([outage])[0], "flowrate:pu1")
    assert np.all(np.abs(flow[12:18]) < 1e-6)
    assert np.all(flow[18:] > 1e-3)
    standby = channel(run([outage])[0], "flowrate:pu2")
    assert np.all(standby[12:18] > 1e-3)
    assert np.all(np.abs(standby[18:]) < 1e-6)


def test_a_fire_flow_adds_demand_in_its_window() -> None:
    fire = {
        "type": "fire_flow",
        "start_hour": 1,
        "node": "node:j2",
        "flow_l_s": 10,
        "duration_hours": 0.5,
    }
    truth, _ = run([fire])
    clean, _ = run([])
    extra = channel(truth, "demand:j2") - channel(clean, "demand:j2")
    assert np.allclose(extra[:12], 0.0, atol=1e-9)
    assert np.allclose(extra[12:18], 0.010, rtol=0.02)
    assert np.allclose(extra[18:], 0.0, atol=1e-9)
    assert truth.events[0].parameters == {"flow_l_s": 10}


def test_the_same_faults_give_the_same_truth() -> None:
    net = pumped_loop()
    series = demand(net, TICKS)
    plan = plan_faults([leak(profile="gradual", ramp_hours=1.0)], net, series.timebase)
    assert (
        simulate(net, series, faults=plan).content_hash()
        == simulate(net, series, faults=plan).content_hash()
    )
    assert STEP == 300


def test_every_event_targets_an_element_with_channels() -> None:
    # The store tags the channels `quantity:<target>` of each event (truth_bundle.py).
    fire = {
        "type": "fire_flow",
        "start_hour": 1,
        "node": "node:j2",
        "flow_l_s": 10,
        "duration_hours": 0.5,
    }
    outage = {
        "type": "pump_outage",
        "start_hour": 1,
        "pump_id": "pu1",
        "duration_hours": 1,
    }
    truth, _ = run([leak(), fire, outage])
    elements = {name.partition(":")[2] for name in truth.channels}
    assert {e.target for e in truth.events} == {"p2", "j2", "pu1"} <= elements
