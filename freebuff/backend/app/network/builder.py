"""Hypothetical water network built programmatically with WNTR.

This is NOT a replica of a real utility. It is a synthetic 6x6 distribution
grid used to exercise the twin, detector, and cost pipeline. It is deliberately
kept behind `NetworkProvider` so a benchmark network could be plugged in later.

Verified WNTR 1.5 APIs used here (see docs/wntr_api_notes.md for the exact
introspection transcript):
  * WaterNetworkModel.add_{junction,reservoir,tank,pipe,pump,valve,pattern,curve}
  * Junction.emitter_coefficient and results.node['emitter_flow'] for leaks
  * wn.options.hydraulic.demand_model = 'PDD'
  * wn.options.time.{duration,hydraulic_timestep,report_timestep,pattern_timestep}
  * WNTRSimulator(wn).run_sim() -> results.node / results.link DataFrames
"""
from __future__ import annotations

from typing import Protocol

import wntr
from pydantic import BaseModel, ConfigDict
from wntr.network import WaterNetworkModel

from app.config import (
    GRID_COLS,
    GRID_ROWS,
    NETWORK_VERSION,
    SENSOR_IDS,
    SENSOR_NOISE,
)
from app.network.zones import (
    ZONE_NAMES,
    ZONE_PEAK_LPS,
    multiplier_series,
    node_demand_factor,
)

# Layout (metres, x right / y down for direct SVG use).
GRID_X0, GRID_Y0, GRID_DX, GRID_DY = 140.0, 100.0, 110.0, 95.0
RESERVOIR_COORD = (900.0, 690.0)
PUMP_SUCTION_COORD = (790.0, 640.0)
PUMP_DISCHARGE_COORD = (860.0, 640.0)
TANK_COORD = (860.0, 60.0)
PRV_IN_COORD = (800.0, 95.0)

RESERVOIR_HEAD = 8.0
TANK_ELEVATION = 66.0
TANK_INIT_LEVEL = 4.0
TANK_MIN_LEVEL = 1.0
TANK_MAX_LEVEL = 7.5
TANK_DIAMETER = 14.0
PRV_SETTING = 35.0

PUMP_CURVE = [
    (0.0, 66.0), (0.023, 64.5), (0.052, 62.5), (0.080, 59.5), (0.115, 52.0)
]

# Grid edges that are represented by isolation valves instead of pipes.
ISOLATION_EDGES = {
    "PIPE_10": "V01",
    "PIPE_25": "V02",
    "PIPE_45": "V03",
}

ZONE_OF_ROW = {0: "gov", 1: "gov", 2: "com", 3: "com", 4: "res", 5: "res"}


class NodeSpec(BaseModel):
    id: str
    kind: str  # junction | reservoir | tank
    x: float
    y: float
    elevation_m: float
    zone: str | None = None


class LinkSpec(BaseModel):
    id: str
    kind: str  # pipe | pump | valve
    start: str
    end: str
    length_m: float | None = None
    diameter_mm: float | None = None
    valve_type: str | None = None
    setting: float | None = None
    zone: str | None = None


class SensorSpec(BaseModel):
    id: str
    kind: str  # pressure | flow | level
    target: str
    unit: str
    sigma: float
    zone: str | None = None
    x: float
    y: float


class PumpSpec(BaseModel):
    id: str
    role: str
    curve: list[tuple[float, float]]
    initial_status: str


class ZoneSpec(BaseModel):
    id: str
    label: str
    node_ids: list[str]
    peak_demand_lps: float


class NetworkDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_version: str
    nodes: list[NodeSpec]
    links: list[LinkSpec]
    sensors: list[SensorSpec]
    zones: list[ZoneSpec]
    pumps: list[PumpSpec]
    tank: dict
    reservoir: dict
    notes: list[str]


def _junction_id(row: int, col: int) -> str:
    return f"J{row * GRID_COLS + col + 1:02d}"


def _junction_coord(row: int, col: int) -> tuple[float, float]:
    return GRID_X0 + col * GRID_DX, GRID_Y0 + row * GRID_DY


def _junction_elevation(row: int, col: int) -> float:
    return round(2.0 + 0.35 * row + 0.15 * col, 2)


