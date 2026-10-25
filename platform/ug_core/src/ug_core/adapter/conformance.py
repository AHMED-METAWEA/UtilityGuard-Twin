"""Checks every domain adapter must pass (the logic behind `platform/tests/conformance/`).

Kept free of pytest so the same checks can run from `ug doctor` or a domain's own tests.

The contract for each interface method:
- Declared unimplemented (`unimplemented_methods()`): calling it raises `NotImplementedError`.
  The test suite reports this as a strict expected failure with the adapter's reason. If such a
  method returns data instead, that test passes by accident, strict mode turns it into a failure,
  and the declaration has to be corrected.
- Anything else: calling it returns a value of the declared type. `None` is never accepted,
  except from `localizer`, which the Spec allows to be `None`; neither is a bare built-in value
  or `object()`, which can only be a placeholder.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ug_core.adapter.domain import ADAPTER_METHODS, DomainAdapter
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

DOMAIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

_ARGUMENTS: dict[str, tuple[Any, ...]] = {
    "asset_model": ({},),
    # A path that does not exist: a conforming adapter returns a report that says so.
    "validate_dataset": (Path("conformance-missing-dataset"),),
}
_SINGLE: dict[str, type] = {
    "asset_model": AssetModel,
    "solver": PhysicalSolver,
    "measurement_model": MeasurementModel,
    "fault_library": FaultLibrary,
    "expectation_model": ExpectationModel,
    "impact_model": ImpactModel,
    "cost_model": CostModelSpec,
    "ui_manifest": UiManifest,
    "validate_dataset": ValidationReport,
}
_LISTS: dict[str, type] = {"detectors": Detector, "action_catalog": ActionSpec}
_OPTIONAL: dict[str, type] = {"localizer": Localizer}


# Marker protocols accept any object, so a bare built-in value or `object()` is never accepted as a
# component: it can only be a placeholder.
_PLACEHOLDER_TYPES = (
    object,
    bool,
    int,
    float,
    str,
    bytes,
    dict,
    list,
    tuple,
    set,
    frozenset,
)


def _is_placeholder(value: object) -> bool:
    return type(value) in _PLACEHOLDER_TYPES


class ConformanceError(AssertionError):
    """An adapter does not meet the interface."""


def identity_problems(adapter: object) -> list[str]:
    """Problems with the adapter's identity; empty means it is a usable `DomainAdapter`."""
    problems: list[str] = []
    domain_id = getattr(adapter, "domain_id", None)
    if not isinstance(domain_id, str) or not DOMAIN_ID_PATTERN.match(domain_id):
        problems.append(
            f"domain_id must be a lower-case identifier (letters, digits, '_'), got {domain_id!r}"
        )
    if not isinstance(adapter, DomainAdapter):
        missing = [
            name
            for name in ADAPTER_METHODS
            if not callable(getattr(adapter, name, None))
        ]
        problems.append(f"does not implement DomainAdapter; missing methods: {missing}")
    return problems


def unimplemented_methods(adapter: object) -> frozenset[str]:
    """Methods the adapter declares as not implemented (none, for a plain adapter)."""
    getter = getattr(adapter, "unimplemented_methods", None)
    return frozenset(getter()) if callable(getter) else frozenset()


def unimplemented_reason(adapter: object, name: str) -> str:
    getter = getattr(adapter, "unimplemented_reason", None)
    if callable(getter):
        return str(getter(name))
    return f"{getattr(adapter, 'domain_id', '?')}.{name}: declared unimplemented"


def check_method(adapter: object, name: str) -> None:
    """Call `adapter.<name>` and check the result. `NotImplementedError` is not caught here."""
    if name not in ADAPTER_METHODS:
        raise ConformanceError(f"{name!r} is not a DomainAdapter method")
    result = getattr(adapter, name)(*_ARGUMENTS.get(name, ()))
    label = f"{getattr(adapter, 'domain_id', '?')}.{name}()"
    if name in _OPTIONAL:
        expected = _OPTIONAL[name]
        if result is not None and (
            _is_placeholder(result) or not isinstance(result, expected)
        ):
            raise ConformanceError(f"{label} must return {expected.__name__} or None")
    elif name in _LISTS:
        if not isinstance(result, list):
            raise ConformanceError(
                f"{label} must return a list, got {type(result).__name__}"
            )
        expected = _LISTS[name]
        if any(_is_placeholder(i) or not isinstance(i, expected) for i in result):
            raise ConformanceError(
                f"{label} returned items that are not {expected.__name__}"
            )
    else:
        expected = _SINGLE[name]
        if (
            result is None
            or _is_placeholder(result)
            or not isinstance(result, expected)
        ):
            raise ConformanceError(
                f"{label} must return {expected.__name__}, got {type(result).__name__}"
            )
