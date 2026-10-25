"""The token grammars and money rules of the contracts, as code.

`contracts/v1/common.schema.json` fixes how identifiers, units, hashes and commits are written
and which labels money may carry. The objects in `ug_core` (`Evidenced`, `Manifest`,
`TelemetrySeries`, `AssumptionSet`) enforce the same rules when they are built, so they can never
produce a payload the contract rejects (card T-A1-002c). A test compares every pattern here with
the schema's, character for character, so the two cannot drift apart.

Matching uses `fullmatch`: Python's `$` also matches before a trailing newline, which a JSON
Schema validator on another platform would refuse.

Money (pitfall P-14) is guarded twice. A unit that looks like a currency must be written `EGP`
or `EGP/<m3|kWh|MWh|kW|h|day|month|year>` (`looks_like_money`: a best-effort reading of
spellings, which a new spelling can always dodge). And a value labelled SIMULATION, MODEL,
SENSOR_SIM or PUBLIC_GEOMETRY must carry a unit built from known physical units
(`is_physical_unit`), so it fails closed: whatever a currency is called, it cannot be one.
"""

from __future__ import annotations

import re

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$"
UNIT_PATTERN = r"^[A-Za-z0-9/^*.%-]{1,24}$"
ASSUMPTION_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_COMMIT_PATTERN = r"^[0-9a-f]{6,40}$"


def _ci(word: str) -> str:
    return "".join(f"[{c.upper()}{c.lower()}]" for c in word)


