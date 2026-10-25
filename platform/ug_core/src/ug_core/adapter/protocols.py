"""The parts a domain adapter hands to the platform (Master Spec section 4.6).

Phase A1 fixes the names and the places where they plug in. Only two parts have members the
Spec already pins down: the solver (`run`, returning truth) and the measurement model (`measure`,
truth in, telemetry out). The other parts are marker protocols: any object passes the type check,
and the milestone that implements them adds the members, which then become checked by the
conformance suite without any change to the adapter interface itself.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ug_core.ports import MeasurementPort
from ug_core.truth import TruthSeries


@runtime_checkable
class AssetModel(Protocol):
    """Topology, assets, sensors and zones of one network (members: milestone M1)."""


@runtime_checkable
class PhysicalSolver(Protocol):
    """Runs a scenario over a horizon and returns truth. Truth never leaves the evaluation side."""

    def run(self, state: Any, scenario: Any, horizon: Any) -> TruthSeries: ...


@runtime_checkable
class MeasurementModel(MeasurementPort, Protocol):
    """Truth to telemetry, with sensor errors and faults. The port is defined in `ug_core.ports`."""


@runtime_checkable
class FaultLibrary(Protocol):
    """Fault types, their parameters and injectors (members: milestone M1)."""


@runtime_checkable
class ExpectationModel(Protocol):
    """Fault-free expected behaviour (members: milestone M3)."""


@runtime_checkable
class Detector(Protocol):
    """A domain detector behind the common detector interface (members: milestone M3)."""


@runtime_checkable
class Localizer(Protocol):
    """Where an incident is, from telemetry only (members: milestone M3)."""


@runtime_checkable
class ImpactModel(Protocol):
    """What-if simulations to physical indicators (members: milestone M4)."""


@runtime_checkable
class ActionSpec(Protocol):
    """One intervention and how to simulate it (members: milestone M4)."""


@runtime_checkable
class CostModelSpec(Protocol):
    """Cost components and their formulas (members: milestone M4)."""


@runtime_checkable
class UiManifest(Protocol):
    """Layers, legends, units and panels the UI should render (members: milestone M2)."""


@runtime_checkable
class ValidationReport(Protocol):
    """The outcome of validating an imported dataset (members: milestones M1 and M5)."""
