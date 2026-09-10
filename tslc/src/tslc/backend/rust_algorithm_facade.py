"""Render the generated root Rust algorithm facade and private modules."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.algorithm_surface import (
    ALGORITHM_CALLABLE_FORMS,
    AlgorithmSemanticFamily,
)
from tslc.backend.rust_algorithm_contracts import (
    rust_algorithm_contract_holes,
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_public_declarations,
)
from tslc.compiler_assets import RenderAssets


@dataclass(frozen=True, slots=True)
class RustAlgorithmFacadeChildModule:
    """One generated private child of the root algorithm facade."""

    module_name: str
    content: str

    def __post_init__(self) -> None:
        if not self.module_name.isidentifier() or not self.content:
            raise ValueError("Rust algorithm facade children require names and content")


def rust_algorithm_facade_root_module(assets: RenderAssets) -> str:
    """Render the stable public shell with an explicit algorithm export list."""

    family_exports = {
        f"algorithm_{family.value}_reexports": _rust_algorithm_reexports(
            rust_algorithm_facade_export_names((family,))
        )
        for family, _, _ in _RUST_ALGORITHM_SPLIT_FAMILY_ASSETS
    }
    return assets.fill(
        "tsl_algorithm.rs",
        **family_exports,
        algorithm_family_reexports=_rust_algorithm_reexports(
            rust_algorithm_facade_export_names(
                _RUST_ALGORITHM_REMAINING_FAMILIES
            )
        ),
    )


def rust_algorithm_facade_child_modules(
    assets: RenderAssets,
) -> tuple[RustAlgorithmFacadeChildModule, ...]:
    """Render private substrate modules followed by the temporary family owner."""

    modules = tuple(
        RustAlgorithmFacadeChildModule(module_name, assets.text(asset_name))
        for module_name, asset_name in _RUST_ALGORITHM_SUBSTRATE_ASSETS
    )
    split_families = tuple(
        RustAlgorithmFacadeChildModule(
            module_name,
            assets.fill(
                asset_name,
                **rust_algorithm_contract_holes(
                    admitted_form_names=_rust_algorithm_form_names((family,))
                ),
            ),
        )
        for family, module_name, asset_name in _RUST_ALGORITHM_SPLIT_FAMILY_ASSETS
    )
    families = RustAlgorithmFacadeChildModule(
        "families",
        assets.fill(
            "tsl_algorithm_families.rs",
            **rust_algorithm_contract_holes(
                admitted_form_names=_rust_algorithm_form_names(
                    _RUST_ALGORITHM_REMAINING_FAMILIES
                )
            ),
        ),
    )
    return (*modules, *split_families, families)


def rust_algorithm_facade_export_names(
    semantic_families: tuple[AlgorithmSemanticFamily, ...] | None = None,
) -> tuple[str, ...]:
    """Project exact callable records to the root facade's explicit exports."""

    admitted_form_names = (
        None
        if semantic_families is None
        else _rust_algorithm_form_names(semantic_families)
    )
    declarations = (
        *rust_profile_algorithm_public_declarations(
            ("profile", "algo"),
            admitted_form_names=admitted_form_names,
        ),
        *rust_profile_scaled_checked_algorithm_declarations(
            ("profile", "algo"),
            admitted_form_names=admitted_form_names,
        ),
    )
    return tuple(dict.fromkeys(declaration.name for declaration in declarations))


def _rust_algorithm_form_names(
    semantic_families: tuple[AlgorithmSemanticFamily, ...],
) -> frozenset[str]:
    return frozenset(
        form.name
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family in semantic_families
    )


def _rust_algorithm_reexports(names: tuple[str, ...]) -> str:
    if not names:
        raise ValueError("Rust algorithm family modules require public exports")
    return "\n".join(f"    {name}," for name in names)


_RUST_ALGORITHM_SUBSTRATE_ASSETS = (
    ("representation", "tsl_algorithm_representation.rs"),
    ("masks", "tsl_algorithm_masks.rs"),
    ("kernel_traits", "tsl_algorithm_kernel_traits.rs"),
    ("validation", "tsl_algorithm_validation.rs"),
)
_RUST_ALGORITHM_SPLIT_FAMILY_ASSETS = (
    (
        AlgorithmSemanticFamily.ITERATION,
        "iteration",
        "tsl_algorithm_iteration.rs",
    ),
    (
        AlgorithmSemanticFamily.PREDICATE,
        "predicate",
        "tsl_algorithm_predicate.rs",
    ),
    (AlgorithmSemanticFamily.COUNT, "count", "tsl_algorithm_count.rs"),
    (AlgorithmSemanticFamily.SELECT, "select", "tsl_algorithm_select.rs"),
    (
        AlgorithmSemanticFamily.TRANSFORM,
        "transform",
        "tsl_algorithm_transform.rs",
    ),
)
_RUST_ALGORITHM_REMAINING_FAMILIES = tuple(
    family
    for family in AlgorithmSemanticFamily
    if family
    not in {
        entry[0] for entry in _RUST_ALGORITHM_SPLIT_FAMILY_ASSETS
    }
)


__all__ = (
    "RustAlgorithmFacadeChildModule",
    "rust_algorithm_facade_child_modules",
    "rust_algorithm_facade_export_names",
    "rust_algorithm_facade_root_module",
)
