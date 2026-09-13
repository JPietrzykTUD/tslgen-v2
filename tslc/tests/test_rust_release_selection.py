"""Generated proof for deterministic Rust release-profile selection."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustTargetRequirement,
    plan_rust_static_selection,
)
from tslc.diagnostics import has_errors
from tslc.pipeline import GenerationResult
from tslc.render.rust_static_selection import (
    rust_static_fallback_cfg,
    rust_static_profile_cfg,
)


_FOCUSED_RELEASE_PROFILES = (
    "scalar",
    "skylake",
    "cannonlake",
    "cascadelake",
    "icelake_rockerlake",
    "neon",
    "wasm32-simd128",
)


@pytest.fixture(scope="module")
def rust_release_selection_results(
    data_root: Path,
    machine_profiles_path: Path,
) -> tuple[GenerationResult, GenerationResult]:
    def generate(profiles: tuple[str, ...]) -> GenerationResult:
        result = generate_project(
            [data_root],
            machine_profiles_path=machine_profiles_path,
            primitives=["add"],
            profiles=profiles,
            type_tags=["si32"],
            backends=["rust"],
        )
        assert not has_errors(result.diagnostics), result.diagnostics
        return result

    return (
        generate(_FOCUSED_RELEASE_PROFILES),
        generate(tuple(reversed(_FOCUSED_RELEASE_PROFILES))),
    )


def _selected_profile(
    plan: RustStaticSelectionPlan,
    *,
    target_arch: str,
    target_features: frozenset[str],
) -> str | None:
    matches = tuple(
        selection.profile_name
        for selection in plan.profiles
        if selection.requirement.target_arch == target_arch
        and set(selection.requirement.target_features) <= target_features
        and not any(
            higher.target_arch == target_arch
            and set(higher.target_features) <= target_features
            for higher in selection.higher_priority_requirements
        )
    )
    assert len(matches) <= 1
    return matches[0] if matches else None


def _requirement(
    plan: RustStaticSelectionPlan,
    profile_name: str,
) -> RustTargetRequirement:
    selection = plan.profile(profile_name)
    assert selection is not None
    return selection.requirement


def _selection_fingerprint(plan: RustStaticSelectionPlan) -> tuple[object, ...]:
    return (
        tuple(
            (
                selection.profile_name,
                selection.requirement,
                selection.higher_priority_requirements,
                selection.selection_priority,
                selection.mappings,
                selection.native_mappings,
            )
            for selection in plan.profiles
        ),
        plan.fallback_mappings,
        plan.fallback_module.metadata_profile_name,
        plan.fallback_module.metadata_profile_family,
    )


def test_release_selection_is_input_order_and_artifact_deterministic(
    rust_release_selection_results: tuple[GenerationResult, GenerationResult],
) -> None:
    forward, reverse = rust_release_selection_results
    forward_plan = plan_rust_static_selection(forward.emitted_profiles)
    reverse_plan = plan_rust_static_selection(reverse.emitted_profiles)
    reordered_plan = plan_rust_static_selection(
        tuple(reversed(forward.emitted_profiles))
    )

    plans_are_identical = forward_plan == reordered_plan
    assert plans_are_identical
    assert _selection_fingerprint(forward_plan) == _selection_fingerprint(reverse_plan)
    forward_digests = dict(forward.artifacts.digest_manifest())
    reverse_digests = dict(reverse.artifacts.digest_manifest())
    assert set(forward_digests) == set(reverse_digests)
    differences = tuple(
        path
        for path in sorted(forward_digests)
        if forward_digests[path] != reverse_digests[path]
    )
    assert differences == ()


def test_release_selection_covers_exact_union_and_cross_arch_targets(
    rust_release_selection_results: tuple[GenerationResult, GenerationResult],
) -> None:
    result, _reverse = rust_release_selection_results
    plan = plan_rust_static_selection(result.emitted_profiles)
    cannonlake = _requirement(plan, "cannonlake")
    cascadelake = _requirement(plan, "cascadelake")
    icelake = _requirement(plan, "icelake_rockerlake")
    neon = _requirement(plan, "neon")
    wasm = _requirement(plan, "wasm32-simd128")

    cases = (
        (cannonlake.target_arch, frozenset(cannonlake.target_features), "cannonlake"),
        (
            cascadelake.target_arch,
            frozenset(cascadelake.target_features),
            "cascadelake",
        ),
        (
            "x86_64",
            frozenset((*cannonlake.target_features, *cascadelake.target_features)),
            "cascadelake",
        ),
        (icelake.target_arch, frozenset(icelake.target_features), "icelake_rockerlake"),
        ("x86_64", frozenset(), None),
        (neon.target_arch, frozenset(neon.target_features), "neon"),
        (wasm.target_arch, frozenset(wasm.target_features), "wasm32-simd128"),
    )
    assert tuple(
        _selected_profile(plan, target_arch=arch, target_features=features)
        for arch, features, _expected in cases
    ) == tuple(expected for _arch, _features, expected in cases)


def test_release_selection_renders_only_mutually_exclusive_cfgs(
    rust_release_selection_results: tuple[GenerationResult, GenerationResult],
) -> None:
    result, _reverse = rust_release_selection_results
    plan = plan_rust_static_selection(result.emitted_profiles)
    library = next(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path == "rust/src/lib.rs"
    )

    for selection in plan.profiles:
        assert rust_static_profile_cfg(selection) in library
    assert rust_static_fallback_cfg(plan) in library
    cannonlake = plan.profile("cannonlake")
    cascadelake = plan.profile("cascadelake")
    assert cannonlake is not None
    assert cascadelake is not None
    assert "cannonlake" not in rust_static_profile_cfg(cannonlake)
    assert "cascadelake" not in rust_static_profile_cfg(cascadelake)


def test_equal_normal_and_oneapi_predicates_require_separate_scopes(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["skylake", "skylake-oneapi"],
        type_tags=["si32"],
        backends=["rust"],
        render_artifacts=False,
    )

    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "TSL-BACKEND-RUST-DUPLICATE-TARGET-PROFILES"
    }
    assert "separate gated generation scopes" in result.diagnostics[0].message


@pytest.mark.generated_build
def test_generated_release_cfgs_compile_for_every_selection_case(
    rust_release_selection_results: tuple[GenerationResult, GenerationResult],
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    rustc = shutil.which("rustc")
    if cargo is None or rustc is None:
        pytest.skip("cargo and rustc are required")
    result, _reverse = rust_release_selection_results
    generated = tmp_path / "generated"
    report = write_artifacts(result.artifacts, generated)
    assert not has_errors(report.diagnostics), report.diagnostics
    manifest = generated / "rust" / "Cargo.toml"
    bins = generated / "rust" / "src" / "bin"
    bins.mkdir(exist_ok=True)
    plan = plan_rust_static_selection(result.emitted_profiles)
    cannonlake = _requirement(plan, "cannonlake")
    cascadelake = _requirement(plan, "cascadelake")
    icelake = _requirement(plan, "icelake_rockerlake")
    neon = _requirement(plan, "neon")
    wasm = _requirement(plan, "wasm32-simd128")
    x86_features = frozenset(
        feature
        for selection in plan.profiles
        if selection.requirement.target_arch == "x86_64"
        for feature in selection.requirement.target_features
    )
    cases = (
        (
            "cannonlake",
            "cannonlake",
            frozenset(cannonlake.target_features),
            "x86_64-unknown-linux-gnu",
        ),
        (
            "cascadelake",
            "cascadelake",
            frozenset(cascadelake.target_features),
            "x86_64-unknown-linux-gnu",
        ),
        (
            "cascadelake_union",
            "cascadelake",
            frozenset((*cannonlake.target_features, *cascadelake.target_features)),
            "x86_64-unknown-linux-gnu",
        ),
        (
            "icelake_rockerlake",
            "icelake_rockerlake",
            frozenset(icelake.target_features),
            "x86_64-unknown-linux-gnu",
        ),
        (
            "target_fallback",
            "target_fallback",
            frozenset(f"-{feature}" for feature in x86_features),
            "x86_64-unknown-linux-gnu",
        ),
        (
            "neon",
            "neon",
            frozenset(neon.target_features),
            "aarch64-unknown-linux-musl",
        ),
        (
            "wasm32_simd128",
            "wasm32_simd128",
            frozenset(wasm.target_features),
            "wasm32-wasip1",
        ),
    )

    missing_targets: list[str] = []
    for case_name, expected, features, target in cases:
        if not _rust_target_is_installed(rustc, target):
            missing_targets.append(target)
            continue
        (bins / f"selection_{case_name}.rs").write_text(
            _selection_witness(expected),
            encoding="utf-8",
        )
        feature_flags = ",".join(
            feature if feature.startswith("-") else f"+{feature}"
            for feature in sorted(features)
        )
        environment = os.environ.copy()
        target_rustflags = (
            "CARGO_TARGET_" + target.upper().replace("-", "_") + "_RUSTFLAGS"
        )
        environment[target_rustflags] = f"-C target-feature={feature_flags}"
        command = [
            cargo,
            "check",
            "--quiet",
            "--manifest-path",
            str(manifest),
            "--bin",
            f"selection_{case_name}",
            "--target-dir",
            str(tmp_path / f"target-{case_name}"),
        ]
        command.extend(("--target", target))
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert completed.returncode == 0, (
            f"{case_name}:\n{completed.stderr}{completed.stdout}"
        )
    if missing_targets:
        pytest.skip(
            "Rust selection targets are unavailable: "
            + ", ".join(sorted(set(missing_targets)))
        )


def _rust_target_is_installed(rustc: str, target: str) -> bool:
    completed = subprocess.run(
        (rustc, "--print", "target-libdir", "--target", target),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and Path(completed.stdout.strip()).is_dir()


def _selection_witness(expected: str) -> str:
    return f"""const fn same(left: &str, right: &str) -> bool {{
    let left = left.as_bytes();
    let right = right.as_bytes();
    if left.len() != right.len() {{
        return false;
    }}
    let mut index = 0;
    while index < left.len() {{
        if left[index] != right[index] {{
            return false;
        }}
        index += 1;
    }}
    true
}}

const _: () = assert!(same(tsl::profile::ACTIVE_PROFILE, {json.dumps(expected)}));

fn main() {{}}
"""
