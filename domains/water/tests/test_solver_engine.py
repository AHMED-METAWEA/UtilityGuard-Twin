"""T-B1-016: the hydraulic engine (WNTR, pressure-driven demand), offline."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import wntr
from solver_fixtures import demand, line, provenance, pumped_loop
from ug_water.network.model import Junction, Network, Pipe, Pump, Reservoir, Zone
from ug_water.network.procedural import ProceduralCapitalProvider
from ug_water.solver import HydraulicsError, build_model, load_options, simulate
from ug_water.solver import engine as E

OPTIONS = load_options()


def epanet() -> Any:
    return replace(OPTIONS, engine="epanet")


@pytest.mark.parametrize("head", [3.0, 5.0, 12.0])
def test_pdd_delivers_less_when_pressure_is_below_the_required_pressure(
    head: float,
) -> None:
    """Below the required pressure the delivered share follows ((p - p_min) / (p_req - p_min))
    ** exponent, from the configured settings (20 m, 0 m, 0.5)."""
    net = line(head)
    result = simulate(net, demand(net, 3))
    p = np.array(result.truth.channels["pressure:j1"])
    delivered = np.array(result.truth.channels["demand:j1"])
    assert (p < OPTIONS.required_pressure_m).all()
    expected = (
        (p - OPTIONS.minimum_pressure_m)
        / (OPTIONS.required_pressure_m - OPTIONS.minimum_pressure_m)
    ) ** OPTIONS.pressure_exponent
    assert delivered / 0.01 == pytest.approx(expected, rel=1e-3)
    assert (delivered < 0.01).all()


def test_pdd_delivers_everything_above_the_required_pressure() -> None:
    net = line(40.0)
    result = simulate(net, demand(net, 3))
    assert np.array(result.truth.channels["demand:j1"]) == pytest.approx(0.01, rel=1e-6)


def test_the_truth_has_one_channel_per_quantity_and_element() -> None:
    net = pumped_loop()
    result = simulate(net, demand(net, 13))
    names = set(result.truth.channels)
    for j in ("j0", "j1", "j2", "j3"):
        assert {f"pressure:{j}", f"head:{j}", f"demand:{j}"} <= names
    assert {"level:t1", "head:t1", "power:pu1", "power:pu2"} <= names
    assert {
        f"flowrate:{p}" for p in ("p0", "p1", "p2", "p3", "p4", "pu1", "pu2")
    } <= names
    assert {f"velocity:{p}" for p in ("p0", "p1", "p2", "p3", "p4")} <= names
    assert result.label == "SIMULATION" and result.engine == "wntr"
    assert len(result.truth.timebase) == 13


def test_the_standby_pump_starts_closed_and_the_duty_pump_runs() -> None:
    net = pumped_loop()
    result = simulate(net, demand(net, 13))
    assert max(abs(v) for v in result.truth.channels["flowrate:pu2"]) == 0.0
    assert min(result.truth.channels["flowrate:pu1"]) > 0.0
    assert result.energy_kwh["pu2"] == 0.0


def test_pump_energy_agrees_with_an_independent_calculation() -> None:
    """Two independent routes: WNTR's own `pump_power` at every solved time (its global
    efficiency set to this pump's 75%, because WNTR 1.5 leaves it unset and `pump_power` divides
    by it), integrated over the solved intervals; and a hand calculation at the ticks."""
    net = pumped_loop()
    series = demand(net, 73, [1 + 0.3 * math.sin(k / 10) for k in range(73)])
    result = simulate(net, series)
    wn = build_model(net, series, OPTIONS)
    raw = wntr.sim.WNTRSimulator(wn).run_sim(convergence_error=True)
    wn.options.energy.global_efficiency = 75.0
    theirs = wntr.metrics.pump_power(raw.link["flowrate"], raw.node["head"], wn)["pu1"]
    times = np.asarray(theirs.index, dtype=float)
    watts = theirs.to_numpy(dtype=float)
    reference_kwh = float((watts[:-1] * np.diff(times)).sum() / 3.6e6)
    assert result.energy_kwh is not None
    assert result.energy_kwh["pu1"] == pytest.approx(reference_kwh, rel=1e-2)
    ours = np.array(result.truth.channels["power:pu1"])
    at_ticks = theirs.loc[[k * 300 for k in range(73)]].to_numpy(dtype=float)
    assert ours * 1000 == pytest.approx(at_ticks, rel=1e-2)
    q = np.array(result.truth.channels["flowrate:pu1"])
    gain = np.array(result.truth.channels["head:j1"]) - np.array(
        result.truth.channels["head:j0"]
    )
    assert ours == pytest.approx(1000 * 9.81 * q * gain / 0.75 / 1000, rel=1e-9)
    assert result.total_energy_kwh == pytest.approx(result.energy_kwh["pu1"])


def test_energy_counts_what_happens_between_two_ticks() -> None:
    """Round 1 (Codex): a small tank fills 3 s into the first step and the pump's power drops;
    holding the power of the tick over the whole step overstated the energy by 38%. The
    reference is the same network solved at a 1 s step, integrated the same way."""
    net = pumped_loop()
    net = replace(net, tanks=(replace(net.tanks[0], diameter=1.0, max_level=3.1),))
    series = demand(net, 3)
    result = simulate(net, series)
    fine = build_model(net, series, OPTIONS)
    fine.options.time.hydraulic_timestep = 1
    fine.options.time.report_timestep = 1
    raw = wntr.sim.WNTRSimulator(fine).run_sim(convergence_error=True)
    fine.options.energy.global_efficiency = 75.0
    watts = wntr.metrics.pump_power(raw.link["flowrate"], raw.node["head"], fine)["pu1"]
    reference_kwh = float((watts.to_numpy(dtype=float)[:-1]).sum() / 3.6e6)
    assert result.energy_kwh is not None
    assert result.energy_kwh["pu1"] == pytest.approx(reference_kwh, rel=1e-2)
    tick_held = sum(result.truth.channels["power:pu1"][:-1]) * 300 / 3600
    assert tick_held > 1.3 * result.energy_kwh["pu1"]  # the old rule was this far off


def test_epanet_returns_no_energy_rather_than_a_wrong_one() -> None:
    net = pumped_loop()
    result = simulate(net, demand(net, 13), epanet())
    assert result.energy_kwh is None and result.total_energy_kwh is None
    assert "power:pu1" in result.truth.channels


def test_a_pump_run_past_its_zero_head_flow_is_an_error() -> None:
    """Round 1 (Codex): a 200 m source pushes 0.08 m3/s through a pump whose curve reaches
    zero head near 0.05 m3/s; WNTR only warns, and the head the pump loses became negative
    power. It is an error now."""
    curve = ((0.0, 45.0), (0.02, 40.0), (0.04, 28.0))
    net = Network(
        name="overrun",
        provenance=provenance(),
        zones=(Zone("z1", "Test zone", "residential"),),
        junctions=(
            Junction("j0", 0.0, 0.0, 0.0, 0.0, "z1"),
            Junction("j1", 100.0, 0.0, 0.0, 0.08, "z1"),
        ),
        reservoirs=(Reservoir("r1", -50.0, 0.0, 200.0),),
        tanks=(),
        pipes=(Pipe("p0", "r1", "j0", 10.0, 0.5, 140.0, "transmission"),),
        pumps=(Pump("pu1", "j0", "j1", "s1", "duty", curve, 0.75),),
    )
    with pytest.raises(
        HydraulicsError, match="pu1 carries .* while losing .* zero head"
    ):
        simulate(net, demand(net, 3))


def test_a_table_on_another_time_axis_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round 1 (Codex): only the pressure table's axis was checked; a reordered flow table
    became wrongly timed truth."""
    run = E._run

    def reordered(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        results.link["flowrate"] = results.link["flowrate"].iloc[::-1]
        return results

    monkeypatch.setattr(E, "_run", reordered)
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match="time axis of the flow table"):
        simulate(net, demand(net, 13))


