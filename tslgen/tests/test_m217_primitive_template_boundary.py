from __future__ import annotations

from pathlib import Path

from tslgen.rendering import (
    PrimitiveTemplateRenderContext,
    ProjectSkeletonRenderContext,
    cpp_primitive_template_context,
    render_primitive_templates,
    rust_primitive_template_context,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"


def test_m217_renders_minimal_cpp_primitive_template_artifact() -> None:
    context = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
        includes=("#include <cstdint>",),
        namespace_open="namespace tsl {",
        primitive_definitions=(
            "inline std::int32_t add(std::int32_t left, std::int32_t right) {\n"
            "  return left + right;\n"
            "}",
        ),
        namespace_close="}  // namespace tsl",
    )

    result = render_primitive_templates(_SUPPLEMENTARY_ROOT, (context,))

    assert result.diagnostics == ()
    artifact = result.artifacts.artifacts[0]
    assert artifact.logical_path == "cpp/include/profiles/scalar.hpp"
    assert artifact.media_type == "text/x-c++hdr"
    assert "#include <cstdint>" in artifact.content
    assert "namespace tsl {" in artifact.content
    assert "inline std::int32_t add" in artifact.content
    assert "return left + right;" in artifact.content
    assert artifact.metadata[0].key == "backend"
    assert artifact.metadata[0].value == "cpp"


def test_m217_renders_minimal_rust_primitive_template_artifact() -> None:
    context = rust_primitive_template_context(
        logical_path="rust/src/profiles/scalar.rs",
        profile_name="scalar",
        imports=("use core::primitive::i32;",),
        primitive_definitions=(
            "pub fn add(left: i32, right: i32) -> i32 {\n"
            "    left + right\n"
            "}",
        ),
    )

    result = render_primitive_templates(_SUPPLEMENTARY_ROOT, (context,))

    assert result.diagnostics == ()
    artifact = result.artifacts.artifacts[0]
    assert artifact.logical_path == "rust/src/profiles/scalar.rs"
    assert artifact.media_type == "text/x-rust"
    assert "use core::primitive::i32;" in artifact.content
    assert "pub fn add(left: i32, right: i32) -> i32" in artifact.content
    assert "left + right" in artifact.content
    assert artifact.metadata[0].key == "backend"
    assert artifact.metadata[0].value == "rust"


def test_m217_artifact_order_is_deterministic_for_both_backends() -> None:
    rust = rust_primitive_template_context(
        logical_path="rust/src/profiles/scalar.rs",
        profile_name="scalar",
        primitive_definitions=("pub fn id(value: i32) -> i32 { value }",),
    )
    cpp = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
        primitive_definitions=("inline int id(int value) { return value; }",),
    )

    first = render_primitive_templates(_SUPPLEMENTARY_ROOT, (rust, cpp))
    second = render_primitive_templates(_SUPPLEMENTARY_ROOT, (rust, cpp))

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert [artifact.logical_path for artifact in first.artifacts.artifacts] == [
        "cpp/include/profiles/scalar.hpp",
        "rust/src/profiles/scalar.rs",
    ]
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m217_missing_cpp_template_is_diagnostic(tmp_path: Path) -> None:
    context = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
        primitive_definitions=("inline int id(int value) { return value; }",),
    )

    result = render_primitive_templates(tmp_path, (context,))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-TEMPLATE-MISSING-TEMPLATE",
    ]
    assert "templates/cpp/primitive.hpp.in" in result.diagnostics[0].message


def test_m217_missing_rust_template_is_diagnostic(tmp_path: Path) -> None:
    context = rust_primitive_template_context(
        logical_path="rust/src/profiles/scalar.rs",
        profile_name="scalar",
        primitive_definitions=("pub fn id(value: i32) -> i32 { value }",),
    )

    result = render_primitive_templates(tmp_path, (context,))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-TEMPLATE-MISSING-TEMPLATE",
    ]
    assert "templates/rust/primitive.rs.in" in result.diagnostics[0].message


def test_m217_unknown_template_field_is_diagnostic(tmp_path: Path) -> None:
    root = _root_with_cpp_template(tmp_path, "{project_name}\n")
    context = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
    )

    result = render_primitive_templates(root, (context,))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-TEMPLATE-UNKNOWN-FIELD",
    ]
    assert "project_name" in result.diagnostics[0].message


def test_m217_compound_template_field_is_diagnostic(tmp_path: Path) -> None:
    root = _root_with_cpp_template(tmp_path, "{includes[0]}\n")
    context = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
        includes=("#include <cstdint>",),
    )

    result = render_primitive_templates(root, (context,))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-TEMPLATE-UNSUPPORTED-FIELD-SHAPE",
    ]
    assert "includes[0]" in result.diagnostics[0].message


def test_m217_semantic_template_field_is_diagnostic(tmp_path: Path) -> None:
    root = _root_with_cpp_template(tmp_path, "{tsil}\n{primitive_name}\n")
    context = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
    )

    result = render_primitive_templates(root, (context,))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-TEMPLATE-SEMANTIC-FIELD",
        "TSL-PRIMITIVE-TEMPLATE-SEMANTIC-FIELD",
    ]
    assert "primitive_name" in result.diagnostics[0].message
    assert "tsil" in result.diagnostics[1].message


def test_m217_primitive_context_is_not_project_skeleton_context() -> None:
    context = cpp_primitive_template_context(
        logical_path="cpp/include/profiles/scalar.hpp",
        profile_name="scalar",
        primitive_definitions=("inline int id(int value) { return value; }",),
    )

    assert isinstance(context, PrimitiveTemplateRenderContext)
    assert not isinstance(context, ProjectSkeletonRenderContext)
    values = context.format_values()
    assert "primitive_definitions" in values
    assert "project_name" not in values


def test_m217_public_rendering_imports_are_stable() -> None:
    from tslgen.rendering import (  # noqa: PLC0415
        CPP_PRIMITIVE_TEMPLATE_PATH,
        RUST_PRIMITIVE_TEMPLATE_PATH,
        PrimitiveTemplateRenderResult,
    )

    assert CPP_PRIMITIVE_TEMPLATE_PATH == "templates/cpp/primitive.hpp.in"
    assert RUST_PRIMITIVE_TEMPLATE_PATH == "templates/rust/primitive.rs.in"
    assert PrimitiveTemplateRenderResult.__name__ == "PrimitiveTemplateRenderResult"


def _root_with_cpp_template(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "templates" / "cpp" / "primitive.hpp.in"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return tmp_path
