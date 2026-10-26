"""Offline preset checks: configuration assertions, never hydraulic validation."""

from __future__ import annotations

import ast
import math
import runpy
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path

import pytest
from ug_water.network.procedural import ProceduralCapitalProvider
from ug_water.scenarios import list_presets, load_preset

ROOT = Path(__file__).resolve().parents[3]
# Reuse the contract suite's strict parser, Draft 2020-12 validator and local registry.
CONTRACT_SUPPORT = runpy.run_path(
    str(ROOT / "platform/tests/contract/contract_support.py")
)
IDS = tuple(
    sorted(
        (
            "normal_week",
            "holiday",
            "heatwave",
            "ramadan_peak",
            "friday_weekend_pattern",
            "fire_flow_event",
            "leak_gradual_medium",
            "leak_sudden",
            "burst_main",
            "pump_outage_standby",
        )
    )
)
EVENTS = {
    "fire_flow_event": {
        "type": "fire_flow",
        "start_hour": 19,
        "node": "node:j_0088",
        "flow_l_s": 31.5,
        "duration_hours": 2,
    },
    "leak_gradual_medium": {
        "type": "leak",
        "profile": "gradual",
        "start_hour": 24,
        "location": "pipe:p_0276",
        "ramp_hours": 24,
        "final_area_cm2": 4.0,
    },
    "leak_sudden": {
        "type": "leak",
        "profile": "sudden",
        "start_hour": 30,
        "location": "pipe:p_0124",
        "final_area_cm2": 6.0,
    },
    "burst_main": {
        "type": "burst",
        "start_hour": 30,
        "location": "pipe:p_0229",
        "final_area_cm2": 50.0,
    },
    "pump_outage_standby": {
        "type": "pump_outage",
        "start_hour": 20,
        "pump_id": "station_east_duty_0",
        "duration_hours": 6,
    },
}


@pytest.fixture(scope="module")
def network():
    return ProceduralCapitalProvider().build(1)


def test_inventory_and_unknown_id():
    assert list_presets() == IDS
    for unknown in ("missing", "../normal_week", "NORMAL_WEEK"):
        with pytest.raises(KeyError) as exc:
            load_preset(unknown)
        assert unknown in str(exc.value)
        assert all(name in str(exc.value) for name in IDS)


@pytest.mark.parametrize("preset_id", IDS)
def test_independent_nested_copies(preset_id):
    expected = load_preset(preset_id)
    changed = load_preset(preset_id)
    changed["demand"]["forecast_error"]["sigma_pct"] = 99
    changed["demand"]["zone_multipliers"]["business"] = 99
    changed["cross_domain_inputs"].append({"bad": True})
    if changed["faults"]:
        changed["faults"][0]["start_hour"] = 999
    else:
        changed["faults"].append({"type": "bad"})
    assert load_preset(preset_id) == expected


@pytest.mark.parametrize("preset_id", IDS)
def test_contract_filename_and_values(preset_id, network):
    path = files("ug_water.scenarios").joinpath("presets", f"{preset_id}.json")
    config = CONTRACT_SUPPORT["parse_json"](path.read_text(encoding="utf-8"))
    CONTRACT_SUPPORT["validator_for"]("scenario-config").validate(config)
    assert config == load_preset(preset_id)
    assert config["scenario_id"] == path.name.removesuffix(".json")
    assert config["schema_version"] == "1"
    assert config["network_version"] == "procedural-capital-v1-seed1"
    assert config["seed"] == 1
    assert config["sensor_set"] == "S_base"
    assert config["sensor_set"] in network.sensor_sets
    assert config["assumption_set"] == "demand_v1"
    assert config["timestep_minutes"] == 5
    assert config["cross_domain_inputs"] == []
    assert config["demand"] == {
        "calendar": "default_egypt",
        "holiday": preset_id == "holiday",
        "ramadan": preset_id == "ramadan_peak",
        "heatwave_multiplier": 1.25 if preset_id == "heatwave" else 1.0,
        "zone_multipliers": {},
        "forecast_error": {"model": "ar1", "sigma_pct": 0.0},
    }
    assert config["faults"] == ([EVENTS[preset_id]] if preset_id in EVENTS else [])
    expected_duration = (
        96
        if preset_id == "friday_weekend_pattern"
        else (48 if preset_id in EVENTS else 168)
    )
    assert config["duration_hours"] == expected_duration
    start = datetime.fromisoformat(config["start"]).astimezone(
        timezone(timedelta(hours=2))
    )
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)
    assert start.weekday() == (3 if preset_id == "friday_weekend_pattern" else 4)
    assert start.date().isoformat() == (
        "2027-03-04" if preset_id == "friday_weekend_pattern" else "2027-03-05"
    )
    for fault in config["faults"]:
        assert fault["start_hour"] < expected_duration
        end = fault["start_hour"] + fault.get(
            "duration_hours", fault.get("ramp_hours", 0)
        )
        assert end <= expected_duration
        for hours in (fault["start_hour"], end):
            assert hours * 60 % config["timestep_minutes"] == 0
        for value in fault.values():
            if isinstance(value, str) and value.startswith(("pipe:", "node:")):
                kind, element_id = value.split(":")
                elements = network.pipes if kind == "pipe" else network.junctions
                assert element_id in {e.id for e in elements}


