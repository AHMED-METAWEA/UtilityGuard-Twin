"""The street graph of a cached OpenStreetMap extract, in local metres.

Reads an extract made by `ug fetch-geometry` (T-B1-010) after `verify_extract` has checked it, so
only an intact extract with its provenance is used. Nothing read here is written into the
repository (decision G2): the graph lives in memory, and a network built from it is rebuilt from
the cache whenever it is needed.

Only the street segments whose midpoint lies inside the study box are kept (the coverage
report's rule): Overpass returns whole ways, which reach beyond the box.

Projection: equirectangular about the centre of the study box, `x = R (lon - lon0) cos(lat0)`,
`y = R (lat - lat0)`, with R = 6,371,008.8 m. `projection_error` measures the largest relative
difference between projected and great-circle lengths over the study box (about 0.1% for the
capital's box) and is recorded with the network.
"""

from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ug_core.canonical import canonical_json, sha256_hex
from ug_core.geometry.fetch import (
    ROADS,
    Area,
    default_cache,
    latest_extract,
    load_area,
    verify_extract,
)
from ug_core.geometry.report import haversine_km
from ug_core.rng import SeedStreams

from ug_water.network.model import (
    Junction,
    Network,
    NetworkProvenance,
    Pipe,
    Pump,
    PumpRole,
    Reservoir,
    Tank,
    Zone,
)
from ug_water.network.overlay import assign, load_overlay

if TYPE_CHECKING:
    from ug_water.network.inference import TierRule

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class Projection:
    lat0: float
    lon0: float

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        x = (
            EARTH_RADIUS_M
            * math.radians(lon - self.lon0)
            * math.cos(math.radians(self.lat0))
        )
        y = EARTH_RADIUS_M * math.radians(lat - self.lat0)
        return x, y


def projection_error(
    projection: Projection, box: tuple[float, float, float, float]
) -> float:
    """Largest relative length error of the projection over the box, measured on short
    east-west, north-south and diagonal segments at a 5 x 5 grid of points (the error of a
    longer segment lies between those of its parts)."""
    south, west, north, east = box
    worst = 0.0
    step = 0.001  # about 100 m
    for i in range(5):
        for k in range(5):
            lat = south + (north - south) * i / 4
            lon = west + (east - west) * k / 4
            for d_lat, d_lon in ((step, 0.0), (0.0, step), (step, step)):
                a, b = (lat, lon), (lat + d_lat, lon + d_lon)
                true = haversine_km(a, b) * 1000
                (xa, ya), (xb, yb) = projection.xy(*a), projection.xy(*b)
                worst = max(worst, abs(math.hypot(xb - xa, yb - ya) - true) / true)
    return worst


@dataclass(frozen=True)
class Street:
    """One street segment between two consecutive OSM nodes of a way."""

    a: int
    b: int
    length_m: float
    highway: str
    way: int


@dataclass(frozen=True)
class StreetGraph:
    nodes: Mapping[int, tuple[float, float]]  # OSM node id -> local (x, y) in metres
    streets: tuple[Street, ...]
    projection: Projection
    projection_error: float
    provenance: Mapping[
        str, Any
    ]  # source, licence, osm_base, extract_sha256, retrieved


def load_street_graph(
    extract: Path, area: Area, *, include_construction: bool = False
) -> StreetGraph:
    """The street graph of a verified extract. Roads under construction are a separate,
    opt-in layer. Raises `FetchError` (from `verify_extract`) if the extract is not intact."""
    record = verify_extract(extract, area)
    south, west, north, east = (float(v) for v in record["study_box"]["bbox"])
    projection = Projection((south + north) / 2, (west + east) / 2)
    data = json.loads((extract / f"{ROADS}.json").read_bytes())
    nodes: dict[int, tuple[float, float]] = {}
    streets: list[Street] = []
    for way in sorted(data["elements"], key=lambda w: int(w["id"])):
        highway = way["tags"]["highway"]
        if highway == "construction" and not include_construction:
            continue
        ids, points = way["nodes"], way["geometry"]
        for (i, p), (j, q) in itertools.pairwise(zip(ids, points, strict=True)):
            if i == j:
                continue
            # The network holds the streets inside the study box: a segment counts where its
            # midpoint lies (the coverage report's rule); Overpass returns whole ways.
            mid_lat = (float(p["lat"]) + float(q["lat"])) / 2
            mid_lon = (float(p["lon"]) + float(q["lon"])) / 2
            if not (south <= mid_lat <= north and west <= mid_lon <= east):
                continue
            for node, point in ((i, p), (j, q)):
                xy = projection.xy(float(point["lat"]), float(point["lon"]))
                if nodes.setdefault(int(node), xy) != xy:
                    raise ValueError(
                        f"OSM node {node} has two positions in the extract"
                    )
            length = math.dist(nodes[int(i)], nodes[int(j)])
            streets.append(Street(int(i), int(j), length, highway, int(way["id"])))
    return StreetGraph(
        nodes=nodes,
        streets=tuple(streets),
        projection=projection,
        projection_error=projection_error(projection, (south, west, north, east)),
        provenance={
            "source": record["source"],
            "licence": record["licence"],
            "attribution": record["attribution"],
            "osm_base": record["osm_base"],
            "extract_sha256": record["extract_sha256"],
            "retrieved": record["retrieved"],
            "coverage_report": record["coverage_report"],
        },
    )


