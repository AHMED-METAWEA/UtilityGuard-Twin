"""Type-flip fuzz: replace each value of each valid example with a value of another JSON type
(or a malformed string, or a non-integer number) and demand that the contract rejects it, except
where the schema deliberately allows it.

The allowlist below was produced by running the fuzz and reading every entry. It only lists
free text, plain numbers and nullable fields. A schema change that starts accepting anything
else (an identifier that is a number, a timestamp that is free text, a label that is any string)
fails this test, which is what makes it hard to loosen a schema by accident.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from contract_support import files, is_valid, load_json

CANDIDATES: dict[str, Any] = {
    "str": "x y",  # not an identifier, a label, a timestamp, a hash or a template id
    "num": 12345.5,  # not an integer, outside every bounded range
    "bool": True,
    "null": None,
    "obj": {},
    "arr": [],
}
# Maps whose keys are data (sensor ids, detector ids, names): their position becomes `*`.
DYNAMIC_MAPS = {
    "detectors",
    "residuals",
    "zone_multipliers",
    "versions",
    "libraries",
    "output_hashes",
    "assumptions",
}

# (schema, path) -> candidate kinds that the schema accepts on purpose.
ALLOWED: dict[tuple[str, str], set[str]] = {
    ("assumption-set", "assumptions/*/distribution/max"): {"num"},
    ("assumption-set", "assumptions/*/distribution/min"): {"num"},
    ("assumption-set", "assumptions/*/distribution/mode"): {"num"},
    ("assumption-set", "assumptions/*/source_note"): {"str"},
    ("assumption-set", "assumptions/*/unit"): {"str"},
    ("assumption-set", "note"): {"str"},
    ("assumption-set", "parent"): {"null"},
    ("evidence-record", "formula"): {"str"},
    ("evidence-record", "inputs/*/unit"): {"null", "str"},
    ("evidence-record", "inputs/*/value"): {"bool", "str"},
    ("evidence-record", "reason"): {"str"},
    ("evidence-record", "uncertainty/basis"): {"str"},
    ("evidence-record", "uncertainty/p10"): {"num"},
    ("evidence-record", "uncertainty/p50"): {"num"},
    ("evidence-record", "uncertainty/p90"): {"num"},
    ("evidence-record", "unit"): {"null", "str"},
    ("evidence-record", "value"): {"bool", "num", "str"},
    ("incident", "location/zone_id"): {"null"},
    ("incident", "model_score/basis"): {"str"},
    ("run-manifest", "config/duration_hours"): {"num"},
    ("run-manifest", "config/faults/*/ramp_hours"): {"num"},
    ("run-manifest", "config/faults/*/start_hour"): {"num"},
    ("run-manifest", "git_commit"): {"null"},
    ("run-manifest", "libraries/*"): {"str"},
    ("run-manifest", "unordered/*"): {"str"},
    ("run-manifest", "versions/*"): {"str"},
    ("scenario-config", "duration_hours"): {"num"},
    ("scenario-config", "faults/*/duration_hours"): {"num"},
    ("scenario-config", "faults/*/factor"): {"num"},
    ("scenario-config", "faults/*/final_area_cm2"): {"num"},
    ("scenario-config", "faults/*/flow_l_s"): {"num"},
    ("scenario-config", "faults/*/ramp_hours"): {"num"},
    ("scenario-config", "faults/*/start_hour"): {"num"},
    ("stream-envelope", "payload/network_confidence/basis"): {"str"},
    ("stream-envelope", "payload/readings/*/unit"): {"str"},
    ("stream-envelope", "payload/readings/*/value"): {"null", "num"},
    ("stream-envelope", "payload/speed"): {"num"},
    ("telemetry-reading", "unit"): {"str"},
    ("telemetry-reading", "value"): {"null", "num"},
}


def kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "num"
    if isinstance(value, str):
        return "str"
    return "obj" if isinstance(value, dict) else "arr"


def leaves(
    node: Any, path: tuple[Any, ...] = ()
) -> Iterator[tuple[tuple[Any, ...], Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from leaves(value, (*path, index))
    else:
        yield path, node


def replaced(instance: Any, path: tuple[Any, ...], value: Any) -> Any:
    copy_ = copy.deepcopy(instance)
    node = copy_
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    return copy_


def normalise(path: tuple[Any, ...]) -> str:
    parts: list[str] = []
    previous: Any = None
    for part in path:
        parts.append(
            "*" if isinstance(part, int) or previous in DYNAMIC_MAPS else str(part)
        )
        previous = part
    return "/".join(parts)


def worth_trying(original: Any, candidate: Any) -> bool:
    if kind(original) != kind(candidate):
        return True
    if kind(original) == "str":
        return True  # a malformed string of the same kind
    # An integer replaced by a non-integer number tests `integer`; floats are skipped.
    return (
        kind(original) == "num"
        and isinstance(original, int)
        and not isinstance(candidate, int)
    )


def accepted_flips() -> dict[tuple[str, str], set[str]]:
    accepted: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path_on_disk in files("examples"):
        schema = path_on_disk.parent.name
        instance = load_json(path_on_disk)
        for path, original in leaves(instance):
            for name, candidate in CANDIDATES.items():
                if worth_trying(original, candidate) and is_valid(
                    schema, replaced(instance, path, candidate)
                ):
                    accepted[(schema, normalise(path))].add(name)
    return accepted


def test_no_example_value_can_be_swapped_for_the_wrong_type_unless_allowed() -> None:
    surprises = {
        key: sorted(found - ALLOWED.get(key, set()))
        for key, found in accepted_flips().items()
        if found - ALLOWED.get(key, set())
    }
    assert surprises == {}, surprises


def test_the_allowlist_has_no_dead_entries() -> None:
    """An entry nobody needs is a hole waiting to be used: remove it once the schema is stricter."""
    found = accepted_flips()
    dead = sorted(
        key for key, kinds in ALLOWED.items() if not kinds <= found.get(key, set())
    )
    assert dead == [], dead


def test_the_examples_directory_is_the_one_the_fuzz_reads() -> None:
    assert files("examples") and all(isinstance(p, Path) for p in files("examples"))
