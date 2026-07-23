"""Assemble generated value-test artifacts from typed value-test plans."""

from __future__ import annotations

import json

from tslc.backend.rust_package import (
    DEFAULT_RUST_PACKAGE_CONFIG,
    RustPackageConfig,
)
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.backend.rust_static_selection import RustStaticSelectionPlan
from tslc.render._common import slug, text
from tslc.render.rust_static_selection import (
    rust_static_fallback_cfg,
    rust_static_profile_cfg,
)
from tslc.value_tests.model import ValueTestProjectPlan
from tslc.value_tests.compile_failure import (
    compile_failure_target_name,
    render_cpp_compile_failure,
    render_rust_compile_failure,
)
from tslc.value_tests.render_cpp import render_cpp_values_runner
from tslc.value_tests.render_rust import render_rust_values_file


def cpp_test_artifacts(
    plan: ValueTestProjectPlan,
    assets: RenderAssets,
    *,
    media_type: str,
) -> list[Artifact]:
    """C++ value-test sources: the shared helper asset plus one runner per profile."""

    artifacts = [
        text(
            "cpp/include/tsl_test_core.hpp",
            assets.text("tsl_test_core.hpp"),
            media_type=media_type,
        )
    ]
    support_headers = sorted(
        {
            header
            for profile in plan.profiles_for("cpp")
            for header in profile.support_headers
        }
    )
    artifacts.extend(
        text(f"cpp/include/{header}", assets.text(header), media_type=media_type)
        for header in support_headers
    )
    for profile in plan.profiles_for("cpp"):
        source = render_cpp_values_runner(profile, assets)
        artifacts.append(
            text(
                f"cpp/tests/values_{slug(profile.profile_name)}.cpp",
                source,
                media_type=media_type,
            )
        )
        artifacts.extend(
            text(
                f"cpp/tests/{compile_failure_target_name(profile, case)}.cpp",
                render_cpp_compile_failure(case),
                media_type=media_type,
            )
            for case in profile.compile_failure_cases
        )
    return artifacts


def rust_test_artifacts(
    plan: ValueTestProjectPlan,
    assets: RenderAssets,
    *,
    media_type: str,
    static_selection_plan: RustStaticSelectionPlan,
    package_config: RustPackageConfig = DEFAULT_RUST_PACKAGE_CONFIG,
) -> list[Artifact]:
    """Rust value-test sources: shared helper module plus the cfg-gated test file."""

    artifacts = [
        text(
            "rust/src/tsl_test_core.rs",
            assets.text("tsl_test_core.rs"),
            media_type=media_type,
        ),
        text(
            "rust/tests/values.rs",
            render_rust_values_file(
                plan.profiles_for("rust"),
                assets,
                profile_cfgs={
                    profile.profile_name: (
                        rust_static_profile_cfg(selection)
                        if (
                            selection := static_selection_plan.profile(
                                profile.profile_name
                            )
                        )
                        is not None
                        else rust_static_fallback_cfg(static_selection_plan)
                    )
                    for profile in plan.profiles_for("rust")
                },
            ),
            media_type=media_type,
        ),
    ]
    for profile in plan.profiles_for("rust"):
        for case in profile.compile_failure_cases:
            target = compile_failure_target_name(profile, case)
            artifacts.append(
                text(
                    f"rust/examples/{target}.rs",
                    render_rust_compile_failure(case),
                    media_type=media_type,
                )
            )
            artifacts.append(
                text(
                    f"rust/verify/{target}/Cargo.toml",
                    _rust_compile_failure_manifest(target, package_config),
                    media_type="text/toml",
                )
            )
    return artifacts


def _rust_compile_failure_manifest(
    target: str,
    package: RustPackageConfig,
) -> str:
    return "\n".join(
        (
            "[package]",
            f'name = {json.dumps(target.replace("_", "-"))}',
            'version = "0.0.0"',
            f"edition = {json.dumps(package.edition)}",
            "publish = false",
            "",
            "[dependencies]",
            "tsl = { package = "
            f"{json.dumps(package.name)}, path = \"../..\" }}",
            "",
            "[[bin]]",
            f"name = {json.dumps(target)}",
            f'path = "../../examples/{target}.rs"',
            "",
        )
    )


__all__ = ["cpp_test_artifacts", "rust_test_artifacts"]
