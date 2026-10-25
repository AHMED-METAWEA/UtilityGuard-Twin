"""Assumption sets: the shipped file, the strict loader, and the link to Master Spec Appendix A."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from ug_core.assumptions import (
    AssumptionError,
    load_assumptions,
    parse_assumptions,
)
from ug_core.evidence import EvidenceLabel

REPO = Path(__file__).resolve().parents[3]
SHIPPED = REPO / "assumptions" / "v1.yaml"
ENTRY = "inspection_cost"


def raw() -> dict[str, Any]:
    """The shipped file as a plain dictionary, to be damaged one way per test."""
    loaded = yaml.safe_load(SHIPPED.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def damaged(mutate: Callable[[dict[str, Any]], object]) -> dict[str, Any]:
    data = copy.deepcopy(raw())
    mutate(data)
    return data


def distribution(data: dict[str, Any]) -> dict[str, Any]:
    return data["assumptions"][ENTRY]["distribution"]  # type: ignore[no-any-return]


def test_shipped_file_loads() -> None:
    assumption_set = load_assumptions(SHIPPED)
    assert assumption_set.set_id == "v1"
    assert assumption_set.parent is None
    assert len(assumption_set.assumptions) == 13


def test_every_entry_has_the_required_fields_and_is_labelled_assumption() -> None:
    for name, entry in load_assumptions(SHIPPED).assumptions.items():
        assert entry.name == name
        assert entry.unit and entry.source_note
        assert isinstance(entry.verified, bool)
        assert entry.label is EvidenceLabel.ASSUMPTION
        low, mode, high = (
            entry.distribution.min,
            entry.distribution.mode,
            entry.distribution.max,
        )
        assert low <= mode <= high


def test_all_shipped_values_are_unverified_placeholders() -> None:
    assumption_set = load_assumptions(SHIPPED)
    entries = assumption_set.assumptions.values()
    assert all(not entry.verified for entry in entries)
    assert set(assumption_set.unverified()) == set(assumption_set.assumptions)
    assert all(e.source_note.lower().startswith("placeholder") for e in entries)


def test_shipped_values_equal_the_master_spec_appendix_a() -> None:
    spec = (REPO / "docs" / "UtilityGuard_Master_Spec.md").read_text(encoding="utf-8")
    block = (
        spec.split("## Appendix A", 1)[1].split("```yaml\n", 1)[1].split("```", 1)[0]
    )
    from_spec = yaml.safe_load(block)["assumptions"]
    shipped = raw()["assumptions"]
    assert set(shipped) == set(from_spec)
    for name, entry in from_spec.items():
        assert shipped[name]["unit"] == entry["unit"], name
        assert shipped[name]["distribution"] == entry["distribution"], name
        assert shipped[name]["verified"] is False and entry["verified"] is False, name


def test_evidence_id_matches_the_spec_style() -> None:
    assumption_set = load_assumptions(SHIPPED)
    assert (
        assumption_set.evidence_id("water_production_cost")
        == "as_water_production_cost@v1"
    )
    with pytest.raises(KeyError):
        assumption_set.evidence_id("no_such_assumption")


def test_content_hash_is_stable_and_follows_content() -> None:
    first = parse_assumptions(raw())
    reordered = raw()
    reordered["assumptions"] = dict(reversed(list(reordered["assumptions"].items())))
    assert parse_assumptions(reordered).content_hash() == first.content_hash()
    assert re.fullmatch(r"[0-9a-f]{64}", first.content_hash())
    changed = raw()
    changed["assumptions"][ENTRY]["distribution"]["mode"] = 4001
    assert parse_assumptions(changed).content_hash() != first.content_hash()
    assert json.loads(json.dumps(first.to_dict()))["set_id"] == "v1"


BAD_FILES: dict[str, Callable[[dict[str, Any]], object]] = {
    "missing verified": lambda d: d["assumptions"][ENTRY].pop("verified"),
    "missing unit": lambda d: d["assumptions"][ENTRY].pop("unit"),
    "missing source_note": lambda d: d["assumptions"][ENTRY].pop("source_note"),
    "missing distribution": lambda d: d["assumptions"][ENTRY].pop("distribution"),
    "missing set_id": lambda d: d.pop("set_id"),
    "missing note": lambda d: d.pop("note"),
    "unknown top-level key": lambda d: d.update(extra=1),
    "unknown entry key": lambda d: d["assumptions"][ENTRY].update(price=1),
    "unknown distribution key": lambda d: distribution(d).update(sd=1),
    "unknown distribution type": lambda d: distribution(d).update(type="normal"),
    "min above mode": lambda d: distribution(d).update(min=5000),
    "mode above max": lambda d: distribution(d).update(mode=9000),
    "nan": lambda d: distribution(d).update(mode=float("nan")),
    "infinity": lambda d: distribution(d).update(max=float("inf")),
    "bool as number": lambda d: distribution(d).update(mode=True),
    "text as number": lambda d: distribution(d).update(mode="4000"),
    "verified as text": lambda d: d["assumptions"][ENTRY].update(verified="false"),
    "verified true on a placeholder": lambda d: d["assumptions"][ENTRY].update(
        verified=True
    ),
    "empty unit": lambda d: d["assumptions"][ENTRY].update(unit=" "),
    "empty source note": lambda d: d["assumptions"][ENTRY].update(source_note=""),
    "bad name": lambda d: d["assumptions"].update(
        {"Bad Name": d["assumptions"][ENTRY]}
    ),
    "empty set": lambda d: d.update(assumptions={}),
    "list instead of table": lambda d: d.update(assumptions=[]),
    "bad set id": lambda d: d.update(set_id="v 1"),
    "parent not a string": lambda d: d.update(parent=3),
    "entry not a mapping": lambda d: d["assumptions"].update({ENTRY: "cheap"}),
}


@pytest.mark.parametrize("reason", sorted(BAD_FILES))
def test_loader_rejects(reason: str) -> None:
    with pytest.raises(AssumptionError):
        parse_assumptions(damaged(BAD_FILES[reason]))


def test_verified_true_is_accepted_with_a_real_source_note() -> None:
    data = damaged(
        lambda d: d["assumptions"][ENTRY].update(
            verified=True, source_note="ACUD tariff letter 2026-03, table 2"
        )
    )
    assert ENTRY not in parse_assumptions(data).unverified()


def test_a_point_distribution_is_allowed() -> None:
    data = damaged(lambda d: distribution(d).update(min=4000, mode=4000, max=4000))
    assert parse_assumptions(data).assumptions[ENTRY].distribution.max == 4000


def test_the_top_level_must_be_a_mapping() -> None:
    with pytest.raises(AssumptionError):
        parse_assumptions([1, 2])
    with pytest.raises(AssumptionError):
        parse_assumptions(None)


def test_a_repeated_yaml_key_is_an_error_not_a_silent_override(tmp_path: Path) -> None:
    text = SHIPPED.read_text(encoding="utf-8").replace(
        f"  {ENTRY}:\n", f"  water_production_cost:\n    unit: x\n  {ENTRY}:\n", 1
    )
    file = tmp_path / "dup.yaml"
    file.write_text(text, encoding="utf-8")
    with pytest.raises(AssumptionError, match="appears twice"):
        load_assumptions(file)


def test_invalid_yaml_is_an_assumption_error(tmp_path: Path) -> None:
    file = tmp_path / "bad.yaml"
    file.write_text("a: [unclosed", encoding="utf-8")
    with pytest.raises(AssumptionError, match="not valid YAML"):
        load_assumptions(file)


def test_yaml_nan_literal_is_rejected(tmp_path: Path) -> None:
    text = SHIPPED.read_text(encoding="utf-8").replace("mode: 4000", "mode: .nan", 1)
    file = tmp_path / "nan.yaml"
    file.write_text(text, encoding="utf-8")
    with pytest.raises(AssumptionError):
        load_assumptions(file)


def test_a_loaded_set_cannot_be_changed() -> None:
    assumption_set = load_assumptions(SHIPPED)
    before = assumption_set.content_hash()
    other = assumption_set.assumptions["crew_response_hours"]
    with pytest.raises(TypeError):
        assumption_set.assumptions["inspection_cost"] = other  # type: ignore[index]
    with pytest.raises(TypeError):
        del assumption_set.assumptions["inspection_cost"]  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        assumption_set.assumptions.clear()  # type: ignore[attr-defined]
    assert assumption_set.content_hash() == before
    assert len(assumption_set.unverified()) == 13


def test_a_directly_built_set_is_frozen_too() -> None:
    from ug_core.assumptions import AssumptionSet

    source = dict(load_assumptions(SHIPPED).assumptions)
    built = AssumptionSet("v1", None, "note", source)
    source.clear()
    assert len(built.assumptions) == 13


def test_integers_that_do_not_survive_a_float_are_rejected() -> None:
    low = 2**53
    for value in (low + 1, -(low + 1)):
        data = damaged(lambda d, v=value: distribution(d).update(min=v, mode=v, max=v))
        with pytest.raises(AssumptionError, match="exactly"):
            parse_assumptions(data)
    exact = damaged(lambda d: distribution(d).update(min=low, mode=low, max=low))
    assert parse_assumptions(exact).assumptions[ENTRY].distribution.mode == low


@pytest.mark.parametrize(
    "note",
    [
        "Unverified placeholder; no source exists",
        "TBD",
        "to do: find the source",
        "figure from a chat, unsourced",
        "قيمة افتراضية",
        "غير موثق",
        "short",
        "   ",
    ],
)
def test_verified_true_needs_a_note_that_names_a_source(note: str) -> None:
    data = damaged(
        lambda d: d["assumptions"][ENTRY].update(verified=True, source_note=note)
    )
    with pytest.raises(AssumptionError):
        parse_assumptions(data)


def test_numpy_integers_cannot_slip_past_the_exactness_guard() -> None:
    import numpy as np

    low = 2**53
    big = damaged(
        lambda d: distribution(d).update(
            min=np.int64(low + 1), mode=np.int64(low + 1), max=np.int64(low + 1)
        )
    )
    with pytest.raises(AssumptionError, match="exactly"):
        parse_assumptions(big)
    ok = damaged(
        lambda d: distribution(d).update(
            min=np.int64(low), mode=np.int64(low), max=np.int64(low)
        )
    )
    assert parse_assumptions(ok).assumptions[ENTRY].distribution.mode == low


@pytest.mark.parametrize(
    "note",
    [
        "ACUD tariff letter 2026-03; replaces placeholder in v1",
        "وزارة الإسكان، تقرير الافتراضات الاقتصادية المعتمدة 2026، جدول 2",
        "Signed contract annex 3 replaced the unverified draft values",
    ],
)
def test_legitimate_citations_that_mention_the_marker_words_are_accepted(
    note: str,
) -> None:
    data = damaged(
        lambda d: d["assumptions"][ENTRY].update(verified=True, source_note=note)
    )
    assert ENTRY not in parse_assumptions(data).unverified()
