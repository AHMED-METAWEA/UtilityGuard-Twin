"""Domain plugin interface: the one way a domain (water, electricity, cooling) joins the platform."""

from ug_core.adapter.base import AdapterBase
from ug_core.adapter.domain import ADAPTER_METHODS, DomainAdapter
from ug_core.adapter.health import HasHealthChecks, HealthCheck

__all__ = [
    "ADAPTER_METHODS",
    "AdapterBase",
    "DomainAdapter",
    "HasHealthChecks",
    "HealthCheck",
]
