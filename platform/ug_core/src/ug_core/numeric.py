"""Numeric guards.

Pitfall P-17 (reference baseline): NaN and infinity were silently turned into 0.0, which then looked
like a healthy reading. Here a non-finite number is an error, and a missing value is `None`,
never 0.
"""

from __future__ import annotations

import math
import numbers

import numpy as np

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


def normalize_scalar(
    value: object, name: str = "value"
) -> None | bool | int | float | str:
    """Return a plain Python scalar equal to `value`, or raise.

    Accepted: None, str, bool, int, float, and NumPy bool, integer and floating scalars of at
    most 64 bits (converted to plain Python). Floats must be finite. Everything else is rejected
    (Decimal, Fraction, complex, long NumPy floats, lists, dicts, arbitrary objects): converting
    them could silently change the number or leave a mutable object behind a frozen label.
    """
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, float) or (
        isinstance(value, np.floating) and value.dtype.itemsize <= 8
    ):
        return finite(value, name)
    raise TypeError(f"{name} must be a plain scalar, got {type(value).__name__}")


def round_for_hash(value: object, name: str = "value") -> float:
    """Round a finite number to `HASH_DIGITS` decimals; negative zero becomes zero."""
    return round(finite(value, name), HASH_DIGITS) + 0.0
