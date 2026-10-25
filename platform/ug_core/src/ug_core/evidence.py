"""Evidence labels and the `Evidenced` wrapper.

Honesty Rule: every displayed number carries exactly one evidence label. The type makes it
impossible to build a labelled value without a label, with an unknown label, with a number that is
not finite, or with a label that contradicts its content.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from ug_core import grammar
from ug_core.numeric import normalize_scalar


class EvidenceLabel(StrEnum):
    """The nine evidence labels (AGENTS.md, Honesty Rules; Master Spec section 2)."""

    OBSERVED = "OBSERVED"  # measured by a real source
    BENCHMARK = "BENCHMARK"  # from a public benchmark dataset (itself model-generated)
    PUBLIC_GEOMETRY = "PUBLIC_GEOMETRY"  # public-source layout, with provenance
    SIMULATION = "SIMULATION"  # output of the physical solver
    SENSOR_SIM = "SENSOR_SIM"  # output of the measurement simulator
    MODEL = "MODEL"  # output of a detector or statistical model, with version
    ASSUMPTION = "ASSUMPTION"  # a user-editable, versioned input
    CALCULATED = "CALCULATED"  # derived from the above by a displayed formula
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # the system declines a number


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
        grammar.require_identifier(self.evidence_id, "evidence_id")
        inputs = tuple(self.inputs)
        for item in inputs:
            grammar.require_identifier(item, "an input evidence id")
        object.__setattr__(self, "inputs", inputs)
        if self.unit is not None:
            grammar.require_unit(self.unit)
        if self.formula is not None and (
            not isinstance(self.formula, str) or not self.formula.strip()
        ):
            raise ValueError("formula must be a non-blank text or None")
        object.__setattr__(self, "value", normalize_scalar(self.value))

        if self.label is EvidenceLabel.INSUFFICIENT_EVIDENCE:
            if self.value is not None:
                raise ValueError(
                    "INSUFFICIENT_EVIDENCE must carry no value (value=None)"
                )
        elif self.value is None:
            raise ValueError(
                f"a {self.label} value cannot be None; use INSUFFICIENT_EVIDENCE"
            )
        if self.label is EvidenceLabel.CALCULATED:
            if not (isinstance(self.formula, str) and self.formula.strip()):
                raise ValueError("a CALCULATED value needs a displayed formula")
            if not inputs:
                raise ValueError(
                    "a CALCULATED value needs at least one input evidence id"
                )
        self._check_money()

    def _check_money(self) -> None:
        """Money (a unit that looks like a currency) follows the contract's rules (P-14)."""
        unit = self.unit
        if unit is None:
            return
        if grammar.looks_like_money(unit) and not grammar.is_canonical_money_unit(unit):
            raise ValueError(
                f"a currency unit is written EGP or EGP/<m3|kWh|MWh|kW|h|day|month|year>, "
                f"got {unit!r}"
            )
        if self.label.value in grammar.MONEY_FORBIDDEN_LABELS:
            # Fail closed: what a simulator, a model, a sensor or a geometry reports is physical.
            # A unit that is not built from known physical units may be a currency in a spelling
            # nobody listed, so it is refused (a new physical unit is added to the vocabulary).
            if grammar.is_money_unit(unit):
                raise ValueError(
                    f"money ({unit}) is never {self.label}: it is CALCULATED from labelled "
                    "inputs, an ASSUMPTION, OBSERVED or BENCHMARK"
                )
            if not grammar.is_physical_unit(unit):
                raise ValueError(
                    f"a {self.label} value carries a physical unit, and {unit!r} is not one the "
                    "code knows. Money is written EGP and is never simulator, model, sensor or "
                    "geometry output; a new physical unit is added to "
                    "ug_core.grammar.PHYSICAL_UNIT_ATOMS in a reviewed change"
                )
            return
        if not grammar.is_money_unit(unit):
            return
        if self.value is not None and (
            isinstance(self.value, bool) or not isinstance(self.value, int | float)
        ):
            raise ValueError(f"a money value ({unit}) is a number, got {self.value!r}")
