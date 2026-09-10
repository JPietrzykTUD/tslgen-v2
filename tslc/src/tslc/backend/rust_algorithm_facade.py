"""Render the generated root Rust algorithm facade and private modules."""

from __future__ import annotations

from dataclasses import dataclass

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

    exports = "\n".join(
        f"    {name}," for name in rust_algorithm_facade_export_names()
    )
    return assets.fill("tsl_algorithm.rs", algorithm_family_reexports=exports)


def rust_algorithm_facade_child_modules(
    assets: RenderAssets,
) -> tuple[RustAlgorithmFacadeChildModule, ...]:
    """Render private substrate modules followed by the temporary family owner."""

    modules = tuple(
        RustAlgorithmFacadeChildModule(module_name, assets.text(asset_name))
        for module_name, asset_name in _RUST_ALGORITHM_SUBSTRATE_ASSETS
    )
    families = RustAlgorithmFacadeChildModule(
        "families",
        assets.fill("tsl_algorithm_families.rs", **rust_algorithm_contract_holes()),
    )
    return (*modules, families)


def rust_algorithm_facade_export_names() -> tuple[str, ...]:
    """Project exact callable records to the root facade's explicit exports."""

    declarations = (
        *rust_profile_algorithm_public_declarations(("profile", "algo")),
        *rust_profile_scaled_checked_algorithm_declarations(("profile", "algo")),
    )
    return tuple(dict.fromkeys(declaration.name for declaration in declarations))


_RUST_ALGORITHM_SUBSTRATE_ASSETS = (
    ("representation", "tsl_algorithm_representation.rs"),
    ("masks", "tsl_algorithm_masks.rs"),
    ("kernel_traits", "tsl_algorithm_kernel_traits.rs"),
    ("validation", "tsl_algorithm_validation.rs"),
)


__all__ = (
    "RustAlgorithmFacadeChildModule",
    "rust_algorithm_facade_child_modules",
    "rust_algorithm_facade_export_names",
    "rust_algorithm_facade_root_module",
)
