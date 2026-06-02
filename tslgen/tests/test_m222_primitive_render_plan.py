from __future__ import annotations

from tslgen.rendering import (
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileName,
    PrimitiveRenderPlan,
    PrimitiveRenderPlanAdaptationResult,
    PrimitiveRenderPlanPrimitiveId,
    PrimitiveRenderPlanRecord,
    PrimitiveRenderPlanSource,
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
    adapt_primitive_render_plans,
)


def test_m222_adapts_cpp_plan_to_m218_template_context() -> None:
    plan = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        includes=(RenderedIncludeLine("#include <cstdint>"),),
        namespace_open=RenderedNamespaceText("namespace tsl {"),
        namespace_close=RenderedNamespaceText("}  // namespace tsl"),
        source=PrimitiveRenderPlanSource("selected:add/scalar"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("add.si32"),
                presentation_sort_key=PrimitiveRenderSortKey("z-presentation"),
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
                source=PrimitiveRenderPlanSource("body:add.si32"),
            ),
        ),
    )

    result = adapt_primitive_render_plans((plan,))

    assert result.diagnostics == ()
    assert result.plans[0].source == PrimitiveRenderPlanSource("selected:add/scalar")
    assert result.plans[0].primitives[0].source == (
        PrimitiveRenderPlanSource("body:add.si32")
    )
    assert result.models[0].backend_id == PrimitiveBackendId("cpp")
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


def test_m222_adapts_rust_plan_to_m218_template_context() -> None:
    plan = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("rust"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        imports=(RenderedImportLine("use core::primitive::i32;"),),
        module_open=RenderedModuleText("pub mod scalar {"),
        module_close=RenderedModuleText("}"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("add.si32"),
                presentation_sort_key=PrimitiveRenderSortKey("add"),
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

    result = adapt_primitive_render_plans((plan,))

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


def test_m222_preserves_supplied_primitive_order_not_presentation_sort_key() -> None:
    plan = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("z-first"),
                presentation_sort_key=PrimitiveRenderSortKey("z"),
                declarations=(RenderedPrimitiveDeclarationText("int z_first();"),),
                definitions=(
                    RenderedPrimitiveDefinitionText("int z_first() { return 2; }"),
                ),
                body_text=RenderedPrimitiveBodyText("return 2;"),
            ),
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("a-second"),
                presentation_sort_key=PrimitiveRenderSortKey("a"),
                declarations=(RenderedPrimitiveDeclarationText("int a_second();"),),
                definitions=(
                    RenderedPrimitiveDefinitionText("int a_second() { return 1; }"),
                ),
                body_text=RenderedPrimitiveBodyText("return 1;"),
            ),
        ),
    )

    result = adapt_primitive_render_plans((plan,))

    assert result.diagnostics == ()
    context = result.contexts[0]
    assert context.primitive_declarations == ("int z_first();", "int a_second();")
    assert context.primitive_definitions == (
        "int z_first() { return 2; }",
        "int a_second() { return 1; }",
    )
    assert context.rendered_body_text == "return 2;\n\nreturn 1;"


def test_m222_orders_multiple_plan_contexts_deterministically() -> None:
    rust = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("rust"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
    )
    cpp = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
    )

    result = adapt_primitive_render_plans((rust, cpp))

    assert result.diagnostics == ()
    assert [(plan.backend_id.text, plan.logical_path.text) for plan in result.plans] == [
        ("cpp", "cpp/include/profiles/scalar.hpp"),
        ("rust", "rust/src/profiles/scalar.rs"),
    ]
    assert [
        (context.backend_id, context.logical_path) for context in result.contexts
    ] == [
        ("cpp", "cpp/include/profiles/scalar.hpp"),
        ("rust", "rust/src/profiles/scalar.rs"),
    ]


def test_m222_unsupported_backend_id_is_diagnostic() -> None:
    plan = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("c"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("c/include/profiles/scalar.h"),
    )

    result = adapt_primitive_render_plans((plan,))

    assert result.plans == ()
    assert result.models == ()
    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-PLAN-UNKNOWN-BACKEND",
    ]
    assert "unsupported primitive render plan backend 'c'" in (
        result.diagnostics[0].message
    )


def test_m222_wrong_backend_context_fields_are_diagnostic() -> None:
    cpp = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        imports=(RenderedImportLine("use core::primitive::i32;"),),
    )
    rust = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("rust"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        includes=(RenderedIncludeLine("#include <cstdint>"),),
    )

    result = adapt_primitive_render_plans((rust, cpp))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-PLAN-WRONG-BACKEND-FIELD",
        "TSL-PRIMITIVE-RENDER-PLAN-WRONG-BACKEND-FIELD",
    ]
    assert [diagnostic.message for diagnostic in result.diagnostics] == [
        "primitive render plan backend 'cpp' does not consume field 'imports'",
        "primitive render plan backend 'rust' does not consume field 'includes'",
    ]


def test_m222_duplicate_plan_identity_is_diagnostic() -> None:
    first = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
    )
    second = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
    )

    result = adapt_primitive_render_plans((first, second))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-PLAN-DUPLICATE-PLAN",
    ]
    assert "duplicate primitive render plan" in result.diagnostics[0].message


def test_m222_duplicate_primitive_identity_is_diagnostic() -> None:
    plan = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("rust"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("id"),
                presentation_sort_key=PrimitiveRenderSortKey("a"),
            ),
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("id"),
                presentation_sort_key=PrimitiveRenderSortKey("b"),
            ),
        ),
    )

    result = adapt_primitive_render_plans((plan,))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-PLAN-DUPLICATE-PRIMITIVE",
    ]
    assert "duplicate primitive render record 'id'" in result.diagnostics[0].message


def test_m222_raw_tsil_and_unresolved_values_are_diagnostic_boundaries() -> None:
    cpp = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("raw"),
                presentation_sort_key=PrimitiveRenderSortKey("raw"),
                definitions=(RawTsilPrimitiveRenderValue('tsil "emit_return(x);"'),),
            ),
        ),
    )
    rust = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("rust"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("unresolved"),
                presentation_sort_key=PrimitiveRenderSortKey("unresolved"),
                body_text=UnresolvedPrimitiveRenderValue("BackendValueRequest(...)"),
            ),
        ),
    )

    result = adapt_primitive_render_plans((cpp, rust))

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-RENDER-CONTEXT-RAW-TSIL",
        "TSL-PRIMITIVE-RENDER-CONTEXT-UNRESOLVED-VALUE",
    ]


def test_m222_primitive_plan_context_is_not_skeleton_context() -> None:
    plan = PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
    )

    result = adapt_primitive_render_plans((plan,))

    assert result.diagnostics == ()
    context = result.contexts[0]
    assert isinstance(context, PrimitiveTemplateRenderContext)
    assert not isinstance(context, ProjectSkeletonRenderContext)
    assert "primitive_definitions" in context.format_values()
    assert "project_name" not in context.format_values()


def test_m222_public_rendering_imports_are_stable() -> None:
    from tslgen.rendering import (  # noqa: PLC0415
        PrimitiveRenderPlan,
        PrimitiveRenderPlanAdaptationResult,
        adapt_primitive_render_plans,
    )

    assert PrimitiveRenderPlan.__name__ == "PrimitiveRenderPlan"
    assert PrimitiveRenderPlanAdaptationResult.__name__ == (
        "PrimitiveRenderPlanAdaptationResult"
    )
    assert callable(adapt_primitive_render_plans)