def test_wntr_and_epanet_agree_on_the_loop() -> None:
    net = pumped_loop()
    series = demand(net, 37, [1 + 0.4 * math.sin(k / 6) for k in range(37)])
    a, b = simulate(net, series), simulate(net, series, epanet())
    assert b.engine == "epanet"
    for name in ("pressure:j2", "pressure:j3", "level:t1"):
        assert np.array(a.truth.channels[name]) == pytest.approx(
            np.array(b.truth.channels[name]), abs=0.05
        )
    assert np.array(a.truth.channels["flowrate:pu1"]) == pytest.approx(
        np.array(b.truth.channels["flowrate:pu1"]), rel=0.01
    )


def test_a_planted_nan_raises_and_never_becomes_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = E._run

    def planted(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        results.node["pressure"].iloc[4, 1] = float("nan")
        return results

    monkeypatch.setattr(E, "_run", planted)
    net = pumped_loop()
    with pytest.raises(
        HydraulicsError, match="non-finite junction pressure for j1 at 1200 s"
    ):
        simulate(net, demand(net, 13))


def test_infinity_in_a_flow_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    run = E._run

    def planted(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        results.link["flowrate"].iloc[2, 0] = float("inf")
        return results

    monkeypatch.setattr(E, "_run", planted)
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match="non-finite flow"):
        simulate(net, demand(net, 13))


def test_a_results_axis_that_is_not_the_series_axis_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = E._run

    def shortened(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        for table in (results.node, results.link):
            for key in list(table):
                table[key] = table[key].iloc[:-1]
        return results

    monkeypatch.setattr(E, "_run", shortened)
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match="time axis"):
        simulate(net, demand(net, 13))


def test_reverse_flow_through_a_pump_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    run = E._run

    def reversed_pump(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        results.link["flowrate"].loc[600, "pu1"] = -0.01
        return results

    monkeypatch.setattr(E, "_run", reversed_pump)
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match="reverse flow .* pu1 at 600 s"):
        simulate(net, demand(net, 13))


def test_a_network_the_engine_cannot_solve_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fails(self: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Simulation did not converge at time 00:00:00.")

    monkeypatch.setattr(wntr.sim.WNTRSimulator, "run_sim", fails)
    net = pumped_loop()
    with pytest.raises(
        HydraulicsError, match="did not solve the network: Simulation did not"
    ):
        simulate(net, demand(net, 13))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d: replace(
                d, junction_ids=d.junction_ids[:-1], values=d.values[:, :-1]
            ),
            "exactly the network's junctions",
        ),
        (lambda d: replace(d, values=d.values[:-1]), "shape"),
        (lambda d: replace(d, values=d.values * -1 - 1e-3), "negative"),
        (
            lambda d: replace(d, values=np.where(d.values > 0, np.nan, 0.0)),
            "non-finite",
        ),
        (lambda d: replace(d, timebase=replace(d.timebase, step_seconds=600)), "step"),
    ],
)
def test_a_demand_series_that_does_not_fit_is_refused(
    change: Any, message: str
) -> None:
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match=message):
        simulate(net, change(demand(net, 13)))


