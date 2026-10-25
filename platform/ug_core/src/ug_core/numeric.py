"""Numeric guards.

Pitfall P-17 (reference baseline): NaN and infinity were silently turned into 0.0, which then looked
like a healthy reading. Here a non-finite number is an error, and a missing value is `None`,
never 0.
"""

from __future__ import annotations

import math
import numbers

# Output values are rounded to this many decimals before hashing, so tiny platform differences in
# floating-point noise do not change a hash. Inputs (config) are never rounded.
HASH_DIGITS = 6


class NonFiniteError(ValueError):
    """A number that must be finite was NaN or infinite."""


def finite(value: object, name: str = "value") -> float:
    """Return `value` as a float, or raise.

    Accepts real numbers (int, float, numpy scalars). Rejects bool, None, strings, NaN and infinity.
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise NonFiniteError(f"{name} must be finite, got {value!r}")
    return number


def round_for_hash(value: object, name: str = "value") -> float:
    """Round a finite number to `HASH_DIGITS` decimals; negative zero becomes zero."""
    return round(finite(value, name), HASH_DIGITS) + 0.0
