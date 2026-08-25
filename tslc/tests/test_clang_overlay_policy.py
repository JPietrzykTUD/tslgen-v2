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
_SIX_WAY_EXACT_COMPILER_OPERATION_SHAPES = (
    ("abs", "v:=(v)", (), "ui?"),
    ("add", "v:=(v,v)", (), "arith"),
    ("binary_and", "v:=(v,v)", (), "?i?"),
    ("binary_andnot", "v:=(v,v)", (), "?i?"),
    ("binary_or", "v:=(v,v)", (), "?i?"),
    ("binary_xor", "v:=(v,v)", (), "?i?"),
    ("div", "v:=(v,v)", (), "f?"),
    ("equal", "m:=(v,v)", (), "arith"),
    ("extract_value", "s:=v[idx]", (), "arith"),
    ("greater_than", "m:=(v,v)", (), "arith"),
    ("greater_than_or_equal", "m:=(v,v)", (), "arith"),
    ("less_than", "m:=(v,v)", (), "arith"),
    ("less_than_or_equal", "m:=(v,v)", (), "arith"),
    ("mask_binary_and", "m:=(m,m)", (), "arith"),
    ("mask_binary_not", "m:=m", (), "arith"),
    ("mask_binary_or", "m:=(m,m)", (), "arith"),
    ("mask_binary_xor", "m:=(m,m)", (), "arith"),
    ("mask_false", "m:=()", (("value", "zero"),), "arith"),
    ("mask_true", "m:=()", (("value", "all"),), "arith"),
    ("mul", "v:=(v,v)", (), "arith"),
    ("nequal", "m:=(v,v)", (), "arith"),
    ("reinterpret", "v:=v", (("cast", "reinterpret"),), "arith"),
    ("select", "v:=(m,v,v)", (("mask", "pass_through"),), "arith"),
    ("sequence", "v:=()", (), "arith"),
    ("set", "v:=(lanes<s>)", (), "arith"),
    ("set1", "v:=s", (), "arith"),
    ("set_zero", "v:=()", (("value", "zero"),), "arith"),
    ("sub", "v:=(v,v)", (), "arith"),
)
_EXPECTED_EXACT_COMPILER_OPERATIONS = frozenset(
    (*shape, extension)
    for shape in _SIX_WAY_EXACT_COMPILER_OPERATION_SHAPES
    for extension in _CLANG_OVERLAYS
) | frozenset(
    {
        ("to_vector", "v:=m", (), "arith", "clang_v128"),
        ("to_vector", "v:=m", (), "arith", "clang_v256"),
        ("to_vector", "v:=m", (), "arith", "clang_v512"),
    }
)
_FIXED_NATIVE_BOOTSTRAP_FALLBACKS = frozenset(
    (primitive, signature, (), "arith", extension)
    for primitive, signature in (
        ("to_integral", "im:=m"),
        ("to_mask", "m:=im"),
    )
    for extension in _CLANG_OVERLAYS
)
_EXPECTED_NON_NATIVE_FIRST_PORTABLE_OPERATIONS = (
    _EXPECTED_EXACT_COMPILER_OPERATIONS | _FIXED_NATIVE_BOOTSTRAP_FALLBACKS
)


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


def test_clang_overlay_compiler_operations_precede_native_and_have_fallbacks(
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
            capabilities = _cpp_capabilities(implementation)
            uses_builtin = _uses_builtin(implementation)
            if (
                implementation.prefer_fixed_native
                and (capabilities or uses_builtin)
            ):
                failures.append(
                    f"{primitive.name}/{implementation.extension}: "
                    "compiler operation preempted by native preference"
                )
            if not capabilities and not uses_builtin:
                continue
            if uses_builtin and not capabilities:
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


def test_non_native_first_clang_bodies_are_explicitly_classified(
    catalog: Catalog,
) -> None:
    non_native_first = frozenset(
        (
            primitive.name,
            primitive.signature,
            tuple(sorted(primitive.attributes.items())),
            implementation.type_group,
            implementation.extension,
        )
        for primitive in catalog.primitives
        for implementation in primitive.implementations
        if implementation.extension in _CLANG_OVERLAYS
        and not _uses_builtin(implementation)
        and not _cpp_capabilities(implementation)
        and not implementation.prefer_fixed_native
    )

    assert non_native_first == _EXPECTED_NON_NATIVE_FIRST_PORTABLE_OPERATIONS
