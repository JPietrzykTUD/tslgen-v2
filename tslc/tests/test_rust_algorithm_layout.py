"""Generated profile-local Rust algorithm module layout."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.backend.algorithm_surface import AlgorithmSemanticFamily
from tslc.diagnostics import has_errors


def test_concrete_and_fallback_algorithms_share_private_family_layout(
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
    family_names = tuple(family.value for family in AlgorithmSemanticFamily)

    concrete_parent = artifacts["rust/src/tsl_scalar.rs"]
    fallback_parent = artifacts["rust/src/tsl_target_fallback.rs"]
    assert "pub mod algo;" in concrete_parent
    assert "pub mod algo {" not in concrete_parent
    assert concrete_parent.index("#![cfg(") < concrete_parent.index("pub mod algo;")
    assert "pub mod algo;" in fallback_parent
    assert "pub mod algo {" not in fallback_parent

    for profile_path in (
        "rust/src/tsl_scalar",
        "rust/src/tsl_target_fallback",
    ):
        root = artifacts[f"{profile_path}/algo.rs"]
        support = artifacts[f"{profile_path}/algo/support.rs"]
        assert "mod support;" in root
        assert "pub use self::support::{" in root
        assert "pub struct Profile;" in support
        assert "#![cfg(" not in root
        assert "#![cfg(" not in support
        positions = tuple(root.index(f"mod {name};") for name in family_names)
        assert positions == tuple(sorted(positions))
        for name in family_names:
            child_path = f"{profile_path}/algo/{name}.rs"
            assert child_path in artifacts
            assert f"pub use self::{name}::{{" in root
            assert "#![cfg(" not in artifacts[child_path]

    transform = artifacts["rust/src/tsl_scalar/algo/transform.rs"]
    selection = artifacts["rust/src/tsl_scalar/algo/select.rs"]
    assert "transform_unary_checked" in transform
    assert "select_unary_checked" not in transform
    assert "select_unary_checked" in selection
    assert "transform_unary_checked" not in selection
    assert '"src/**"' in artifacts["rust/Cargo.toml"]
    assert not any(path.startswith("rust/tslc/") for path in artifacts)
