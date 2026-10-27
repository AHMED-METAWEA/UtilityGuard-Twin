"""Small synthetic networks for validation; no runtime data or network access."""

from dataclasses import replace

from ug_water.network.model import (
    LABELLED_PARTS,
    Junction,
    Network,
    NetworkProvenance,
    Pipe,
    Reservoir,
    Tank,
    Zone,
)


def line(head: float = 40, diameter: float = 0.5) -> Network:
    return Network(
        name="validation_line",
        provenance=NetworkProvenance(
            "test",
            "F0",
            0,
            "0" * 64,
            {part: "ASSUMPTION" for part in LABELLED_PARTS},
        ),
        zones=(Zone("z1", "Test", "residential"),),
        junctions=(Junction("j1", 1, 0, 0, 0.01, "z1"),),
        reservoirs=(Reservoir("r1", 0, 0, head),),
        tanks=(),
        pipes=(Pipe("p1", "r1", "j1", 1, diameter, 140, "transmission"),),
    )


def with_tank(level: float) -> Network:
    network = line(40)
    return replace(
        network,
        tanks=(Tank("t1", 1, 1, 35, level, 0, 10, 100),),
        pipes=(*network.pipes, Pipe("pt", "j1", "t1", 100, 0.1, 140, "submain")),
    )
