"""Tank-level pump controls (network tuning card): model rules and their effect in WNTR."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from solver_fixtures import demand, pumped_loop
from ug_water.network.model import LevelControl
from ug_water.solver import build_model, load_options, simulate


def controlled(on: float = 2.5, off: float = 3.5):
    net = pumped_loop()
    return replace(net, controls=(LevelControl("ctl_pu1", "pu1", "t1", on, off),))


def test_a_control_needs_a_known_pump_and_tank_and_levels_inside_the_tank() -> None:
    net = pumped_loop()
    for bad in (
        LevelControl("c", "nope", "t1", 1.0, 2.0),
        LevelControl("c", "pu1", "nope", 1.0, 2.0),
        LevelControl("c", "pu1", "t1", 0.1, 2.0),  # below the tank's minimum level 0.5
        LevelControl("c", "pu1", "t1", 1.0, 7.0),  # above its maximum level 6.0
    ):
        with pytest.raises(ValueError):
            replace(net, controls=(bad,))
    with pytest.raises(ValueError, match="below"):
        LevelControl("c", "pu1", "t1", 3.0, 3.0)


def test_the_engine_adds_two_wntr_controls_per_level_control() -> None:
    net = controlled()
    wn = build_model(net, demand(net, 3), load_options())
    assert sorted(wn.control_name_list) == ["ctl_pu1:off", "ctl_pu1:on"]


def test_the_pump_switches_with_the_tank_level() -> None:
    net = controlled()
    result = simulate(net, demand(net, 145))  # 12 hours
    q = np.array(result.truth.channels["flowrate:pu1"])
    level = np.array(result.truth.channels["level:t1"])
    assert (q == 0).any() and (q > 0).any()  # it ran and it was switched off
    assert level.max() <= 3.5 + 0.2  # off above 3.5 m; one step's inflow of overshoot
    assert level.min() >= 2.5 - 0.5  # on below 2.5 m


def test_a_network_without_controls_hashes_as_before() -> None:
    net = pumped_loop()
    assert "controls" not in net.to_dict()
    assert "controls" in controlled().to_dict()