def _centroid(junctions):
    return tuple(
        math.fsum(getattr(j, axis) for j in junctions) / len(junctions)
        for axis in ("x", "y")
    )


def test_element_choice_rules(network):
    nodes = {j.id: j for j in (*network.junctions, *network.reservoirs, *network.tanks)}
    inner = [j for j in network.junctions if j.zone == "residential_inner"]
    assert (
        next(z for z in network.zones if z.id == "residential_inner").land_use
        == "residential"
    )
    cx, cy = _centroid(inner)
    fire = min(inner, key=lambda j: (math.hypot(j.x - cx, j.y - cy), j.id))
    assert load_preset("fire_flow_event")["faults"][0]["node"] == f"node:{fire.id}"

    def distance(pipe, center):
        a, b = nodes[pipe.start], nodes[pipe.end]
        dx, dy = b.x - a.x, b.y - a.y
        t = max(
            0,
            min(
                1,
                ((center[0] - a.x) * dx + (center[1] - a.y) * dy) / (dx * dx + dy * dy),
            ),
        )
        return math.hypot(center[0] - a.x - t * dx, center[1] - a.y - t * dy)

    for preset_id, zone in (
        ("leak_gradual_medium", "business"),
        ("leak_sudden", "residential_outer"),
        ("burst_main", None),
    ):
        center = _centroid(
            [j for j in network.junctions if zone is None or j.zone == zone]
        )
        candidates = [
            p
            for p in network.pipes
            if p.tier == ("transmission" if zone is None else "distribution")
            and (
                zone is None
                or (nodes[p.start].zone == zone and nodes[p.end].zone == zone)
            )
        ]
        chosen = min(candidates, key=lambda p: (distance(p, center), p.id))
        assert load_preset(preset_id)["faults"][0]["location"] == f"pipe:{chosen.id}"

    # Undirected pipe/valve reachability from discharge, excluding pumps/source.
    graph = {}
    for link in (*network.pipes, *network.valves):
        graph.setdefault(link.start, set()).add(link.end)
        graph.setdefault(link.end, set()).add(link.start)
    duties = [p for p in network.pumps if p.role == "duty"]
    counts = {}
    for pump in duties:
        seen, todo = set(), [pump.end]
        while todo:
            node = todo.pop()
            if node not in seen:
                seen.add(node)
                todo.extend(graph.get(node, ()))
        counts[pump.station] = len(seen & {j.id for j in network.junctions})
    station = min(counts, key=lambda s: (-counts[s], s))
    pump = min((p for p in duties if p.station == station), key=lambda p: p.id)
    assert load_preset("pump_outage_standby")["faults"][0]["pump_id"] == pump.id


def test_no_freebuff_imports():
    sources = ROOT / "domains/water/src/ug_water/scenarios"
    for path in sources.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                names.extend(alias.name for alias in node.names)
            assert all("freebuff" not in name.split(".") for name in names), path
