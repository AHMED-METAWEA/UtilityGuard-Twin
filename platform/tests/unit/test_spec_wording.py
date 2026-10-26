"""The shell says exactly what the Master Spec says about fidelity (section 1.4).

The badge text and the F1 notice line live in `frontend/src/app/strings.ts`; the Spec states them
in its F1 rules. This test reads both, so a wording change in one without the other fails CI
(card T-B1-005, owner decisions G1 to G3).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "UtilityGuard_Master_Spec.md").read_text(encoding="utf-8")
STRINGS = (ROOT / "frontend" / "src" / "app" / "strings.ts").read_text(encoding="utf-8")


def shell_string(key: str) -> str:
    match = re.search(rf"\b{key}:\s*\n?\s*\"([^\"]+)\"", STRINGS)
    assert match, f"strings.ts has no string {key!r}"
    return match.group(1)


def spec_quote(pattern: str) -> str:
    match = re.search(pattern, SPEC)
    assert match, f"the Spec has no sentence matching {pattern!r}"
    return match.group(1)


def test_the_f1_badge_text_is_the_specs() -> None:
    assert shell_string("f1") == spec_quote(
        r"For an F1 network the badge text is `([^`]+)`"
    )


def test_the_f1_notice_line_is_the_specs() -> None:
    assert shell_string("f1Notice") == spec_quote(r"the honesty notice adds `([^`]+)`")


def test_the_f0_and_no_network_texts_are_the_specs() -> None:
    for key in ("f0", "none"):
        assert f"`{shell_string(key)}`" in SPEC, key


def test_the_notice_line_carries_the_odbl_attribution() -> None:
    line = shell_string("f1Notice")
    assert "© OpenStreetMap contributors" in line and "ODbL" in line
