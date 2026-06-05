from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicLiteralFragment,
    BackendTranslatedIntrinsicModifier,
)
from tslgen.backends.rust import RustArchitectureModule
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import (
    Catalog,
    ExtensionCatalog,
    ExtensionName,
    Implementation,
    ImplementationBody,
    Primitive,
    TypeTag,
)
from tslgen.io.sources import SourceDocument, SourceLoader
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
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
    SelectedImplementationRenderContext,
    render_intrinsic_body_token_profile_artifact,
)
from tslgen.syntax.parser import TslParser


ROOT = Path(__file__).resolve().parents[2]
SUPPLEMENTARY_ROOT = ROOT / "supplementary"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
_DEFAULT_SELECTED_CONTEXT = object()
_DEFAULT_EXTENSION_CATALOG = object()


def test_m247_cpp_bridge_uses_selected_extension_default_compose_policy() -> None:
    context = _cpp_context("intrin_compose<add>(left, right)")

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == "_mm256_add_ps(left, right)"
    assert result.definition is not None
    assert "_mm256_add_ps(left, right)" in result.definition.text


def test_m247_cpp_explicit_suffix_uses_default_prefix_without_needing_suffix_policy() -> None:
    handoff = _text_handoff("intrin_compose<add, suffix=s>(left, right)")
    request = _single_compose_request(handoff)
    context = _cpp_context(
        handoff=handoff,
        selected_implementation=_selected_render_context(type_tag="bool"),
        translated_modifiers=(
            _translated(
                _field(request, "suffix"),
                BackendIntrinsicLiteralFragment("custom_suffix"),
            ),
        ),
    )

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == "_mm256_add_custom_suffix(left, right)"


def test_m247_rust_bridge_uses_full_policy_prefix_without_double_qualification() -> None:
    context = _rust_context("unsafe { intrin_compose<add>(left, right) }")

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == (
        "unsafe { core::arch::x86_64::_mm256_add_ps(left, right) }"
    )
    assert result.definition is not None
    assert "core::arch::x86_64::core::arch::x86_64" not in result.definition.text


def test_m247_explicit_rust_modifiers_keep_architecture_module_qualification() -> None:
    handoff = _text_handoff(
        "unsafe { intrin_compose<add, prefix=p, suffix=s>(left, right) }",
        backend="rust",
    )
    request = _single_compose_request(handoff)
    context = _rust_context(
        handoff=handoff,
        selected_implementation=None,
        rust_architecture_module=RustArchitectureModule("x86_64"),
        translated_modifiers=(
            _translated(
                _field(request, "prefix"),
                BackendIntrinsicLiteralFragment("_mm256_"),
                backend="rust",
            ),
            _translated(
                _field(request, "suffix"),
                BackendIntrinsicLiteralFragment("epi32"),
                backend="rust",
            ),
        ),
    )

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == (
        "unsafe { core::arch::x86_64::_mm256_add_epi32(left, right) }"
    )


def test_m247_explicit_rust_prefix_uses_default_suffix_and_module_qualification() -> None:
    handoff = _text_handoff(
        "unsafe { intrin_compose<add, prefix=p>(left, right) }",
        backend="rust",
    )
    request = _single_compose_request(handoff)
    context = _rust_context(
        handoff=handoff,
        rust_architecture_module=RustArchitectureModule("x86_64"),
        translated_modifiers=(
            _translated(
                _field(request, "prefix"),
                BackendIntrinsicLiteralFragment("_mm256_"),
                backend="rust",
            ),
        ),
    )

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.diagnostics == ()
    assert result.body_text is not None
    assert result.body_text.text == (
        "unsafe { core::arch::x86_64::_mm256_add_ps(left, right) }"
    )


