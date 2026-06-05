from __future__ import annotations

import ast
import inspect
from pathlib import Path

from tslgen.backends.rust import RustArchitectureModule
from tslgen.core.diagnostics import SourceLocation
from tslgen.io.artifacts import ArtifactSet
from tslgen.lowering.model import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicRequest,
)
from tslgen.rendering import (
    IntrinsicBodyTokenProfileRenderContext,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveFunctionNameText,
    PrimitiveFunctionParameterListText,
    PrimitiveFunctionResultTypeText,
    PrimitiveProfileName,
    RenderedIncludeLine,
    RenderedNamespaceText,
    render_intrinsic_body_token_profile_artifact,
)
from tslgen.rendering import intrinsic_body_token_bridge as bridge_module


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"


def test_m239_renders_cpp_typed_intrinsic_handoff_to_profile_artifact() -> None:
    context = _cpp_context()

    result = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == "_mm_add_epi32(left, right)"
    assert result.definition is not None
    assert result.definition.text == (
        "inline __m128i add_sse_si32(__m128i left, __m128i right) {\n"
        "  return _mm_add_epi32(left, right);\n"
        "}\n"
    )
    by_path = _artifact_content_by_path(result.artifacts)
    assert tuple(by_path) == ("cpp/include/profiles/sse.hpp",)
    assert "#include <immintrin.h>" in by_path["cpp/include/profiles/sse.hpp"]
    assert "namespace tsl::profiles::sse {" in by_path[
        "cpp/include/profiles/sse.hpp"
    ]
    assert result.definition.text in by_path["cpp/include/profiles/sse.hpp"]


def test_m239_renders_rust_typed_intrinsic_handoff_to_profile_artifact() -> None:
    context = _rust_context()

    result = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == (
        "unsafe { core::arch::x86_64::_mm_add_epi32(left, right) }"
    )
    assert result.definition is not None
    assert result.definition.text == (
        "pub fn add_sse_si32"
        "(left: core::arch::x86_64::__m128i, "
        "right: core::arch::x86_64::__m128i) "
        "-> core::arch::x86_64::__m128i {\n"
        "    unsafe { core::arch::x86_64::_mm_add_epi32(left, right) }\n"
        "}\n"
    )
    by_path = _artifact_content_by_path(result.artifacts)
    assert tuple(by_path) == ("rust/src/profiles/sse.rs",)
    assert result.definition.text in by_path["rust/src/profiles/sse.rs"]


def test_m239_cpp_and_rust_profile_artifacts_are_deterministic() -> None:
    for context in (_cpp_context(), _rust_context()):
        first = render_intrinsic_body_token_profile_artifact(
            _SUPPLEMENTARY_ROOT,
            context,
        )
        second = render_intrinsic_body_token_profile_artifact(
            _SUPPLEMENTARY_ROOT,
            context,
        )

        assert first.diagnostics == ()
        assert second.diagnostics == ()
        assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
        assert _artifact_content_by_path(first.artifacts) == _artifact_content_by_path(
            second.artifacts
        )


def test_m239_diagnoses_missing_typed_intrinsic_handoff_before_artifacts() -> None:
    source = _location()
    handoff = BackendIntrinsicHandoff(
        segments=(BackendIntrinsicOpaqueTextSegment("left + right", source),),
        source=source,
    )
    context = _cpp_context(handoff=handoff)

    result = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.artifacts.artifacts == ()
    assert result.body_text is None
    assert result.definition is None
    assert _codes(result.diagnostics) == (
        "TSL-INTRINSIC-BODY-TOKEN-BRIDGE-MISSING-HANDOFF-REQUEST",
    )
    assert result.diagnostics[0].location == source


def test_m239_diagnoses_unsupported_backend_before_artifacts() -> None:
    context = IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("c"),
        logical_path=PrimitiveArtifactLogicalPath("c/profiles/sse.h"),
        profile_name=PrimitiveProfileName("sse"),
        handoff=_handoff(),
        function_name=PrimitiveFunctionNameText("add_sse_si32"),
        result_type=PrimitiveFunctionResultTypeText("__m128i"),
        parameters=PrimitiveFunctionParameterListText("__m128i left, __m128i right"),
    )

    result = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.artifacts.artifacts == ()
    assert result.body_text is None
    assert result.definition is None
    assert _codes(result.diagnostics) == (
        "TSL-INTRINSIC-BODY-TOKEN-BRIDGE-UNSUPPORTED-BACKEND",
    )


def test_m239_diagnoses_unsupported_typed_intrinsic_request_before_artifacts() -> None:
    context = _cpp_context(handoff=_handoff(intrinsic_name="vshlq_{{suffix}}"))

    result = render_intrinsic_body_token_profile_artifact(
        _SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.artifacts.artifacts == ()
    assert result.body_text is None
    assert result.definition is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-UNSUPPORTED-DIRECT-NAME",
    )


def test_m239_bridge_does_not_access_parser_or_lowerer() -> None:
    source = inspect.getsource(bridge_module)
    imported_modules, imported_names = _imported_modules_and_names(source)

    assert "tslgen.lowering.model" in imported_modules
    assert not any(name.startswith("tslgen.syntax") for name in imported_modules)
    assert "tslgen.domain.catalog" in imported_modules
    assert not any(name.startswith("tslgen.pipeline") for name in imported_modules)
    assert "Lowerer" not in imported_names
    assert "discover_backend_intrinsic_requests_in_text" not in imported_names


def _cpp_context(
    *,
    handoff: BackendIntrinsicHandoff | None = None,
) -> IntrinsicBodyTokenProfileRenderContext:
    return IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("cpp"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/sse.hpp"),
        profile_name=PrimitiveProfileName("sse"),
        handoff=handoff or _handoff(),
        function_name=PrimitiveFunctionNameText("add_sse_si32"),
        result_type=PrimitiveFunctionResultTypeText("__m128i"),
        parameters=PrimitiveFunctionParameterListText("__m128i left, __m128i right"),
        includes=(RenderedIncludeLine("#include <immintrin.h>"),),
        namespace_open=RenderedNamespaceText("namespace tsl::profiles::sse {"),
        namespace_close=RenderedNamespaceText("}  // namespace tsl::profiles::sse"),
    )


def _rust_context() -> IntrinsicBodyTokenProfileRenderContext:
    return IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("rust"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/sse.rs"),
        profile_name=PrimitiveProfileName("sse"),
        handoff=_handoff(prefix="unsafe { ", suffix=" }"),
        function_name=PrimitiveFunctionNameText("add_sse_si32"),
        result_type=PrimitiveFunctionResultTypeText("core::arch::x86_64::__m128i"),
        parameters=PrimitiveFunctionParameterListText(
            "left: core::arch::x86_64::__m128i, "
            "right: core::arch::x86_64::__m128i"
        ),
        rust_architecture_module=RustArchitectureModule("x86_64"),
    )


def _handoff(
    prefix: str = "",
    suffix: str = "",
    *,
    intrinsic_name: str = "_mm_add_epi32",
) -> BackendIntrinsicHandoff:
    source = _location()
    island = BackendIntrinsicRequest(
        intrinsic_kind="intrin",
        angle_payload_text=intrinsic_name,
        angle_payload_source=source,
        argument_text="left, right",
        argument_source=source,
        source_text=f"intrin<{intrinsic_name}>(left, right)",
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


def _artifact_content_by_path(artifacts: ArtifactSet) -> dict[str, str]:
    return {artifact.logical_path: artifact.content for artifact in artifacts.artifacts}


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


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