def _grid_edges() -> list[tuple[str, str, str]]:
    """Return (pipe_name, start_junction, end_junction) in deterministic order."""
    edges: list[tuple[str, str, str]] = []
    number = 1
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS - 1):
            edges.append((f"PIPE_{number:02d}", _junction_id(row, col), _junction_id(row, col + 1)))
            number += 1
    for row in range(GRID_ROWS - 1):
        for col in range(GRID_COLS):
            edges.append((f"PIPE_{number:02d}", _junction_id(row, col), _junction_id(row + 1, col)))
            number += 1
    return edges


GRID_EDGES = _grid_edges()
GRID_PIPE_MAX = len(GRID_EDGES)  # 60


class NetworkProvider(Protocol):
    """Extension point: swap in a benchmark .inp network later."""

    version: str

    def build(self) -> WaterNetworkModel: ...

    def describe(self) -> NetworkDescription: ...


class HypotheticalGridProvider:
    version = NETWORK_VERSION

    def build(self) -> WaterNetworkModel:
        wn = WaterNetworkModel()

        # --- options -----------------------------------------------------
        wn.options.time.duration = 0
        wn.options.time.hydraulic_timestep = 300
        wn.options.time.report_timestep = 300
        wn.options.time.pattern_timestep = 300
        wn.options.hydraulic.demand_model = "PDD"
        wn.options.hydraulic.minimum_pressure = 0.0
        wn.options.hydraulic.required_pressure = 20.0
        wn.options.hydraulic.pressure_exponent = 0.5
        wn.options.quality.parameter = "NONE"

        # --- nodes --------------------------------------------------------
        wn.add_reservoir("R1", base_head=RESERVOIR_HEAD, coordinates=RESERVOIR_COORD)
        wn.add_junction("PS_SUC", base_demand=0.0, elevation=1.0,
                        coordinates=PUMP_SUCTION_COORD)
        wn.add_junction("PS_DIS", base_demand=0.0, elevation=1.0,
                        coordinates=PUMP_DISCHARGE_COORD)
        wn.add_tank(
            "TANK1",
            elevation=TANK_ELEVATION,
            init_level=TANK_INIT_LEVEL,
            min_level=TANK_MIN_LEVEL,
            max_level=TANK_MAX_LEVEL,
            diameter=TANK_DIAMETER,
            coordinates=TANK_COORD,
        )
        wn.add_junction("PRV_IN", base_demand=0.0, elevation=TANK_ELEVATION,
                        coordinates=PRV_IN_COORD)

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                node_id = _junction_id(row, col)
                x, y = _junction_coord(row, col)
                zone = ZONE_OF_ROW[row]
                # Base demand is filled in per scenario/chunk by the runner.
                wn.add_junction(
                    node_id,
                    base_demand=0.0,
                    demand_pattern=zone,
                    elevation=_junction_elevation(row, col),
                    coordinates=(x, y),
                )

        # --- links --------------------------------------------------------
        wn.add_pipe("PL_SUC", "R1", "PS_SUC", length=90.0, diameter=0.5,
                    roughness=110.0)
        wn.add_pipe("PL_DIS", "PS_DIS", "TANK1", length=180.0, diameter=0.45,
                    roughness=110.0)
        wn.add_pipe("PL_OUT", "TANK1", "PRV_IN", length=25.0, diameter=0.4,
                    roughness=110.0)

        wn.add_curve("PUMP_CURVE", "HEAD", PUMP_CURVE)
        wn.add_pump("PUMP_1", "PS_SUC", "PS_DIS", pump_type="HEAD",
                    pump_parameter="PUMP_CURVE", initial_status="OPEN")
        wn.add_pump("PUMP_2", "PS_SUC", "PS_DIS", pump_type="HEAD",
                    pump_parameter="PUMP_CURVE", initial_status="CLOSED")

        for name, start, end in GRID_EDGES:
            if name in ISOLATION_EDGES:
                valve_name = ISOLATION_EDGES[name]
                wn.add_valve(
                    valve_name, start, end, diameter=0.15, valve_type="TCV",
                    initial_setting=0.01, minor_loss=0.0, initial_status="ACTIVE",
                )
                continue
            # PIPE_17 is a smaller local distributor: leaks on it create a
            # visible local pressure gradient instead of only a network-wide
            # flow increase. This is a deliberate synthetic design choice.
            diameter = 0.08 if name == "PIPE_17" else 0.15
            wn.add_pipe(name, start, end, length=110.0, diameter=diameter,
                        roughness=110.0)

        wn.add_valve("V_PR", "PRV_IN", "J06", diameter=0.4, valve_type="PRV",
                    initial_setting=PRV_SETTING, minor_loss=0.0,
                    initial_status="ACTIVE")

        # --- zone demand patterns (values replaced by the runner) ----------
        for zone in ZONE_NAMES:
            wn.add_pattern(zone, [1.0] * 2)
        return wn

    def describe(self) -> NetworkDescription:
        nodes: list[NodeSpec] = [
            NodeSpec(id="R1", kind="reservoir", x=RESERVOIR_COORD[0],
                     y=RESERVOIR_COORD[1], elevation_m=RESERVOIR_HEAD)
        ]
        nodes.append(NodeSpec(id="PS_SUC", kind="junction",
                              x=PUMP_SUCTION_COORD[0], y=PUMP_SUCTION_COORD[1],
                              elevation_m=1.0, zone=None))
        nodes.append(NodeSpec(id="PS_DIS", kind="junction",
                              x=PUMP_DISCHARGE_COORD[0], y=PUMP_DISCHARGE_COORD[1],
                              elevation_m=1.0, zone=None))
        nodes.append(NodeSpec(id="PRV_IN", kind="junction", x=PRV_IN_COORD[0],
                              y=PRV_IN_COORD[1], elevation_m=TANK_ELEVATION,
                              zone=None))
        nodes.append(NodeSpec(id="TANK1", kind="tank", x=TANK_COORD[0],
                              y=TANK_COORD[1], elevation_m=TANK_ELEVATION,
                              zone=None))
        zones: dict[str, list[str]] = {z: [] for z in ZONE_NAMES}
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                node_id = _junction_id(row, col)
                x, y = _junction_coord(row, col)
                zone = ZONE_OF_ROW[row]
                nodes.append(NodeSpec(
                    id=node_id, kind="junction", x=x, y=y,
                    elevation_m=_junction_elevation(row, col), zone=zone,
                ))
                zones[zone].append(node_id)

        links: list[LinkSpec] = [
            LinkSpec(id="PL_SUC", kind="pipe", start="R1", end="PS_SUC",
                     length_m=90.0, diameter_mm=500.0),
            LinkSpec(id="PL_DIS", kind="pipe", start="PS_DIS", end="TANK1",
                     length_m=180.0, diameter_mm=450.0),
            LinkSpec(id="PL_OUT", kind="pipe", start="TANK1", end="PRV_IN",
                     length_m=25.0, diameter_mm=400.0),
            LinkSpec(id="PUMP_1", kind="pump", start="PS_SUC", end="PS_DIS"),
            LinkSpec(id="PUMP_2", kind="pump", start="PS_SUC", end="PS_DIS"),
        ]
        for name, start, end in GRID_EDGES:
            if name in ISOLATION_EDGES:
                links.append(LinkSpec(
                    id=ISOLATION_EDGES[name], kind="valve", start=start, end=end,
                    diameter_mm=150.0, valve_type="TCV", setting=0.01,
                    zone=self._zone_of_node(start),
                ))
            else:
                links.append(LinkSpec(
                    id=name, kind="pipe", start=start, end=end, length_m=110.0,
                    diameter_mm=(80.0 if name == "PIPE_17" else 150.0),
                    zone=self._zone_of_node(start),
                ))
        links.append(LinkSpec(id="V_PR", kind="valve", start="PRV_IN", end="J06",
                              diameter_mm=400.0, valve_type="PRV",
                              setting=PRV_SETTING))

        sensors = self._sensor_specs()
        return NetworkDescription(
            network_version=self.version,
            nodes=nodes,
            links=links,
            sensors=sensors,
            zones=[
                ZoneSpec(id=z, label={"gov": "Government district",
                                      "res": "Residential",
                                      "com": "Commercial"}[z],
                         node_ids=zones[z], peak_demand_lps=ZONE_PEAK_LPS[z])
                for z in ZONE_NAMES
            ],
            pumps=[
                PumpSpec(id="PUMP_1", role="duty", curve=PUMP_CURVE,
                         initial_status="OPEN"),
                PumpSpec(id="PUMP_2", role="standby", curve=PUMP_CURVE,
                         initial_status="CLOSED"),
            ],
            tank={
                "id": "TANK1", "elevation_m": TANK_ELEVATION,
                "init_level_m": TANK_INIT_LEVEL, "min_level_m": TANK_MIN_LEVEL,
                "max_level_m": TANK_MAX_LEVEL, "diameter_m": TANK_DIAMETER,
                "riser_valve": "V_PR", "prv_setting_m": PRV_SETTING,
            },
            reservoir={"id": "R1", "base_head_m": RESERVOIR_HEAD},
            notes=[
                "Hypothetical 6x6 grid; no real utility data.",
                "Duty pump runs at a fixed speed; the elevated tank head sets its "
                "operating point (no pump speed control is modelled).",
                "V_PR is a pressure-reducing valve at the tank outlet.",
                "Valves V01-V03 replace three grid pipes and can isolate branches.",
                "Zone demand curves are ASSUMPTIONS, not measured demand.",
            ],
        )

    @staticmethod
    def _zone_of_node(node_id: str) -> str | None:
        if not node_id.startswith("J"):
            return None
        number = int(node_id[1:])
        row = (number - 1) // GRID_COLS
        return ZONE_OF_ROW[row]

    def _sensor_specs(self) -> list[SensorSpec]:
        # Pressure sensor placement (node ids chosen for coverage).
        pressure_nodes = {
            "P01": "J02", "P02": "J05", "P03": "J10", "P04": "J13",
            "P05": "J21", "P06": "J23", "P07": "J27", "P08": "J34",
        }
        specs: list[SensorSpec] = []
        coords = {n.id: (n.x, n.y) for n in self.describe_nodes_only()}
        for sensor_id, node_id in pressure_nodes.items():
            x, y = coords[node_id]
            specs.append(SensorSpec(
                id=sensor_id, kind="pressure", target=node_id, unit="m",
                sigma=SENSOR_NOISE[sensor_id], zone=self._zone_of_node(node_id),
                x=x, y=y,
            ))
        flow_links = {"F01": "PL_DIS", "F02": "V_PR", "F03": "PIPE_34"}
        link_coords = {
            "PL_DIS": (825.0, 350.0), "V_PR": (775.0, 80.0),
            "PIPE_34": (470.0, 148.0),
        }
        for sensor_id, link_id in flow_links.items():
            x, y = link_coords[link_id]
            specs.append(SensorSpec(
                id=sensor_id, kind="flow", target=link_id, unit="L/s",
                sigma=SENSOR_NOISE[sensor_id], zone=None, x=x, y=y,
            ))
        specs.append(SensorSpec(
            id="T01", kind="level", target="TANK1", unit="m",
            sigma=SENSOR_NOISE["T01"], zone=None,
            x=TANK_COORD[0] + 26, y=TANK_COORD[1] + 18,
        ))
        assert tuple(s.id for s in specs) == SENSOR_IDS
        return specs

    def describe_nodes_only(self) -> list[NodeSpec]:
        """Small helper used for sensor coordinates (avoids recursive describe)."""
        nodes = [NodeSpec(id="R1", kind="reservoir", x=RESERVOIR_COORD[0],
                          y=RESERVOIR_COORD[1], elevation_m=RESERVOIR_HEAD)]
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                x, y = _junction_coord(row, col)
                nodes.append(NodeSpec(
                    id=_junction_id(row, col), kind="junction", x=x, y=y,
                    elevation_m=_junction_elevation(row, col),
                    zone=ZONE_OF_ROW[row],
                ))
        return nodes

    def demand_base_demands(self) -> dict[str, float]:
        """Per-junction base demand in m3/s (peak-zone allocation)."""
        result: dict[str, float] = {}
        counts = {z: 0 for z in ZONE_NAMES}
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                counts[ZONE_OF_ROW[row]] += 1
        index = 0
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                zone = ZONE_OF_ROW[row]
                peak_lps = ZONE_PEAK_LPS[zone] / counts[zone]
                result[_junction_id(row, col)] = (
                    peak_lps * node_demand_factor(index) / 1000.0
                )
                index += 1
        return result


def zone_patterns(
    ticks: int,
    timestep_minutes: int,
    start_hour: float,
    holiday: bool,
    heatwave: float,
    zone_multipliers: dict[str, float],
) -> dict[str, list[float]]:
    return {
        zone: multiplier_series(
            zone, ticks, timestep_minutes, start_hour, holiday, heatwave,
            zone_multipliers.get(zone, 1.0),
        )
        for zone in ZONE_NAMES
    }


DEFAULT_PROVIDER: NetworkProvider = HypotheticalGridProvider()
