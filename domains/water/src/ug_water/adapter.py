"""The water domain adapter (Master Spec section 4.6).

Phase A1 registers the adapter and nothing else: every method is still unimplemented and says
which Spec milestone delivers it. Each milestone overrides its methods here; the conformance suite
in `platform/tests/conformance/` then starts checking them.
"""

from __future__ import annotations

from typing import ClassVar

from ug_core.adapter import AdapterBase


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
