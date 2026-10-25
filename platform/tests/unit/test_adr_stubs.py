"""ADR-001 to ADR-010 exist, with the titles of Master Spec Appendix D."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def spec_titles() -> dict[int, str]:
    spec = (REPO / "docs" / "UtilityGuard_Master_Spec.md").read_text(encoding="utf-8")
    appendix = spec.split("## Appendix D", 1)[1].split("## Appendix E", 1)[0]
    return {
        int(n): title.strip()
        for n, title in re.findall(r"ADR-(\d{3}) ([^.]+)\.", appendix)
    }


def test_the_spec_lists_ten_decisions() -> None:
    assert sorted(spec_titles()) == list(range(1, 11))


@pytest.mark.parametrize("number", range(1, 11))
def test_stub_exists_with_the_spec_title(number: int) -> None:
    files = sorted((REPO / "docs" / "adr").glob(f"ADR-{number:03d}-*.md"))
    assert len(files) == 1, f"expected exactly one ADR-{number:03d}-*.md"
    text = files[0].read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert first_line.startswith(f"# ADR-{number:03d}: ")
    assert first_line.split(": ", 1)[1].lower() == spec_titles()[number].lower()
    assert re.search(r"^Status: ", text, flags=re.MULTILINE)
    assert "Master Spec" in text
