from __future__ import annotations

import ast
import inspect
from pathlib import Path

from tslgen.backends.rust import RustArchitectureModule
from tslgen.core.diagnostics import SourceLocation
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.artifacts import ArtifactSet
from tslgen.lowering.model import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicRequest,
)
from tslgen.pipeline.build_verifier import (
    BuildCommandEnvironment,
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering import (
    IntrinsicBodyTokenProfileRenderContext,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveFunctionNameText,
    PrimitiveFunctionParameterListText,
    PrimitiveFunctionResultTypeText,
    PrimitiveProfileName,
    RenderedIncludeLine,
    RenderedModuleText,
    RenderedNamespaceText,
    build_generated_project_render_model,
    compose_generated_primitive_project_artifacts,
    render_generated_project_skeleton,
    render_intrinsic_body_token_profile_artifact,
    selected_profile_replacement_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"
_PROFILE = "sse2"


def test_m240_synthetic_intrinsic_project_writes_and_verifies(
    tmp_path: Path,
) -> None:
    model = _generated_project_model()
    artifacts = _composed_synthetic_intrinsic_project(model)
    output_root = tmp_path / "generated"

    write_report = ArtifactWriter().write(
        artifacts,
        output_root,
        mode="manifest-clean",
    )
    assert write_report.diagnostics == ()

    report = verify_generated_project(
        output_root,
        model,
        policy=BuildVerificationPolicy(cxx_compiler="clang++"),
    )

    assert report.diagnostics == ()
    assert _command_keys(report) == (
        ("cpp", _PROFILE, "configure"),
        ("cpp", _PROFILE, "build"),
        ("cpp", _PROFILE, "test"),
        ("rust", _PROFILE, "test"),
    )
    assert all(result.returncode == 0 for result in report.commands)
    rust = report.commands[-1].command
    assert rust.env == (
        _environment("RUSTFLAGS", "-C target-feature=+sse,+sse2"),
    )


def test_m240_composed_intrinsic_project_uses_profile_build_flags() -> None:
    model = _generated_project_model()
    by_path = _artifact_content_by_path(_composed_synthetic_intrinsic_project(model))

    assert "target_compile_options(tsl_generated INTERFACE -msse -msse2)" in (
        by_path["cpp/CMakeLists.txt"]
    )
    assert 'target_features = ["+sse", "+sse2"]' in by_path["rust/Cargo.toml"]
    assert 'rustflags = ["-C", "target-feature=+sse,+sse2"]' in by_path[
        "rust/Cargo.toml"
    ]
    assert "_mm_add_epi32(left, right)" in by_path[
        "cpp/include/profiles/sse2.hpp"
    ]
    assert 'inline constexpr const char* active_profile = profiles::sse2::name;' in (
        by_path["cpp/include/profiles/sse2.hpp"]
    )
    assert "core::arch::x86_64::_mm_add_epi32(left, right)" in by_path[
        "rust/src/profiles/sse2.rs"
    ]
    assert 'pub const ACTIVE_PROFILE: &str = "sse2";' in by_path[
        "rust/src/profiles/sse2.rs"
    ]


def test_m240_synthetic_project_artifacts_are_deterministic() -> None:
    model = _generated_project_model()

    first = _composed_synthetic_intrinsic_project(model)
    second = _composed_synthetic_intrinsic_project(model)

    assert first.digest_manifest() == second.digest_manifest()
    assert _artifact_content_by_path(first) == _artifact_content_by_path(second)


def test_m240_fixture_does_not_parse_or_lower_source() -> None:
    source = inspect.getsource(__import__(__name__))
    imported_modules, imported_names = _imported_modules_and_names(source)

    assert "tslgen.lowering.model" in imported_modules
    assert not any(name.startswith("tslgen.syntax") for name in imported_modules)
    assert not any(name.startswith("tslgen.domain.catalog") for name in imported_modules)
    assert not any(name.startswith("frozen") for name in imported_modules)
    assert not any(name.startswith("tslgenold") for name in imported_modules)
    assert "Lowerer" not in imported_names
    assert "discover_backend_intrinsic_requests_in_text" not in imported_names


def _generated_project_model():
    catalog_result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    assert catalog_result.flag_catalog is not None
    selection = select_generated_profiles(catalog_result.catalog, (_PROFILE,))
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    model_result = build_generated_project_render_model(
        selection.profile_set,
        catalog_result.flag_catalog,
    )
    assert model_result.diagnostics == ()
    assert model_result.model is not None
    return model_result.model


def _composed_synthetic_intrinsic_project(model) -> ArtifactSet:
    skeleton = render_generated_project_skeleton(_SUPPLEMENTARY_ROOT, model)
    assert skeleton.diagnostics == ()

    cpp = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        _cpp_context(),
    )
    rust = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        _rust_context(),
    )
    assert cpp.diagnostics == ()
    assert rust.diagnostics == ()
    primitive_artifacts = ArtifactSet.create(
        (*cpp.artifacts.artifacts, *rust.artifacts.artifacts)
    )

    composed = compose_generated_primitive_project_artifacts(
        skeleton.artifacts,
        primitive_artifacts,
        selected_profile_replacement_policy(model),
    )
    assert composed.diagnostics == ()
    return composed.artifacts