def test_m247_diagnoses_missing_selected_context_only_when_default_policy_is_needed() -> None:
    explicit_handoff = _text_handoff(
        "intrin_compose<add, prefix=p, suffix=s>(left, right)"
    )
    explicit_request = _single_compose_request(explicit_handoff)
    explicit_context = _cpp_context(
        handoff=explicit_handoff,
        selected_implementation=None,
        translated_modifiers=(
            _translated(
                _field(explicit_request, "prefix"),
                BackendIntrinsicLiteralFragment("_mm256_"),
            ),
            _translated(
                _field(explicit_request, "suffix"),
                BackendIntrinsicLiteralFragment("epi32"),
            ),
        ),
    )
    explicit_result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        explicit_context,
    )

    missing_context_result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        _cpp_context("intrin_compose<add>(left, right)", selected_implementation=None),
    )

    assert explicit_result.diagnostics == ()
    assert missing_context_result.artifacts.artifacts == ()
    assert _codes(missing_context_result.diagnostics) == (
        "TSL-INTRINSIC-BODY-TOKEN-BRIDGE-MISSING-SELECTED-IMPLEMENTATION-CONTEXT",
    )


def test_m247_diagnoses_missing_extension_catalog_in_selected_context() -> None:
    context = _cpp_context(
        "intrin_compose<add>(left, right)",
        selected_implementation=_selected_render_context(extension_catalog=None),
    )

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.artifacts.artifacts == ()
    assert _codes(result.diagnostics) == (
        "TSL-INTRINSIC-BODY-TOKEN-BRIDGE-MISSING-EXTENSION-CATALOG",
    )


def test_m247_forwards_default_policy_resolution_diagnostics() -> None:
    missing_policy = _cpp_context(
        "intrin_compose<add>(left, right)",
        selected_implementation=_selected_render_context(extension="scalar"),
    )
    unknown_extension = _cpp_context(
        "intrin_compose<add>(left, right)",
        selected_implementation=_selected_render_context(extension="missing"),
    )
    missing_backend_prefix = _rust_context(
        "unsafe { intrin_compose<add>(left, right) }",
        selected_implementation=_selected_render_context(
            backend="rust",
            extension="custom",
            type_tag="si32",
            extension_catalog=_extension_catalog_missing_rust_prefix(),
        ),
    )
    missing_suffix = _cpp_context(
        "intrin_compose<add>(left, right)",
        selected_implementation=_selected_render_context(type_tag="bool"),
    )

    policy_result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        missing_policy,
    )
    unknown_result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        unknown_extension,
    )
    prefix_result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        missing_backend_prefix,
    )
    suffix_result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        missing_suffix,
    )

    assert _codes(policy_result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-POLICY",
    )
    assert _codes(unknown_result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-UNKNOWN-EXTENSION",
    )
    assert _codes(prefix_result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-BACKEND-PREFIX",
    )
    assert _codes(suffix_result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-TYPE-SUFFIX",
    )


def test_m247_diagnoses_selected_context_backend_mismatch() -> None:
    context = _cpp_context(
        "intrin_compose<add>(left, right)",
        selected_implementation=_selected_render_context(backend="rust"),
    )

    result = render_intrinsic_body_token_profile_artifact(
        SUPPLEMENTARY_ROOT,
        context,
    )

    assert result.artifacts.artifacts == ()
    assert _codes(result.diagnostics) == (
        "TSL-INTRINSIC-BODY-TOKEN-BRIDGE-SELECTED-CONTEXT-BACKEND-MISMATCH",
    )


def _cpp_context(
    text: str | None = None,
    *,
    handoff: BackendIntrinsicHandoff | None = None,
    selected_implementation: SelectedImplementationRenderContext | object | None = (
        _DEFAULT_SELECTED_CONTEXT
    ),
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...] = (),
) -> IntrinsicBodyTokenProfileRenderContext:
    selected = (
        _selected_render_context()
        if selected_implementation is _DEFAULT_SELECTED_CONTEXT
        else selected_implementation
    )
    return IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("cpp"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/avx2.hpp"),
        profile_name=PrimitiveProfileName("avx2"),
        handoff=handoff or _text_handoff(text or "intrin_compose<add>(left, right)"),
        function_name=PrimitiveFunctionNameText("add_avx2_f32"),
        result_type=PrimitiveFunctionResultTypeText("__m256"),
        parameters=PrimitiveFunctionParameterListText("__m256 left, __m256 right"),
        translated_modifiers=translated_modifiers,
        includes=(RenderedIncludeLine("#include <immintrin.h>"),),
        namespace_open=RenderedNamespaceText("namespace tsl::profiles::avx2 {"),
        namespace_close=RenderedNamespaceText("}  // namespace tsl::profiles::avx2"),
        selected_implementation=selected,
    )


