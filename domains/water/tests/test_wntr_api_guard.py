"""Static WNTR references must stay inside the introspected API registry."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from ug_water import wntr_api

WATER_SOURCE = Path(wntr_api.__file__).parent


def wntr_references(source: str) -> list[tuple[int, str]]:
    """Resolve direct imports and their dotted uses without importing the source."""
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    references: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "wntr" or alias.name.startswith("wntr."):
                    aliases[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else "wntr"
                    )
                    references.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module == "wntr" or module.startswith("wntr."):
                for alias in node.names:
                    path = f"{module}.{alias.name}"
                    aliases[alias.asname or alias.name] = path
                    references.append((node.lineno, path))

    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Name, ast.Attribute)):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.Attribute) and parent.value is node:
            continue  # The outer attribute records the complete dotted reference.
        parts: list[str] = []
        root = node
        while isinstance(root, ast.Attribute):
            parts.append(root.attr)
            root = root.value
        if isinstance(root, ast.Name) and root.id in aliases:
            reference = ".".join([aliases[root.id], *reversed(parts)])
            references.append((node.lineno, reference))
    return references


def assert_declared_wntr_references(source_root: Path) -> None:
    """Check every Python file, exempting only the registry at the package root."""
    declared = wntr_api.load_manifest()["callables"]
    problems: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        if path == source_root / "wntr_api.py":
            continue
        for line, reference in wntr_references(path.read_text(encoding="utf-8")):
            if not any(
                allowed == reference or allowed.startswith(reference + ".")
                for allowed in declared
            ):
                problems.append(f"{path}:{line}: undeclared WNTR reference {reference}")
    assert not problems, "\n".join(problems)


def test_water_source_uses_only_declared_wntr_references() -> None:
    assert_declared_wntr_references(WATER_SOURCE)


@pytest.mark.parametrize(
    ("source", "reference", "allowed"),
    [
        ("import wntr\nwntr.morph.split_pipe(None)\n", "wntr.morph.split_pipe", True),
        ("import wntr\nwntr.morph.undeclared(None)\n", "wntr.morph.undeclared", False),
        ("import wntr.morph as m\nm.split_pipe(None)\n", "wntr.morph.split_pipe", True),
        (
            "import wntr.morph as m\nm.undeclared(None)\n",
            "wntr.morph.undeclared",
            False,
        ),
        (
            "from wntr.sim import WNTRSimulator\nWNTRSimulator(None)\n",
            "wntr.sim.WNTRSimulator",
            True,
        ),
        (
            "from wntr.sim import WNTRSimulator as Sim\nSim.run_sim(None)\n",
            "wntr.sim.WNTRSimulator.run_sim",
            True,
        ),
        (
            "from wntr.sim import WNTRSimulator as Sim\nSim.undeclared(None)\n",
            "wntr.sim.WNTRSimulator.undeclared",
            False,
        ),
        (
            "from wntr.morph import undeclared\nundeclared(None)\n",
            "wntr.morph.undeclared",
            False,
        ),
        (
            "import wntr.morph\nwntr.morph.break_pipe(None)\n",
            "wntr.morph.break_pipe",
            True,
        ),
        ("import wntr\nwntr.sim\n", "wntr.sim", True),
        ("import wntr\nwntr.simulator\n", "wntr.simulator", False),
        ("from wntr.morph import *\n", "wntr.morph.*", False),
    ],
)
def test_guard_on_planted_files(
    tmp_path: Path, source: str, reference: str, allowed: bool
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    planted = nested / "planted.py"
    planted.write_text(source, encoding="utf-8")
    assert reference in {ref for _, ref in wntr_references(source)}
    if allowed:
        assert_declared_wntr_references(tmp_path)
    else:
        with pytest.raises(AssertionError) as error:
            assert_declared_wntr_references(tmp_path)
        assert f"{planted}:" in str(error.value)
        assert reference in str(error.value)
        assert any(f"{planted}:{line}:" in str(error.value) for line in (1, 2))


def test_guard_exempts_only_the_registry_at_the_root(tmp_path: Path) -> None:
    source = "import wntr\nwntr.undeclared()\n"
    (tmp_path / "wntr_api.py").write_text(source, encoding="utf-8")
    assert_declared_wntr_references(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "wntr_api.py").write_text(source, encoding="utf-8")
    with pytest.raises(AssertionError, match="wntr.undeclared"):
        assert_declared_wntr_references(tmp_path)
