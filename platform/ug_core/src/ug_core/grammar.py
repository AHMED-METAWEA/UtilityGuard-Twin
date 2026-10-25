"""The token grammars and money rules of the contracts, as code.

`contracts/v1/common.schema.json` fixes how identifiers, units, hashes and commits are written
and which labels money may carry. The objects in `ug_core` (`Evidenced`, `Manifest`,
`TelemetrySeries`, `AssumptionSet`) enforce the same rules when they are built, so they can never
produce a payload the contract rejects (card T-A1-002c). A test compares every pattern here with
the schema's, character for character, so the two cannot drift apart.

Matching uses `fullmatch`: Python's `$` also matches before a trailing newline, which a JSON
Schema validator on another platform would refuse.
"""

from __future__ import annotations

import re

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$"
UNIT_PATTERN = r"^[A-Za-z0-9/^*.%-]{1,24}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_COMMIT_PATTERN = r"^[0-9a-f]{6,40}$"


def _ci(word: str) -> str:
    return "".join(f"[{c.upper()}{c.lower()}]" for c in word)


_CURRENCY_CODES = (
    "EGP",
    "USD",
    "EUR",
    "GBP",
    "SAR",
    "AED",
    "JPY",
    "CNY",
    "INR",
    "KWD",
    "QAR",
    "CHF",
)
_CURRENCY_WORDS = ("pound", "dollar", "euro", "riyal", "dirham")
# Anything that looks like a currency, in any spelling. The recogniser lists common codes and
# words; a currency it does not list is not recognised (the contract says so too).
MONEY_LOOKING_PATTERN = "|".join(
    [r"\.?".join(_ci(letter) for letter in code) for code in _CURRENCY_CODES]
    + [r"(^|[^A-Za-z])[Ll]\.?[Ee]\.?($|[^A-Za-z])"]
    + [_ci(word) for word in _CURRENCY_WORDS]
)
CANONICAL_MONEY_PATTERN = r"^EGP(/(m3|kWh|MWh|kW|h|day|month|year))?$"

# Money is never simulator, model, sensor or geometry output (pitfall P-14). Label names, not
# `EvidenceLabel` members, so this module does not import the evidence module that uses it.
MONEY_FORBIDDEN_LABELS = frozenset(
    {"SIMULATION", "MODEL", "SENSOR_SIM", "PUBLIC_GEOMETRY"}
)

_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
_UNIT = re.compile(UNIT_PATTERN)
_SHA256 = re.compile(SHA256_PATTERN)
_GIT_COMMIT = re.compile(GIT_COMMIT_PATTERN)
_MONEY_LOOKING = re.compile(MONEY_LOOKING_PATTERN)
_CANONICAL_MONEY = re.compile(CANONICAL_MONEY_PATTERN)


def is_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def is_unit(value: object) -> bool:
    return isinstance(value, str) and _UNIT.fullmatch(value) is not None


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def is_git_commit(value: object) -> bool:
    return isinstance(value, str) and _GIT_COMMIT.fullmatch(value) is not None


def looks_like_money(unit: str) -> bool:
    return _MONEY_LOOKING.search(unit) is not None


def is_canonical_money_unit(unit: str) -> bool:
    return _CANONICAL_MONEY.fullmatch(unit) is not None


def is_money_unit(unit: str) -> bool:
    """A unit the contract treats as money: it starts with EGP (the canonical spelling)."""
    return unit.startswith("EGP")


def require_identifier(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{what} must be text, got {type(value).__name__}")
    if not is_identifier(value):
        raise ValueError(
            f"{what} must be 1 to 128 characters: letters, digits and . _ : @ -, starting with "
            f"a letter or digit; got {value!r}"
        )
    return value


def require_unit(value: object, what: str = "unit") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{what} must be text, got {type(value).__name__}")
    if not is_unit(value):
        raise ValueError(
            f"{what} must be one ASCII token of 1 to 24 characters (letters, digits and "
            f"/ ^ * . % -), got {value!r}"
        )
    return value
