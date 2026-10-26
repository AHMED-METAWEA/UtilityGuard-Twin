"""UtilityGuard Twin core: entities, time model, scenario engine, evidence kernel (domain-agnostic).

Truth lives in `ug_core.truth` and is deliberately NOT exported here: importing it must be an
explicit act that an import-graph test can see. Detectors and the operator view use `Timebase` and
`TelemetrySeries` only.
"""

from ug_core.evidence import Evidenced, EvidenceLabel
from ug_core.manifest import Manifest
from ug_core.numeric import NonFiniteError, finite
from ug_core.rng import SeedStreams
from ug_core.telemetry import StreamSource, TelemetrySeries
from ug_core.timebase import Timebase

__version__ = "0.0.0"

__all__ = [
    "EvidenceLabel",
    "Evidenced",
    "Manifest",
    "NonFiniteError",
    "SeedStreams",
    "StreamSource",
    "TelemetrySeries",
    "Timebase",
    "__version__",
    "finite",
]