def _rust_context(
    text: str | None = None,
    *,
    handoff: BackendIntrinsicHandoff | None = None,
    selected_implementation: SelectedImplementationRenderContext | object | None = (
        _DEFAULT_SELECTED_CONTEXT
    ),
    rust_architecture_module: RustArchitectureModule | None = None,
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...] = (),
) -> IntrinsicBodyTokenProfileRenderContext:
    selected = (
        _selected_render_context(backend="rust")
        if selected_implementation is _DEFAULT_SELECTED_CONTEXT
        else selected_implementation
    )
    return IntrinsicBodyTokenProfileRenderContext(
        backend_id=PrimitiveBackendId("rust"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/avx2.rs"),
        profile_name=PrimitiveProfileName("avx2"),
        handoff=handoff
        or _text_handoff(
            text or "unsafe { intrin_compose<add>(left, right) }",
            backend="rust",
        ),
        function_name=PrimitiveFunctionNameText("add_avx2_f32"),
        result_type=PrimitiveFunctionResultTypeText("core::arch::x86_64::__m256"),
        parameters=PrimitiveFunctionParameterListText(
            "left: core::arch::x86_64::__m256, "
            "right: core::arch::x86_64::__m256"
        ),
        translated_modifiers=translated_modifiers,
        rust_architecture_module=rust_architecture_module,
        selected_implementation=selected,
    )


def _selected_render_context(
    *,
    backend: str = "cpp",
    extension: str = "avx2",
    type_tag: str = "f32",
    extension_catalog: ExtensionCatalog | object | None = _DEFAULT_EXTENSION_CATALOG,
) -> SelectedImplementationRenderContext:
    catalog = (
        _extension_catalog()
        if extension_catalog is _DEFAULT_EXTENSION_CATALOG
        else extension_catalog
    )
    return SelectedImplementationRenderContext(
        backend_id=PrimitiveBackendId(backend),
        extension=ExtensionName(extension),
        type_tag=TypeTag(type_tag),
        extension_catalog=catalog,
    )


def _text_handoff(
    text: str,
    *,
    backend: str = "cpp",
) -> BackendIntrinsicHandoff:
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_intrinsic_discovery(
        _selected(backend),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    return result.handoff


def _single_compose_request(
    handoff: BackendIntrinsicHandoff,
) -> BackendIntrinsicComposeHandoffRequest:
    segments = tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    )
    assert len(segments) == 1
    request = segments[0].request
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    return request


def _selected(backend: str) -> SelectedImplementation:
    source = _location()
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="unknown",
        implementations=(implementation,),
        source=source,
    )
    target = Target(
        backend=backend,
        primitive_name="fixture",
        extension="generic",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _translated(
    field: BackendIntrinsicModifierField,
    value: object,
    *,
    backend: str = "cpp",
) -> BackendTranslatedIntrinsicModifier:
    return BackendTranslatedIntrinsicModifier(
        backend=BackendId(backend),
        field=field,
        name=field.name,
        value=value,
        source=field.source,
    )


def _field(
    request: BackendIntrinsicComposeHandoffRequest,
    name: str,
) -> BackendIntrinsicModifierField:
    matches = tuple(field for field in request.modifiers if field.name == name)
    assert len(matches) == 1
    return matches[0]


def _extension_catalog() -> ExtensionCatalog:
    return _catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL).extensions


def _extension_catalog_missing_rust_prefix() -> ExtensionCatalog:
    return _catalog_from_texts(
        _types_text(),
        (
            "extension.tsl",
            """extension custom:
  extension_name "custom"
  intrinsic_compose:
    prefix:
      cpp "custom_"
    suffix:
      by_type:
        si32 "i32"
""",
        ),
    ).extensions


def _catalog_from_paths(*paths: Path) -> Catalog:
    source_result = SourceLoader().load(tuple(paths))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _catalog_from_texts(*documents: tuple[str, str]) -> Catalog:
    sources = tuple(
        SourceDocument(
            path=Path(name),
            text=text,
            digest="",
            kind="tsl",
        )
        for name, text in documents
    )
    parse_result = TslParser().parse(sources)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _types_text() -> tuple[str, str]:
    return (
        "types.tsl",
        """types:
  si32 {types [si32]}
""",
    )


def _codes(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
