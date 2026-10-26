"""Synthetic street graphs and overlays for the OSM provider tests (no OpenStreetMap data)."""

from __future__ import annotations

import math
from typing import Any

from ug_water.network.osm import Projection, Street, StreetGraph

PROJECTION = Projection(30.0, 31.7)
PROVENANCE = {
    "source": "OpenStreetMap",
    "licence": "ODbL-1.0",
    "attribution": "© OpenStreetMap contributors",
    "osm_base": "2026-10-26T10:24:21Z",
    "extract_sha256": "a" * 64,
    "retrieved": "2026-10-26T10:25:33Z",
    "coverage_report": "report.json",
}


def node(row: int, col: int) -> int:
    return 1000 + 100 * row + col


def graph(
    streets: list[tuple[int, int, str]], positions: dict[int, tuple[float, float]]
) -> StreetGraph:
    out = tuple(
        Street(a, b, math.dist(positions[a], positions[b]), cls, way)
        for way, (a, b, cls) in enumerate(streets)
    )
    return StreetGraph(
        nodes=positions,
        streets=out,
        projection=PROJECTION,
        projection_error=0.0,
        provenance=PROVENANCE,
    )


def grid(
    rows: int, cols: int, spacing: float = 200.0, main_row: int | None = None
) -> StreetGraph:
    """A street grid; row `main_row` is a primary road, the rest residential. Every street is
    split by a midpoint node of degree 2, which the skeleton must contract away."""
    positions: dict[int, tuple[float, float]] = {}
    streets: list[tuple[int, int, str]] = []
    mid = 50_000
    for r in range(rows):
        for c in range(cols):
            # A deterministic jitter, so street lengths differ as they do in a real city.
            jx = 0.15 * spacing * math.sin(1.7 * r + 2.3 * c)
            jy = 0.15 * spacing * math.cos(2.9 * r + 1.1 * c)
            positions[node(r, c)] = (c * spacing + jx, r * spacing + jy)
    for r in range(rows):
        for c in range(cols):
            for dr, dc in ((0, 1), (1, 0)):
                if r + dr < rows and c + dc < cols:
                    a, b = node(r, c), node(r + dr, c + dc)
                    m = mid
                    mid += 1
                    (xa, ya), (xb, yb) = positions[a], positions[b]
                    positions[m] = ((xa + xb) / 2, (ya + yb) / 2)
                    cls = "primary" if dr == 0 and r == main_row else "residential"
                    streets += [(a, m, cls), (m, b, cls)]
    return graph(streets, positions)


def overlay(
    polygons: list[tuple[str, str, list[tuple[float, float]]]],
) -> dict[str, Any]:
    """Polygons given in local metres, written as longitude and latitude (inverse projection)."""
    features = []
    for zone, land_use, ring in polygons:
        coords = [[lon, lat] for lat, lon in (_latlon(x, y) for x, y in ring)]
        features.append(
            {
                "type": "Feature",
                "properties": {"id": zone, "name": zone.title(), "land_use": land_use},
                "geometry": {"type": "Polygon", "coordinates": [coords]},
            }
        )
    return {
        "type": "FeatureCollection",
        "label": "ASSUMPTION",
        "method": "hand-drawn",
        "source": "test fixture",
        "drawn": "2026-10-26",
        "confidence": "approximate",
        "features": features,
    }


def box(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _latlon(x: float, y: float) -> tuple[float, float]:
    r = 6_371_008.8
    lat = PROJECTION.lat0 + math.degrees(y / r)
    lon = PROJECTION.lon0 + math.degrees(
        x / (r * math.cos(math.radians(PROJECTION.lat0)))
    )
    return lat, lon
