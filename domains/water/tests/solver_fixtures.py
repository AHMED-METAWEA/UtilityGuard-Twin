"""Small hand-checkable networks and a demand series for the solver tests (no OSM data)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from ug_core.timebase import Timebase
from ug_water.network.model import (
    LABELLED_PARTS,
    Junction,
    Network,
    NetworkProvenance,
    Pipe,
    Pump,
    Reservoir,
    Tank,
    Zone,
)

START = datetime(2027, 3, 4, 22, tzinfo=UTC)
STEP = 300


def provenance() -> NetworkProvenance:
    return NetworkProvenance(
        provider="test",
        fidelity="F0",
        seed=0,
        config_hash="0" * 64,
        labels={part: "ASSUMPTION" for part in LABELLED_PARTS},
    )


def line(head: float, demand: float = 0.01) -> Network:
    """A reservoir feeding one junction through a short wide pipe: pressure ~ head."""
    return Network(
        name="line",
        provenance=provenance(),
        zones=(Zone("z1", "Test zone", "residential"),),
        junctions=(Junction("j1", 100.0, 0.0, 0.0, demand, "z1"),),
        reservoirs=(Reservoir("r1", 0.0, 0.0, head),),
        tanks=(),
        pipes=(Pipe("p1", "r1", "j1", 100.0, 0.5, 140.0, "transmission"),),
    )


def pumped_loop() -> Network:
    """A source pumped into a three-junction loop with a ground tank."""
    return Network(
        name="loop",
        provenance=provenance(),
        zones=(Zone("z1", "Test zone", "residential"),),
        junctions=(
            Junction("j1", 0.0, 0.0, 5.0, 0.004, "z1"),
            Junction("j2", 400.0, 0.0, 8.0, 0.006, "z1"),
            Junction("j3", 200.0, 300.0, 10.0, 0.005, "z1"),
            Junction("j0", -50.0, 0.0, 0.0, 0.0, "z1"),
        ),
        reservoirs=(Reservoir("r1", -100.0, 0.0, 10.0),),
        tanks=(Tank("t1", 200.0, 400.0, 30.0, 3.0, 0.5, 6.0, 12.0),),
        pipes=(
            Pipe("p0", "r1", "j0", 50.0, 0.3, 130.0, "transmission"),
            Pipe("p1", "j1", "j2", 400.0, 0.2, 130.0, "submain"),
            Pipe("p2", "j2", "j3", 360.0, 0.15, 120.0, "distribution"),
            Pipe("p3", "j3", "j1", 360.0, 0.15, 120.0, "distribution"),
            Pipe("p4", "j3", "t1", 100.0, 0.2, 130.0, "submain"),
        ),
        pumps=(
            Pump(
                "pu1",
                "j0",
                "j1",
                "s1",
                "duty",
                ((0.0, 45.0), (0.02, 40.0), (0.04, 28.0)),
                0.75,
            ),
            Pump(
                "pu2",
                "j0",
                "j1",
                "s1",
                "standby",
                ((0.0, 45.0), (0.02, 40.0), (0.04, 28.0)),
                0.75,
            ),
        ),
    )


@dataclass(frozen=True)
class SeriesDemand:
    """A demand series of the shape the engine reads (the demand model's `DemandSeries` is one)."""

    timebase: Timebase
    junction_ids: tuple[str, ...]
    values: np.ndarray


def demand(
    network: Network, ticks: int, multipliers: list[float] | None = None
) -> SeriesDemand:
    """Every junction's base demand times one multiplier per tick (1.0 when not given)."""
    ids = tuple(sorted(j.id for j in network.junctions))
    base = np.array(
        [next(j.base_demand for j in network.junctions if j.id == i) for i in ids]
    )
    factor = (
        np.ones(ticks) if multipliers is None else np.asarray(multipliers, dtype=float)
    )
    return SeriesDemand(Timebase(START, STEP, ticks), ids, np.outer(factor, base))
