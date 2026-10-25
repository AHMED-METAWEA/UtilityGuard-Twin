"""Finding the installed domain adapters.

A domain package declares itself in its own `pyproject.toml`:

    [project.entry-points."ug.domains"]
    water = "ug_water.adapter:WaterAdapter"

The platform reads that group at run time. It never imports a domain by name, which keeps the rule
"`platform/` never imports `domains/`" true and checkable (`scripts/check_imports.py`).

`discover()` fails loudly. A domain that is installed but cannot load must not silently vanish
from the UI, so a broken entry point, a name that disagrees with `domain_id`, two different
registrations of one name, or an object that is not a `DomainAdapter` all raise
`DomainRegistrationError` naming the entry point.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points

from ug_core.adapter.conformance import identity_problems
from ug_core.adapter.domain import DomainAdapter

ENTRY_POINT_GROUP = "ug.domains"


class DomainRegistrationError(RuntimeError):
    """An installed domain could not be registered."""


def _entry_points() -> list[EntryPoint]:
    """Registered entry points, sorted by name, identical duplicates (same name and target) merged."""
    unique: dict[tuple[str, str], EntryPoint] = {}
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        unique[(entry.name, entry.value)] = entry
    return [unique[key] for key in sorted(unique)]


def discover() -> dict[str, DomainAdapter]:
    """Instantiate every registered adapter. Keys are domain ids, in sorted order."""
    adapters: dict[str, DomainAdapter] = {}
    sources: dict[str, str] = {}
    for entry in _entry_points():
        where = f"entry point {entry.name!r} -> {entry.value}"
        if entry.name in adapters:
            raise DomainRegistrationError(
                f"domain {entry.name!r} is registered twice: {sources[entry.name]} and {entry.value}"
            )
        try:
            factory = entry.load()
            adapter = factory() if callable(factory) else factory
        except Exception as exc:  # re-raised with the entry point named
            raise DomainRegistrationError(
                f"{where} could not be loaded: {exc!r}"
            ) from exc
        problems = identity_problems(adapter)
        if problems:
            raise DomainRegistrationError(
                f"{where} is not a valid adapter: " + "; ".join(problems)
            )
        if adapter.domain_id != entry.name:
            raise DomainRegistrationError(
                f"{where} has domain_id {adapter.domain_id!r}; "
                "the entry point name must equal domain_id"
            )
        adapters[entry.name] = adapter
        sources[entry.name] = entry.value
    return adapters
