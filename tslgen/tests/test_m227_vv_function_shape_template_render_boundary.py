from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.signatures import SignatureTermKind, parse_primitive_signature
from tslgen.io.artifacts import Artifact, ArtifactSet
from tslgen.io.sources import SourceDocument
from tslgen.pipeline import build_parsed_tiny_generated_project_artifacts
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering import (
    PrimitiveBackendId,
    PrimitiveFunctionBodyText,
    PrimitiveFunctionNameText,
    PrimitiveFunctionParameterListText,
    PrimitiveFunctionResultTypeText,
    PrimitiveFunctionShapeRenderContext,
    V_ASSIGN_V_V_FUNCTION_SHAPE,
    build_generated_project_render_model,
    compose_generated_primitive_project_artifacts,
    render_generated_project_skeleton,
    render_primitive_function_shape,
    selected_profile_replacement_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"


def test_m227_parsed_lowering_carries_vv_signature_shape_to_render_plan(
    tmp_path: Path,
) -> None:
    result = build_parsed_tiny_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=(_tiny_add_document(tmp_path),),
        targets=_targets("add"),
        machine_profiles=_catalog(),
    )

    assert result.diagnostics == ()
    assert len(result.lowered_functions.functions) == 2
    assert all(
        function.signature.signature_shape is not None
        for function in result.lowered_functions.functions
    )
    assert {
        function.signature.signature_shape.source_text
        for function in result.lowered_functions.functions
        if function.signature.signature_shape is not None
    } == {"v:=(v,v)"}
    assert all(
        function.signature.signature_shape.result.kind is SignatureTermKind.VECTOR
        for function in result.lowered_functions.functions
        if function.signature.signature_shape is not None
    )
    assert tuple(plan.logical_path.text for plan in result.render_plans) == (
        "cpp/include/profiles/scalar.hpp",
        "rust/src/profiles/scalar.rs",
    )

    by_path = _artifact_content_by_path(result.artifacts)
    assert "inline std::int32_t add_scalar_si32" in by_path[
        "cpp/include/profiles/scalar.hpp"
    ]
    assert "return left + right;" in by_path["cpp/include/profiles/scalar.hpp"]
    assert "pub fn add_scalar_si32(left: i32, right: i32) -> i32" in by_path[
        "rust/src/profiles/scalar.rs"
    ]
    assert "    left + right" in by_path["rust/src/profiles/scalar.rs"]


def test_m227_shape_templates_render_cpp_and_rust_function_definitions() -> None:
    cpp = render_primitive_function_shape(
        _SUPPLEMENTARY_ROOT,
        PrimitiveFunctionShapeRenderContext(
            backend_id=PrimitiveBackendId("cpp"),
            shape_key=V_ASSIGN_V_V_FUNCTION_SHAPE,
            function_name=PrimitiveFunctionNameText("add_scalar_si32"),
            result_type=PrimitiveFunctionResultTypeText("std::int32_t"),
            parameters=PrimitiveFunctionParameterListText(
                "std::int32_t left, std::int32_t right"
            ),
            body_text=PrimitiveFunctionBodyText("left + right"),
        ),
    )
    rust = render_primitive_function_shape(
        _SUPPLEMENTARY_ROOT,
        PrimitiveFunctionShapeRenderContext(
            backend_id=PrimitiveBackendId("rust"),
            shape_key=V_ASSIGN_V_V_FUNCTION_SHAPE,
            function_name=PrimitiveFunctionNameText("add_scalar_si32"),
            result_type=PrimitiveFunctionResultTypeText("i32"),
            parameters=PrimitiveFunctionParameterListText("left: i32, right: i32"),
            body_text=PrimitiveFunctionBodyText("left + right"),
        ),
    )

    assert cpp.diagnostics == ()
    assert cpp.definition is not None
    assert cpp.definition.text == (
        "inline std::int32_t add_scalar_si32"
        "(std::int32_t left, std::int32_t right) {\n"
        "  return left + right;\n"
        "}\n"
    )
    assert rust.diagnostics == ()
    assert rust.definition is not None
    assert rust.definition.text == (
        "pub fn add_scalar_si32(left: i32, right: i32) -> i32 {\n"
        "    left + right\n"
        "}\n"
    )


def test_m227_unsupported_signature_shape_diagnoses_before_rendering(
    tmp_path: Path,
) -> None:
    result = build_parsed_tiny_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=(_tiny_neg_document(tmp_path),),
        targets=_targets("neg"),
        machine_profiles=_catalog(),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-FUNCTION-SHAPE-UNSUPPORTED-SIGNATURE",
        "TSL-PRIMITIVE-FUNCTION-SHAPE-UNSUPPORTED-SIGNATURE",
    ]
    assert all("v:=(v,v)" in diagnostic.message for diagnostic in result.diagnostics)


