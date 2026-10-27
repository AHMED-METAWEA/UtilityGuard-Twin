"""T-B1-013: the OSM provider on synthetic street graphs (no OpenStreetMap data)."""

from __future__ import annotations

from collections import Counter

import pytest
from osm_fixtures import PROVENANCE, box, graph, grid, node, overlay
from ug_core.geometry.fetch import load_area
from ug_water.network.inference import TierRule, skeleton
from ug_water.network.osm import OsmCapitalProvider, Projection, projection_error
from ug_water.network.overlay import OverlayError, assign, load_overlay

ALL = frozenset({"primary", "residential", "secondary", "service", "trunk"})


def test_the_projection_error_over_the_capital_box_is_about_a_tenth_of_a_percent() -> (
    None
):
    box_ = (29.85, 31.62, 30.06, 31.79)
    centre = Projection((box_[0] + box_[2]) / 2, (box_[1] + box_[3]) / 2)
    assert 1e-4 < projection_error(centre, box_) < 2e-3


def test_degree_two_nodes_are_contracted_and_lengths_kept() -> None:
    g = grid(3, 3)
    sk = skeleton(g, "test", TierRule(ALL, None))
    # The four edge middles (three streets) and the centre (four) stay; the corners (two
    # streets) and the street midpoints are contracted into the pipes that pass them.
    assert set(sk.nodes) == {node(0, 1), node(1, 0), node(1, 1), node(1, 2), node(2, 1)}
    edges = {frozenset((s.a, s.b)): s.length_m for s in g.streets}
    for pipe in sk.pipes:
        assert pipe.length_m == pytest.approx(
            sum(edges[frozenset(s)] for s in pipe.streets)
        )
    assert sum(p.length_m for p in sk.pipes) == pytest.approx(sum(edges.values()))


def test_every_pipe_lies_on_streets() -> None:
    """A pipe follows street segments of the graph and is as long as they are; they form one
    route between its two end junctions, which are OSM nodes (distance 0 to a street)."""
    g = grid(6, 6, main_row=2)
    sk = skeleton(g, "test", TierRule(ALL, 12))
    edges = {(min(s.a, s.b), max(s.a, s.b)): s.length_m for s in g.streets}
    for pipe in sk.pipes:
        assert all(segment in edges for segment in pipe.streets), pipe
        assert pipe.length_m == pytest.approx(sum(edges[s] for s in pipe.streets))
        # The segments form one street route from one end junction to the other.
        degree = Counter(n for s in pipe.streets for n in s)
        odd = {n for n, d in degree.items() if d % 2}
        assert odd == {pipe.a, pipe.b} or (pipe.a == pipe.b and not odd), pipe
        for end in (pipe.a, pipe.b):
            assert sk.nodes[end] == g.nodes[end]


def test_a_target_is_met_within_ten_percent_by_joining_close_junctions() -> None:
    g = grid(10, 10, spacing=100.0)
    sk = skeleton(g, "test", TierRule(ALL, 30))
    assert 27 <= len(sk.nodes) <= 30 and sk.radius_m > 0
    reachable = _component({p.a for p in sk.pipes} | {p.b for p in sk.pipes}, sk.pipes)
    assert reachable == set(sk.nodes)


def test_a_target_the_graph_cannot_reach_is_an_error() -> None:
    g = grid(3, 3)
    with pytest.raises(ValueError, match="below 90% of the target"):
        skeleton(g, "test", TierRule(ALL, 500))


def test_the_largest_component_is_kept_and_the_rest_counted() -> None:
    g = grid(3, 3)
    positions = dict(g.nodes) | {1: (5000.0, 0.0), 2: (5100.0, 0.0)}
    streets = [(s.a, s.b, s.highway) for s in g.streets] + [(1, 2, "residential")]
    sk = skeleton(graph(streets, positions), "test", TierRule(ALL, None))
    assert 1 not in sk.nodes and sk.dropped["nodes_outside_the_largest_component"] == 2


