"""Optional self-checks of a domain adapter, for `ug doctor`.

This is an addition to the Spec's adapter interface, kept out of `DomainAdapter` on purpose: it is
optional, and a plain adapter without it still conforms. It exists so the platform can ask a domain
"is your environment sound?" (for water: does the installed WNTR still match the manifest) without
`platform/` ever importing `domains/`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class HealthCheck:
    """One finished check. `ok=False` is a failure; `detail` always says what was checked."""

    name: str
    ok: bool
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("a health check needs a name")
        if not isinstance(self.ok, bool):
            raise TypeError("ok must be a bool")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("a health check needs a detail text")


@runtime_checkable
class HasHealthChecks(Protocol):
    def health_checks(self) -> Sequence[HealthCheck]: ...