def test_m227_shape_template_rejects_semantic_fields(tmp_path: Path) -> None:
    source = SourceLocation(Path("fixture.tsl"), 1, 1)
    signature = parse_primitive_signature("v:=(v,v)", source).signature
    assert signature is not None

    root = tmp_path
    template = root / "templates" / "cpp" / "shapes" / "v_assign_v_v.hpp.in"
    template.parent.mkdir(parents=True)
    template.write_text("{primitive_name}\n{tsil}\n", encoding="utf-8")

    result = render_primitive_function_shape(
        root,
        PrimitiveFunctionShapeRenderContext(
            backend_id=PrimitiveBackendId("cpp"),
            shape_key=V_ASSIGN_V_V_FUNCTION_SHAPE,
            function_name=PrimitiveFunctionNameText("add_scalar_si32"),
            result_type=PrimitiveFunctionResultTypeText("std::int32_t"),
            parameters=PrimitiveFunctionParameterListText(
                "std::int32_t left, std::int32_t right"
            ),
            body_text=PrimitiveFunctionBodyText("left + right"),
        ),
    )

    assert result.definition is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-FUNCTION-SHAPE-TEMPLATE-SEMANTIC-FIELD",
        "TSL-PRIMITIVE-FUNCTION-SHAPE-TEMPLATE-SEMANTIC-FIELD",
    ]
    assert "primitive_name" in result.diagnostics[0].message
    assert "tsil" in result.diagnostics[1].message


def test_m227_selected_profile_replacement_policy_covers_avx2() -> None:
    model = _model_for_profiles(("scalar", "avx2"))
    skeleton = render_generated_project_skeleton(_SUPPLEMENTARY_ROOT, model)
    assert skeleton.diagnostics == ()
    primitives = ArtifactSet.create(
        (
            _artifact("cpp/include/profiles/scalar.hpp", "cpp scalar\n"),
            _artifact("cpp/include/profiles/avx2.hpp", "cpp avx2\n"),
            _artifact("rust/src/profiles/scalar.rs", "rust scalar\n"),
            _artifact("rust/src/profiles/avx2.rs", "rust avx2\n"),
        )
    )

    first = compose_generated_primitive_project_artifacts(
        skeleton.artifacts,
        primitives,
        selected_profile_replacement_policy(model),
    )
    second = compose_generated_primitive_project_artifacts(
        skeleton.artifacts,
        primitives,
        selected_profile_replacement_policy(model),
    )

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
    by_path = _artifact_content_by_path(first.artifacts)
    assert by_path["cpp/include/profiles/scalar.hpp"] == "cpp scalar\n"
    assert by_path["cpp/include/profiles/avx2.hpp"] == "cpp avx2\n"
    assert by_path["rust/src/profiles/scalar.rs"] == "rust scalar\n"
    assert by_path["rust/src/profiles/avx2.rs"] == "rust avx2\n"


def _tiny_add_document(tmp_path: Path) -> SourceDocument:
    return _source_document(
        tmp_path,
        "add_si32.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                "    body add(left, right)",
                "",
            )
        ),
    )


def _tiny_neg_document(tmp_path: Path) -> SourceDocument:
    return _source_document(
        tmp_path,
        "neg_si32.tsl",
        "\n".join(
            (
                "prim<v:=(v)> neg(value):",
                "  implementation scalar si32:",
                "    body neg(value)",
                "",
            )
        ),
    )


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    return SourceDocument(
        path=path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def _targets(primitive_name: str) -> tuple[Target, ...]:
    return (
        Target(
            backend="cpp",
            primitive_name=primitive_name,
            extension="scalar",
            type_tag="si32",
        ),
        Target(
            backend="rust",
            primitive_name=primitive_name,
            extension="scalar",
            type_tag="si32",
        ),
    )


def _catalog():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _model_for_profiles(profiles: tuple[str, ...]):
    catalog_result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    assert catalog_result.flag_catalog is not None
    selection = select_generated_profiles(catalog_result.catalog, profiles)
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    model_result = build_generated_project_render_model(
        selection.profile_set,
        catalog_result.flag_catalog,
    )
    assert model_result.diagnostics == ()
    assert model_result.model is not None
    return model_result.model


def _artifact(path: str, content: str) -> Artifact:
    return Artifact(
        logical_path=path,
        content=content,
        media_type="text/plain",
        metadata=(),
    )


def _artifact_content_by_path(artifacts: ArtifactSet) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in artifacts.artifacts
    }
