"""Offline acceptance of the generic F0 fixture; no hydraulic claims are made."""

from __future__ import annotations

import ast
import json
import math
from collections import Counter
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from ug_core.canonical import canonical_json, sha256_hex
from ug_core.rng import SeedStreams
from ug_water.network.model import Network
from ug_water.network.procedural import ProceduralCapitalProvider


def config() -> dict[str, Any]:
    return json.loads(
        files("ug_water.network")
        .joinpath("data/procedural_capital_v1.json")
        .read_text()
    )


@pytest.fixture(scope="module")
def network() -> Network:
    return ProceduralCapitalProvider().build(1)


def reachable(net: Network) -> set[str]:
    adjacency: dict[str, set[str]] = {}
    for link in (*net.pipes, *net.pumps, *net.valves):
        adjacency.setdefault(link.start, set()).add(link.end)
        adjacency.setdefault(link.end, set()).add(link.start)
    seen = {net.reservoirs[0].id}
    pending = list(seen)
    while pending:
        for neighbor in adjacency.get(pending.pop(), set()) - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    return seen


def test_reproducible_across_builds_and_providers(network: Network) -> None:
    provider = ProceduralCapitalProvider()
    a, b = provider.build(1), provider.build(1)
    assert a.content_hash() == b.content_hash() == network.content_hash()
    assert canonical_json(a.to_dict()).encode() == canonical_json(b.to_dict()).encode()
    different = provider.build(2)
    assert different.content_hash() != network.content_hash()
    assert [(j.x, j.y) for j in different.junctions] != [
        (j.x, j.y) for j in network.junctions
    ]


def test_scale_equipment_and_nested_sensor_sets(network: Network) -> None:
    cfg = config()
    for kind in ("junctions", "pipes"):
        assert len(getattr(network, kind)) == pytest.approx(
            cfg["targets"][kind], rel=0.15
        )
    assert 8 <= len(network.zones) <= 10
    assert len(network.reservoirs) == 1
    assert len(network.tanks) == 3
    assert sum(t.elevated for t in network.tanks) == 1
    stations: dict[str, Counter[str]] = {}
    for pump in network.pumps:
        stations.setdefault(pump.station, Counter())[pump.role] += 1
        assert all(
            a[0] < b[0] and a[1] > b[1]
            for a, b in zip(pump.curve, pump.curve[1:], strict=False)
        )
        assert 0 < pump.efficiency <= 1
    assert len(stations) == 3
    assert all(c == {"duty": 2, "standby": 1} for c in stations.values())
    assert Counter(v.kind for v in network.valves) == {"isolation": 30, "prv": 2}
    assert all(v.setting > 0 for v in network.valves if v.kind == "prv")
    sites = {s.id: s for s in network.sensors}
    assert Counter(sites[s].kind for s in network.sensor_sets["S_base"]) == {
        "pressure": 48,
        "flow": 10,
        "level": 3,
    }
    assert set(network.sensor_sets["S_sparse"]) < set(network.sensor_sets["S_base"])
    assert set(network.sensor_sets["S_base"]) < set(network.sensor_sets["S_dense"])
    assert {p.tier for p in network.pipes} == {
        "transmission",
        "submain",
        "distribution",
    }
    assert {j.id for j in network.junctions} <= reachable(network)
    base_flow = {
        sites[s].element
        for s in network.sensor_sets["S_base"]
        if sites[s].kind == "flow"
    }
    for station in stations:
        assert any(p.id in base_flow for p in network.pumps if p.station == station)


def test_disconnected_config_fails_with_junction_names() -> None:
    cfg = config()
    cfg["topology"]["radials"] = []
    with pytest.raises(ValueError, match=r"unreachable junctions:.*j_"):
        ProceduralCapitalProvider(cfg).build(1)


def test_provenance_and_config_are_independent_snapshots(network: Network) -> None:
    cfg = config()
    provider = ProceduralCapitalProvider(cfg)
    cfg["diameters_m"]["transmission"] = [0.99]
    assert provider.build(1).content_hash() == network.content_hash()
    changed = ProceduralCapitalProvider(cfg).build(1)
    assert changed.provenance.config_hash != network.provenance.config_hash
    assert changed.provenance.config_hash == sha256_hex(canonical_json(cfg))
    assert {p.diameter for p in changed.pipes if p.tier == "transmission"} == {0.99}
    assert network.provenance.provider == "procedural"
    assert network.provenance.fidelity == "F0"
    assert len(network.provenance.labels) == 6
    assert set(network.provenance.labels.values()) == {"ASSUMPTION"}


def test_sensor_parameters_do_not_change_physical_network(network: Network) -> None:
    cfg = config()
    cfg["sensors"]["coverage_hops"] += 1
    cfg["sensors"]["S_base"]["pressure"] += 1
    other = ProceduralCapitalProvider(cfg).build(1)
    for field in ("junctions", "pipes", "pumps", "tanks", "valves", "reservoirs"):
        assert getattr(other, field) == getattr(network, field)
    assert other.sensor_sets != network.sensor_sets


