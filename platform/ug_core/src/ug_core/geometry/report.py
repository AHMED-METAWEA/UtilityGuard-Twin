"""The coverage report of a cached geometry extract (the numbers of the feasibility test).

It answers, for one extract: how much of the street network OpenStreetMap holds, how connected
it is, how evenly it covers the study area, and how much of the districts, land use, buildings
and water network is mapped. It is computed from the cached answers only, so the same extract
gives the same report, byte for byte.

Labels: counts of mapped features are `OBSERVED` (what OpenStreetMap contributors have mapped,
not the ground); lengths, junctions, components and shares computed from them are
`CALCULATED` (the formulas are written into the report), and so are the kilometres Overpass
sums per highway class; the study box is an `ASSUMPTION` placed at fetch time and read from the
extract's provenance. Every statistic of `mapped_features` has its own label; a statistic the
report does not know is refused, not guessed.

Street-graph rules: road segments are the consecutive node pairs of each way; a junction is a
node with three or more distinct neighbours; a dead end has one; components are connected sets
of segments; lengths are great-circle distances on a sphere of radius 6,371.0088 km.
"""

from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ug_core.canonical import canonical_json
from ug_core.geometry.fetch import (
    KM_PER_DEG_LAT,
    LANDMARKS,
    ROADS,
    STATS,
    Area,
    FetchError,
    landmark_positions,
    verify_extract,
)

REPORT_SCHEMA_VERSION = "1"
EARTH_RADIUS_KM = 6371.0088
MAIN_STREETS = frozenset(
    {
        "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
        "residential", "living_street", "motorway_link", "trunk_link", "primary_link",
        "secondary_link", "tertiary_link",
    }
)  # fmt: skip
FORMULAS = {
    "segment": "consecutive node pairs of each way",
    "length_km": "great-circle distance, sphere of radius 6371.0088 km",
    "junction": "node with three or more distinct neighbours",
    "dead_end": "node with exactly one neighbour",
    "component": "connected set of segments (union-find)",
    "grid": "segments assigned to square cells by their midpoint",
    "landmark_road_km": "length of segments whose midpoint lies within the radius",
    "landmark_position": "the feature of that name nearest the anchor",
    "mapped_km": "computed by Overpass: sum(length()) / 1000 over the ways of the class",
}
STAT_LABELS = {
    "ways": "OBSERVED",
    "relations": "OBSERVED",
    "n": "OBSERVED",
    "km": "CALCULATED",
}


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


Segment = tuple[int, int, float, tuple[float, float]]  # node a, node b, km, midpoint


def segments(ways: Iterable[dict[str, Any]]) -> list[Segment]:
    out: list[Segment] = []
    for way in ways:
        ids = way.get("nodes") or []
        geometry = way.get("geometry") or []
        if len(ids) != len(geometry):
            raise FetchError(
                f"way {way.get('id')} has {len(ids)} nodes but {len(geometry)} points"
            )
        for (i, a), (j, b) in itertools.pairwise(zip(ids, geometry, strict=True)):
            if a is None or b is None or i == j:
                continue
            pa, pb = (
                (float(a["lat"]), float(a["lon"])),
                (float(b["lat"]), float(b["lon"])),
            )
            mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            out.append((int(i), int(j), haversine_km(pa, pb), mid))
    return out


def graph_metrics(segs: list[Segment], ways: int) -> dict[str, Any]:
    neighbours: dict[int, set[int]] = defaultdict(set)
    for a, b, _, _ in segs:
        neighbours[a].add(b)
        neighbours[b].add(a)
    parent = {node: node for node in neighbours}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _, _ in segs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)  # deterministic root choice
    length: dict[int, float] = defaultdict(float)
    for a, _, km, _ in segs:
        length[find(a)] += km
    total = math.fsum(km for _, _, km, _ in segs)
    junction_roots = [find(n) for n, ns in neighbours.items() if len(ns) >= 3]
    largest = max(length, key=lambda root: (length[root], -root)) if length else None
    return {
        "ways": ways,
        "length_km": round(total, 1),
        "nodes": len(neighbours),
        "junctions": len(junction_roots),
        "dead_ends": sum(1 for ns in neighbours.values() if len(ns) == 1),
        "components": len(length),
        "largest_component_length_share": round(length[largest] / total, 3)
        if largest is not None and total
        else 0.0,
        "junctions_in_largest_component": sum(
            1 for root in junction_roots if root == largest
        ),
    }


