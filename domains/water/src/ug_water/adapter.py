"""The water domain adapter (Master Spec section 4.6).

Phase A1 registers the adapter and nothing else: every method is still unimplemented and says
which Spec milestone delivers it. Each milestone overrides its methods here; the conformance suite
in `platform/tests/conformance/` then starts checking them.

The adapter also offers the optional `health_checks()` hook (ADR-004), so `ug doctor` can ask the
water domain whether its environment is sound without `platform/` importing this package.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from ug_core.adapter import AdapterBase, HealthCheck

from ug_water import wntr_api


class WaterAdapter(AdapterBase):
    domain_id: ClassVar[str] = "water"
    unimplemented_reasons: ClassVar[dict[str, str]] = {
        "asset_model": "arrives with Spec milestone M1 (twin core)",
        "solver": "arrives with Spec milestone M1 (twin core)",
        "fault_library": "arrives with Spec milestone M1 (twin core)",
        "measurement_model": "arrives with Spec milestone M2 (telemetry)",
        "ui_manifest": "arrives with Spec milestone M2 (map and shell)",
        "expectation_model": "arrives with Spec milestone M3 (detection)",
        "detectors": "arrives with Spec milestone M3 (detection)",
        "localizer": "arrives with Spec milestone M3 (detection)",
        "impact_model": "arrives with Spec milestone M4 (impact and decision)",
        "action_catalog": "arrives with Spec milestone M4 (impact and decision)",
        "cost_model": "arrives with Spec milestone M4 (impact and decision)",
        "validate_dataset": "arrives with Spec milestones M1 and M5 (network and benchmark import)",
    }

    def health_checks(self) -> Sequence[HealthCheck]:
        """Is the installed WNTR the one the code was written against? Never raises."""
        location = wntr_api.manifest_location()
        try:
            manifest = wntr_api.load_manifest()
        except (OSError, ValueError) as exc:
            reason = f"cannot read the WNTR API manifest ({location}): {type(exc).__name__}: {exc}"
            return [
                HealthCheck("wntr_version", False, reason),
                HealthCheck("wntr_api_manifest", False, reason),
            ]
        try:
            installed = wntr_api.installed_version()
        except (
            Exception
        ) as exc:  # WNTR missing or broken: report it, do not crash the doctor
            reason = f"WNTR cannot be imported: {type(exc).__name__}: {exc}"
            return [
                HealthCheck("wntr_version", False, reason),
                HealthCheck("wntr_api_manifest", False, reason),
            ]
        recorded = manifest.get("wntr_version")
        version_ok = recorded == installed
        version = HealthCheck(
            "wntr_version",
            version_ok,
            f"WNTR {installed} installed; the manifest ({location}) was generated for {recorded}",
        )
        try:
            problems = wntr_api.verify(manifest)
        except (
            Exception
        ) as exc:  # the probe network or simulation failed: that is a finding
            problems = [f"verification failed: {type(exc).__name__}: {exc}"]
        if problems:
            shown = "; ".join(p.splitlines()[0] for p in problems[:5])
            more = f" (and {len(problems) - 5} more)" if len(problems) > 5 else ""
            detail = (
                f"{len(problems)} problem(s) against WNTR {installed}: {shown}{more}"
            )
        else:
            detail = (
                f"{wntr_api.symbol_count(manifest)} symbols verified against WNTR {installed} "
                f"({location})"
            )
        return [version, HealthCheck("wntr_api_manifest", not problems, detail)]
