"""Generic synthetic F0 capital fixture; never a surveyed or hydraulically validated city.

All physical parameters live in the packaged JSON. Links follow straight synthetic
street segments, so pipe length is exactly the Euclidean endpoint distance. Inline
valves occupy the remaining configured fraction of a split street segment (the
plain model has no valve length). Hydraulic validation belongs to T-B1-014.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import replace
from importlib.resources import files
from typing import Any

import numpy as np
from ug_core.canonical import canonical_json, sha256_hex
from ug_core.rng import SeedStreams

from ug_water.network.model import (
    LABELLED_PARTS,
    Junction,
    LevelControl,
    Network,
    NetworkProvenance,
    Pipe,
    PipeTier,
    Pump,
    Reservoir,
    Sensor,
    SensorKind,
    Tank,
    Valve,
    ValveKind,
    Zone,
)


def _count(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _adjacency(links: list[Pipe | Pump | Valve]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for link in links:
        result.setdefault(link.start, set()).add(link.end)
        result.setdefault(link.end, set()).add(link.start)
    return result


def _neighborhood(node: str, graph: dict[str, set[str]], hops: int) -> set[str]:
    seen, frontier = {node}, {node}
    for _ in range(hops):
        frontier = {v for u in frontier for v in graph.get(u, ())} - seen
        seen.update(frontier)
        if not frontier:
            break
    return seen


def _coverage_order(
    candidates: Mapping[str, str],
    graph: dict[str, set[str]],
    rng: np.random.Generator,
    hops: int,
    count: int,
) -> list[str]:
    """Greedy diminishing-return coverage of graph neighborhoods, with seeded ties.

    A node covered n times contributes 1/(n+1) to the next site's score. This
    structural proxy is not a claim of hydraulic observability. Sorting both
    candidates and covered nodes keeps floating-point tie decisions reproducible.
    """
    if count > len(candidates):
        raise ValueError(f"requested {count} sensors from {len(candidates)} sites")
    order = [str(k) for k in rng.permutation(sorted(candidates))]
    neighborhoods = {
        k: sorted(_neighborhood(candidates[k], graph, hops)) for k in order
    }
    covered: dict[str, int] = {}
    chosen: list[str] = []
    while len(chosen) < count:
        best = max(
            order,
            key=lambda k: math.fsum(
                1 / (1 + covered.get(n, 0)) for n in neighborhoods[k]
            ),
        )
        chosen.append(best)
        order.remove(best)
        for node in neighborhoods[best]:
            covered[node] = covered.get(node, 0) + 1
    return chosen


class ProceduralCapitalProvider:
    """Build an independent, repeatable F0 network from a complete config snapshot."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        if config is None:
            config = json.loads(
                files("ug_water.network")
                .joinpath("data/procedural_capital_v1.json")
                .read_text(encoding="utf-8")
            )
        # Canonical round-trip both rejects non-JSON values and detaches nested input.
        self._config: dict[str, Any] = json.loads(canonical_json(config))
        if self._config["label"] != "ASSUMPTION":
            raise ValueError("procedural configuration must be labelled ASSUMPTION")

    def build(self, seed: int) -> Network:
        return _Builder(self._config, seed).build()


