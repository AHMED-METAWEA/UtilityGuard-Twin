"""Determinism across fresh interpreters, hash salts and scenario permutations."""

import json
import os
import subprocess
import sys
import textwrap

from honesty_support import ROOT

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
