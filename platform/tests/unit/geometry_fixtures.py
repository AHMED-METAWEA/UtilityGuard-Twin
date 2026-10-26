"""Synthetic Overpass answers for the geometry tests. No OpenStreetMap data is used: the tests
build a small hand-checkable street grid themselves."""

from __future__ import annotations

import io
import json
from typing import Any

BASE = "2026-10-26T10:24:21Z"
# A 3 x 3 grid of nodes 0.001 degrees apart near the anchor of the capital area file.
LAT0, LON0, STEP = 30.0, 31.70, 0.001
# Six of the nine landmarks (the area asks for at least six); "Green River" and two more are
# missing. The study box is their bounding box (29.95..30.001 N, 31.70..31.76 E) plus 3 km,
# rounded outward to 0.01 degree: 3 km is 0.02695 degree of latitude and, at 29.975 N,
# 0.03111 degree of longitude.
LANDMARKS = {
    "Central Business District": (LAT0 + STEP, LON0 + STEP),  # the centre of the grid
    "Governmental District": (29.95, 31.76),
    "Arts and Culture City": (29.98, 31.72),
    "The Iconic Tower": (29.99, 31.74),
    "Capital Presidential Palace": (29.96, 31.70),
    "Egypt International Olympic City": (29.97, 31.75),
}
STUDY_BOX = (29.92, 31.66, 30.03, 31.80)


def node_id(row: int, col: int) -> int:
    return 100 + row * 3 + col


def point(row: int, col: int) -> dict[str, float]:
    return {"lat": LAT0 + row * STEP, "lon": LON0 + col * STEP}


def way(way_id: int, cells: list[tuple[int, int]], highway: str) -> dict[str, Any]:
    return {
        "type": "way",
        "id": way_id,
        "tags": {"highway": highway},
        "nodes": [node_id(r, c) for r, c in cells],
        "geometry": [point(r, c) for r, c in cells],
    }


def roads_answer() -> dict[str, Any]:
    """Three residential rows, three residential columns (a connected 3 x 3 grid), one service
    spur and one road under construction off the grid (its own component)."""
    ways = [way(1 + r, [(r, 0), (r, 1), (r, 2)], "residential") for r in range(3)]
    ways += [way(10 + c, [(0, c), (1, c), (2, c)], "residential") for c in range(3)]
    spur = {
        "type": "way",
        "id": 20,
        "tags": {"highway": "service"},
        "nodes": [node_id(2, 2), 900],
        "geometry": [point(2, 2), {"lat": LAT0 + 3 * STEP, "lon": LON0 + 2 * STEP}],
    }
    building = {
        "type": "way",
        "id": 21,
        "tags": {"highway": "construction"},
        "nodes": [901, 902],
        "geometry": [{"lat": 29.95, "lon": 31.75}, {"lat": 29.95, "lon": 31.751}],
    }
    return {
        "version": 0.6,
        "osm3s": {"timestamp_osm_base": BASE},
        "elements": [*ways, spur, building],
    }


def stat(group: str, value: str, **numbers: float) -> dict[str, Any]:
    tags = {"group": group, "value": value, **{k: str(v) for k, v in numbers.items()}}
    return {"type": "stat", "id": 0, "tags": tags}


def stats_answer() -> dict[str, Any]:
    return {
        "version": 0.6,
        "osm3s": {"timestamp_osm_base": BASE},
        "elements": [
            stat("highway", "residential", ways=6, km=0.6489),
            stat("highway", "service", ways=1, km=0.111),
            stat("landuse", "residential", ways=2),
            stat("buildings", "all", ways=12, relations=1),
            stat("buildings", "with_levels", ways=0),
            stat("names", "named_highways", ways=3),
            stat("freshness", "highways_edited_last_year", ways=5),
            stat("freshness", "highways_edited_last_two_years", ways=8),
            stat("amenity", "office_government", n=0),
            stat("water_infrastructure", "water_tower", n=1),
        ],
    }


def landmark(element_id: int, name: str, lat: float, lon: float) -> dict[str, Any]:
    return {
        "type": "node",
        "id": element_id,
        "lat": lat,
        "lon": lon,
        "tags": {"name:en": name},
    }


def landmarks_answer() -> dict[str, Any]:
    return {
        "version": 0.6,
        "osm3s": {"timestamp_osm_base": BASE},
        "elements": [
            landmark(7 + i, name, lat, lon)
            for i, (name, (lat, lon)) in enumerate(LANDMARKS.items())
        ],
    }


ANSWERS = {
    "roads_v1": roads_answer,
    "stats_v1": stats_answer,
    "landmarks_v1": landmarks_answer,
}


class FakeOverpass:
    """Stands in for `Overpass`: answers by which template the query came from."""

    user_agent = "test-agent"

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self.queries: list[str] = []
        self.overrides = overrides or {}

    def query(self, text: str) -> tuple[bytes, dict[str, Any]]:
        self.queries.append(text)
        name = (
            "roads_v1"
            if "out geom" in text
            else "landmarks_v1"
            if "name:en" in text
            else "stats_v1"
        )
        value = self.overrides.get(name)
        if isinstance(value, Exception):
            raise value
        data = value if value is not None else ANSWERS[name]()
        raw = json.dumps(data, sort_keys=True).encode()
        return raw, json.loads(raw)


class Response(io.BytesIO):
    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
