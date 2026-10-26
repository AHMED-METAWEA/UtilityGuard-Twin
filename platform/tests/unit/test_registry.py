"""The domain registry: loud failures, deterministic order, and no domain imported by name."""

from __future__ import annotations

import subprocess
import sys
import types
from importlib.metadata import EntryPoint

import pytest
import ug_core.registry as registry
from ug_core.adapter import AdapterBase
from ug_core.registry import DomainRegistrationError, discover


class Alpha(AdapterBase):
    domain_id = "alpha"


class Beta(AdapterBase):
    domain_id = "beta"


class WrongName(AdapterBase):
    domain_id = "other"


class NotAnAdapter:
    domain_id = "alpha"


def install_domains(
    monkeypatch: pytest.MonkeyPatch, **targets: object
) -> list[EntryPoint]:
    """Register fake domains: name -> class, via a throw-away module and fake entry points."""
    module = types.ModuleType("fake_domains")
    entries = []
    for name, target in targets.items():
        setattr(module, name.upper(), target)
        entries.append(
            EntryPoint(name, f"fake_domains:{name.upper()}", registry.ENTRY_POINT_GROUP)
        )
    monkeypatch.setitem(sys.modules, "fake_domains", module)
    monkeypatch.setattr(registry, "entry_points", lambda group: entries)
    return entries


def test_adapters_are_found_and_sorted_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    install_domains(monkeypatch, beta=Beta, alpha=Alpha)
    found = discover()
    assert list(found) == ["alpha", "beta"]
    assert isinstance(found["alpha"], Alpha)


def test_an_entry_point_name_must_equal_the_domain_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_domains(monkeypatch, alpha=WrongName)
    with pytest.raises(
        DomainRegistrationError, match="entry point name must equal domain_id"
    ):
        discover()


def test_an_object_that_is_not_an_adapter_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_domains(monkeypatch, alpha=NotAnAdapter)
    with pytest.raises(DomainRegistrationError, match="not a valid adapter"):
        discover()


def test_a_broken_entry_point_is_reported_not_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = EntryPoint(
        "ghost", "no_such_module_anywhere:Thing", registry.ENTRY_POINT_GROUP
    )
    monkeypatch.setattr(registry, "entry_points", lambda group: [broken])
    with pytest.raises(DomainRegistrationError, match="ghost.*could not be loaded"):
        discover()


def test_a_factory_that_raises_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode() -> object:
        raise RuntimeError("boom")

    install_domains(monkeypatch, alpha=explode)
    with pytest.raises(DomainRegistrationError, match="boom"):
        discover()


def test_two_different_registrations_of_one_name_are_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = install_domains(monkeypatch, alpha=Alpha)
    module = sys.modules["fake_domains"]
    module.ALPHA2 = Alpha  # type: ignore[attr-defined]
    entries.append(
        EntryPoint("alpha", "fake_domains:ALPHA2", registry.ENTRY_POINT_GROUP)
    )
    with pytest.raises(DomainRegistrationError, match="registered twice"):
        discover()


def test_the_same_registration_seen_twice_is_merged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = install_domains(monkeypatch, alpha=Alpha)
    entries.append(entries[0])
    assert list(discover()) == ["alpha"]


def test_importing_the_registry_imports_no_domain_package() -> None:
    code = (
        "import sys, ug_core.registry, ug_core.adapter; "
        "bad = [m for m in sys.modules if m.split('.')[0] in {'ug_water', 'domains'}]; "
        "assert not bad, bad"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
