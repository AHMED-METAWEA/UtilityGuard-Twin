"""Named, independent random streams derived from one seed.

Pitfall P-12 (reference baseline): all sensor noise came from one shared stream, and a dropout fault
drew extra numbers only inside its window, so configuring one fault changed the noise on every other
sensor. Here every consumer asks for a stream by name; a stream is a pure function of
`(seed, name)`, so adding, removing or reordering other streams never changes it.

The name is hashed with SHA-256 (not Python's salted `hash`), so streams are identical across
processes and machines for the same NumPy version. Record the NumPy version in the run manifest
(`Manifest.libraries`): NumPy does not promise identical streams across releases.
"""

from __future__ import annotations

import hashlib

import numpy as np


class SeedStreams:
    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative int")
        self._seed = seed

    @property
    def seed(self) -> int:
        return self._seed

    def stream(self, name: str) -> np.random.Generator:
        """A fresh generator for `name`. Hold on to it: calling again restarts the stream."""
        if not isinstance(name, str) or not name:
            raise ValueError("stream name must be a non-empty string")
        digest = hashlib.sha256(name.encode("utf-8")).digest()
        words = [int.from_bytes(digest[i : i + 4], "big") for i in range(0, 16, 4)]
        sequence = np.random.SeedSequence(entropy=[self._seed, *words])
        return np.random.Generator(np.random.PCG64(sequence))
