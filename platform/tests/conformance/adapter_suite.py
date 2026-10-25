"""Shared pieces of the adapter conformance suite.

`conformance_params(adapters)` turns registered adapters into one test case per interface method.
A method the adapter declares as unimplemented becomes a strict expected failure that must raise
`NotImplementedError`. If it returns data instead, the case passes by accident and strict mode
reports a failure, so a declaration can never be a hiding place for placeholder data.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from ug_core.adapter import ADAPTER_METHODS
from ug_core.adapter.conformance import unimplemented_methods, unimplemented_reason


def conformance_params(adapters: Mapping[str, Any]) -> list[Any]:
    params: list[Any] = []
    for domain_id, adapter in adapters.items():
        declared = unimplemented_methods(adapter)
        for name in ADAPTER_METHODS:
            marks = []
            if name in declared:
                marks.append(
                    pytest.mark.xfail(
                        strict=True,
                        raises=NotImplementedError,
                        reason=unimplemented_reason(adapter, name),
                    )
                )
            params.append(
                pytest.param(adapter, name, id=f"{domain_id}-{name}", marks=marks)
            )
    return params
