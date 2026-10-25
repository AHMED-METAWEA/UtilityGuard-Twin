"""Run manifest: everything needed to reproduce a run, with a canonical hash.

Honesty Rule: deterministic, same manifest (config, seed, versions) gives the same output. The hash
below identifies a manifest regardless of dictionary order, of the order of list items whose order
does not matter (pitfall P-06: the reference produced different leaks from the same canonical
manifest because fault order leaked into the result), and of the interpreter's hash seed.

Two hashes:
- `config_hash()`: config and seed only. Use it to cache work that does not depend on code.
- `input_hash()`: config, seed, named versions, library versions and git commit. This is the
  identity of a run recipe. Output hashes are recorded next to it but are not part of it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from ug_core.canonical import canonical_json, freeze, sha256_hex, thaw

MANIFEST_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class Manifest:
    """Immutable run manifest.

    `unordered` names top-level config keys whose list order carries no meaning (for example
    `"faults"`); those lists are sorted into a canonical order on construction, so two manifests
    that differ only in that order are equal and hash the same. Lists under other keys keep their
    order.
    """

    config: Mapping[str, Any]
    seed: int
    versions: Mapping[str, str]
    libraries: Mapping[str, str] = field(default_factory=dict)
    git_commit: str | None = None
    output_hashes: Mapping[str, str] = field(default_factory=dict)
    unordered: tuple[str, ...] = ()
    schema_version: str = MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or self.seed < 0
        ):
            raise ValueError("seed must be a non-negative int")
        for name, mapping in (
            ("versions", self.versions),
            ("libraries", self.libraries),
            ("output_hashes", self.output_hashes),
        ):
            if not all(
                isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
            ):
                raise TypeError(f"{name} must map strings to strings")
        unordered = tuple(self.unordered)
        config = thaw(self.config)
        if not isinstance(config, dict):
            raise TypeError("config must be a mapping")
        for key in unordered:
            if key in config:
                items = config[key]
                if not isinstance(items, list | tuple):
                    raise TypeError(
                        f"config[{key!r}] must be a list to be treated as unordered"
                    )
                config[key] = sorted(items, key=canonical_json)
        object.__setattr__(self, "unordered", unordered)
        object.__setattr__(self, "config", freeze(config))
        object.__setattr__(self, "versions", freeze(dict(self.versions)))
        object.__setattr__(self, "libraries", freeze(dict(self.libraries)))
        object.__setattr__(self, "output_hashes", freeze(dict(self.output_hashes)))
        self.input_hash()  # fail early on NaN, infinity or non-JSON content

    def _input_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config": thaw(self.config),
            "seed": self.seed,
            "versions": thaw(self.versions),
            "libraries": thaw(self.libraries),
            "git_commit": self.git_commit,
            "unordered": list(self.unordered),
        }

    def config_hash(self) -> str:
        return sha256_hex(
            canonical_json({"config": thaw(self.config), "seed": self.seed})
        )

    def input_hash(self) -> str:
        return sha256_hex(canonical_json(self._input_payload()))

    def with_output_hashes(self, output_hashes: Mapping[str, str]) -> Manifest:
        return replace(self, output_hashes=dict(output_hashes))

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dictionary (the shape contract T-A1-002 will describe)."""
        payload = self._input_payload()
        payload["output_hashes"] = thaw(self.output_hashes)
        return payload

    def __hash__(self) -> int:
        return hash((self.input_hash(), canonical_json(thaw(self.output_hashes))))
