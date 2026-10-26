"""The network model (T-B1-011 prerequisite): plain, validated, order-independent data."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from ug_water.network.model import (
    Junction,
    Network,
    NetworkProvenance,
    Pipe,
    Pump,
    Reservoir,
    Sensor,
    Tank,
    Valve,
    Zone,
)

HASH = "a" * 64
F0_LABELS = {
    "coordinates": "ASSUMPTION",
    "topology": "ASSUMPTION",
    "zones": "ASSUMPTION",
    "diameters": "ASSUMPTION",
    "demands": "ASSUMPTION",
    "equipment": "ASSUMPTION",
}
OSM = {
    "label": "PUBLIC_GEOMETRY",
    "source": "OpenStreetMap",
    "licence": "ODbL-1.0",
    "retrieved": "2026-10-26T10:25:33Z",
    "coverage_report": "coverage.json",
    "osm_base": "2026-10-26T10:24:21Z",
    "extract_sha256": "b" * 64,
}
DISTRICTS = {
    "label": "ASSUMPTION",
    "method": "hand-drawn",
    "source": "capital_districts_v1",
    "drawn": "2026-10-26",
}


def f0(**changes: Any) -> NetworkProvenance:
    fields: dict[str, Any] = {
        "provider": "procedural",
        "fidelity": "F0",
        "seed": 1,
        "config_hash": HASH,
        "labels": F0_LABELS,
    }
    fields.update(changes)
    return NetworkProvenance(**fields)


def f1(**changes: Any) -> NetworkProvenance:
    labels = {
        **F0_LABELS,
        "coordinates": "PUBLIC_GEOMETRY",
        "topology": "PUBLIC_GEOMETRY",
    }
    fields: dict[str, Any] = {
        "provider": "osm",
        "fidelity": "F1",
        "seed": 1,
        "config_hash": HASH,
        "labels": labels,
        "geometry": OSM,
        "district_boundaries": DISTRICTS,
    }
    fields.update(changes)
    return NetworkProvenance(**fields)


def small(**changes: Any) -> Network:
    fields: dict[str, Any] = {
        "name": "tiny_v1",
        "provenance": f0(),
        "zones": (Zone("z1", "Government District", "government"),),
        "junctions": (
            Junction("j2", 100.0, 0.0, 10.0, 0.002, "z1"),
            Junction("j1", 0.0, 0.0, 12.0, 0.001, "z1"),
        ),
        "reservoirs": (Reservoir("r1", -50.0, 0.0, 60.0),),
        "tanks": (Tank("t1", 50.0, 50.0, 30.0, 3.0, 0.5, 6.0, 15.0, elevated=True),),
        "pipes": (
            Pipe("p1", "j1", "j2", 100.0, 0.2, 130.0, "distribution"),
            Pipe("p2", "j1", "t1", 70.0, 0.3, 130.0, "transmission"),
        ),
        "pumps": (
            Pump(
                "pu1",
                "r1",
                "j1",
                "ps1",
                "duty",
                ((0.0, 60.0), (0.05, 50.0), (0.1, 30.0)),
                0.75,
            ),
        ),
        "valves": (Valve("v1", "j1", "j2", 0.2, "isolation"),),
        "sensors": (Sensor("P01", "pressure", "j2"), Sensor("L01", "level", "t1")),
        "sensor_sets": {"S_base": ("P01", "L01")},
    }
    fields.update(changes)
    return Network(**fields)


def test_a_valid_network_builds_and_sorts_its_elements() -> None:
    net = small()
    assert [j.id for j in net.junctions] == ["j1", "j2"]
    assert net.sensor_sets["S_base"] == ("L01", "P01")
    assert net.total_base_demand() == pytest.approx(0.003)


def test_the_hash_does_not_depend_on_input_order_and_changes_with_content() -> None:
    a = small()
    b = small(junctions=tuple(reversed(a.junctions)), pipes=tuple(reversed(a.pipes)))
    assert a.content_hash() == b.content_hash()
    moved = small(junctions=(replace(a.junctions[0], x=0.5), a.junctions[1]))
    assert moved.content_hash() != a.content_hash()
    assert small(provenance=f0(seed=2)).content_hash() != a.content_hash()


@pytest.mark.parametrize(
    "make",
    [
        lambda: Junction("j1", float("nan"), 0.0, 10.0, 0.0, "z1"),
        lambda: Junction("j1", 0.0, 0.0, 10.0, -0.001, "z1"),
        lambda: Junction("j 1", 0.0, 0.0, 10.0, 0.0, "z1"),
        lambda: Junction("j1", True, 0.0, 10.0, 0.0, "z1"),
        lambda: Pipe("p1", "j1", "j1", 10.0, 0.2, 130.0, "distribution"),
        lambda: Pipe("p1", "j1", "j2", 0.0, 0.2, 130.0, "distribution"),
        lambda: Pipe("p1", "j1", "j2", 10.0, 0.2, 130.0, "trunk"),
        lambda: Tank("t1", 0.0, 0.0, 10.0, 7.0, 0.5, 6.0, 15.0),
        lambda: Tank("t1", 0.0, 0.0, 10.0, 1.0, 1.0, 1.0, 15.0),
        lambda: Pump("pu1", "r1", "j1", "ps1", "duty", ((0.0, 30.0), (0.1, 60.0)), 0.7),
        lambda: Pump("pu1", "r1", "j1", "ps1", "duty", ((0.1, 60.0), (0.0, 50.0)), 0.7),
        lambda: Pump("pu1", "r1", "j1", "ps1", "duty", ((0.0, 60.0),), 1.5),
        lambda: Pump("pu1", "r1", "j1", "ps1", "spare", ((0.0, 60.0),), 0.7),
        lambda: Valve("v1", "j1", "j2", 0.2, "prv", 0.0),
        lambda: Sensor("P01", "temperature", "j1"),
        lambda: Zone("z1", " ", "residential"),
    ],
)
def test_an_element_that_breaks_a_rule_does_not_construct(make: Any) -> None:
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize(
    "changes",
    [
        {"pipes": (Pipe("p1", "j1", "ghost", 10.0, 0.2, 130.0, "distribution"),)},
        {"junctions": (Junction("j1", 0.0, 0.0, 10.0, 0.0, "nowhere"),)},
        {"sensors": (Sensor("P01", "pressure", "ghost"),), "sensor_sets": {}},
        {"sensor_sets": {"S_base": ("P99",)}},
        {
            "junctions": (
                Junction("x1", 0, 0, 1, 0, "z1"),
                Junction("x1", 1, 1, 1, 0, "z1"),
            )
        },
        {
            "reservoirs": (),
            "tanks": (),
            "pumps": (),
            "pipes": (),
            "sensors": (),
            "sensor_sets": {},
        },
        {
            "junctions": (),
            "pipes": (),
            "pumps": (),
            "valves": (),
            "sensors": (),
            "sensor_sets": {},
        },
        {"valves": (Valve("p1", "j1", "j2", 0.2, "isolation"),)},
    ],
)
def test_a_network_with_broken_references_does_not_construct(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        small(**changes)


def test_an_f0_network_is_synthetic_everywhere() -> None:
    with pytest.raises(ValueError, match="F0"):
        f0(labels={**F0_LABELS, "coordinates": "PUBLIC_GEOMETRY"})
    with pytest.raises(ValueError, match="F0"):
        f0(geometry=OSM)
    with pytest.raises(ValueError):
        f0(labels={**F0_LABELS, "diameters": "PUBLIC_GEOMETRY"})
    with pytest.raises(ValueError):
        f0(labels={k: v for k, v in F0_LABELS.items() if k != "demands"})


def test_an_f1_network_needs_osm_streets_and_hand_drawn_districts() -> None:
    assert f1().fidelity == "F1"
    for broken in (
        {"geometry": None},
        {"geometry": {**OSM, "source": "municipal CAD export"}},
        {"geometry": {**OSM, "licence": "CC0"}},
        {"geometry": {**OSM, "label": "ASSUMPTION"}},
        {"geometry": {**OSM, "extract_sha256": "short"}},
        {"geometry": {k: v for k, v in OSM.items() if k != "osm_base"}},
        {"district_boundaries": None},
        {"district_boundaries": {**DISTRICTS, "label": "PUBLIC_GEOMETRY"}},
        {"district_boundaries": {**DISTRICTS, "method": "traced"}},
        {"district_boundaries": {**DISTRICTS, "drawn": ""}},
        {"labels": {**F0_LABELS, "topology": "PUBLIC_GEOMETRY"}},
        {
            "labels": {
                **F0_LABELS,
                "coordinates": "PUBLIC_GEOMETRY",
                "zones": "PUBLIC_GEOMETRY",
            }
        },
    ):
        with pytest.raises(ValueError):
            f1(**broken)


def test_demands_diameters_and_equipment_are_never_public_geometry() -> None:
    for part in ("demands", "diameters", "equipment"):
        with pytest.raises(ValueError):
            f1(labels={**f1().labels, part: "PUBLIC_GEOMETRY"})


def test_provenance_is_frozen_and_serialised() -> None:
    p = f1()
    with pytest.raises(TypeError):
        p.labels["demands"] = "PUBLIC_GEOMETRY"  # type: ignore[index]
    assert p.to_dict()["geometry"]["source"] == "OpenStreetMap"
    assert small(provenance=f0()).to_dict()["schema_version"] == "1"