def test_each_junction_gets_its_own_pattern() -> None:
    net = pumped_loop()
    series = demand(net, 5, [0.5, 1.0, 1.5, 1.0, 1.0])
    wn = build_model(net, series, OPTIONS)
    junction = wn.get_node("j2")
    assert junction.demand_timeseries_list[0].base_value == pytest.approx(0.006 * 1.0)
    assert list(wn.get_pattern("demand:j2").multipliers) == pytest.approx(
        [0.5, 1.0, 1.5, 1.0, 1.0]
    )
    assert wn.get_node("j0").demand_timeseries_list[0].base_value == 0.0
    assert (
        wn.options.time.duration == 4 * 300
        and wn.options.hydraulic.demand_model == "PDA"
    )


def test_the_same_input_gives_the_same_truth_also_in_another_process() -> None:
    net = pumped_loop()
    first = simulate(net, demand(net, 25)).content_hash()
    assert simulate(net, demand(net, 25)).content_hash() == first
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from solver_fixtures import demand, pumped_loop;"
        "from ug_water.solver import simulate;"
        "n = pumped_loop(); print(simulate(n, demand(n, 25)).content_hash())"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(Path(__file__).parent)],
        check=True, capture_output=True, text=True,
    )  # fmt: skip
    assert out.stdout.strip() == first
    assert simulate(net, demand(net, 25, [1.1] * 25)).content_hash() != first


