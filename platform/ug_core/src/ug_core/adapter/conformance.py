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

import inspect
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


# Members the platform will call on a component, and how many positional arguments it passes.
_REQUIRED_CALLS: dict[type, dict[str, int]] = {
    PhysicalSolver: {"run": 3},  # run(state, scenario, horizon)
    MeasurementModel: {"measure": 2},  # measure(truth, seeds)
}


def _check_calls(label: str, result: object, expected: type) -> None:
    """A runtime protocol check only proves the name exists; check it can be called."""
    for member, argument_count in _REQUIRED_CALLS.get(expected, {}).items():
        attribute = getattr(result, member)
        if not callable(attribute):
            raise ConformanceError(f"{label}: {member} must be callable")
        try:
            inspect.signature(attribute, follow_wrapped=False).bind(
                *([None] * argument_count)
            )
        except TypeError:
            raise ConformanceError(
                f"{label}: {member}() must accept {argument_count} positional arguments"
            ) from None
        except ValueError:
            raise ConformanceError(
                f"{label}: the signature of {member} cannot be inspected"
            ) from None


def _validate(label: str, name: str, result: object) -> None:
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
        _check_calls(label, result, expected)


def check_method(adapter: object, name: str) -> None:
    """Call `adapter.<name>` and check the result.

    A `NotImplementedError` raised by the call itself propagates: that is how an unimplemented
    method answers, and the suite expects it for declared-unimplemented methods. Anything the
    checking itself raises, `NotImplementedError` included, is a `ConformanceError`, so a result
    object cannot turn a failed check into an expected failure.
    """
    if name not in ADAPTER_METHODS:
        raise ConformanceError(f"{name!r} is not a DomainAdapter method")
    result = getattr(adapter, name)(*_ARGUMENTS.get(name, ()))
    domain = getattr(adapter, "domain_id", None)
    label = f"{domain if isinstance(domain, str) else '?'}.{name}()"
    try:
        _validate(label, name, result)
    except ConformanceError:
        raise
    except Exception as exc:
        # Only the exception's class name is used: describing it with str() could run code of
        # the object being checked. The original exception stays attached as the cause.
        raise ConformanceError(
            f"{label} raised {type(exc).__name__} while the result was being checked"
        ) from exc
