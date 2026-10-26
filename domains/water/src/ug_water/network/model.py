"""The water network as data: what every network provider produces and the solver consumes.

A provider (`ProceduralCapitalProvider` for F0, `OsmCapitalProvider` for F1, later files from
ACUD) builds a `Network`; the hydraulic engine turns it into a WNTR model. Nothing here imports
WNTR: the network is plain, frozen, validated data that hashes the same on every machine.

Units are SI throughout: coordinates, lengths, elevations, levels and heads in metres, diameters in
metres, demand in m3/s, pump curves as (flow m3/s, head m) points, Hazen-Williams roughness as the
dimensionless C factor. Coordinates are local Cartesian metres (x east, y north) about the
provider's reference point; a georeferenced provider records that point in its provenance.

Honesty: every network says where its parts come from. `NetworkProvenance.labels` names the
evidence label of each part (`coordinates`, `topology`, `diameters`, `demands`, `equipment`,
`zones`); the Fidelity badge shows F1 only when the street geometry is `PUBLIC_GEOMETRY` from
OpenStreetMap and the district boundaries are a hand-drawn `ASSUMPTION` (owner decisions G1 to
G3). A network that cannot meet its own rules does not construct: `ValueError` names the rule.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from ug_core import grammar
from ug_core.canonical import canonical_json, freeze, sha256_hex, thaw

NETWORK_SCHEMA_VERSION = "1"

PipeTier = Literal["transmission", "submain", "distribution"]
PumpRole = Literal["duty", "standby"]
ValveKind = Literal["isolation", "prv"]
SensorKind = Literal["pressure", "flow", "level"]
Fidelity = Literal["F0", "F1"]

PIPE_TIERS: frozenset[str] = frozenset({"transmission", "submain", "distribution"})
PUMP_ROLES: frozenset[str] = frozenset({"duty", "standby"})
VALVE_KINDS: frozenset[str] = frozenset({"isolation", "prv"})
SENSOR_KINDS: frozenset[str] = frozenset({"pressure", "flow", "level"})
FIDELITIES: frozenset[str] = frozenset({"F0", "F1"})
# The parts of a network that carry an evidence label, and the labels each part may carry.
LABELLED_PARTS: dict[str, frozenset[str]] = {
    "coordinates": frozenset({"PUBLIC_GEOMETRY", "ASSUMPTION"}),
    "topology": frozenset({"PUBLIC_GEOMETRY", "ASSUMPTION"}),
    "zones": frozenset({"PUBLIC_GEOMETRY", "ASSUMPTION"}),
    "diameters": frozenset({"ASSUMPTION"}),
    "demands": frozenset({"ASSUMPTION"}),
    "equipment": frozenset({"ASSUMPTION"}),
}


def _identifier(value: object, what: str) -> str:
    return grammar.require_identifier(value, what)


def _number(
    value: object, what: str, *, minimum: float | None = None, positive: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{what} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{what} must be finite, got {value!r}")
    if positive and number <= 0:
        raise ValueError(f"{what} must be positive, got {value!r}")
    if minimum is not None and number < minimum:
        raise ValueError(f"{what} must be at least {minimum}, got {value!r}")
    return number


def _choice(value: object, allowed: frozenset[str], what: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{what} must be one of {sorted(allowed)}, got {value!r}")
    return value


@dataclass(frozen=True)
class Zone:
    """A demand zone, named after a capital district (Master Spec 5.1)."""

    id: str
    name: str
    land_use: str

    def __post_init__(self) -> None:
        _identifier(self.id, "zone id")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"zone {self.id}: name must be non-blank text")
        _identifier(self.land_use, f"zone {self.id}: land use")


@dataclass(frozen=True)
class Junction:
    id: str
    x: float
    y: float
    elevation: float
    base_demand: float
    zone: str

    def __post_init__(self) -> None:
        _identifier(self.id, "junction id")
        for name in ("x", "y", "elevation"):
            object.__setattr__(
                self, name, _number(getattr(self, name), f"junction {self.id}: {name}")
            )
        object.__setattr__(
            self,
            "base_demand",
            _number(self.base_demand, f"junction {self.id}: base_demand", minimum=0.0),
        )
        _identifier(self.zone, f"junction {self.id}: zone")


@dataclass(frozen=True)
class Reservoir:
    """The abstract source and treatment plant (Master Spec 5.1)."""

    id: str
    x: float
    y: float
    head: float

    def __post_init__(self) -> None:
        _identifier(self.id, "reservoir id")
        for name in ("x", "y", "head"):
            object.__setattr__(
                self, name, _number(getattr(self, name), f"reservoir {self.id}: {name}")
            )


@dataclass(frozen=True)
class Tank:
    id: str
    x: float
    y: float
    elevation: float
    init_level: float
    min_level: float
    max_level: float
    diameter: float
    elevated: bool = False

    def __post_init__(self) -> None:
        _identifier(self.id, "tank id")
        for name in ("x", "y", "elevation"):
            object.__setattr__(
                self, name, _number(getattr(self, name), f"tank {self.id}: {name}")
            )
        for name in ("init_level", "min_level", "max_level"):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), f"tank {self.id}: {name}", minimum=0.0),
            )
        object.__setattr__(
            self,
            "diameter",
            _number(self.diameter, f"tank {self.id}: diameter", positive=True),
        )
        if not isinstance(self.elevated, bool):
            raise ValueError(f"tank {self.id}: elevated must be true or false")
        if not self.min_level <= self.init_level <= self.max_level:
            raise ValueError(
                f"tank {self.id}: needs min_level <= init_level <= max_level, got "
                f"{self.min_level}, {self.init_level}, {self.max_level}"
            )
        if self.min_level == self.max_level:
            raise ValueError(f"tank {self.id}: min_level and max_level must differ")


@dataclass(frozen=True)
class Pipe:
    id: str
    start: str
    end: str
    length: float
    diameter: float
    roughness: float
    tier: PipeTier
    minor_loss: float = 0.0

    def __post_init__(self) -> None:
        _identifier(self.id, "pipe id")
        _identifier(self.start, f"pipe {self.id}: start")
        _identifier(self.end, f"pipe {self.id}: end")
        if self.start == self.end:
            raise ValueError(
                f"pipe {self.id}: start and end are the same node {self.start!r}"
            )
        for name in ("length", "diameter", "roughness"):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), f"pipe {self.id}: {name}", positive=True),
            )
        object.__setattr__(
            self,
            "minor_loss",
            _number(self.minor_loss, f"pipe {self.id}: minor_loss", minimum=0.0),
        )
        _choice(self.tier, PIPE_TIERS, f"pipe {self.id}: tier")


@dataclass(frozen=True)
class Pump:
    """A pump with a head curve of (flow m3/s, head m) points, decreasing head with flow."""

    id: str
    start: str
    end: str
    station: str
    role: PumpRole
    curve: tuple[tuple[float, float], ...]
    efficiency: float

    def __post_init__(self) -> None:
        _identifier(self.id, "pump id")
        _identifier(self.start, f"pump {self.id}: start")
        _identifier(self.end, f"pump {self.id}: end")
        _identifier(self.station, f"pump {self.id}: station")
        _choice(self.role, PUMP_ROLES, f"pump {self.id}: role")
        points = tuple(
            (
                _number(q, f"pump {self.id}: curve flow", minimum=0.0),
                _number(h, f"pump {self.id}: curve head", positive=True),
            )
            for q, h in self.curve
        )
        if not points:
            raise ValueError(f"pump {self.id}: needs at least one curve point")
        flows = [q for q, _ in points]
        heads = [h for _, h in points]
        if flows != sorted(set(flows)):
            raise ValueError(f"pump {self.id}: curve flows must be strictly increasing")
        if any(b >= a for a, b in zip(heads, heads[1:], strict=False)):
            raise ValueError(f"pump {self.id}: curve head must fall as flow rises")
        object.__setattr__(self, "curve", points)
        efficiency = _number(
            self.efficiency, f"pump {self.id}: efficiency", positive=True
        )
        if efficiency > 1:
            raise ValueError(
                f"pump {self.id}: efficiency is a fraction, got {efficiency}"
            )
        object.__setattr__(self, "efficiency", efficiency)


@dataclass(frozen=True)
class Valve:
    id: str
    start: str
    end: str
    diameter: float
    kind: ValveKind
    setting: float = 0.0

    def __post_init__(self) -> None:
        _identifier(self.id, "valve id")
        _identifier(self.start, f"valve {self.id}: start")
        _identifier(self.end, f"valve {self.id}: end")
        object.__setattr__(
            self,
            "diameter",
            _number(self.diameter, f"valve {self.id}: diameter", positive=True),
        )
        _choice(self.kind, VALVE_KINDS, f"valve {self.id}: kind")
        object.__setattr__(
            self,
            "setting",
            _number(self.setting, f"valve {self.id}: setting", minimum=0.0),
        )
        if self.kind == "prv" and self.setting <= 0:
            raise ValueError(
                f"valve {self.id}: a pressure-reducing valve needs a positive setting"
            )


@dataclass(frozen=True)
class Sensor:
    """A sensor site on a network element; what it measures arrives with the measurement model (B2)."""

    id: str
    kind: SensorKind
    element: str

    def __post_init__(self) -> None:
        _identifier(self.id, "sensor id")
        _choice(self.kind, SENSOR_KINDS, f"sensor {self.id}: kind")
        _identifier(self.element, f"sensor {self.id}: element")


@dataclass(frozen=True)
class NetworkProvenance:
    """Where the network comes from, and the evidence label of each of its parts."""

    provider: str
    fidelity: Fidelity
    seed: int
    config_hash: str
    labels: Mapping[str, str]
    geometry: Mapping[str, Any] | None = None
    district_boundaries: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _identifier(self.provider, "provider")
        _choice(self.fidelity, FIDELITIES, "fidelity")
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or self.seed < 0
        ):
            raise ValueError(f"seed must be a non-negative integer, got {self.seed!r}")
        if not grammar.is_sha256(self.config_hash):
            raise ValueError("config_hash must be a lower-case SHA-256")
        labels = dict(self.labels)
        if set(labels) != set(LABELLED_PARTS):
            raise ValueError(
                f"labels must name exactly {sorted(LABELLED_PARTS)}, got {sorted(labels)}"
            )
        for part, label in labels.items():
            if label not in LABELLED_PARTS[part]:
                raise ValueError(
                    f"label of {part} must be one of {sorted(LABELLED_PARTS[part])}, got {label!r}"
                )
        object.__setattr__(self, "labels", freeze(labels))
        if self.fidelity == "F0":
            if any(label == "PUBLIC_GEOMETRY" for label in labels.values()):
                raise ValueError(
                    "an F0 network is synthetic: no part may be PUBLIC_GEOMETRY"
                )
            if self.geometry is not None or self.district_boundaries is not None:
                raise ValueError(
                    "an F0 network has no public geometry or district overlay"
                )
        else:
            self._check_f1(labels)
        if self.geometry is not None:
            object.__setattr__(self, "geometry", freeze(dict(self.geometry)))
        if self.district_boundaries is not None:
            object.__setattr__(
                self, "district_boundaries", freeze(dict(self.district_boundaries))
            )

    def _check_f1(self, labels: dict[str, str]) -> None:
        """F1 is the hybrid of decisions G1 to G3: OSM street geometry, hand-drawn districts."""
        geometry = dict(self.geometry or {})
        required = (
            "label",
            "source",
            "licence",
            "retrieved",
            "coverage_report",
            "osm_base",
            "extract_sha256",
        )
        missing = [key for key in required if not geometry.get(key)]
        if missing:
            raise ValueError(
                f"an F1 network needs street geometry provenance; missing {missing}"
            )
        if (
            geometry["label"] != "PUBLIC_GEOMETRY"
            or geometry["source"] != "OpenStreetMap"
        ):
            raise ValueError(
                "F1 street geometry must be PUBLIC_GEOMETRY from OpenStreetMap"
            )
        if geometry["licence"] != "ODbL-1.0":
            raise ValueError("OpenStreetMap geometry is licensed ODbL-1.0")
        if not grammar.is_sha256(geometry["extract_sha256"]):
            raise ValueError("extract_sha256 must be a lower-case SHA-256")
        districts = dict(self.district_boundaries or {})
        if (
            districts.get("label") != "ASSUMPTION"
            or districts.get("method") != "hand-drawn"
        ):
            raise ValueError(
                "F1 district boundaries must be declared as hand-drawn ASSUMPTION"
            )
        if not districts.get("source") or not districts.get("drawn"):
            raise ValueError("F1 district boundaries need a source and a date")
        if (
            labels["coordinates"] != "PUBLIC_GEOMETRY"
            or labels["zones"] != "ASSUMPTION"
        ):
            raise ValueError(
                "an F1 network has PUBLIC_GEOMETRY coordinates and ASSUMPTION zones"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "fidelity": self.fidelity,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "labels": thaw(self.labels),
            "geometry": thaw(self.geometry) if self.geometry is not None else None,
            "district_boundaries": thaw(self.district_boundaries)
            if self.district_boundaries is not None
            else None,
        }


@dataclass(frozen=True)
class Network:
    """A complete network. Elements are stored sorted by id, so equal networks hash equal."""

    name: str
    provenance: NetworkProvenance
    zones: tuple[Zone, ...]
    junctions: tuple[Junction, ...]
    reservoirs: tuple[Reservoir, ...]
    tanks: tuple[Tank, ...]
    pipes: tuple[Pipe, ...]
    pumps: tuple[Pump, ...] = ()
    valves: tuple[Valve, ...] = ()
    sensors: tuple[Sensor, ...] = ()
    sensor_sets: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _identifier(self.name, "network name")
        if not isinstance(self.provenance, NetworkProvenance):
            raise ValueError("provenance must be a NetworkProvenance")
        for name in (
            "zones",
            "junctions",
            "reservoirs",
            "tanks",
            "pipes",
            "pumps",
            "valves",
            "sensors",
        ):
            items = tuple(sorted(getattr(self, name), key=lambda item: item.id))
            object.__setattr__(self, name, items)
        sets = {str(k): tuple(sorted(v)) for k, v in dict(self.sensor_sets).items()}
        object.__setattr__(self, "sensor_sets", freeze(sets))
        self._check_references()

    def _check_references(self) -> None:
        node_items: list[Junction | Reservoir | Tank] = [
            *self.junctions,
            *self.reservoirs,
            *self.tanks,
        ]
        links: list[Pipe | Pump | Valve] = [*self.pipes, *self.pumps, *self.valves]
        node_ids = [n.id for n in node_items]
        link_ids = [link.id for link in links]
        for kind, ids in (
            ("node", node_ids),
            ("link", link_ids),
            ("zone", [z.id for z in self.zones]),
            ("sensor", [s.id for s in self.sensors]),
        ):
            duplicates = sorted(i for i, n in Counter(ids).items() if n > 1)
            if duplicates:
                raise ValueError(f"{kind} ids must be unique, repeated: {duplicates}")
        overlap = sorted(set(node_ids) & set(link_ids))
        if overlap:
            raise ValueError(f"a node and a link share an id: {overlap}")
        if not self.junctions:
            raise ValueError("a network needs at least one junction")
        if not self.reservoirs and not self.tanks:
            raise ValueError("a network needs a source: a reservoir or a tank")
        nodes = set(node_ids)
        for link in links:
            for end in (link.start, link.end):
                if end not in nodes:
                    raise ValueError(f"link {link.id} refers to unknown node {end!r}")
        zones = {z.id for z in self.zones}
        for junction in self.junctions:
            if junction.zone not in zones:
                raise ValueError(
                    f"junction {junction.id} refers to unknown zone {junction.zone!r}"
                )
        elements = nodes | set(link_ids)
        for sensor in self.sensors:
            if sensor.element not in elements:
                raise ValueError(
                    f"sensor {sensor.id} is on unknown element {sensor.element!r}"
                )
        sensor_ids = {s.id for s in self.sensors}
        for set_name, members in self.sensor_sets.items():
            _identifier(set_name, "sensor set name")
            unknown = sorted(set(members) - sensor_ids)
            if unknown:
                raise ValueError(
                    f"sensor set {set_name} names unknown sensors {unknown}"
                )

    def to_dict(self) -> dict[str, Any]:
        def rows(items: tuple[Any, ...]) -> list[dict[str, Any]]:
            out = []
            for item in items:
                row = {name: getattr(item, name) for name in item.__dataclass_fields__}
                if "curve" in row:
                    row["curve"] = [list(point) for point in row["curve"]]
                out.append(row)
            return out

        return {
            "schema_version": NETWORK_SCHEMA_VERSION,
            "name": self.name,
            "provenance": self.provenance.to_dict(),
            "zones": rows(self.zones),
            "junctions": rows(self.junctions),
            "reservoirs": rows(self.reservoirs),
            "tanks": rows(self.tanks),
            "pipes": rows(self.pipes),
            "pumps": rows(self.pumps),
            "valves": rows(self.valves),
            "sensors": rows(self.sensors),
            "sensor_sets": {k: list(v) for k, v in sorted(self.sensor_sets.items())},
        }

    def content_hash(self) -> str:
        """SHA-256 of the canonical content: the same network gives the same hash everywhere."""
        return sha256_hex(canonical_json(self.to_dict()))

    def total_base_demand(self) -> float:
        return math.fsum(j.base_demand for j in self.junctions)
