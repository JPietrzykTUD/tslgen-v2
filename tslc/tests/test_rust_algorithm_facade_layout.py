"""Generated root Rust algorithm facade ownership and layout."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.backend.algorithm_surface import AlgorithmSemanticFamily
from tslc.backend.rust_algorithm_facade import (
    rust_algorithm_facade_export_names,
    rust_algorithm_facade_root_module,
)
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors


def test_root_algorithm_exports_are_projected_from_exact_declarations() -> None:
    root = rust_algorithm_facade_root_module(load_default_render_assets())
    export_groups = tuple(
        (family.value, (family,)) for family in AlgorithmSemanticFamily
    )

    projected_names: list[str] = []
    for module_name, families in export_groups:
        export_block = root.split(f"pub use self::{module_name}::{{\n", 1)[
            1
        ].split("\n};", 1)[0]
        names = tuple(
            line.strip().removesuffix(",")
            for line in export_block.splitlines()
        )
        assert names == rust_algorithm_facade_export_names(families)
        projected_names.extend(names)
    assert len(projected_names) == len(set(projected_names))
    assert set(projected_names) == set(rust_algorithm_facade_export_names())


def test_root_algorithm_uses_private_one_way_substrate_modules(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "load", "store"],
        profiles=["scalar"],
        type_tags=["si32"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
    root = artifacts["rust/src/tsl_algorithm.rs"]
    private_modules = (
        "representation",
        "masks",
        "kernel_traits",
        "validation",
        *(family.value for family in AlgorithmSemanticFamily),
    )

    for module_name in private_modules:
        assert f"mod {module_name};" in root
        assert f"pub mod {module_name};" not in root
        assert f"rust/src/tsl_algorithm/{module_name}.rs" in artifacts
    assert "pub use self::representation::{" in root
    assert "pub use self::masks::{" in root
    assert "pub use self::kernel_traits::{" in root
    for family in AlgorithmSemanticFamily:
        assert f"pub use self::{family.value}::{{" in root
    assert "families" not in root

    substrate_modules = ("representation", "masks", "kernel_traits", "validation")
    substrate = tuple(
        artifacts[f"rust/src/tsl_algorithm/{module_name}.rs"]
        for module_name in substrate_modules
    )
    for family in AlgorithmSemanticFamily:
        assert all(f"super::{family.value}" not in content for content in substrate)
    utility = artifacts["rust/src/tsl_algorithm/utility.rs"]
    iteration = artifacts["rust/src/tsl_algorithm/iteration.rs"]
    predicate = artifacts["rust/src/tsl_algorithm/predicate.rs"]
    count = artifacts["rust/src/tsl_algorithm/count.rs"]
    selection = artifacts["rust/src/tsl_algorithm/select.rs"]
    transform = artifacts["rust/src/tsl_algorithm/transform.rs"]
    consume = artifacts["rust/src/tsl_algorithm/consume.rs"]
    aggregate = artifacts["rust/src/tsl_algorithm/aggregate.rs"]
    assert "integral_mask_chunk_count" in utility
    assert "for_each_chunk_raw" not in utility
    assert "for_each_chunk_raw" in iteration
    assert "predicate_unary_raw" not in iteration
    assert "predicate_unary_raw" in predicate
    assert "count_unary_raw" not in predicate
    assert "count_unary_raw" in count
    assert "select_unary_raw" not in count
    assert "select_unary_raw" in selection
    assert "select_selected_indices_binary_scaled_raw" in selection
    assert "transform_selected_unary_raw" not in selection
    assert "transform_selected_unary_raw" in transform
    assert "transform_where_binary_raw" in transform
    assert "transform_masked_binary_mask_layout_raw" in transform
    assert "consume_selected_unary_raw" not in transform
    assert "consume_selected_unary_raw" in consume
    assert "consume_masked_binary_raw" in consume
    assert "aggregate_selected_unary_raw" not in consume
    assert "aggregate_selected_unary_raw" in aggregate
    assert "aggregate_masked_binary_raw" in aggregate
    assert "consume_selected_unary_raw" not in aggregate
    assert "rust/src/tsl_algorithm/families.rs" not in artifacts

    public_inventory = artifacts["rust/public-api.json"]
    assert "tsl_algorithm::representation" not in public_inventory
    assert "tsl_algorithm::masks" not in public_inventory
    assert "tsl_algorithm::kernel_traits" not in public_inventory
    assert "tsl_algorithm::validation" not in public_inventory
    for family in AlgorithmSemanticFamily:
        assert f"tsl_algorithm::{family.value}" not in public_inventory
    assert "tsl_algorithm::families" not in public_inventory
