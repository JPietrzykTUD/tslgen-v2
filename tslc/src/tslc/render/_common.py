"""Shared helpers for generated-project rendering."""

from __future__ import annotations

from collections.abc import Mapping
import re

from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact


def slug(profile_name: str) -> str:
    """A safe C++/Rust/CMake identifier for a profile."""

    return re.sub(r"[^0-9A-Za-z_]", "_", profile_name)


def feature_spelling(feature: str, alternatives: Mapping[str, str]) -> str:
    """A feature's compiler/target-feature spelling."""

    if feature in alternatives:
        return alternatives[feature]
    if feature.startswith("sse4_"):
        return "sse4." + feature[len("sse4_") :]
    if feature.startswith("avx512_"):
        return "avx512" + feature[len("avx512_") :]
    return feature


def text(logical_path: str, content: str) -> Artifact:
    media = "text/x-c++" if logical_path.startswith("cpp/") else "text/rust"
    return Artifact(logical_path=logical_path, content=content, media_type=media)


def used_exts(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> list[str]:
    exts: set[str] = set()
    for specs in by_primitive.values():
        exts.update(spec.extension_name for spec in specs)
        # A representation-change primitive's target vector lives under another extension
        # (`extract` avx2->sse): register it too so its `simd<>` tag is defined.
        exts.update(spec.target.extension_isa for spec in specs if spec.target)
    return sorted(exts)


def used_pairs(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for specs in by_primitive.values():
        pairs.update((spec.extension_name, spec.base_type_spelling) for spec in specs)
        # The target vector's `simd<base, ext>` must be registered too.
        pairs.update(
            (spec.target.extension_isa, spec.target.base_spelling)
            for spec in specs
            if spec.target
        )
    return sorted(pairs)


def used_type_specs(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> list[tuple[str, str, str]]:
    """Used ``(extension, type_tag, base_spelling)`` triples, including targets."""

    specs: set[tuple[str, str, str]] = set()
    for lowered_specs in by_primitive.values():
        specs.update(
            (spec.extension_name, spec.type_tag, spec.base_type_spelling)
            for spec in lowered_specs
        )
        specs.update(
            (
                spec.target.extension_isa,
                spec.target.base_tag,
                spec.target.base_spelling,
            )
            for spec in lowered_specs
            if spec.target
        )
    return sorted(specs)


def type_bits(base_spelling: str) -> int:
    """Bit width from a base-type spelling: ``i8``/``u32``/``f64`` -> 8/32/64."""

    digits = "".join(c for c in base_spelling if c.isdigit())
    return int(digits) if digits else 8
