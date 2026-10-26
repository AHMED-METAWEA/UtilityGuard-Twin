"""T-B1-010: the coverage report on a hand-checkable street grid (offline)."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
from geometry_fixtures import (
    LAT0,
    LON0,
    STEP,
    STUDY_BOX,
    FakeOverpass,
    roads_answer,
    stat,
    stats_answer,
)
from ug_core.geometry import fetch as F
from ug_core.geometry import report as R

NOW = datetime(2026, 10, 26, 10, 25, 33, tzinfo=UTC)


@pytest.fixture
def extract(tmp_path: Path) -> Path:
    return F.fetch_area(F.load_area("capital"), tmp_path, FakeOverpass(), NOW)  # type: ignore[arg-type]


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return R.haversine_km(a, b)


ROW = km((LAT0, LON0), (LAT0, LON0 + STEP))  # one east-west grid segment
COL = km((LAT0, LON0), (LAT0 + STEP, LON0))  # one north-south grid segment
SPUR = km((LAT0 + 2 * STEP, LON0 + 2 * STEP), (LAT0 + 3 * STEP, LON0 + 2 * STEP))
BUILDING = km((29.95, 31.75), (29.95, 31.751))


def test_the_haversine_distance_is_right() -> None:
    # One degree of latitude is 111.195 km on a sphere of radius 6371.0088 km.
    assert R.haversine_km((0.0, 0.0), (1.0, 0.0)) == pytest.approx(111.195, abs=1e-3)
    assert R.haversine_km((30.0, 31.0), (30.0, 31.0)) == 0.0


def test_the_street_graph_of_the_grid(extract: Path) -> None:
    streets = R.coverage_report(extract, F.load_area("capital"))["streets"]
    everything, built, main = (
        streets["drivable_and_under_construction"],
        streets["drivable_built"],
        streets["main_streets"],
    )
    # 4 edge middles (3 neighbours), the centre (4) and the corner with the spur (3).
    assert everything | {"length_km": None, "length_km_inside_study_box": None} == {
        "ways": 8,
        "length_km": None,
        "length_km_inside_study_box": None,
        "nodes": 12,
        "junctions": 6,
        "dead_ends": 3,
        "components": 2,
        "largest_component_length_share": round(
            (6 * ROW + 6 * COL + SPUR) / (6 * ROW + 6 * COL + SPUR + BUILDING), 3
        ),
        "junctions_in_largest_component": 6,
    }
    assert everything["length_km"] == round(6 * ROW + 6 * COL + SPUR + BUILDING, 1)
    # Every segment of the fixture lies in the study box.
    assert everything["length_km_inside_study_box"] == everything["length_km"]
    assert built["length_km_inside_study_box"] == built["length_km"]
    assert (
        built["ways"],
        built["junctions"],
        built["dead_ends"],
        built["components"],
    ) == (7, 6, 1, 1)
    assert built["largest_component_length_share"] == 1.0
    assert (main["ways"], main["junctions"], main["dead_ends"], main["components"]) == (
        6,
        5,
        0,
        1,
    )
    assert streets["share_of_length_under_construction"] == round(
        BUILDING / (6 * ROW + 6 * COL + SPUR + BUILDING), 3
    )


def test_landmarks_grid_and_mapped_features(extract: Path) -> None:
    report = R.coverage_report(extract, F.load_area("capital"))
    marks = report["landmarks"]["by_name"]
    assert marks["Central Business District"] == {
        "found": True,
        "road_km_within_radius": round(6 * ROW + 6 * COL + SPUR, 1),
    }
    assert marks["Green River"] == {"found": False}
    grid = report["grid"]
    # The study box spans 0.11 degree of latitude (12.2 cells of 1 km at 111.32 km a degree)
    # and 0.14 degree of longitude (13.5 cells at 29.975 N): 13 x 14 cells. The street grid
    # straddles the boundary of rows 8 and 9 (at 30.00085 N) and of columns 3 and 4 (at
    # 31.70148 E), so it lies in four cells; the road under construction lies in a fifth.
    assert grid["cells"] == 13 * 14 and grid["cells_with_any_road"] == 5
    assert report["mapped_features"]["highway"]["residential"] == {"km": 0.6, "ways": 6}
    assert report["mapped_features"]["buildings"]["all"] == {"relations": 1, "ways": 12}
    assert report["mapped_features"]["water_infrastructure"] == {
        "water_tower": {"n": 1}
    }


def test_the_report_names_its_source_labels_and_formulas(extract: Path) -> None:
    report = R.coverage_report(extract, F.load_area("capital"))
    assert (
        report["source"]["source"] == "OpenStreetMap"
        and report["source"]["licence"] == "ODbL-1.0"
    )
    assert report["source"]["attribution"] == "© OpenStreetMap contributors"
    assert report["labels"] == {
        "counts": "OBSERVED",
        "derived": "CALCULATED",
        "study_area": "ASSUMPTION",
        "mapped_features": {
            "ways": "OBSERVED",
            "relations": "OBSERVED",
            "n": "OBSERVED",
            "km": "CALCULATED",
        },
    }
    assert report["area"]["label"] == "ASSUMPTION" and "junction" in report["formulas"]
    assert "sum(length())" in report["formulas"]["mapped_km"]
    assert report["area"]["anchor"]["source"].startswith("Wikidata")
    south, west, north, east = STUDY_BOX
    assert report["study_box"]["bbox"] == {
        "south": south, "west": west, "north": north, "east": east
    }  # fmt: skip
    assert report["study_box"]["label"] == "ASSUMPTION"
    assert "Green River" not in report["study_box"]["landmarks_found"]


def test_the_report_is_identical_byte_for_byte(extract: Path) -> None:
    area = F.load_area("capital")
    first = [p.read_bytes() for p in R.write_report(extract, area)]
    second = [p.read_bytes() for p in R.write_report(extract, area)]
    assert first == second
    assert json.loads(first[0])["schema_version"] == "1"
    markdown = first[1].decode()
    assert "© OpenStreetMap contributors" in markdown and "ODbL-1.0" in markdown
    assert "residential km=0.6 (CALCULATED) ways=6 (OBSERVED)" in markdown
    assert "Study box (ASSUMPTION): south 29.92, west 31.66, north 30.03" in markdown
    assert "km is CALCULATED, computed by Overpass" in markdown


def test_a_way_across_the_edge_counts_inside_only_where_its_segments_are(
    tmp_path: Path,
) -> None:
    """Overpass returns whole ways: the part beyond the box edge is reported apart."""
    points = [
        (30.02, 31.70),
        (30.025, 31.70),
        (30.05, 31.70),
    ]  # the box ends at 30.03 N
    crossing = {
        "type": "way",
        "id": 30,
        "tags": {"highway": "residential"},
        "nodes": [950, 951, 952],
        "geometry": [{"lat": lat, "lon": lon} for lat, lon in points],
    }
    roads = roads_answer()
    roads["elements"].append(crossing)
    extract = F.fetch_area(
        F.load_area("capital"), tmp_path, FakeOverpass({"roads_v1": roads}), NOW
    )  # type: ignore[arg-type]
    report = R.coverage_report(extract, F.load_area("capital"))
    m = report["streets"]["drivable_built"]
    inner, outer = km(points[0], points[1]), km(points[1], points[2])
    base = 6 * ROW + 6 * COL + SPUR
    assert m["length_km"] == round(base + inner + outer, 1)
    assert m["length_km_inside_study_box"] == round(base + inner, 1)
    assert "Inside the box (km)" in R.render_markdown(report)
    assert "whole length" in report["formulas"]["length_km"]


def test_a_statistic_the_report_does_not_know_is_refused(tmp_path: Path) -> None:
    answer = stats_answer()
    answer["elements"].append(stat("highway", "track", ways=1, metres=5))
    extract = F.fetch_area(
        F.load_area("capital"), tmp_path, FakeOverpass({"stats_v1": answer}), NOW
    )  # type: ignore[arg-type]
    with pytest.raises(F.FetchError, match="unknown field 'metres'"):
        R.coverage_report(extract, F.load_area("capital"))


def test_a_tampered_extract_gives_no_report(extract: Path) -> None:
    (extract / "stats_v1.json").write_bytes(b'{"elements": []}')
    with pytest.raises(F.FetchError):
        R.coverage_report(extract, F.load_area("capital"))


def test_a_way_whose_nodes_and_points_disagree_is_refused() -> None:
    with pytest.raises(F.FetchError, match="nodes but"):
        R.segments([{"id": 1, "nodes": [1, 2], "geometry": [{"lat": 0, "lon": 0}]}])
    assert math.isclose(
        sum(
            s[2]
            for s in R.segments(
                [
                    {
                        "id": 1,
                        "nodes": [1, 2],
                        "geometry": [{"lat": 0, "lon": 0}, {"lat": 1, "lon": 0}],
                    }
                ]
            )
        ),
        111.195,
        abs_tol=1e-3,
    )


def test_a_repeated_node_is_not_a_segment() -> None:
    way = {
        "id": 1,
        "nodes": [1, 1, 2],
        "geometry": [{"lat": 0, "lon": 0}, {"lat": 0, "lon": 0}, {"lat": 1, "lon": 0}],
    }
    segs = R.segments([way])
    assert [(a, b) for a, b, _, _ in segs] == [(1, 2)]
    assert R.graph_metrics(segs, 1)["dead_ends"] == 2


def test_the_landmark_radius_is_respected(tmp_path: Path) -> None:
    base = json.loads(
        (Path(F.__file__).parent / "areas" / "capital_v1.json").read_text()
    )
    area = F.area_from_dict({**base, "landmark_radius_m": 100})
    extract = F.fetch_area(area, tmp_path, FakeOverpass(), NOW)  # type: ignore[arg-type]
    near = R.coverage_report(extract, area)["landmarks"]["by_name"][
        "Central Business District"
    ]
    # Within 100 m of the centre node: the four segments that touch it, nothing else.
    assert near == {"found": True, "road_km_within_radius": round(2 * ROW + 2 * COL, 1)}
