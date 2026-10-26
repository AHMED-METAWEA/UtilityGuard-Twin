"""District overlay: hand-drawn zone polygons, labelled ASSUMPTION (owner decisions G1 and G3).

The overlay is a GeoJSON FeatureCollection (RFC 7946, longitude and latitude). The collection
says how it was made (`label` "ASSUMPTION", `method` "hand-drawn", `source`, `drawn`,
`confidence`); each feature is a `Polygon` with the properties `id` (the zone id), `name` and
`land_use`. Junctions are assigned to the polygon that contains them, in the provider's local
metres. A junction in no polygon, or in more than one, is an error that names it: a zone is
never given by default.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ug_core import grammar

Ring = tuple[tuple[float, float], ...]


class OverlayError(ValueError):
    """The overlay is malformed, or it does not cover the network exactly once."""


@dataclass(frozen=True)
class District:
    id: str
    name: str
    land_use: str
    outer: Ring  # local metres
    holes: tuple[Ring, ...] = ()

    @property
    def area_ha(self) -> float:
        return (_area(self.outer) - sum(_area(h) for h in self.holes)) / 10_000

    def contains(self, point: tuple[float, float]) -> bool:
        return _inside(point, self.outer) and not any(
            _inside(point, h) for h in self.holes
        )


@dataclass(frozen=True)
class Overlay:
    districts: tuple[District, ...]
    provenance: Mapping[str, Any]  # label, method, source, drawn, confidence


def load_overlay(
    data: Mapping[str, Any], project: Callable[[float, float], tuple[float, float]]
) -> Overlay:
    """Check an overlay and project it with `project(lat, lon) -> (x, y)`."""
    if data.get("type") != "FeatureCollection":
        raise OverlayError("an overlay is a GeoJSON FeatureCollection")
    provenance = {
        k: data.get(k) for k in ("label", "method", "source", "drawn", "confidence")
    }
    if provenance["label"] != "ASSUMPTION" or provenance["method"] != "hand-drawn":
        raise OverlayError(
            "hand-drawn boundaries carry label ASSUMPTION and method hand-drawn"
        )
    for key in ("source", "drawn"):
        value = provenance[key]
        if not isinstance(value, str) or not value.strip():
            raise OverlayError(f"the overlay must say {key}")
    districts: list[District] = []
    for feature in data.get("features") or []:
        props, geometry = feature.get("properties") or {}, feature.get("geometry") or {}
        zone = grammar.require_identifier(props.get("id"), "overlay zone id")
        grammar.require_identifier(props.get("land_use"), f"zone {zone}: land use")
        if geometry.get("type") != "Polygon" or not geometry.get("coordinates"):
            raise OverlayError(f"zone {zone}: the geometry must be a Polygon")
        rings = [_ring(r, project, zone) for r in geometry["coordinates"]]
        districts.append(
            District(
                zone,
                str(props.get("name", zone)),
                props["land_use"],
                rings[0],
                tuple(rings[1:]),
            )
        )
    if not districts:
        raise OverlayError("the overlay holds no district")
    ids = [d.id for d in districts]
    if len(set(ids)) != len(ids):
        raise OverlayError("zone ids must be unique")
    return Overlay(tuple(sorted(districts, key=lambda d: d.id)), provenance)


def read_overlay(
    path: Path, project: Callable[[float, float], tuple[float, float]]
) -> Overlay:
    return load_overlay(json.loads(path.read_text(encoding="utf-8")), project)


def assign(
    nodes: Mapping[Any, tuple[float, float]], overlay: Overlay
) -> dict[Any, str]:
    """The zone of every node; an uncovered or doubly covered node is an `OverlayError`."""
    zones: dict[Any, str] = {}
    outside: list[Any] = []
    for node, point in nodes.items():
        found = [d.id for d in overlay.districts if d.contains(point)]
        if len(found) > 1:
            raise OverlayError(f"node {node} lies in more than one zone: {found}")
        if not found:
            outside.append(node)
            continue
        zones[node] = found[0]
    if outside:
        raise OverlayError(
            f"{len(outside)} nodes lie in no zone of the overlay (for example {sorted(outside)[:5]}); "
            "a zone is never given by default"
        )
    return zones


def _ring(
    coordinates: Any, project: Callable[[float, float], tuple[float, float]], zone: str
) -> Ring:
    points = [project(float(lat), float(lon)) for lon, lat in coordinates]
    if len(points) < 4 or points[0] != points[-1]:
        raise OverlayError(f"zone {zone}: a ring needs at least four positions, closed")
    if _area(tuple(points)) <= 0:
        raise OverlayError(f"zone {zone}: a ring encloses no area")
    return tuple(points)


def _area(ring: Ring) -> float:
    return (
        abs(
            sum(
                x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False)
            )
        )
        / 2
    )


def _inside(point: tuple[float, float], ring: Ring) -> bool:
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside
