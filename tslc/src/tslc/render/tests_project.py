"""Assemble generated value-test artifacts from typed value-test plans."""

from __future__ import annotations

from tslc.output.artifacts import Artifact
from tslc.render._common import asset, slug, text
from tslc.value_tests.model import ValueTestProjectPlan
from tslc.value_tests.render_cpp import render_cpp_values_runner
from tslc.value_tests.render_rust import render_rust_values_file


def cpp_test_artifacts(plan: ValueTestProjectPlan) -> list[Artifact]:
    """C++ value-test sources: the shared helper asset plus one runner per profile."""

    artifacts = [text("cpp/include/tsl_test_core.hpp", asset("tsl_test_core.hpp"))]
    support_headers = sorted(
        {
            header
            for profile in plan.profiles_for("cpp")
            for header in profile.support_headers
        }
    )
    artifacts.extend(
        text(f"cpp/include/{header}", asset(header)) for header in support_headers
    )
    for profile in plan.profiles_for("cpp"):
        source = render_cpp_values_runner(profile)
        artifacts.append(text(f"cpp/tests/values_{slug(profile.profile_name)}.cpp", source))
    return artifacts


def rust_test_artifacts(plan: ValueTestProjectPlan) -> list[Artifact]:
    """Rust value-test sources: shared helper module plus the cfg-gated test file."""

    return [
        text("rust/src/tsl_test_core.rs", asset("tsl_test_core.rs")),
        text("rust/tests/values.rs", render_rust_values_file(plan.profiles_for("rust"))),
    ]


__all__ = ["cpp_test_artifacts", "rust_test_artifacts"]