_SCHEMA_CURRENCY_CODES = (
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
# The contract's own recogniser: common codes and words, with optional dots between the letters.
# It is kept character for character (a test compares it with the schema). The contract says that
# a currency it does not list is caught by the code, which `looks_like_money` below does.
MONEY_LOOKING_PATTERN = "|".join(
    [r"\.?".join(_ci(letter) for letter in code) for code in _SCHEMA_CURRENCY_CODES]
    + [r"(^|[^A-Za-z])[Ll]\.?[Ee]\.?($|[^A-Za-z])"]
    + [_ci(word) for word in _CURRENCY_WORDS]
)
CANONICAL_MONEY_PATTERN = r"^EGP(/(m3|kWh|MWh|kW|h|day|month|year))?$"

# Every active ISO 4217 alphabetic code (the schema's recogniser lists only twelve of them).
CURRENCY_CODES = (
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN", "BAM", "BBD", "BDT",
    "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL", "BSD", "BTN", "BWP", "BYN", "BZD", "CAD",
    "CDF", "CHF", "CLP", "CNY", "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD",
    "EGP", "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP", "GMD", "GNF", "GTQ",
    "GYD", "HKD", "HNL", "HTG", "HUF", "IDR", "ILS", "INR", "IQD", "IRR", "ISK", "JMD", "JOD",
    "JPY", "KES", "KGS", "KHR", "KMF", "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR",
    "LRD", "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU", "MUR", "MVR",
    "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK", "NPR", "NZD", "OMR", "PAB", "PEN",
    "PGK", "PHP", "PKR", "PLN", "PYG", "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR",
    "SDG", "SEK", "SGD", "SHP", "SLE", "SOS", "SRD", "SSP", "STN", "SVC", "SYP", "SZL", "THB",
    "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TWD", "TZS", "UAH", "UGX", "USD", "UYU", "UZS",
    "VED", "VES", "VND", "VUV", "WST", "XAF", "XCD", "XCG", "XOF", "XPF", "YER", "ZAR", "ZMW",
    "ZWG", "ZWL",
)  # fmt: skip
# Currency words, matched anywhere in a unit once the letters are joined and lower-cased.
CURRENCY_WORDS = (
    "pound", "dollar", "euro", "riyal", "dirham", "dinar", "lira", "rupee", "rupiah", "yuan",
    "shilling", "peso", "franc", "naira", "ringgit", "forint", "zloty", "koruna", "hryvnia",
    "kwacha", "shekel", "baht", "krona", "krone", "rand", "cedi", "birr", "taka", "denar",
)  # fmt: skip
# A metric prefix may stand in front of a code (`kEGP`, `MLE`); matching is case-insensitive.
_METRIC_PREFIX = r"(?:da|[yzafpnumcdhkgtep])?"
_CURRENCY_ATOM = re.compile(
    _METRIC_PREFIX
    + "(?:"
    + "|".join([*(c.lower() for c in CURRENCY_CODES), "le"])
    + ")"
)
# The units a simulator, a model, a sensor or a geometry may report: the four labels that money
# can never carry (pitfall P-14). Recognising a currency by its spelling can always be dodged by
# a new spelling, so for these labels the check is the other way round: the unit must be built
# only from the atoms below (optionally with a metric prefix and an exponent), or it is refused.
# A new physical unit is added here in a reviewed change. No currency code or word is an atom
# (a test checks every one, in three spellings).
PHYSICAL_UNIT_ATOMS = frozenset({
    # length, area, volume
    "m", "ha", "L", "l",
    # time
    "s", "min", "h", "day", "week", "month", "year",
    # mass
    "g", "t", "tonne",
    # pressure, force, energy, power
    "Pa", "bar", "atm", "psi", "mmHg", "N", "J", "cal", "W", "Wh", "VA", "var",
    # electrical and thermal
    "V", "A", "Hz", "ohm", "S", "K", "degC", "degF",
    # concentration, turbidity, ratios and counts
    "ppm", "ppb", "NTU", "pH", "pct", "rpm", "count",
})  # fmt: skip
_PHYSICAL_PREFIXES = (
    "da", "y", "z", "a", "f", "p", "n", "u", "m", "c", "d", "h", "k", "M", "G", "T", "P", "E",
)  # fmt: skip
# One factor of a unit: letters with an optional exponent (`m3`, `m^-3`, `m-1`), the number 1
# (`1/s`) or a percent sign.
_UNIT_FACTOR = re.compile(r"(?P<body>[A-Za-z]+)(?:\^?-?[0-9]+)?|%|1")
_PRODUCT_OPERATORS = re.compile(r"[/*.]")
_NOT_A_LETTER = re.compile(r"[^A-Za-z]")
_LETTER_RUNS = re.compile(r"[A-Za-z]+")
_UNIT_OPERATORS = re.compile(r"[/*]")

# Money is never simulator, model, sensor or geometry output (pitfall P-14). Label names, not
# `EvidenceLabel` members, so this module does not import the evidence module that uses it.
MONEY_FORBIDDEN_LABELS = frozenset(
    {"SIMULATION", "MODEL", "SENSOR_SIM", "PUBLIC_GEOMETRY"}
)

_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
_UNIT = re.compile(UNIT_PATTERN)
_ASSUMPTION_NAME = re.compile(ASSUMPTION_NAME_PATTERN)
_SHA256 = re.compile(SHA256_PATTERN)
_GIT_COMMIT = re.compile(GIT_COMMIT_PATTERN)
_MONEY_LOOKING = re.compile(MONEY_LOOKING_PATTERN)
_CANONICAL_MONEY = re.compile(CANONICAL_MONEY_PATTERN)


def is_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def is_unit(value: object) -> bool:
    return isinstance(value, str) and _UNIT.fullmatch(value) is not None


def is_assumption_name(value: object) -> bool:
    return isinstance(value, str) and _ASSUMPTION_NAME.fullmatch(value) is not None


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def is_git_commit(value: object) -> bool:
    return isinstance(value, str) and _GIT_COMMIT.fullmatch(value) is not None


def looks_like_money(unit: str) -> bool:
    """A unit that looks like a currency, in any spelling the code can recognise.

    The contract's recogniser lists a dozen common codes and words (`_MONEY_LOOKING`). The code
    goes further, as the contract says it does: every ISO 4217 code, a metric prefix in front of
    one, a currency word, and a spelling that breaks the letters apart (`E-G-P`, `C.A.D`, `EG2P`).
    Each part of a quotient or product (`a/b*c`) is read on its own, with everything that is not
    a letter removed. A currency that is in no list at all is not recognised: a human reviews a
    new unit before it carries money.
    """
    if _MONEY_LOOKING.search(unit) is not None:
        return True
    for part in _UNIT_OPERATORS.split(unit):
        # The letters of the whole part joined (`E-G-P`, `EG2P`), and each piece of a product or
        # inverse power on its own (`CAD.m^-3` has the pieces `CAD` and `m`).
        for letters in (
            _NOT_A_LETTER.sub("", part),
            *_LETTER_RUNS.findall(part),
        ):
            letters = letters.casefold()
            if not letters:
                continue
            if _CURRENCY_ATOM.fullmatch(letters) is not None:
                return True
            if any(word in letters for word in CURRENCY_WORDS):
                return True
    return False


def is_canonical_money_unit(unit: str) -> bool:
    return _CANONICAL_MONEY.fullmatch(unit) is not None


def is_physical_unit(unit: object) -> bool:
    """True if the unit is built only from `PHYSICAL_UNIT_ATOMS` (see there)."""
    if not is_unit(unit):
        return False
    assert isinstance(unit, str)
    for part in _PRODUCT_OPERATORS.split(unit):
        factor = _UNIT_FACTOR.fullmatch(part)
        if factor is None:
            return False
        body = factor.group("body")
        if body is None:
            continue
        if body in PHYSICAL_UNIT_ATOMS:
            continue
        if any(
            body.startswith(prefix) and body[len(prefix) :] in PHYSICAL_UNIT_ATOMS
            for prefix in _PHYSICAL_PREFIXES
        ):
            continue
        return False
    return True


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