def test_48_hours_on_the_procedural_network_within_the_budget() -> None:
    """Spec 4.8: 48 h of hydraulics on the `lite` network (about 250 junctions) in under 60 s
    on the lead's laptop. The measured time is printed; the bound here is that budget."""
    net = ProceduralCapitalProvider().build(1)
    ticks = 48 * 12 + 1
    series = demand(
        net, ticks, [1 + 0.35 * math.sin(2 * math.pi * k / 288) for k in range(ticks)]
    )
    started = time.perf_counter()
    result = simulate(net, series)
    seconds = time.perf_counter() - started
    print(
        json.dumps(
            {
                "junctions": len(net.junctions),
                "ticks": ticks,
                "seconds": round(seconds, 1),
            }
        )
    )
    assert seconds < 60
    assert len(result.truth.timebase) == ticks


def test_a_tank_level_is_its_head_above_the_bottom_and_stays_within_its_limits() -> (
    None
):
    net = pumped_loop()
    result = simulate(net, demand(net, 73))
    tank = net.tanks[0]
    level = np.array(result.truth.channels[f"level:{tank.id}"])
    head = np.array(result.truth.channels[f"head:{tank.id}"])
    assert level == pytest.approx(head - tank.elevation, abs=1e-12)
    assert level[0] == pytest.approx(tank.init_level, abs=1e-6)
    # WNTRSimulator lets a filling tank pass its maximum by what flows in during the step in
    # which it fills (0.13 mm here) before it closes the inlet; EPANET clips exactly
    # (docs/approximations.md). The bound allows that, and no more than a millimetre.
    assert (level >= tank.min_level - 1e-6).all()
    assert (level <= tank.max_level + 1e-3).all()
    assert result.truth.channels["flowrate:p4"][-1] == 0.0  # full: nothing flows in


@pytest.mark.parametrize(
    ("change", "what"),
    [
        (lambda f: f.drop(index=f.index[3]), "a tick missing from every table"),
        (lambda f: f.iloc[[0, 1, 1, *range(2, len(f))]], "a repeated time"),
    ],
)
def test_an_axis_that_misses_a_tick_or_repeats_a_time_is_an_error(
    monkeypatch: pytest.MonkeyPatch, change: Any, what: str
) -> None:
    run = E._run

    def broken(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        for table in (results.node, results.link):
            for key in list(table):
                table[key] = change(table[key])
        return results

    monkeypatch.setattr(E, "_run", broken)
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match="time axis"):
        simulate(net, demand(net, 13))


def test_a_two_point_pump_curve_is_refused() -> None:
    """Round 2 (Codex): WNTR 1.5 solves a two-point curve with the wrong slope
    (wntr/network/elements.py:1438-1441), so the operating point was wrong without an error."""
    net = pumped_loop()
    two = ((0.0, 45.0), (0.04, 28.0))
    net = replace(net, pumps=tuple(replace(p, curve=two) for p in net.pumps))
    with pytest.raises(HydraulicsError, match="two-point head curve"):
        simulate(net, demand(net, 3))


def test_a_non_finite_time_on_every_table_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round 2 (Codex): a NaN time shared by every table passed the order check (comparisons
    with NaN are false), returned the wrong pressure at a tick and NaN energy."""
    run = E._run

    def nan_time(wn: Any, options: Any) -> Any:
        results = run(wn, options)
        for table in (results.node, results.link):
            for key in list(table):
                frame = table[key]
                extra = frame.iloc[[0]].copy()
                extra.index = [float("nan")]
                table[key] = pd.concat([frame.iloc[[0]], extra, frame.iloc[1:]])
        return results

    monkeypatch.setattr(E, "_run", nan_time)
    net = pumped_loop()
    with pytest.raises(HydraulicsError, match="time axis"):
        simulate(net, demand(net, 3))
