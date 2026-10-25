"""Every registered domain adapter must pass this suite before it can be enabled (Spec 4.6)."""

from __future__ import annotations

import pytest
from adapter_suite import conformance_params
from ug_core.adapter import ADAPTER_METHODS
from ug_core.adapter.conformance import (
    check_method,
    identity_problems,
    unimplemented_methods,
)
from ug_core.registry import discover

ADAPTERS = discover()  # a domain that cannot load fails collection, loudly


def test_at_least_one_domain_is_registered() -> None:
    assert ADAPTERS, "no domain registered under the 'ug.domains' entry-point group"


@pytest.mark.parametrize("domain_id", sorted(ADAPTERS))
def test_adapter_identity(domain_id: str) -> None:
    adapter = ADAPTERS[domain_id]
    assert identity_problems(adapter) == []
    assert adapter.domain_id == domain_id
    assert unimplemented_methods(adapter) <= set(ADAPTER_METHODS)


@pytest.mark.parametrize(("adapter", "method"), conformance_params(ADAPTERS))
def test_adapter_method(adapter: object, method: str) -> None:
    check_method(adapter, method)