def test_lengths_and_roughness_trace_to_config(network: Network) -> None:
    nodes = {n.id: n for n in (*network.junctions, *network.reservoirs, *network.tanks)}
    cfg = config()
    for pipe in network.pipes:
        a, b = nodes[pipe.start], nodes[pipe.end]
        assert pipe.length == pytest.approx(math.hypot(a.x - b.x, a.y - b.y), rel=1e-9)
        assert pipe.diameter in cfg["diameters_m"][pipe.tier]
        assert pipe.roughness in cfg["roughness_c"].values()


def test_land_use_area_demand_and_equipment_parameters(network: Network) -> None:
    cfg = config()
    for district in cfg["districts"]:
        expected = (
            district["area_ha"] * cfg["demands"]["m3_s_per_ha"][district["land_use"]]
        )
        actual = math.fsum(
            j.base_demand for j in network.junctions if j.zone == district["id"]
        )
        assert actual == pytest.approx(expected)
    changed = deepcopy(cfg)
    changed["demands"]["m3_s_per_ha"]["government"] *= 2
    changed["equipment"]["pump"]["efficiency"] = 0.6
    other = ProceduralCapitalProvider(changed).build(1)
    assert all(p.efficiency == 0.6 for p in other.pumps)
    assert other.total_base_demand() > network.total_base_demand()
    assert [(j.x, j.y) for j in other.junctions] == [
        (j.x, j.y) for j in network.junctions
    ]


def test_no_reference_imports() -> None:
    source = Path(__file__).parents[1] / "src/ug_water/network/procedural.py"
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.Import):
            assert all(not a.name.startswith("freebuff") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("freebuff")


@pytest.mark.parametrize("target", [250, 280])
def test_tunable_junction_and_pipe_targets(target: int) -> None:
    cfg = config()
    cfg["targets"]["junctions"] = target
    cfg["targets"]["pipes"] = target + 70
    net = ProceduralCapitalProvider(cfg).build(3)
    assert len(net.junctions) == target
    assert len(net.pipes) == target + 70
    assert {j.id for j in net.junctions} <= reachable(net)


def test_tanks_use_highest_grid_site_in_their_configured_region(
    network: Network,
) -> None:
    cfg = config()
    tanks = {t.id: t for t in network.tanks}
    # Valve and pump auxiliary junctions carry no demand; only grid sites qualify.
    grid = [j for j in network.junctions if j.base_demand > 0]
    for spec in cfg["equipment"]["tanks"]:
        high = max(
            (j for j in grid if j.zone in spec["zones"]), key=lambda j: j.elevation
        )
        tank = tanks[spec["id"]]
        assert tank.x == high.x + cfg["equipment"]["tank"]["offset_m"][0]
        assert tank.y == high.y + cfg["equipment"]["tank"]["offset_m"][1]


def test_valves_are_in_series_without_a_parallel_pipe_bypass(network: Network) -> None:
    pipe_edges = {frozenset((p.start, p.end)) for p in network.pipes}
    for valve in network.valves:
        assert frozenset((valve.start, valve.end)) not in pipe_edges
        upstream = [p for p in network.pipes if p.end == valve.start]
        assert len(upstream) == 1
        assert upstream[0].diameter == valve.diameter


@pytest.mark.parametrize(
    "path,value,message",
    [
        (("targets", "pipes"), 1, "pipe target"),
        (("targets", "junctions"), True, "junction target"),
        (("streets", "valve_pipe_fraction"), 1, "valve_pipe_fraction"),
        (("sensors", "S_base", "pressure"), 1000, "sensor counts"),
    ],
)
def test_impossible_configs_fail_explicitly(
    path: tuple[str, ...], value: Any, message: str
) -> None:
    cfg = config()
    parent = cfg
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = value
    with pytest.raises(ValueError, match=message):
        ProceduralCapitalProvider(cfg).build(1)


@pytest.mark.parametrize("purpose", ["demands", "sensors"])
def test_extra_random_draws_do_not_shift_other_purposes(
    network: Network, monkeypatch: pytest.MonkeyPatch, purpose: str
) -> None:
    original = SeedStreams.stream
    calls: list[str] = []

    def perturbed(self: SeedStreams, name: str) -> np.random.Generator:
        calls.append(name)
        rng = original(self, name)
        if name == purpose:
            rng.random(17)
        return rng

    monkeypatch.setattr(SeedStreams, "stream", perturbed)
    other = ProceduralCapitalProvider().build(1)
    assert Counter(calls) == dict.fromkeys(
        ("layout", "streets", "terrain", "diameters", "demands", "sensors"), 1
    )
    assert [(j.x, j.y) for j in other.junctions] == [
        (j.x, j.y) for j in network.junctions
    ]
    assert other.pipes == network.pipes
    if purpose == "demands":
        assert other.junctions != network.junctions
    else:
        assert other.sensors != network.sensors
