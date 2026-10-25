# ADR-011: Python package layout

Status: accepted (task T-A1-001, 2026-10-25). Numbered 011 because ADR-001 to ADR-010 are reserved for the titles in Master Spec Appendix D.

## Context
Master Spec section 14 draws `platform/ug_core`, `ug_intel`, `ug_api`, `ug_cli` and `domains/water` as folders, but does not say how they become importable. Two facts constrain the choice:
- A top-level Python package named `platform` would shadow the standard-library module of the same name and break any library that imports it.
- Domains must register through entry points (Spec 4.6), which needs installed package metadata.

## Decision
- `platform/` is a plain folder with no `__init__.py`. Each subfolder is its own installable project.
- Every project (`platform/ug_core`, `platform/ug_intel`, `platform/ug_api`, `platform/ug_cli`, `domains/water`) has its own `pyproject.toml` and a `src/` layout: the importable package is `src/<name>/` (`ug_core`, `ug_intel`, `ug_api`, `ug_cli`, `ug_water`), shipped with a `py.typed` marker.
- `make install` creates `.venv` with Python 3.11 and installs the five projects in editable mode, one by one.
- Build backend: setuptools (>= 68), fetched by pip's build isolation. It is a packaging tool, not a runtime dependency, and any PEP 517 backend can replace it by editing the `[build-system]` table.
- Package dependencies start empty and are added by the card that first needs them (from the approved list in `docs/audit/DECISIONS.md` D-007).
- Entry-point group for domains: `ug.domains` (used from task T-A1-005).

## Consequences
- The standard library stays unshadowed; `scripts/check_layout.py` and a test in the task card verify this.
- Projects can be installed, versioned and tested independently, at the cost of five `pyproject.toml` files.
- The `src/` layout prevents tests from importing the source tree by accident instead of the installed package.