def _cpp_context() -> IntrinsicBodyTokenProfileRenderContext:
    return IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("cpp"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/sse2.hpp"),
        profile_name=PrimitiveProfileName(_PROFILE),
        handoff=_handoff(),
        function_name=PrimitiveFunctionNameText("add_sse2_si32"),
        result_type=PrimitiveFunctionResultTypeText("__m128i"),
        parameters=PrimitiveFunctionParameterListText("__m128i left, __m128i right"),
        includes=(RenderedIncludeLine("#include <immintrin.h>"),),
        namespace_open=RenderedNamespaceText(
            "namespace tsl::profiles::sse2 {\n"
            'inline constexpr const char* name = "sse2";\n'
            'inline constexpr const char* family = "x86";'
        ),
        namespace_close=RenderedNamespaceText(
            "}  // namespace tsl::profiles::sse2\n\n"
            "namespace tsl {\n"
            "inline constexpr const char* active_profile = profiles::sse2::name;\n"
            "inline constexpr const char* active_profile_family = "
            "profiles::sse2::family;\n"
            "}  // namespace tsl"
        ),
    )


def _rust_context() -> IntrinsicBodyTokenProfileRenderContext:
    return IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("rust"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/sse2.rs"),
        profile_name=PrimitiveProfileName(_PROFILE),
        handoff=_handoff(prefix="unsafe { ", suffix=" }"),
        function_name=PrimitiveFunctionNameText("add_sse2_si32"),
        result_type=PrimitiveFunctionResultTypeText("core::arch::x86_64::__m128i"),
        parameters=PrimitiveFunctionParameterListText(
            "left: core::arch::x86_64::__m128i, "
            "right: core::arch::x86_64::__m128i"
        ),
        module_open=RenderedModuleText(
            'pub const ACTIVE_PROFILE: &str = "sse2";\n'
            'pub const ACTIVE_PROFILE_FAMILY: &str = "x86";'
        ),
        rust_architecture_module=RustArchitectureModule("x86_64"),
    )


def _handoff(prefix: str = "", suffix: str = "") -> BackendIntrinsicHandoff:
    source = _location()
    island = BackendIntrinsicRequest(
        intrinsic_kind="intrin",
        angle_payload_text="_mm_add_epi32",
        angle_payload_source=source,
        argument_text="left, right",
        argument_source=source,
        source_text="intrin<_mm_add_epi32>(left, right)",
        source=source,
    )
    request = BackendDirectIntrinsicHandoffRequest(
        angle_payload_text=island.angle_payload_text,
        angle_payload_source=island.angle_payload_source,
        argument_text=island.argument_text,
        argument_source=island.argument_source,
        source_text=island.source_text,
        source=island.source,
    )
    request_segment = BackendIntrinsicHandoffRequestSegment(
        request=request,
        island=island,
        source=source,
    )
    segments = (
        *((BackendIntrinsicOpaqueTextSegment(prefix, source),) if prefix else ()),
        request_segment,
        *((BackendIntrinsicOpaqueTextSegment(suffix, source),) if suffix else ()),
    )
    return BackendIntrinsicHandoff(segments=segments, source=source)


def _command_keys(report) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            result.command.backend_id,
            result.command.profile_name,
            result.command.step,
        )
        for result in report.commands
    )


def _environment(key: str, value: str):
    return BuildCommandEnvironment(key=key, value=value)


def _artifact_content_by_path(artifacts: ArtifactSet) -> dict[str, str]:
    return {artifact.logical_path: artifact.content for artifact in artifacts.artifacts}


def _imported_modules_and_names(source: str) -> tuple[frozenset[str], frozenset[str]]:
    modules: set[str] = set()
    names: set[str] = set()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                modules.add(node.module)
            for alias in node.names:
                names.add(alias.asname or alias.name)

    return frozenset(modules), frozenset(names)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
