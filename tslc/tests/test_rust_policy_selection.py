"""Stable-Rust compile-time selection proof for the first policy-supported slot."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import textwrap

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.rust_policy_consumption import plan_rust_policy_consumption
from tslc.backend.rust_policy_selection import (
    RustPolicySelection,
    RustPolicySelectionPlan,
    plan_rust_policy_selection,
)
from tslc.benchmark.model import SpecializationKey
from tslc.compiler_assets import RenderAssets
from tslc.diagnostics import has_errors
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.render.licensing import add_generated_license_notice
from tslc.render.rust_project import rust_artifacts
from tslc.render.rust_policy_consumption import (
    plan_rust_policy_consumption_render,
)
from tslc.target_text import LoweredBody


@pytest.fixture(scope="module")
def rust_policy_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["sse2"],
        type_tags=["si8"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


def _mul_selection(plan: RustPolicySelectionPlan) -> RustPolicySelection:
    profile = plan.profile("sse2")
    assert profile is not None
    return next(
        selection
        for selection in profile.selections
        if selection.key.primitive_name == "mul"
        and selection.key.extension_name == "sse"
        and selection.key.type_tag == "si8"
    )


def _by_path(artifacts: tuple[Artifact, ...] | list[Artifact]) -> dict[str, Artifact]:
    return {artifact.logical_path: artifact for artifact in artifacts}


def _overlay_project_artifacts(
    base: ArtifactSet,
    project_artifacts: list[Artifact],
) -> ArtifactSet:
    by_path = _by_path(base.artifacts)
    by_path.update(_by_path(project_artifacts))
    return ArtifactSet.create(tuple(by_path.values()))


def _rust_item(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        char = source[position]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError(f"unterminated generated Rust item: {marker}")


def test_rust_policy_plan_and_default_rendering_are_typed_and_deterministic(
    rust_policy_result,
    render_assets: RenderAssets,
) -> None:
    plan = plan_rust_policy_selection(rust_policy_result.emitted_profiles)
    profile = plan.profile("sse2")
    assert profile is not None
    selection = _mul_selection(plan)

    assert len(profile.selections) == 1
    assert selection.key == SpecializationKey(
        backend_id="rust",
        profile_name="sse2",
        primitive_name="mul",
        source_primitive_name="mul",
        extension_name="sse",
        type_tag="si8",
        result_kind="v",
        param_kinds=("v", "v"),
        lanes=16,
    )
    assert selection.candidate_ids == ("default", "generic_fallback")
    assert selection.selected_candidate == "default"

    coverage = {
        entry.key.primitive_name: entry
        for entry in profile.coverage
        if entry.key.extension_name == "sse"
    }
    assert coverage["mul"].status == "supported"
    for primitive_name in ("shift_left", "shift_right"):
        entry = coverage[primitive_name]
        assert entry.status == "report_only"
        assert "overload" in entry.reason.lower()

    forced = plan.with_forced_selection(selection.key, "generic_fallback")
    assert _mul_selection(plan).selected_candidate == "default"
    assert _mul_selection(forced).selected_candidate == "generic_fallback"
    consumption = plan_rust_policy_consumption_render(
        plan_rust_policy_consumption(
            rust_policy_result.rendered.benchmarks,
            plan,
        )
    )

    default_first = rust_artifacts(
        rust_policy_result.emitted_profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=plan,
    )
    default_second = rust_artifacts(
        rust_policy_result.emitted_profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=plan,
    )
    consumable_artifacts = rust_artifacts(
        rust_policy_result.emitted_profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=plan,
        consumption_plan=consumption,
    )
    forced_artifacts = rust_artifacts(
        rust_policy_result.emitted_profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=forced,
    )
    assert default_first == default_second

    default_artifact = _by_path(default_first)["rust/src/tsl_sse2.rs"]
    default_source = default_artifact.content
    forced_source = _by_path(forced_artifacts)["rust/src/tsl_sse2.rs"].content
    normal_source = _by_path(rust_policy_result.artifacts.artifacts)[
        "rust/src/tsl_sse2.rs"
    ].content
    consumable_artifact = _by_path(consumable_artifacts)["rust/src/tsl_sse2.rs"]
    assert add_generated_license_notice(consumable_artifact).content == normal_source

    default_wrapper = _rust_item(default_source, "pub fn mul<")
    forced_wrapper = _rust_item(forced_source, "pub fn mul<")
    assert default_wrapper == forced_wrapper
    assert "pub fn mul<S: detail::primitives::MulImpl>" in default_wrapper
    assert (
        "<S as detail::primitives::MulImpl>::apply(factor1, factor2)"
        in default_wrapper
    )

    default_mapping = _rust_item(
        default_source,
        "impl MulImpl for Simd<i8, Sse>",
    )
    forced_mapping = _rust_item(
        forced_source,
        "impl MulImpl for Simd<i8, Sse>",
    )
    assert "Mul_defaultImpl" in default_mapping
    assert "Mul_generic_fallbackImpl" not in default_mapping
    assert "Mul_generic_fallbackImpl" in forced_mapping
    assert "Mul_defaultImpl" not in forced_mapping
    assert (
        "<Self as Mul_defaultImpl>::IMPLEMENTATION_STATE" in default_mapping
    )
    assert (
        "<Self as Mul_generic_fallbackImpl>::IMPLEMENTATION_STATE"
        in forced_mapping
    )

    stale_selection = replace(
        selection,
        specialization=replace(
            selection.specialization,
            body=LoweredBody.from_text("return factor1;"),
        ),
    )
    stale_profile = replace(profile, selections=(stale_selection,))
    stale_plan = replace(plan, profiles=(stale_profile,))
    with pytest.raises(ValueError, match="stale or incomplete"):
        rust_artifacts(
            rust_policy_result.emitted_profiles,
            render_assets,
            media_type="text/rust",
            selection_plan=stale_plan,
        )


_CONSUMER_SOURCE = textwrap.dedent(
    """
    use tsl::profile::{from_array, mul, to_array, Sse};
    use tsl::tsl_core::{Simd, SimdVector};

    type Vec = Simd<i8, Sse>;

    #[no_mangle]
    #[inline(never)]
    pub fn ordinary_mul(
        left: <Vec as SimdVector>::RegisterType,
        right: <Vec as SimdVector>::RegisterType,
    ) -> <Vec as SimdVector>::RegisterType {
        mul::<Vec>(left, right)
    }

    fn main() {
        let left_values: [i8; 16] = [
            1, 2, 3, 4, 5, 6, 7, 8,
            9, 10, 11, 12, 13, 14, 15, 16,
        ];
        let right_values: [i8; 16] = [
            1, 2, 3, 4, 5, 6, 7, 8,
            9, 10, 11, 12, 13, 14, 15, 16,
        ];
        let expected: [i8; 16] = [
            1, 4, 9, 16, 25, 36, 49, 64,
            81, 100, 121, -112, -87, -60, -31, 0,
        ];
        let mut left: <Vec as SimdVector>::Array = Default::default();
        let mut right: <Vec as SimdVector>::Array = Default::default();
        for lane in 0..16 {
            left[lane] = left_values[lane];
            right[lane] = right_values[lane];
        }
        let actual = to_array::<Vec>(ordinary_mul(
            from_array::<Vec>(&left),
            from_array::<Vec>(&right),
        ));
        for lane in 0..16 {
            assert_eq!(actual[lane], expected[lane]);
        }
    }
    """
).lstrip()


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _write_policy_crate(
    destination: Path,
    result,
    render_assets: RenderAssets,
    plan: RustPolicySelectionPlan,
) -> Path:
    project_artifacts = rust_artifacts(
        result.emitted_profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=plan,
    )
    artifacts = _overlay_project_artifacts(
        result.artifacts,
        [add_generated_license_notice(artifact) for artifact in project_artifacts],
    )
    report = write_artifacts(artifacts, destination)
    assert not has_errors(report.diagnostics), report.diagnostics
    crate = destination / "rust"
    examples = crate / "examples"
    examples.mkdir()
    (examples / "selection_probe.rs").write_text(
        _CONSUMER_SOURCE,
        encoding="utf-8",
    )
    return crate


def _rust_trait_function(
    assembly: str,
    trait_name: str,
) -> tuple[str, tuple[str, ...]]:
    symbol_match = re.search(
        r"(?P<symbol>_ZN[^\s,\"]*Simd\$LT\$i8\$C\$[^\s,\"]*"
        r"Sse\$GT\$\$u20\$as\$u20\$[^\s,\"]*"
        rf"primitives\.\.{re.escape(trait_name)}\$GT\$5apply[^\s,\"]*)",
        assembly,
    )
    assert symbol_match is not None
    symbol = symbol_match.group("symbol")
    aliases: list[str] = []
    seen: set[str] = set()
    while symbol not in seen:
        seen.add(symbol)
        label = f"{symbol}:"
        start = assembly.find(label)
        if start >= 0:
            end = assembly.find(".Lfunc_end", start)
            assert end >= 0
            return assembly[start:end], tuple(aliases)
        alias = re.search(
            rf"(?m)^\s*\.set\s+{re.escape(symbol)},\s*(?P<target>\S+)\s*$",
            assembly,
        )
        assert alias is not None, f"no body or alias for selected Rust symbol {symbol}"
        symbol = alias.group("target")
        aliases.append(symbol)
    raise AssertionError("cycle in generated Rust assembly aliases")


def _ordinary_mul_function(assembly: str) -> str:
    start = assembly.index("ordinary_mul:")
    end = assembly.index(".Lfunc_end", start)
    return assembly[start:end]


def _optimized_mul_function(
    crate: Path,
    candidate: str,
) -> tuple[str, tuple[str, ...], str]:
    environment = os.environ.copy()
    environment["RUSTFLAGS"] = "-Awarnings -Ccodegen-units=1"
    consumer_build = _run(
        (
            "cargo",
            "rustc",
            "--release",
            "--example",
            "selection_probe",
            "--no-default-features",
            "--features",
            "sse2",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
        environment=environment,
    )
    assert consumer_build.returncode == 0, consumer_build.stderr
    consumer_assembly_files = sorted(
        (crate / "target" / "release" / "examples").glob("selection_probe-*.s"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    assert consumer_assembly_files
    consumer_function = _ordinary_mul_function(
        consumer_assembly_files[0].read_text(encoding="utf-8")
    )
    selected_trait = (
        "Mul_defaultImpl"
        if candidate == "default"
        else "Mul_generic_fallbackImpl"
    )
    unselected_trait = (
        "Mul_generic_fallbackImpl"
        if candidate == "default"
        else "Mul_defaultImpl"
    )
    assert selected_trait in consumer_function
    assert unselected_trait not in consumer_function
    assert "primitives..MulImpl$GT$5apply" not in consumer_function
    assert not re.search(r"(?m)^\s*j[a-z]+\s", consumer_function)

    completed = _run(
        (
            "cargo",
            "rustc",
            "--lib",
            "--release",
            "--no-default-features",
            "--features",
            "sse2",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
        environment=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assembly_files = sorted(
        (crate / "target" / "release" / "deps").glob("tsl-*.s"),
        key=lambda path: path.stat().st_size,
        reverse=True,
    )
    assert assembly_files
    function, aliases = _rust_trait_function(
        assembly_files[0].read_text(encoding="utf-8"),
        selected_trait,
    )
    return function, aliases, consumer_function


def _assert_no_dispatch(function: str) -> None:
    assert not re.search(r"(?m)^\s*call[a-z]*\s", function)
    assert not re.search(r"(?m)^\s*j[a-z]+\s", function)


@pytest.mark.generated_build
def test_generated_rust_default_and_forced_selection_are_static_and_correct(
    rust_policy_result,
    render_assets: RenderAssets,
    tmp_path: Path,
) -> None:
    if shutil.which("cargo") is None or shutil.which("rustc") is None:
        pytest.skip("cargo and rustc are required")
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("the optimized Rust selection proof requires native x86-64 Linux")

    default_plan = plan_rust_policy_selection(rust_policy_result.emitted_profiles)
    selected = _mul_selection(default_plan)
    forced_plan = default_plan.with_forced_selection(
        selected.key,
        "generic_fallback",
    )
    crates = (
        (
            "default",
            _write_policy_crate(
                tmp_path / "default",
                rust_policy_result,
                render_assets,
                default_plan,
            ),
        ),
        (
            "generic_fallback",
            _write_policy_crate(
                tmp_path / "generic_fallback",
                rust_policy_result,
                render_assets,
                forced_plan,
            ),
        ),
    )

    functions: dict[str, tuple[str, tuple[str, ...], str]] = {}
    for candidate, crate in crates:
        common = (
            "--no-default-features",
            "--features",
            "sse2,value_tests",
        )
        values = _run(("cargo", "test", *common, "--test", "values"), cwd=crate)
        assert values.returncode == 0, values.stderr
        consumer = _run(
            (
                "cargo",
                "run",
                "--release",
                "--example",
                "selection_probe",
                "--no-default-features",
                "--features",
                "sse2",
            ),
            cwd=crate,
        )
        assert consumer.returncode == 0, consumer.stderr
        functions[candidate] = _optimized_mul_function(crate, candidate)

    default_function, default_aliases, default_consumer = functions["default"]
    forced_function, forced_aliases, forced_consumer = functions[
        "generic_fallback"
    ]
    _assert_no_dispatch(default_function)
    _assert_no_dispatch(forced_function)

    assert re.search(r"(?m)^\s*pmullw\s", default_function)
    assert re.search(r"(?m)^\s*psrlw\s", default_function)
    assert re.search(r"(?m)^\s*psllw\s", default_function)
    assert re.search(r"(?m)^\s*por\s", default_function)
    assert not re.search(r"(?m)^\s*packuswb\s", default_function)

    assert re.search(r"(?m)^\s*pmullw\s", forced_function)
    assert re.search(r"(?m)^\s*punpckhbw\s", forced_function)
    assert re.search(r"(?m)^\s*punpcklbw\s", forced_function)
    assert re.search(r"(?m)^\s*packuswb\s", forced_function)
    assert not re.search(r"(?m)^\s*psrlw\s", forced_function)
    assert not re.search(r"(?m)^\s*psllw\s", forced_function)

    assert not any("Mul_generic_fallbackImpl" in symbol for symbol in default_aliases)
    assert not any("Mul_defaultImpl" in symbol for symbol in forced_aliases)
    assert "Mul_defaultImpl" in default_consumer
    assert "Mul_generic_fallbackImpl" not in default_consumer
    assert "Mul_generic_fallbackImpl" in forced_consumer
    assert "Mul_defaultImpl" not in forced_consumer
