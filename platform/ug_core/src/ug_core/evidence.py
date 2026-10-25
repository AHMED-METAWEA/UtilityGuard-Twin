"""Evidence labels and the `Evidenced` wrapper.

Honesty Rule: every displayed number carries exactly one evidence label. The type makes it
impossible to build a labelled value without a label, with an unknown label, with a number that is
not finite, or with a label that contradicts its content.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from ug_core.numeric import finite


class EvidenceLabel(StrEnum):
    """The nine evidence labels (AGENTS.md, Honesty Rules; Master Spec section 2)."""

    OBSERVED = "OBSERVED"  # measured by a real source
    BENCHMARK = "BENCHMARK"  # from a public benchmark dataset (itself model-generated)
    PUBLIC_GEOMETRY = "PUBLIC_GEOMETRY"  # layout taken from public sources, with provenance
    SIMULATION = "SIMULATION"  # output of the physical solver
    SENSOR_SIM = "SENSOR_SIM"  # output of the measurement simulator
    MODEL = "MODEL"  # output of a detector or statistical model, with version
    ASSUMPTION = "ASSUMPTION"  # a user-editable, versioned input
    CALCULATED = "CALCULATED"  # derived from the above by a displayed formula
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # the system declines to produce a number


T = TypeVar("T")


@dataclass(frozen=True)
class Evidenced(Generic[T]):
    """A value together with the label that says where it comes from.

    - `label` is required; a string is accepted only if it names a real label.
    - `INSUFFICIENT_EVIDENCE` if and only if `value` is `None`: the system either gives a number
      with a source or openly declines.
    - A real-number value must be finite.
    - `CALCULATED` needs a displayed `formula` and at least one input evidence id.
    """

    value: T | None
    label: EvidenceLabel
    evidence_id: str
    unit: str | None = None
    formula: str | None = None
    inputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.label, EvidenceLabel):
            try:
                label = EvidenceLabel(self.label)
            except ValueError:
                raise ValueError(f"unknown evidence label: {self.label!r}") from None
            object.__setattr__(self, "label", label)
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        inputs = tuple(self.inputs)
        if not all(isinstance(item, str) and item.strip() for item in inputs):
            raise ValueError("inputs must be non-empty evidence id strings")
        object.__setattr__(self, "inputs", inputs)

        if self.label is EvidenceLabel.INSUFFICIENT_EVIDENCE:
            if self.value is not None:
                raise ValueError("INSUFFICIENT_EVIDENCE must carry no value (value=None)")
        elif self.value is None:
            raise ValueError(f"a {self.label} value cannot be None; use INSUFFICIENT_EVIDENCE")
        if isinstance(self.value, int | float) and not isinstance(self.value, bool):
            finite(self.value, "value")
        if self.label is EvidenceLabel.CALCULATED:
            if not (isinstance(self.formula, str) and self.formula.strip()):
                raise ValueError("a CALCULATED value needs a displayed formula")
            if not inputs:
                raise ValueError("a CALCULATED value needs at least one input evidence id")
