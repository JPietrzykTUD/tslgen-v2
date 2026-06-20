"""Machine feature profiles (the new notion of a generation 'profile').

A profile is a named feature-set (e.g. ``avx2`` = {sse, sse2, …, avx, avx2}).
Loaded from ``supplementary/buildsystem/machine_profiles.json``. An implementation
body is usable in a profile iff the `requires` clause applying to the type has its
flags ⊆ the profile's features; the profile thus decides which extensions'
specializations are emitted.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

# Sentinel used by the generic/scalar profile to mean "no SIMD features".
_NO_SIMD = "NOSIMD-INVALID"


@dataclass(frozen=True, slots=True)
class MachineProfile:
    name: str
    family: str  # "generic" | "x86" | "aarch64"
    features: frozenset[str]
    # feature -> its compiler/target-feature spelling when it differs from the token
    # (e.g. avx512_vpclmulqdq -> vpclmulqdq, neon -> asimd).
    alternatives: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "alternatives", MappingProxyType(dict(self.alternatives)))


def load_machine_profiles(path: Path) -> Mapping[str, MachineProfile]:
    """Load every machine profile, keyed by name. The filesystem-read boundary."""

    data = json.loads(path.read_text(encoding="utf-8"))
    profiles: dict[str, MachineProfile] = {}
    for family, entries in data.items():
        for entry in entries:
            name = entry["name"]
            flags_text = entry.get("flags", "")
            features = (
                frozenset()
                if flags_text.strip() == _NO_SIMD
                else frozenset(flags_text.split())
            )
            profiles[name] = MachineProfile(
                name=name,
                family=family,
                features=features,
                alternatives=dict(entry.get("alternatives", {})),
            )
    return MappingProxyType(profiles)
