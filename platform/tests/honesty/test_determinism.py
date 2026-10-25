"""Determinism across fresh interpreters, hash salts and scenario permutations."""

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import replace

import numpy as np
import pytest
from honesty_support import ROOT, load_json
from ug_core import Manifest, SeedStreams


@pytest.fixture
def scenario_manifest():
    return Manifest(
        config=load_json(
            ROOT / "contracts/examples/scenario-config/every_fault_type.json"
        ),
        seed=42,
        versions={"scenario": "1"},
        libraries={"numpy": "test_v1"},
        git_commit="aaaaaa1",
        unordered=("faults",),
    )


@pytest.mark.parametrize("hash_method", ["input_hash", "config_hash"])
def test_manifest_hash_includes_seed(scenario_manifest, hash_method):
    """P-06/P-12: changing only the manifest seed changes both recipe hashes."""
    changed = replace(scenario_manifest, seed=scenario_manifest.seed + 1)
    assert (
        getattr(changed, hash_method)() != getattr(scenario_manifest, hash_method)()
    ), f"P-06/P-12: Manifest.{hash_method} ignored a seed-only change"


@pytest.mark.parametrize("field", ["config", "libraries", "versions", "git_commit"])
def test_manifest_input_hash_includes_recipe_fields(scenario_manifest, field):
    """P-06/P-12: each fault parameter or code-version change identifies a new recipe."""
    config = load_json(
        ROOT / "contracts/examples/scenario-config/every_fault_type.json"
    )
    config["faults"][0]["final_area_cm2"] += 0.125
    value = {
        "config": config,
        "libraries": {"numpy": "test_v2"},
        "versions": {"scenario": "2"},
        "git_commit": "bbbbbb2",
    }[field]
    changed = replace(scenario_manifest, **{field: value})
    assert changed.input_hash() != scenario_manifest.input_hash(), (
        f"P-06/P-12: Manifest.input_hash ignored {field}"
    )


def test_manifest_outputs_change_identity_only(scenario_manifest):
    """P-06/P-12: outputs are recorded in equality without changing the input recipe."""
    first = replace(scenario_manifest, output_hashes={"telemetry": "a" * 64})
    second = replace(scenario_manifest, output_hashes={"telemetry": "b" * 64})
    assert first.input_hash() == second.input_hash(), (
        "P-06/P-12: output hashes contaminated Manifest.input_hash"
    )
    assert first != second, "P-06/P-12: Manifest equality ignored output hashes"


PROBE = r"""
import copy
import json
import random
from pathlib import Path
from ug_core import Manifest, SeedStreams

config = json.loads(Path("contracts/examples/scenario-config/every_fault_type.json").read_text())
def manifest_hash(c):
    return Manifest(config=c, seed=42, versions={"scenario": "1"},
                    unordered=("faults",)).input_hash()

base = manifest_hash(config)
reverse = copy.deepcopy(config)
reverse["faults"].reverse()
shuffled = copy.deepcopy(config)
random.Random(19).shuffle(shuffled["faults"])
changes = []
for index, fault in enumerate(config["faults"]):
    for key, value in fault.items():
        changed = copy.deepcopy(config)
        # Every field is varied alone, including numeric and string parameters.
        changed["faults"][index][key] = value + 0.125 if type(value) in (int, float) else value + "_changed"
        changes.append([index, key, manifest_hash(changed)])
streams = SeedStreams(42)
first = streams.stream("sensor:P01").normal(size=16).tolist()
other_first = SeedStreams(42)
other_first.stream("sensor:F02").normal(size=31)
after_other = other_first.stream("sensor:P01").normal(size=16).tolist()
print(json.dumps({"base": base, "reverse": manifest_hash(reverse),
                  "shuffle": manifest_hash(shuffled), "changes": changes,
                  "first": first, "after_other": after_other}))
"""


def test_fresh_process_determinism():
    """P-06/P-12: hashes and independent sensor streams survive process/hash-salt changes."""
    outputs = []
    for salt in ("7", "913"):
        process = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(PROBE)],
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": salt},
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert process.returncode == 0, (
            f"P-06/P-12: subprocess hashseed={salt}: {process.stderr}"
        )
        result = json.loads(process.stdout)
        assert result["base"] == result["reverse"] == result["shuffle"], (
            f"P-06: Manifest.input_hash at hashseed={salt} depends on fault ordering"
        )
        for index, key, changed_hash in result["changes"]:
            assert changed_hash != result["base"], (
                f"P-06: Manifest ignored scenario faults[{index}].{key} at hashseed={salt}"
            )
        assert result["first"] == result["after_other"], (
            f"P-12: SeedStreams sensor:P01 changed after sensor:F02 at hashseed={salt}"
        )
        outputs.append(result)
    assert outputs[0] == outputs[1], (
        "P-06/P-12: Manifest hash or sensor:P01 draws differ across fresh interpreters"
    )


def test_streams_differ_by_name_and_by_seed():
    """P-12: every named stream is its own sequence, so no two sensors share their noise."""
    draws = {
        name: SeedStreams(42).stream(name).normal(size=2000)
        for name in ("sensor:P01", "sensor:P02", "pump:PU1")
    }
    names = sorted(draws)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not np.array_equal(draws[a], draws[b]), (
                f"P-12: streams {a} and {b} are identical"
            )
            correlation = abs(float(np.corrcoef(draws[a], draws[b])[0, 1]))
            assert correlation < 0.1, (
                f"P-12: streams {a} and {b} are correlated ({correlation:.2f})"
            )
    again = SeedStreams(42).stream("sensor:P01").normal(size=2000)
    assert np.array_equal(draws["sensor:P01"], again), (
        "P-12: the same seed and name gave different draws"
    )
    other_seed = SeedStreams(43).stream("sensor:P01").normal(size=2000)
    assert not np.array_equal(draws["sensor:P01"], other_seed), (
        "P-12: the seed does not change the stream"
    )