def test_parallel_carriageways_become_one_main_when_junctions_are_joined() -> None:
    positions = {
        1: (0.0, 0.0), 2: (0.0, 5.0), 3: (1000.0, 0.0), 4: (1000.0, 5.0),
        6: (-500.0, 0.0), 7: (-400.0, 300.0), 8: (1500.0, 0.0), 9: (1400.0, 300.0),
    }  # fmt: skip
    streets = [
        (1, 3, "trunk"), (2, 4, "trunk"),  # the two carriageways of a divided road
        (1, 2, "trunk"), (3, 4, "trunk"),  # short crossovers: their ends get joined
        (1, 6, "residential"), (2, 7, "residential"),
        (3, 8, "residential"), (4, 9, "residential"),
    ]  # fmt: skip
    sk = skeleton(graph(streets, positions), "test", TierRule(ALL, 6))
    assert set(sk.nodes) == {1, 3, 6, 7, 8, 9}
    pairs = Counter((p.a, p.b) for p in sk.pipes)
    assert pairs[(1, 3)] == 1 and all(count == 1 for count in pairs.values())


def test_a_pipe_takes_the_tier_of_most_of_its_length() -> None:
    positions = {
        1: (0.0, 0.0),
        2: (300.0, 0.0),
        3: (400.0, 0.0),
        4: (400.0, 100.0),
        5: (400.0, -100.0),
    }
    streets = [
        (1, 2, "trunk"),
        (2, 3, "residential"),
        (3, 4, "residential"),
        (3, 5, "residential"),
    ]
    sk = skeleton(graph(streets, positions), "test", TierRule(ALL, None))
    tiers = {(p.a, p.b): p.tier for p in sk.pipes}
    assert tiers[(1, 3)] == "transmission" and tiers[(3, 4)] == "distribution"


def two_zones(width: float = 1000.0) -> dict:
    return overlay(
        [
            ("west", "residential", box(-100, -100, width / 2, 1100)),
            ("east", "government", box(width / 2, -100, width + 100, 1100)),
        ]
    )


def test_junctions_are_assigned_to_the_polygon_that_holds_them() -> None:
    g = grid(6, 6)
    o = load_overlay(two_zones(), g.projection.xy)
    zones = assign({n: g.nodes[n] for n in (node(0, 0), node(0, 5))}, o)
    assert zones == {node(0, 0): "west", node(0, 5): "east"}


def test_a_junction_outside_the_overlay_is_an_error_not_a_default() -> None:
    g = grid(6, 6)
    small = overlay([("west", "residential", box(-100, -100, 500, 1100))])
    o = load_overlay(small, g.projection.xy)
    with pytest.raises(OverlayError, match="lie in no zone"):
        assign(dict(g.nodes), o)


def test_overlapping_zones_are_an_error() -> None:
    g = grid(3, 3)
    both = overlay(
        [
            ("a", "residential", box(-100, -100, 500, 500)),
            ("b", "green", box(-50, -50, 450, 450)),
        ]
    )
    with pytest.raises(OverlayError, match="more than one zone"):
        assign(dict(g.nodes), load_overlay(both, g.projection.xy))


@pytest.mark.parametrize(
    "change",
    [
        {"label": "PUBLIC_GEOMETRY"},
        {"method": "traced"},
        {"source": ""},
        {"type": "Feature"},
    ],
)
def test_an_overlay_must_say_it_is_a_hand_drawn_assumption(change: dict) -> None:
    with pytest.raises(OverlayError):
        load_overlay({**two_zones(), **change}, grid(2, 2).projection.xy)


def provider() -> OsmCapitalProvider:
    return OsmCapitalProvider(overlay=two_zones())


def test_the_network_is_f1_with_public_streets_and_assumed_districts() -> None:
    net = provider().from_graph(grid(6, 6, main_row=2), "test", 1, TierRule(ALL, None))
    prov = net.provenance
    assert prov.fidelity == "F1" and prov.provider == "osm"
    assert prov.labels["coordinates"] == "PUBLIC_GEOMETRY"
    assert {
        prov.labels[k]
        for k in ("topology", "zones", "diameters", "demands", "equipment")
    } == {"ASSUMPTION"}
    assert prov.geometry is not None and prov.geometry["source"] == "OpenStreetMap"
    assert prov.geometry["extract_sha256"] == PROVENANCE["extract_sha256"]
    assert (
        prov.district_boundaries is not None
        and prov.district_boundaries["method"] == "hand-drawn"
    )


