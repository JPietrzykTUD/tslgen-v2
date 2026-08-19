"""Corpus-wide policy checks for fixed-width Clang vector overlays."""

from __future__ import annotations

from collections import defaultdict

from tslc.catalog.model import Catalog, Implementation


_CLANG_OVERLAYS = frozenset(
    {
        "clang_v128",
        "clang_v256",
        "clang_v512",
        "clang_v128_bool",
        "clang_v256_bool",
        "clang_v512_bool",
    }
)
_MASK_BRIDGES = frozenset({"to_integral", "to_mask"})


def _uses_builtin(implementation: Implementation) -> bool:
    bodies = (
        implementation.body_text,
        *(variant.body_text for variant in implementation.variants),
    )
    return any("__builtin" in body for body in bodies)


def _cpp_capabilities(implementation: Implementation) -> frozenset[str]:
    return frozenset(
        capability
        for clause in implementation.requirements
        if clause.extension in {None, implementation.extension}
        for requirement in clause.compiler
        if requirement.backend_id == "cpp"
        for capability in requirement.capabilities
    )


def _target_features(implementation: Implementation) -> frozenset[str]:
    return frozenset(
        feature
        for clause in implementation.requirements
        if clause.extension in {None, implementation.extension}
        for feature in clause.flags
    )


def _covers_builtin_types(
    catalog: Catalog,
    candidate: Implementation,
    builtin: Implementation,
) -> bool:
    if candidate.extension != builtin.extension:
        return False
    if candidate.target_constraint != builtin.target_constraint:
        return False
    if not set(catalog.type_group_members(builtin.type_group)) <= set(
        catalog.type_group_members(candidate.type_group)
    ):
        return False
    if builtin.to_target_group is None:
        return candidate.to_target_group is None
    return candidate.to_target_group is not None and set(
        catalog.type_group_members(builtin.to_target_group)
    ) <= set(catalog.type_group_members(candidate.to_target_group))


def test_every_clang_overlay_selector_shape_covers_all_six_identities(
    catalog: Catalog,
) -> None:
    missing: list[str] = []
    for primitive in catalog.primitives:
        identities_by_shape: dict[tuple[object, ...], set[str]] = defaultdict(set)
        for implementation in primitive.implementations:
            if implementation.extension not in _CLANG_OVERLAYS:
                continue
            shape = (
                implementation.type_group,
                implementation.to_target_group,
                implementation.target_constraint,
            )
            identities_by_shape[shape].add(implementation.extension)
        for shape, identities in identities_by_shape.items():
            if identities != _CLANG_OVERLAYS:
                missing.append(
                    f"{primitive.name} {shape}: "
                    f"{sorted(_CLANG_OVERLAYS - identities)}"
                )

    assert missing == []


def test_clang_overlay_builtins_are_gated_and_have_portable_fallbacks(
    catalog: Catalog,
) -> None:
    failures: list[str] = []
    for primitive in catalog.primitives:
        implementations = tuple(
            implementation
            for implementation in primitive.implementations
            if implementation.extension in _CLANG_OVERLAYS
        )
        for implementation in implementations:
            if not _uses_builtin(implementation):
                continue
            if not _cpp_capabilities(implementation):
                failures.append(
                    f"{primitive.name}/{implementation.extension}: ungated builtin"
                )
            if not any(
                not _uses_builtin(candidate)
                and not _cpp_capabilities(candidate)
                and not _target_features(candidate)
                and _covers_builtin_types(catalog, candidate, implementation)
                for candidate in implementations
            ):
                failures.append(
                    f"{primitive.name}/{implementation.extension}: "
                    "no unconditional portable fallback"
                )

    assert failures == []


def test_portable_clang_overlay_bodies_prefer_fixed_native(
    catalog: Catalog,
) -> None:
    unmarked = [
        f"{primitive.name}/{implementation.extension}/{implementation.type_group}"
        for primitive in catalog.primitives
        for implementation in primitive.implementations
        if implementation.extension in _CLANG_OVERLAYS
        and primitive.name not in _MASK_BRIDGES
        and not _uses_builtin(implementation)
        and not implementation.prefer_fixed_native
    ]

    assert unmarked == []
