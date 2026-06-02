from __future__ import annotations

from tslgen.rendering import (
    BackendPrimitiveRenderModel,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileName,
    PrimitiveRenderContextAdaptationResult,
    PrimitiveRenderRecord,
    PrimitiveRenderSortKey,
    PrimitiveTemplateRenderContext,
    ProjectSkeletonRenderContext,
    RawTsilPrimitiveRenderValue,
    RenderedImportLine,
    RenderedIncludeLine,
    RenderedModuleText,
    RenderedNamespaceText,
    RenderedPrimitiveBodyText,
    RenderedPrimitiveDeclarationText,
    RenderedPrimitiveDefinitionText,
    UnresolvedPrimitiveRenderValue,
    adapt_primitive_render_models,
    cpp_primitive_render_model,
    rust_primitive_render_model,
)


def test_m218_adapts_cpp_primitive_render_model_to_template_context() -> None:
    model = cpp_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        profile_name=PrimitiveProfileName("scalar"),
        includes=(RenderedIncludeLine("#include <cstdint>"),),
        namespace_open=RenderedNamespaceText("namespace tsl {"),
        namespace_close=RenderedNamespaceText("}  // namespace tsl"),
        primitives=(
            PrimitiveRenderRecord(
                sort_key=PrimitiveRenderSortKey("add"),
                declarations=(
                    RenderedPrimitiveDeclarationText(
                        "inline std::int32_t add(std::int32_t left, "
                        "std::int32_t right);"
                    ),
                ),
                definitions=(
                    RenderedPrimitiveDefinitionText(
                        "inline std::int32_t add(std::int32_t left, "
                        "std::int32_t right) {\n"
                        "  return left + right;\n"
                        "}"
                    ),
                ),
                body_text=RenderedPrimitiveBodyText("return left + right;"),
            ),
        ),
    )

    result = adapt_primitive_render_models((model,))

    assert result.diagnostics == ()
    context = result.contexts[0]
    assert isinstance(context, PrimitiveTemplateRenderContext)
    assert context.backend_id == "cpp"
    assert context.logical_path == "cpp/include/profiles/scalar.hpp"
    assert context.profile_name == "scalar"
    assert context.includes == ("#include <cstdint>",)
    assert context.namespace_open == "namespace tsl {"
    assert context.namespace_close == "}  // namespace tsl"
    assert context.primitive_declarations == (
        "inline std::int32_t add(std::int32_t left, std::int32_t right);",
    )
    assert "return left + right;" in context.primitive_definitions[0]
    assert context.rendered_body_text == "return left + right;"


def test_m218_adapts_rust_primitive_render_model_to_template_context() -> None:
    model = rust_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        profile_name=PrimitiveProfileName("scalar"),
        imports=(RenderedImportLine("use core::primitive::i32;"),),
        module_open=RenderedModuleText("pub mod scalar {"),
        module_close=RenderedModuleText("}"),
        primitives=(
            PrimitiveRenderRecord(
                sort_key=PrimitiveRenderSortKey("add"),
                definitions=(
                    RenderedPrimitiveDefinitionText(
                        "pub fn add(left: i32, right: i32) -> i32 {\n"
                        "    left + right\n"
                        "}"
                    ),
                ),
                body_text=RenderedPrimitiveBodyText("left + right"),
            ),
        ),
    )

    result = adapt_primitive_render_models((model,))

    assert result.diagnostics == ()
    context = result.contexts[0]
    assert context.backend_id == "rust"
    assert context.logical_path == "rust/src/profiles/scalar.rs"
    assert context.profile_name == "scalar"
    assert context.imports == ("use core::primitive::i32;",)
    assert context.module_open == "pub mod scalar {"
    assert context.module_close == "}"
    assert context.primitive_declarations == ()
    assert "pub fn add(left: i32, right: i32) -> i32" in (
        context.primitive_definitions[0]
    )
    assert context.rendered_body_text == "left + right"