def test_every_junction_is_reachable_from_the_source() -> None:
    net = provider().from_graph(grid(6, 6, main_row=2), "test", 1, TierRule(ALL, None))
    links = [(p.start, p.end) for p in (*net.pipes, *net.pumps)]
    reached = _component({"source"}, links)
    assert {j.id for j in net.junctions} <= reached
    assert {t.id for t in net.tanks} <= reached


def test_a_zone_demand_is_its_rate_times_its_area() -> None:
    net = provider().from_graph(grid(6, 6, main_row=2), "test", 1, TierRule(ALL, None))
    by_zone = Counter()
    for j in net.junctions:
        by_zone[j.zone] += j.base_demand
    rates = provider().config["demand_l_s_per_ha"]
    o = load_overlay(two_zones(), grid(2, 2).projection.xy)
    for district in o.districts:
        expected = rates[district.land_use] * district.area_ha / 1000
        assert by_zone[district.id] == pytest.approx(expected, rel=1e-9)


def test_the_same_graph_and_seed_give_the_same_network() -> None:
    g = grid(6, 6, main_row=2)
    a = provider().from_graph(g, "test", 1, TierRule(ALL, None))
    assert (
        provider().from_graph(g, "test", 1, TierRule(ALL, None)).content_hash()
        == a.content_hash()
    )
    assert (
        provider().from_graph(g, "test", 2, TierRule(ALL, None)).content_hash()
        != a.content_hash()
    )


def test_the_packaged_overlay_is_a_labelled_schematic() -> None:
    data = OsmCapitalProvider().overlay_data
    assert data["label"] == "ASSUMPTION" and data["method"] == "hand-drawn"
    assert (
        "Wikidata" in data["source"]
        and "Not traced from OpenStreetMap" in data["source"]
    )
    assert {f["properties"]["id"] for f in data["features"]} == {
        "core",
        "inner",
        "middle",
        "outer",
    }


def test_the_packaged_overlay_covers_the_whole_search_box_once() -> None:
    """Ruling 2: every junction of the study box must lie in a zone. The study box lies inside
    the area file's search box, so covering the search box covers every junction; checked on a
    200 m grid without any OpenStreetMap data."""
    area = load_area("capital")
    projection = Projection(*area.anchor)
    overlay = load_overlay(OsmCapitalProvider().overlay_data, projection.xy)
    south, west, north, east = area.search_box()
    (x0, y0), (x1, y1) = projection.xy(south, west), projection.xy(north, east)
    step = 200.0
    points = {
        (i, k): (x0 + 1 + i * step, y0 + 1 + k * step)
        for i in range(int((x1 - x0) // step))
        for k in range(int((y1 - y0) // step))
    }
    zones = assign(points, overlay)
    assert len(zones) == len(points)


def test_a_zone_area_counts_inside_the_study_box_only() -> None:
    o = load_overlay(two_zones(), grid(2, 2).projection.xy)
    west = next(d for d in o.districts if d.id == "west")
    whole = west.area_ha
    half = west.area_within_ha((-100.0, -100.0, 500.0, 500.0))
    assert whole == pytest.approx(600 * 1200 / 10_000, rel=1e-6)
    assert half == pytest.approx(600 * 600 / 10_000, rel=1e-6)
    assert west.area_within_ha((5000.0, 5000.0, 6000.0, 6000.0)) == 0.0


def _component(start: set, links: list) -> set:
    links = [(link.a, link.b) if hasattr(link, "a") else link for link in links]
    seen, stack = set(start), list(start)
    while stack:
        n = stack.pop()
        for a, b in links:
            for x, y in ((a, b), (b, a)):
                if x == n and y not in seen:
                    seen.add(y)
                    stack.append(y)
    return seen
