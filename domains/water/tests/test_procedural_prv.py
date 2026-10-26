"""Synthetic F0 PRV zones: structural isolation and conditional hydraulic checks."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest
import wntr
from ug_water.network.model import Network
from ug_water.network.procedural import ProceduralCapitalProvider
from wntr.network.base import LinkStatus


def config() -> dict[str, Any]:
    return json.loads(
        files("ug_water.network")
        .joinpath("data/procedural_capital_v1.json")
        .read_text()
    )


def component(net: Network, start: str, excluded: str) -> set[str]:
    graph: dict[str, set[str]] = {}
    for link in (*net.pipes, *net.pumps, *net.valves):
        if link.id != excluded:
            graph.setdefault(link.start, set()).add(link.end)
            graph.setdefault(link.end, set()).add(link.start)
    seen, pending = {start}, [start]
    while pending:
        for neighbor in graph.get(pending.pop(), set()) - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    return seen


@pytest.mark.parametrize("seed", range(1, 6))
def test_prv_zone_is_a_single_inlet_component(seed: int) -> None:
    net = ProceduralCapitalProvider().build(seed)
    cfg = config()["equipment"]["valves"]
    # Explicit expected zones also reproduce the original defect before config changes.
    zones = cfg.get("prv_zones", ["residential_outer", "green"])
    prvs = [v for v in net.valves if v.kind == "prv"]
    nodes = {j.id: j for j in net.junctions}
    sources = {s.id for s in (*net.reservoirs, *net.tanks)}
    assert len(prvs) == len(zones)
    for valve, zone in zip(prvs, zones, strict=True):
        members = {j.id for j in net.junctions if j.zone == zone}
        downstream = component(net, valve.end, valve.id)
        assert downstream == members
        assert downstream.isdisjoint(sources)
        upstream = component(net, valve.start, valve.id)
        assert valve.start not in downstream
        assert sources <= upstream
        assert nodes[valve.end].zone == zone
        inlet = [p for p in net.pipes if p.end == valve.start]
        assert len(inlet) == 1
        assert inlet[0].diameter == valve.diameter
        margin = net.reservoirs[0].head - nodes[valve.end].elevation - valve.setting
        assert margin >= cfg["prv_min_static_margin_m"]
        print(
            f"ASSUMPTION seed={seed} PRV={valve.id} zone={zone} "
            f"junctions={len(members)} static_margin_m={margin:.6f}"
        )


@pytest.mark.parametrize(
    "zones,margin,pattern",
    [
        # The exact message: the government district also holds the source, so a looser
        # pattern passes on the source rule even without the exclusion (lead mutation).
        (["government", "green"], 15, "government cluster is excluded"),
        (["missing", "green"], 15, "PRV.*unknown.*missing"),
        (["diplomatic", "green"], 15, "PRV.*diplomatic.*tank"),
        (["residential_outer", "green"], 1000, "v_0030.*static.*margin"),
        (["green"], 15, "PRV.*one.*zone"),
        (["green", "green"], 15, "PRV.*distinct"),
    ],
)
def test_invalid_prv_zones_fail(zones: list[str], margin: float, pattern: str) -> None:
    cfg = config()
    cfg["equipment"]["valves"].update(prv_zones=zones, prv_min_static_margin_m=margin)
    if zones[0] == "diplomatic":
        # Test the tank-site rule independently of the discharge-site rule.
        cfg["equipment"]["stations"][1]["zone"] = "government"
    with pytest.raises(ValueError, match=pattern):
        ProceduralCapitalProvider(cfg).build(1)


def test_prv_zone_cannot_hold_source() -> None:
    cfg = config()
    cfg["equipment"]["valves"]["prv_zones"] = ["business", "green"]
    # A steep synthetic eastward slope places the source site in business.
    cfg["terrain"].update(slope_x=1.0, slope_y=0.0, amplitude_m=0.0)
    cfg["districts"][1]["center_m"] = [10000, 2900]
    with pytest.raises(ValueError, match="PRV zone business: holds the source"):
        ProceduralCapitalProvider(cfg).build(1)


def hydraulic_model(net: Network) -> Any:
    """Temporary test adapter; only the installed manifest's construction API."""
    wn = wntr.network.WaterNetworkModel()
    for j in net.junctions:
        wn.add_junction(j.id, base_demand=j.base_demand, elevation=j.elevation)
    for r in net.reservoirs:
        wn.add_reservoir(r.id, base_head=r.head)
    for t in net.tanks:
        wn.add_tank(
            t.id,
            elevation=t.elevation,
            init_level=t.init_level,
            min_level=t.min_level,
            max_level=t.max_level,
            diameter=t.diameter,
        )
    for p in net.pipes:
        wn.add_pipe(
            p.id,
            p.start,
            p.end,
            length=p.length,
            diameter=p.diameter,
            roughness=p.roughness,
            minor_loss=p.minor_loss,
        )
    for pump in net.pumps:
        curve = f"curve_{pump.id}"
        wn.add_curve(curve, "HEAD", list(pump.curve))
        wn.add_pump(
            pump.id,
            pump.start,
            pump.end,
            pump_type="HEAD",
            pump_parameter=curve,
            initial_status="OPEN" if pump.role == "duty" else "CLOSED",
        )
    for v in net.valves:
        wn.add_valve(
            v.id,
            v.start,
            v.end,
            diameter=v.diameter,
            valve_type="PRV" if v.kind == "prv" else "TCV",
            initial_setting=v.setting if v.kind == "prv" else 0.0,
            initial_status="ACTIVE" if v.kind == "prv" else "OPEN",
        )
    wn.options.time.duration = 24 * 3600
    wn.options.time.hydraulic_timestep = 300
    wn.options.time.report_timestep = 300
    wn.options.hydraulic.demand_model = "PDD"
    wn.options.hydraulic.minimum_pressure = 0.0
    wn.options.hydraulic.required_pressure = 20.0
    wn.options.hydraulic.pressure_exponent = 0.5
    return wn


def test_epanet_prvs_regulate_for_24_hours(tmp_path: Path) -> None:
    net = ProceduralCapitalProvider().build(1)
    result = wntr.sim.EpanetSimulator(hydraulic_model(net)).run_sim(
        file_prefix=str(tmp_path / "prv"), convergence_error=True
    )
    # Verified by installed WNTR 1.5.0 enum introspection: Active == 2.
    assert int(LinkStatus.Active) == 2
    assert list(result.node["pressure"].index) == list(range(0, 86401, 300))
    for v in net.valves:
        if v.kind == "prv":
            active = result.link["status"][v.id] == int(LinkStatus.Active)
            pressure = result.node["pressure"][v.end]
            print(
                f"SIMULATION PRV={v.id} active_share={active.mean():.6f} "
                f"mean_downstream_pressure_m={pressure.mean():.6f}"
            )
            assert active.mean() >= 0.95
            assert (pressure[active] - v.setting).abs().max() <= 0.5


def test_wntr_pdd_converges_for_24_hours() -> None:
    start = perf_counter()
    result = wntr.sim.WNTRSimulator(
        hydraulic_model(ProceduralCapitalProvider().build(1))
    ).run_sim(convergence_error=True)
    print(f"BENCHMARK WNTRSimulator_24h_elapsed_s={perf_counter() - start:.6f}")
    assert list(result.node["pressure"].index) == list(range(0, 86401, 300))
