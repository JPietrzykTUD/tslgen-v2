"""Generated root Rust algorithm facade ownership and layout."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.backend.rust_algorithm_facade import (
    rust_algorithm_facade_export_names,
    rust_algorithm_facade_root_module,
)
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors


def test_root_algorithm_exports_are_projected_from_exact_declarations() -> None:
    root = rust_algorithm_facade_root_module(load_default_render_assets())
    export_block = root.split("pub use self::families::{\n", 1)[1].split(
        "\n};", 1
    )[0]

    assert tuple(
        line.strip().removesuffix(",") for line in export_block.splitlines()
    ) == rust_algorithm_facade_export_names()


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
        "families",
    )

    for module_name in private_modules:
        assert f"mod {module_name};" in root
        assert f"pub mod {module_name};" not in root
        assert f"rust/src/tsl_algorithm/{module_name}.rs" in artifacts
    assert "pub use self::representation::{" in root
    assert "pub use self::masks::{" in root
    assert "pub use self::kernel_traits::{" in root
    assert "pub use self::families::{" in root

    substrate = tuple(
        artifacts[f"rust/src/tsl_algorithm/{module_name}.rs"]
        for module_name in private_modules[:-1]
    )
    assert all("super::families" not in content for content in substrate)
    assert all("tsl_algorithm::families" not in content for content in substrate)
    assert "use super::*;" in artifacts["rust/src/tsl_algorithm/families.rs"]

    public_inventory = artifacts["rust/public-api.json"]
    assert "tsl_algorithm::representation" not in public_inventory
    assert "tsl_algorithm::masks" not in public_inventory
    assert "tsl_algorithm::kernel_traits" not in public_inventory
    assert "tsl_algorithm::validation" not in public_inventory
    assert "tsl_algorithm::families" not in public_inventory