class _Builder:
    def __init__(self, config: dict[str, Any], seed: int) -> None:
        self.cfg = config
        self.seed = seed
        streams = SeedStreams(seed)
        self.layout = streams.stream("layout")
        self.streets = streams.stream("streets")
        terrain = streams.stream("terrain")
        self.diameters = streams.stream("diameters")
        self.demands = streams.stream("demands")
        self.sensors_rng = streams.stream("sensors")
        self.phases = terrain.uniform(0, math.tau, size=2)
        self.junctions: list[Junction] = []
        self.pipes: list[Pipe] = []
        self.pumps: list[Pump] = []
        self.valves: list[Valve] = []
        self.tanks: list[Tank] = []
        self.nodes: dict[str, Junction | Reservoir | Tank] = {}
        self.inlets: dict[str, str] = {}
        self.flow_inlets: dict[str, str] = {}
        self.discharge_sensors: dict[str, str] = {}
        self.optional: list[tuple[str, str, PipeTier]] = []
        self.prv_zones = self.validate_prv_zones()

    def validate_prv_zones(self) -> list[str]:
        cfg = self.cfg["equipment"]["valves"]
        zones = cfg["prv_zones"]
        if not isinstance(zones, list) or len(zones) != _count(cfg["prv"], "prv"):
            raise ValueError("PRVs require exactly one district zone per PRV")
        known = {d["id"] for d in self.cfg["districts"]}
        for zone in zones:
            if not isinstance(zone, str) or zone not in known:
                raise ValueError(f"PRV zone: unknown district {zone!r}")
            if zone == "government":
                raise ValueError("PRV zone government: government cluster is excluded")
        if len(set(zones)) != len(zones):
            raise ValueError("PRV zones must be distinct districts")
        margin = cfg["prv_min_static_margin_m"]
        if (
            isinstance(margin, bool)
            or not isinstance(margin, int | float)
            or not math.isfinite(margin)
            or margin < 0
        ):
            raise ValueError(
                "PRV minimum static margin must be finite and non-negative"
            )
        return zones

    def elevation(self, x: float, y: float) -> float:
        t = self.cfg["terrain"]
        scale = math.tau / t["wavelength_m"]
        return float(
            t["base_m"]
            + x * t["slope_x"]
            + y * t["slope_y"]
            + t["amplitude_m"]
            * math.sin(x * scale + self.phases[0])
            * math.cos(y * scale + self.phases[1])
        )

    def junction(self, x: float, y: float, demand: float, zone: str) -> Junction:
        node = Junction(
            f"j_{len(self.junctions):04d}", x, y, self.elevation(x, y), demand, zone
        )
        self.junctions.append(node)
        self.nodes[node.id] = node
        return node

    def pipe(self, start: str, end: str, tier: PipeTier) -> Pipe:
        a, b = self.nodes[start], self.nodes[end]
        pipe = Pipe(
            f"p_{len(self.pipes):04d}",
            start,
            end,
            math.hypot(a.x - b.x, a.y - b.y),
            float(self.diameters.choice(self.cfg["diameters_m"][tier])),
            float(self.diameters.choice(list(self.cfg["roughness_c"].values()))),
            tier,
            self.cfg["pipe_minor_loss"],
        )
        self.pipes.append(pipe)
        return pipe

    def districts(self, count: int) -> tuple[Zone, ...]:
        districts = self.cfg["districts"]
        if not 8 <= len(districts) <= 10:
            raise ValueError("districts must contain 8 to 10 demand zones")
        areas = [float(d["area_ha"]) for d in districts]
        if any(a <= 0 or not math.isfinite(a) for a in areas):
            raise ValueError("district areas must be finite and positive")
        quotas = [count * a / math.fsum(areas) for a in areas]
        counts = [math.floor(q) for q in quotas]
        ranking = sorted(
            range(len(counts)), key=lambda i: quotas[i] - counts[i], reverse=True
        )
        for i in ranking[: count - sum(counts)]:
            counts[i] += 1
        for district, n in zip(districts, counts, strict=True):
            self.grid(district, n)
        return tuple(Zone(d["id"], d["name"], d["land_use"]) for d in districts)

    def grid(self, district: dict[str, Any], count: int) -> None:
        if count < 4:
            raise ValueError(
                f"district {district['id']} needs at least four grid nodes"
            )
        width = math.sqrt(district["area_ha"] * 10000 * district["aspect"])
        height = district["area_ha"] * 10000 / width
        cols = max(2, round(math.sqrt(count * district["aspect"])))
        cols = min(cols, count)
        rows = math.ceil(count / cols)
        if rows < 2:
            raise ValueError("district aspect leaves fewer than two grid rows")
        dx, dy = width / (cols - 1), height / (rows - 1)
        jitter = self.cfg["layout"]["center_jitter_m"]
        cx, cy = np.asarray(district["center_m"]) + self.layout.uniform(
            -jitter, jitter, 2
        )
        low, high = self.cfg["demands"]["junction_weight_range"]
        weights = self.demands.uniform(low, high, size=count)
        if np.any(weights <= 0):
            raise ValueError("demand weights must be positive")
        demand = (
            district["area_ha"]
            * self.cfg["demands"]["m3_s_per_ha"][district["land_use"]]
        )
        weight_sum = math.fsum(weights)
        cells: list[Junction] = []
        for i in range(count):
            row, col = divmod(i, cols)
            noise = self.streets.uniform(-1, 1, 2)
            fraction = (
                0
                if district["planned"]
                else self.cfg["streets"]["irregularity_fraction"]
            )
            node = self.junction(
                float(cx - width / 2 + col * dx + noise[0] * dx * fraction),
                float(cy - height / 2 + row * dy + noise[1] * dy * fraction),
                float(demand * weights[i] / weight_sum),
                district["id"],
            )
            cells.append(node)
            # A street spanning tree: all east-west streets and a north-south spine.
            if col:
                tier: PipeTier = "submain" if row == rows // 2 else "distribution"
                self.pipe(cells[i - 1].id, node.id, tier)
            if row:
                if col == 0:
                    self.pipe(cells[i - cols].id, node.id, "submain")
                else:
                    self.optional.append((cells[i - cols].id, node.id, "distribution"))
        self.inlets[district["id"]] = min(
            cells, key=lambda j: math.hypot(j.x - cx, j.y - cy)
        ).id

    def equipment(self) -> Reservoir:
        eq = self.cfg["equipment"]
        sites = tuple(self.junctions)
        high = max(sites, key=lambda j: j.elevation)
        if high.zone in self.prv_zones:
            raise ValueError(f"PRV zone {high.zone}: holds the source site")
        for station in eq["stations"]:
            if station["zone"] in self.prv_zones:
                raise ValueError(
                    f"PRV zone {station['zone']}: holds a source discharge"
                )
        sx = high.x + eq["source"]["offset_m"][0]
        sy = high.y + eq["source"]["offset_m"][1]
        source = Reservoir(
            "source",
            sx,
            sy,
            self.elevation(sx, sy) + eq["source"]["head_above_terrain_m"],
        )
        self.nodes[source.id] = source
        outlets: dict[str, str] = {}
        pc = eq["pump"]
        for station in eq["stations"]:
            discharge = self.junction(
                sx + station["offset_m"][0],
                sy + station["offset_m"][1],
                0,
                station["zone"],
            )
            outlets[station["id"]] = discharge.id
            for role in ("duty", "standby"):
                for index in range(_count(pc[role], f"pump {role}", 1)):
                    pump = Pump(
                        f"{station['id']}_{role}_{index}",
                        source.id,
                        discharge.id,
                        station["id"],
                        role,
                        tuple(tuple(p) for p in pc["curve"]),
                        pc["efficiency"],
                    )
                    self.pumps.append(pump)
                    if role == "duty" and index == 0:
                        self.discharge_sensors[pump.id] = discharge.id
        ring = self.cfg["topology"]["ring"]
        if ring:
            for start, end in zip(ring, ring[1:] + ring[:1], strict=True):
                self.pipe(self.inlets[start], self.inlets[end], "transmission")
        for radial in self.cfg["topology"]["radials"]:
            pipe = self.pipe(
                outlets[radial["station"]], self.inlets[radial["zone"]], "transmission"
            )
            self.flow_inlets[pipe.id] = pipe.end
        tc = eq["tank"]
        for spec in eq["tanks"]:
            site = max(
                (j for j in sites if j.zone in spec["zones"]), key=lambda j: j.elevation
            )
            if site.zone in self.prv_zones:
                raise ValueError(f"PRV zone {site.zone}: holds tank {spec['id']}")
            x, y = site.x + tc["offset_m"][0], site.y + tc["offset_m"][1]
            tank = Tank(
                spec["id"],
                x,
                y,
                self.elevation(x, y)
                + (tc["elevated_height_m"] if spec["elevated"] else 0),
                tc["init_level_m"],
                tc["min_level_m"],
                tc["max_level_m"],
                tc["diameter_m"],
                spec["elevated"],
            )
            self.tanks.append(tank)
            self.nodes[tank.id] = tank
            # The tank connection's tier (`tank.pipe_tier`, default submain): it carries the
            # whole zone while the pumps are off.
            self.pipe(site.id, tank.id, tc.get("pipe_tier", "submain"))
        return source

    def inline_valves(self, street_pipes: list[Pipe], source: Reservoir) -> None:
        cfg = self.cfg["equipment"]["valves"]
        fraction = self.cfg["streets"]["valve_pipe_fraction"]
        if not 0 < fraction < 1:
            raise ValueError(
                "valve_pipe_fraction must lie strictly between zero and one"
            )
        indices = self.streets.permutation(len(street_pipes)).tolist()
        kinds: list[ValveKind] = []
        kinds.extend("isolation" for _ in range(_count(cfg["isolation"], "isolation")))
        kinds.extend("prv" for _ in range(_count(cfg["prv"], "prv")))
        if len(kinds) > len(indices):
            raise ValueError("not enough street pipes for inline valves")
        positions = {p.id: i for i, p in enumerate(self.pipes)}
        prv_index = 0
        for i, kind in zip(indices, kinds, strict=False):
            old = street_pipes[i]
            if kind == "prv":
                zone = self.prv_zones[prv_index]
                prv_index += 1
                # A PRV replaces the end of the district's sole radial inlet main.
                mains = [
                    p
                    for p in self.pipes
                    if p.tier == "transmission"
                    and p.end == self.inlets[zone]
                    and any(p.start == pump.end for pump in self.pumps)
                ]
                if len(mains) != 1:
                    raise ValueError(
                        f"PRV zone {zone}: requires exactly one radial inlet"
                    )
                old = mains[0]
            a, b = self.nodes[old.start], self.nodes[old.end]
            assert isinstance(a, Junction) and isinstance(b, Junction)
            node = self.junction(
                a.x + fraction * (b.x - a.x), a.y + fraction * (b.y - a.y), 0, b.zone
            )
            self.pipes[positions[old.id]] = replace(
                old, end=node.id, length=math.hypot(a.x - node.x, a.y - node.y)
            )
            if kind == "prv":
                # The new split node is upstream, outside the pressure zone.
                node = replace(node, zone=a.zone)
                self.junctions[-1] = node
                self.nodes[node.id] = node
                margin = source.head - b.elevation - cfg["prv_setting_m"]
                if margin < cfg["prv_min_static_margin_m"]:
                    raise ValueError(
                        f"v_{len(self.valves):04d}: static pressure margin {margin:g} m "
                        f"is below prv_min_static_margin_m "
                        f"{cfg['prv_min_static_margin_m']:g} m"
                    )
            setting = (
                cfg["prv_setting_m"] if kind == "prv" else cfg["isolation_setting"]
            )
            self.valves.append(
                Valve(
                    f"v_{len(self.valves):04d}",
                    node.id,
                    old.end,
                    old.diameter,
                    kind,
                    setting,
                )
            )

    def isolate_prv_zones(self, street_pipes: list[Pipe]) -> None:
        """Omit every district boundary pipe except the PRV's upstream main.

        Construct replacements before omission to keep pipe ids unique and retain
        the existing street RNG sequence (including isolation-valve sites).
        """

        def crosses_zone(start: str, end: str) -> bool:
            a, b = self.nodes[start], self.nodes[end]
            return any(
                (isinstance(a, Junction) and a.zone == zone)
                != (isinstance(b, Junction) and b.zone == zone)
                for zone in self.prv_zones
            )

        omitted = {p.id for p in self.pipes if crosses_zone(p.start, p.end)}
        edges = {frozenset((p.start, p.end)) for p in street_pipes}
        # A replacement must not cross a zone boundary, or it would bypass the PRV.
        unused = [
            p
            for p in self.optional
            if frozenset(p[:2]) not in edges and not crosses_zone(p[0], p[1])
        ]
        if len(unused) < len(omitted):
            raise ValueError("pipe target cannot be met within PRV pressure zones")
        for endpoints in unused[: len(omitted)]:
            self.pipe(*endpoints)
        self.pipes = [p for p in self.pipes if p.id not in omitted]

    def sensors(
        self, graph: dict[str, set[str]]
    ) -> tuple[tuple[Sensor, ...], dict[str, tuple[str, ...]]]:
        cfg = self.cfg["sensors"]
        hops = _count(cfg["coverage_hops"], "coverage_hops")
        sets: dict[str, list[str]] = {
            name: [] for name in ("S_sparse", "S_base", "S_dense")
        }
        sensors: list[Sensor] = []
        for kind in ("pressure", "flow", "level"):
            typed_kind: SensorKind = kind
            counts = [_count(cfg[name][kind], f"{name}.{kind}") for name in sets]
            if counts != sorted(counts):
                raise ValueError("sensor counts must satisfy sparse <= base <= dense")
            mandatory: list[str] = []
            if kind == "pressure":
                candidates = {j.id: j.id for j in self.junctions}
            elif kind == "flow":
                candidates = dict(self.flow_inlets)
                # A representative duty-pump discharge at every station comes first.
                mandatory = sorted(self.discharge_sensors)
                if counts[1] < len(mandatory) or counts[2] < len(mandatory):
                    raise ValueError("base/dense flow counts must cover all stations")
            else:
                candidates = {t.id: t.id for t in self.tanks}
            order = mandatory + _coverage_order(
                candidates,
                graph,
                self.sensors_rng,
                hops,
                max(0, counts[2] - len(mandatory)),
            )
            for index, element in enumerate(order):
                sensor = Sensor(f"sensor_{kind}_{index:03d}", typed_kind, element)
                sensors.append(sensor)
                for name, count in zip(sets, counts, strict=True):
                    if index < count:
                        sets[name].append(sensor.id)
        members = {name: tuple(values) for name, values in sets.items()}
        if (
            not set(members["S_sparse"])
            < set(members["S_base"])
            < set(members["S_dense"])
        ):
            raise ValueError("sensor sets must be strict sparse < base < dense subsets")
        return tuple(sensors), members

    def build(self) -> Network:
        eq = self.cfg["equipment"]
        valve_count = sum(_count(eq["valves"][k], k) for k in ("isolation", "prv"))
        grid_count = (
            _count(self.cfg["targets"]["junctions"], "junction target", 1)
            - len(eq["stations"])
            - valve_count
        )
        zones = self.districts(grid_count)
        street_pipes = list(self.pipes)
        source = self.equipment()
        target = _count(self.cfg["targets"]["pipes"], "pipe target", 1)
        needed = target - len(self.pipes)
        if not 0 <= needed <= len(self.optional):
            raise ValueError("pipe target cannot be met by the configured street grid")
        extra_start = len(self.pipes)
        for i in self.streets.permutation(len(self.optional))[:needed]:
            self.pipe(*self.optional[int(i)])
        street_pipes.extend(self.pipes[extra_start:])
        self.inline_valves(street_pipes, source)
        self.isolate_prv_zones(street_pipes)
        graph = _adjacency([*self.pipes, *self.pumps, *self.valves])
        reached = _neighborhood(source.id, graph, len(self.nodes))
        unreachable = sorted(j.id for j in self.junctions if j.id not in reached)
        if unreachable:
            raise ValueError(f"unreachable junctions: {', '.join(unreachable)}")
        sensors, sensor_sets = self.sensors(graph)
        return Network(
            name=self.cfg["version"],
            provenance=NetworkProvenance(
                provider="procedural",
                fidelity="F0",
                seed=self.seed,
                config_hash=sha256_hex(canonical_json(self.cfg)),
                labels={part: "ASSUMPTION" for part in LABELLED_PARTS},
            ),
            zones=zones,
            junctions=tuple(self.junctions),
            reservoirs=(source,),
            tanks=tuple(self.tanks),
            pipes=tuple(self.pipes),
            pumps=tuple(self.pumps),
            valves=tuple(self.valves),
            sensors=sensors,
            sensor_sets=sensor_sets,
            controls=self.level_controls(),
        )

    def level_controls(self) -> tuple[LevelControl, ...]:
        """Duty pumps switched by a tank level (optional `equipment.level_control`: on below and
        off above, metres above the tank bottom; `tank` names one reference tank for every
        station, otherwise each station uses the tank that serves its zone)."""
        eq = self.cfg["equipment"]
        lc = eq.get("level_control")
        if lc is None:
            return ()
        controls = []
        for station in eq["stations"]:
            # One reference tank switches every station ("tank"), or each station's own tank:
            # in a meshed network a station that stops shifts its load onto the others.
            tanks = (
                [lc["tank"]]
                if "tank" in lc
                else [t["id"] for t in eq["tanks"] if station["zone"] in t["zones"]]
            )
            if len(tanks) != 1:
                raise ValueError(
                    f"station {station['id']}: exactly one tank must serve zone "
                    f"{station['zone']} for its level control"
                )
            # `keep_on` duty pumps per station stay on (default none): the tanks then cover
            # part of the peak instead of the whole network while the switched pumps are off.
            duty = [
                p for p in self.pumps if p.station == station["id"] and p.role == "duty"
            ]
            for pump in duty[int(lc.get("keep_on", 0)) :]:
                controls.append(
                    LevelControl(
                        f"ctl_{pump.id}", pump.id, tanks[0],
                        float(lc["on_below_m"]), float(lc["off_above_m"]),
                    )
                )  # fmt: skip
        return tuple(controls)