class OsmCapitalProvider:
    """The F1 network: pipes on the OpenStreetMap streets of the capital's study box, zones from
    the hand-drawn district overlay, everything else an `ASSUMPTION` of `osm_capital_v1.json`.

    Rules (see also `inference.py`): junction ids are `j_<OSM node id>` at the OSM node's position
    (`PUBLIC_GEOMETRY`); elevations come from a seeded synthetic terrain; a zone's demand is its
    land use's rate (L/s per hectare) times the district's area, shared equally by its junctions;
    the source is a ground reservoir beside the transmission junction furthest to the configured
    side, feeding it through the duty and standby pumps, whose curve is sized for the peak
    demand; each of the tanks stands beside the highest junction of one sector around the centre.
    """

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        overlay: Mapping[str, Any] | None = None,
        *,
        cache: Path | None = None,
    ) -> None:
        self.config = (
            dict(config)
            if config is not None
            else json.loads(
                resources.files("ug_water.network")
                .joinpath("data/osm_capital_v1.json")
                .read_text()
            )
        )
        if self.config.get("label") != "ASSUMPTION":
            raise ValueError(
                "the OSM provider's parameters are chosen: label ASSUMPTION"
            )
        self.overlay_data = overlay
        self.cache = cache

    def build(self, tier: str = "lite", seed: int = 1) -> Network:
        area = load_area("capital")
        extract = latest_extract(area, self.cache or default_cache())
        if extract is None:
            raise ValueError(
                "no verified extract of the capital in the cache: run ug fetch-geometry"
            )
        return self.from_graph(load_street_graph(extract, area), tier, seed)

    def from_graph(
        self, graph: StreetGraph, tier: str, seed: int, rule: TierRule | None = None
    ) -> Network:
        if self.overlay_data is None:
            raise ValueError(
                "the OSM provider needs a district overlay (decisions G1 and G3)"
            )
        from ug_water.network.inference import (
            skeleton,
        )  # inference reads this module's types

        cfg = self.config
        overlay = load_overlay(self.overlay_data, graph.projection.xy)
        sk = skeleton(graph, tier, rule)
        terrain = _Terrain(cfg["terrain"], SeedStreams(seed).stream("terrain"))
        zone_of = assign(sk.nodes, overlay)
        districts = {d.id: d for d in overlay.districts}
        rates = cfg["demand_l_s_per_ha"]
        members: dict[str, list[int]] = defaultdict(list)
        for node, zone in zone_of.items():
            members[zone].append(node)
        demand: dict[int, float] = {}
        for zone, nodes in members.items():
            land_use = districts[zone].land_use
            if land_use not in rates:
                raise ValueError(
                    f"zone {zone}: no demand rate for land use {land_use!r}"
                )
            total = float(rates[land_use]) * districts[zone].area_ha / 1000.0  # m3/s
            for node in nodes:
                demand[node] = total / len(nodes)
        junctions = [
            Junction(f"j_{n}", x, y, terrain(x, y), demand[n], zone_of[n])
            for n, (x, y) in sk.nodes.items()
        ]
        pipes = [
            Pipe(
                f"p_{k:05d}", f"j_{p.a}", f"j_{p.b}", p.length_m,
                float(cfg["diameters_m"][p.tier]), float(cfg["roughness"][p.tier]), p.tier,
            )
            for k, p in enumerate(sk.pipes)
        ]  # fmt: skip
        by_id = {j.id: j for j in junctions}
        main = sorted(
            {e for p in pipes if p.tier == "transmission" for e in (p.start, p.end)}
        )
        if not main:
            raise ValueError(f"tier {tier}: no transmission main to feed")
        side = cfg["source"]["side"]
        sign = {"west": (1, 0), "east": (-1, 0), "south": (0, 1), "north": (0, -1)}[
            side
        ]
        site = by_id[
            min(main, key=lambda j: (sign[0] * by_id[j].x + sign[1] * by_id[j].y, j))
        ]
        dx, dy = cfg["source"]["offset_m"]
        reservoir = Reservoir(
            "source", site.x + dx, site.y + dy,
            site.elevation + float(cfg["source"]["head_above_site_m"]),
        )  # fmt: skip
        pc = cfg["pumps"]
        peak = float(pc["peak_factor"]) * sum(j.base_demand for j in junctions)
        q, h = peak / int(pc["duty"]), float(pc["design_head_m"])
        curve = ((0.0, 4 * h / 3), (q, h), (1.6 * q, h / 2))
        duty = int(pc["duty"])
        pumps = [
            Pump(f"pump_{k}", reservoir.id, site.id, "source_station",
                 _role(k < duty), curve, float(pc["efficiency"]))
            for k in range(duty + int(pc["standby"]))
        ]  # fmt: skip
        tanks, tank_pipes = self._tanks(junctions, cfg["tanks"], cfg)
        zones = [
            Zone(d.id, d.name, d.land_use) for d in overlay.districts if d.id in members
        ]
        provenance = NetworkProvenance(
            provider="osm",
            fidelity="F1",
            seed=seed,
            config_hash=sha256_hex(
                canonical_json(
                    {"config": cfg, "tier": tier, "overlay": self.overlay_data}
                )
            ),
            labels={
                "coordinates": "PUBLIC_GEOMETRY",
                "topology": "ASSUMPTION",
                "zones": "ASSUMPTION",
                "diameters": "ASSUMPTION",
                "demands": "ASSUMPTION",
                "equipment": "ASSUMPTION",
            },
            geometry={**graph.provenance, "label": "PUBLIC_GEOMETRY"},
            district_boundaries=dict(overlay.provenance),
        )
        return Network(
            name=f"osm-capital-v1-{tier}",
            provenance=provenance,
            zones=tuple(zones),
            junctions=tuple(junctions),
            reservoirs=(reservoir,),
            tanks=tuple(tanks),
            pipes=tuple(pipes + tank_pipes),
            pumps=tuple(pumps),
        )

    @staticmethod
    def _tanks(
        junctions: list[Junction], tc: Mapping[str, Any], cfg: Mapping[str, Any]
    ) -> tuple[list[Tank], list[Pipe]]:
        cx = math.fsum(j.x for j in junctions) / len(junctions)
        cy = math.fsum(j.y for j in junctions) / len(junctions)
        count = int(tc["count"])
        sectors: dict[int, list[Junction]] = defaultdict(list)
        for j in junctions:
            angle = math.atan2(j.y - cy, j.x - cx) % (2 * math.pi)
            sectors[min(int(angle / (2 * math.pi) * count), count - 1)].append(j)
        tanks: list[Tank] = []
        pipes: list[Pipe] = []
        dx, dy = tc["offset_m"]
        for k in range(count):
            if not sectors[k]:
                raise ValueError(f"tank sector {k} holds no junction")
            site = max(sectors[k], key=lambda j: (j.elevation, j.id))
            tank = Tank(
                f"tank_{k}", site.x + dx, site.y + dy,
                site.elevation + float(tc["height_above_site_m"]), float(tc["init_level_m"]),
                float(tc["min_level_m"]), float(tc["max_level_m"]), float(tc["diameter_m"]),
                elevated=True,
            )  # fmt: skip
            tanks.append(tank)
            pipes.append(
                Pipe(
                    f"p_tank_{k}", site.id, tank.id, math.hypot(dx, dy),
                    float(cfg["diameters_m"]["submain"]), float(cfg["roughness"]["submain"]),
                    "submain",
                )
            )  # fmt: skip
        return tanks, pipes


def _role(duty: bool) -> PumpRole:
    return "duty" if duty else "standby"


class _Terrain:
    """A gentle synthetic terrain: a plane and one seeded wave (an ASSUMPTION, not a survey)."""

    def __init__(self, cfg: Mapping[str, Any], rng: Any) -> None:
        self.base = float(cfg["base_m"])
        self.gx, self.gy = (float(v) / 1000 for v in cfg["gradient_m_per_km"])
        self.noise = float(cfg["noise_m"])
        self.wave = 2 * math.pi / (float(cfg["wavelength_km"]) * 1000)
        self.px, self.py = (float(v) for v in rng.uniform(0, 2 * math.pi, size=2))

    def __call__(self, x: float, y: float) -> float:
        return (
            self.base + self.gx * x + self.gy * y
            + self.noise * math.sin(self.wave * x + self.px) * math.sin(self.wave * y + self.py)
        )  # fmt: skip