def _load(extract: Path, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((extract / f"{name}.json").read_bytes())
    return data


def _ways(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in data["elements"] if e.get("type") == "way"]


def _stats(data: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for element in data["elements"]:
        if element.get("type") != "stat":
            continue
        tags = dict(element.get("tags") or {})
        group, value = str(tags.pop("group", "")), str(tags.pop("value", ""))
        if not group:
            continue
        numbers: dict[str, Any] = {}
        for key, raw in sorted(tags.items()):
            if key not in STAT_LABELS:
                raise FetchError(
                    f"statistic {group}/{value} has an unknown field {key!r}"
                )
            number = float(raw)
            numbers[key] = round(number, 1) if key == "km" else int(round(number))
        groups[group][value or "(none)"] = numbers
    return {
        group: dict(sorted(values.items())) for group, values in sorted(groups.items())
    }


def coverage_report(extract: Path, area: Area) -> dict[str, Any]:
    """Compute the report of a verified extract. Raises `FetchError` if the extract is not intact."""
    provenance = verify_extract(extract, area)
    roads = _ways(_load(extract, ROADS))
    built = [w for w in roads if (w.get("tags") or {}).get("highway") != "construction"]
    main = [w for w in roads if (w.get("tags") or {}).get("highway") in MAIN_STREETS]
    all_segs, built_segs, main_segs = segments(roads), segments(built), segments(main)
    all_metrics = graph_metrics(all_segs, len(roads))
    total_km = math.fsum(km for _, _, km, _ in all_segs)
    construction_km = total_km - math.fsum(km for _, _, km, _ in built_segs)

    study = provenance["study_box"]
    south, west, north, east = (float(v) for v in study["bbox"])
    cell_lat = area.grid_cell_m / 1000 / KM_PER_DEG_LAT
    cell_lon = (
        area.grid_cell_m
        / 1000
        / (KM_PER_DEG_LAT * math.cos(math.radians((south + north) / 2)))
    )
    rows, cols = (
        math.ceil((north - south) / cell_lat),
        math.ceil((east - west) / cell_lon),
    )
    cell_km: dict[tuple[int, int], float] = defaultdict(float)
    for _, _, km, (lat, lon) in all_segs:
        if south <= lat <= north and west <= lon <= east:
            cell_km[
                (
                    min(int((lat - south) / cell_lat), rows - 1),
                    min(int((lon - west) / cell_lon), cols - 1),
                )
            ] += km

    positions = landmark_positions(_load(extract, LANDMARKS), area)
    landmarks: dict[str, Any] = {}
    radius_km = area.landmark_radius_m / 1000
    for name in area.landmarks:
        position = positions.get(name)
        if position is None:
            landmarks[name] = {"found": False}
            continue
        near = math.fsum(
            km for _, _, km, mid in all_segs if haversine_km(position, mid) <= radius_km
        )
        landmarks[name] = {"found": True, "road_km_within_radius": round(near, 1)}

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "area": {
            "name": area.name,
            "version": area.version,
            "label": area.label,
            "note": area.note,
            "anchor": {
                "lat": area.anchor[0],
                "lon": area.anchor[1],
                "source": area.anchor_source,
            },
            "sha256": area.sha256,
        },
        "study_box": {
            "bbox": {"south": south, "west": west, "north": north, "east": east},
            "label": study["label"],
            "method": study["method"],
            "landmarks_found": study["landmarks_found"],
        },
        "source": {
            key: provenance.get(key)
            for key in (
                "label",
                "source",
                "licence",
                "attribution",
                "retrieved",
                "osm_base",
                "extract_sha256",
            )
        },
        "labels": {
            "counts": "OBSERVED",
            "derived": "CALCULATED",
            "study_area": "ASSUMPTION",
            "mapped_features": STAT_LABELS,
        },
        "formulas": FORMULAS,
        "streets": {
            "drivable_and_under_construction": all_metrics,
            "drivable_built": graph_metrics(built_segs, len(built)),
            "main_streets": graph_metrics(main_segs, len(main)),
            "share_of_length_under_construction": round(construction_km / total_km, 3)
            if total_km
            else 0.0,
        },
        "grid": {
            "cell_m": area.grid_cell_m,
            "cells": rows * cols,
            "cells_with_any_road": len(cell_km),
            "cells_with_at_least_5_km": sum(1 for v in cell_km.values() if v >= 5),
            "cells_with_at_least_10_km": sum(1 for v in cell_km.values() if v >= 10),
        },
        "landmarks": {"radius_m": area.landmark_radius_m, "by_name": landmarks},
        "mapped_features": _stats(_load(extract, STATS)),
    }


def render_markdown(report: dict[str, Any]) -> str:
    src, streets, grid = report["source"], report["streets"], report["grid"]
    box = report["study_box"]["bbox"]
    lines = [
        f"# Geometry coverage report: {report['area']['name']} (area version {report['area']['version']})",
        "",
        f"Source: {src['source']}, {src['licence']}, {src['attribution']}. OSM data timestamp "
        f"{src['osm_base']}, retrieved {src['retrieved']}. Counts are OBSERVED (what OpenStreetMap "
        "holds, not the ground); lengths, junctions and shares are CALCULATED; the study area is an "
        "ASSUMPTION.",
        "",
        f"Study box (ASSUMPTION): south {box['south']}, west {box['west']}, north {box['north']}, "
        f"east {box['east']}; {report['study_box']['method']}; landmarks used: "
        f"{', '.join(report['study_box']['landmarks_found'])}.",
        "",
        "| Road set | Ways | Length (km) | Junctions | Dead ends | Components | Largest component (length share) |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, label in (
        ("drivable_built", "Drivable, built"),
        ("drivable_and_under_construction", "Drivable plus under construction"),
        ("main_streets", "Main streets (no service, no construction)"),
    ):
        m = streets[key]
        lines.append(
            f"| {label} | {m['ways']} | {m['length_km']} | {m['junctions']} | {m['dead_ends']} | "
            f"{m['components']} | {m['largest_component_length_share']} |"
        )
    lines += [
        "",
        f"Share of drivable length under construction: {streets['share_of_length_under_construction']}.",
        f"Grid of {grid['cell_m']:g} m cells: {grid['cells_with_any_road']} of {grid['cells']} hold a road, "
        f"{grid['cells_with_at_least_5_km']} at least 5 km, {grid['cells_with_at_least_10_km']} at least 10 km.",
        "",
        f"Road length within {report['landmarks']['radius_m']:g} m of each landmark:",
        "",
    ]
    for name, value in report["landmarks"]["by_name"].items():
        text = (
            f"{value['road_km_within_radius']} km"
            if value["found"]
            else "not found in the extract"
        )
        lines.append(f"- {name}: {text}")
    labels = report["labels"]["mapped_features"]
    lines += [
        "",
        "Mapped features: counts (ways, relations, n) are OBSERVED; km is CALCULATED, "
        f"{report['formulas']['mapped_km']}.",
        "",
    ]
    for group, values in report["mapped_features"].items():
        parts = ", ".join(
            f"{value} " + " ".join(f"{k}={v} ({labels[k]})" for k, v in numbers.items())
            for value, numbers in values.items()
        )
        lines.append(f"- {group}: {parts}")
    return "\n".join(lines) + "\n"


def write_report(extract: Path, area: Area) -> tuple[Path, Path]:
    report = coverage_report(extract, area)
    json_path, md_path = extract / "report.json", extract / "report.md"
    json_path.write_text(canonical_json(report) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
