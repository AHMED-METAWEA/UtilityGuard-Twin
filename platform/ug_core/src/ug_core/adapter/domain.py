"""The `DomainAdapter` interface, as written in Master Spec section 4.6.

Rules enforced elsewhere: `platform/` never imports `domains/` (`scripts/check_imports.py`);
adapters register through the `ug.domains` entry-point group (`ug_core.registry`); every adapter
passes the conformance suite in `platform/tests/conformance/` before it can be enabled.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ug_core.adapter.protocols import (
    ActionSpec,
    AssetModel,
    CostModelSpec,
    Detector,
    ExpectationModel,
    FaultLibrary,
    ImpactModel,
    Localizer,
    MeasurementModel,
    PhysicalSolver,
    UiManifest,
    ValidationReport,
)

# The methods of the interface, in the order of the Spec. A test compares this tuple with the
# Spec text and with the members of `DomainAdapter`, so the three cannot drift apart.
ADAPTER_METHODS: tuple[str, ...] = (
    "asset_model",
    "solver",
    "measurement_model",
    "fault_library",
    "expectation_model",
    "detectors",
    "localizer",
    "impact_model",
    "action_catalog",
    "cost_model",
    "ui_manifest",
    "validate_dataset",
)


@runtime_checkable
class DomainAdapter(Protocol):
    domain_id: str  # "water" | "electricity" | "cooling"

    def asset_model(self, params: Any) -> AssetModel: ...
    def solver(self) -> PhysicalSolver: ...
    def measurement_model(self) -> MeasurementModel: ...
    def fault_library(self) -> FaultLibrary: ...
    def expectation_model(self) -> ExpectationModel: ...
    def detectors(self) -> list[Detector]: ...
    def localizer(self) -> Localizer | None: ...
    def impact_model(self) -> ImpactModel: ...
    def action_catalog(self) -> list[ActionSpec]: ...
    def cost_model(self) -> CostModelSpec: ...
    def ui_manifest(self) -> UiManifest: ...
    def validate_dataset(self, path: Path) -> ValidationReport: ...
