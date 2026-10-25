"""A starting point for adapters: every method says "not implemented" until it is overridden.

A domain adapter subclasses `AdapterBase`, sets `domain_id`, and overrides one method at a time as
its milestone delivers it. A method that is not overridden raises `NotImplementedError` with a
reason. The conformance suite reads `unimplemented_methods()` and expects exactly that failure for
those methods (strict xfail), and expects real, well-typed data for all others. So a method cannot
quietly return placeholder data while still being listed as unimplemented, and an implemented
method cannot return nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar, NoReturn

from ug_core.adapter.domain import ADAPTER_METHODS
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


class AdapterBase:
    domain_id: ClassVar[str]
    # Why a method is still missing, per method name (shown as the xfail reason).
    unimplemented_reasons: ClassVar[Mapping[str, str]] = {}

    @classmethod
    def unimplemented_methods(cls) -> frozenset[str]:
        """Names of the interface methods this class has not overridden."""
        return frozenset(
            name
            for name in ADAPTER_METHODS
            if getattr(cls, name) is getattr(AdapterBase, name)
        )

    @classmethod
    def unimplemented_reason(cls, name: str) -> str:
        detail = cls.unimplemented_reasons.get(name, "not implemented yet")
        return f"{cls.domain_id}.{name}: {detail}"

    def _unimplemented(self, name: str) -> NoReturn:
        raise NotImplementedError(type(self).unimplemented_reason(name))

    def asset_model(self, params: Any) -> AssetModel:
        self._unimplemented("asset_model")

    def solver(self) -> PhysicalSolver:
        self._unimplemented("solver")

    def measurement_model(self) -> MeasurementModel:
        self._unimplemented("measurement_model")

    def fault_library(self) -> FaultLibrary:
        self._unimplemented("fault_library")

    def expectation_model(self) -> ExpectationModel:
        self._unimplemented("expectation_model")

    def detectors(self) -> list[Detector]:
        self._unimplemented("detectors")

    def localizer(self) -> Localizer | None:
        self._unimplemented("localizer")

    def impact_model(self) -> ImpactModel:
        self._unimplemented("impact_model")

    def action_catalog(self) -> list[ActionSpec]:
        self._unimplemented("action_catalog")

    def cost_model(self) -> CostModelSpec:
        self._unimplemented("cost_model")

    def ui_manifest(self) -> UiManifest:
        self._unimplemented("ui_manifest")

    def validate_dataset(self, path: Path) -> ValidationReport:
        self._unimplemented("validate_dataset")
