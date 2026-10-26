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
import pytest
import wntr
from solver_fixtures import demand, line, pumped_loop
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
    """Two independent routes: WNTR's own `pump_power` (with its global efficiency set to this
    pump's 75%) and a hand calculation from the reported heads."""
    net = pumped_loop()
    series = demand(net, 73, [1 + 0.3 * math.sin(k / 10) for k in range(73)])
    result = simulate(net, series)
    wn = build_model(net, series, OPTIONS)
    raw = wntr.sim.WNTRSimulator(wn).run_sim(convergence_error=True)
    # WNTR 1.5 leaves the global efficiency unset; pump_power divides by it (read in its
    # source). Set it to this pump's efficiency so that WNTR's arithmetic checks ours.
    wn.options.energy.global_efficiency = 75.0
    theirs = wntr.metrics.pump_power(raw.link["flowrate"], raw.node["head"], wn)["pu1"]
    ours = np.array(result.truth.channels["power:pu1"])
    assert ours * 1000 == pytest.approx(theirs.to_numpy(dtype=float), rel=1e-2)
    q = np.array(result.truth.channels["flowrate:pu1"])
    gain = np.array(result.truth.channels["head:j1"]) - np.array(
        result.truth.channels["head:j0"]
    )
    hand = 1000 * 9.81 * q * gain / 0.75 / 1000
    assert ours == pytest.approx(hand, rel=1e-9)
    assert result.energy_kwh["pu1"] == pytest.approx(
        hand[:-1].sum() * 300 / 3600, rel=1e-9
    )
    assert result.total_energy_kwh == pytest.approx(result.energy_kwh["pu1"])


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
        HydraulicsError, match="non-finite junction pressure .* at tick 4"
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
    with pytest.raises(HydraulicsError, match="reverse flow .* pu1 at tick 2"):
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
