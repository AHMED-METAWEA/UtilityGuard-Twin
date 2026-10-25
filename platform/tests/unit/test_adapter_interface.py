"""The DomainAdapter interface: it matches the Spec, and the base class and checks behave."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, get_type_hints

import pytest
from ug_core.adapter import ADAPTER_METHODS, AdapterBase, DomainAdapter, HealthCheck
from ug_core.adapter.conformance import (
    ConformanceError,
    check_method,
    identity_problems,
    unimplemented_methods,
)
from ug_core.adapter.protocols import PhysicalSolver

REPO = Path(__file__).resolve().parents[3]


def spec_methods() -> list[str]:
    text = (REPO / "docs" / "UtilityGuard_Master_Spec.md").read_text(encoding="utf-8")
    block = text.split("class DomainAdapter(Protocol):", 1)[1].split("```", 1)[0]
    return re.findall(r"^\s+def (\w+)\(", block, flags=re.MULTILINE)


def test_method_list_matches_the_master_spec() -> None:
    assert list(ADAPTER_METHODS) == spec_methods()


def test_method_list_matches_the_protocol_members() -> None:
    members = {
        name
        for name in vars(DomainAdapter)
        if not name.startswith("_") and callable(vars(DomainAdapter)[name])
    }
    assert members == set(ADAPTER_METHODS)
    assert "domain_id" in get_type_hints(DomainAdapter)


class Minimal(AdapterBase):
    domain_id = "minimal"


def test_every_method_of_a_fresh_adapter_is_unimplemented_with_a_reason() -> None:
    adapter = Minimal()
    assert unimplemented_methods(adapter) == set(ADAPTER_METHODS)
    for name in ADAPTER_METHODS:
        args: tuple[Any, ...] = ({},) if name == "asset_model" else ()
        if name == "validate_dataset":
            args = (Path("x"),)
        with pytest.raises(NotImplementedError, match=rf"minimal\.{name}: "):
            getattr(adapter, name)(*args)


def test_overriding_a_method_removes_it_from_the_unimplemented_set() -> None:
    class Partial(AdapterBase):
        domain_id = "partial"

        def localizer(self) -> None:
            return None

    assert Partial.unimplemented_methods() == set(ADAPTER_METHODS) - {"localizer"}
    check_method(Partial(), "localizer")


def test_a_reason_given_by_the_adapter_is_used() -> None:
    class Reasoned(AdapterBase):
        domain_id = "reasoned"
        unimplemented_reasons = {"solver": "arrives with milestone M1"}

    with pytest.raises(
        NotImplementedError, match="reasoned.solver: arrives with milestone M1"
    ):
        Reasoned().solver()


def test_identity_problems() -> None:
    assert identity_problems(Minimal()) == []

    class NoId:
        pass

    problems = identity_problems(NoId())
    assert any("domain_id" in p for p in problems)
    assert any("missing methods" in p for p in problems)

    class BadId(AdapterBase):
        domain_id = "Water Domain"

    assert any("domain_id" in p for p in identity_problems(BadId()))


def test_check_method_rejects_wrong_results() -> None:
    class Wrong(AdapterBase):
        domain_id = "wrong"

        def solver(self) -> PhysicalSolver:
            return None  # type: ignore[return-value]

        def detectors(self) -> list[Any]:
            return (1, 2)  # type: ignore[return-value]

        def localizer(self) -> Any:
            return 5

    for name in ("solver", "detectors", "localizer"):
        with pytest.raises(ConformanceError):
            check_method(Wrong(), name)
    with pytest.raises(ConformanceError, match="not a DomainAdapter method"):
        check_method(Wrong(), "not_a_method")


def test_check_method_accepts_a_valid_solver() -> None:
    class Good(AdapterBase):
        domain_id = "good"

        def solver(self) -> PhysicalSolver:
            class Solver:
                def run(self, state: Any, scenario: Any, horizon: Any) -> Any:
                    raise NotImplementedError

            return Solver()  # type: ignore[return-value]

    check_method(Good(), "solver")


def test_health_check_validation() -> None:
    assert HealthCheck("wntr", True, "WNTR 1.5.0 matches the manifest").ok
    with pytest.raises(ValueError):
        HealthCheck("", True, "x")
    with pytest.raises(ValueError):
        HealthCheck("x", True, " ")
    with pytest.raises(TypeError):
        HealthCheck("x", 1, "y")  # type: ignore[arg-type]