def test_m218_primitive_records_are_adapted_in_deterministic_order() -> None:
    model = cpp_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        profile_name=PrimitiveProfileName("scalar"),
        primitives=(
            PrimitiveRenderRecord(
                sort_key=PrimitiveRenderSortKey("z"),
                declarations=(RenderedPrimitiveDeclarationText("int z();"),),
                definitions=(RenderedPrimitiveDefinitionText("int z() { return 2; }"),),
                body_text=RenderedPrimitiveBodyText("return 2;"),
            ),
            PrimitiveRenderRecord(
                sort_key=PrimitiveRenderSortKey("a"),
                declarations=(RenderedPrimitiveDeclarationText("int a();"),),
                definitions=(RenderedPrimitiveDefinitionText("int a() { return 1; }"),),
                body_text=RenderedPrimitiveBodyText("return 1;"),
            ),
        ),
    )

    result = adapt_primitive_render_models((model,))

    assert result.diagnostics == ()
    context = result.contexts[0]
    assert context.primitive_declarations == ("int a();", "int z();")
    assert context.primitive_definitions == (
        "int a() { return 1; }",
        "int z() { return 2; }",
    )
    assert context.rendered_body_text == "return 1;\n\nreturn 2;"


def test_m218_backend_contexts_are_adapted_in_artifact_path_order() -> None:
    rust = rust_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        profile_name=PrimitiveProfileName("scalar"),
    )
    cpp = cpp_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        profile_name=PrimitiveProfileName("scalar"),
    )

    result = adapt_primitive_render_models((rust, cpp))

    assert result.diagnostics == ()
    assert [(context.backend_id, context.logical_path) for context in result.contexts] == [
        ("cpp", "cpp/include/profiles/scalar.hpp"),
        ("rust", "rust/src/profiles/scalar.rs"),
    ]
    assert [context.profile_name for context in result.contexts] == [
        "scalar",
        "scalar",
    ]


def test_m218_primitive_render_context_is_not_skeleton_context() -> None:
    model = cpp_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        profile_name=PrimitiveProfileName("scalar"),
    )

    result = adapt_primitive_render_models((model,))

    assert result.diagnostics == ()
    context = result.contexts[0]
    assert isinstance(context, PrimitiveTemplateRenderContext)
    assert not isinstance(context, ProjectSkeletonRenderContext)


def test_m218_raw_tsil_values_are_diagnostic_boundaries() -> None:
    model = cpp_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        profile_name=PrimitiveProfileName("scalar"),
        primitives=(
            PrimitiveRenderRecord(
                sort_key=PrimitiveRenderSortKey("bad"),
                definitions=(RawTsilPrimitiveRenderValue("tsil \"emit_return(x);\""),),
            ),
        ),
    )

    result = adapt_primitive_render_models((model,))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-CONTEXT-RAW-TSIL",
    ]
    assert "raw TSIL/source text" in result.diagnostics[0].message


def test_m218_unresolved_values_are_diagnostic_boundaries() -> None:
    model = rust_primitive_render_model(
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        profile_name=PrimitiveProfileName("scalar"),
        primitives=(
            PrimitiveRenderRecord(
                sort_key=PrimitiveRenderSortKey("bad"),
                body_text=UnresolvedPrimitiveRenderValue("BackendValueRequest(...)"),
            ),
        ),
    )

    result = adapt_primitive_render_models((model,))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-CONTEXT-UNRESOLVED-VALUE",
    ]
    assert "unresolved semantic value" in result.diagnostics[0].message


def test_m218_wrong_backend_presentation_field_is_diagnostic() -> None:
    rust_model = BackendPrimitiveRenderModel(
        backend_id=PrimitiveBackendId("rust"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        profile_name=PrimitiveProfileName("scalar"),
        includes=(RenderedIncludeLine("#include <cstdint>"),),
    )
    cpp_model = BackendPrimitiveRenderModel(
        backend_id=PrimitiveBackendId("cpp"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        profile_name=PrimitiveProfileName("scalar"),
        imports=(RenderedImportLine("use core::primitive::i32;"),),
    )

    result = adapt_primitive_render_models((rust_model, cpp_model))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-CONTEXT-UNSUPPORTED-BACKEND-FIELD",
        "TSL-PRIMITIVE-RENDER-CONTEXT-UNSUPPORTED-BACKEND-FIELD",
    ]
    assert [diagnostic.message for diagnostic in result.diagnostics] == [
        "primitive render backend 'cpp' does not consume field 'imports'",
        "primitive render backend 'rust' does not consume field 'includes'",
    ]


def test_m218_public_rendering_imports_are_stable() -> None:
    from tslgen.rendering import (  # noqa: PLC0415
        RenderedPrimitiveDefinitionText,
        adapt_primitive_render_models,
    )

    assert RenderedPrimitiveDefinitionText.__name__ == (
        "RenderedPrimitiveDefinitionText"
    )
    assert PrimitiveRenderContextAdaptationResult.__name__ == (
        "PrimitiveRenderContextAdaptationResult"
    )
    assert callable(adapt_primitive_render_models)
