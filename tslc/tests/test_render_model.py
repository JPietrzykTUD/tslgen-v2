"""Typed render values for lowered backend body text."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend import translation_common
from tslc.backend.cpp_profile_model import cpp_project_render_model
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.lower.lowerer import Lowerer
from tslc.target_text import (
    LiteralText,
    LoweredBody,
    RenderPlaceholder,
    RenderContext,
    TemplateApplication,
    TemplateRenderError,
    render_sequence,
    unsafe_block,
)
from tslc.select.selector import Selector

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BODY_TEXT_NAMES = frozenset({"body", "body_text"})


def test_lowered_body_default_render_preserves_rust_vector_owner() -> None:
    body = LoweredBody.from_text("return to_array::<Self>(data);")

    assert body.render() == "return to_array::<Self>(data);"


def test_lowered_body_context_renders_explicit_current_placeholders() -> None:
    body = LoweredBody.from_render_text(
        render_sequence(
            (
                "return reinterpret::<",
                RenderPlaceholder("current_vector", "Self"),
                ", ToVec>(data as ",
                RenderPlaceholder("current_register", "Self::RegisterType"),
                ");",
            )
        ),
    )

    rendered = body.render(
        RenderContext(
            current_vector="Simd<i32, Avx2>",
            current_register="core::arch::x86_64::__m256i",
            current_base="i32",
        )
    )

    assert rendered == (
        "return reinterpret::<Simd<i32, Avx2>, ToVec>"
        "(data as core::arch::x86_64::__m256i);"
    )


def test_lowered_body_context_renders_explicit_owner_placeholder() -> None:
    body = LoweredBody.from_render_text(
        render_sequence(
            (
                "return ",
                RenderPlaceholder("current_owner", "Self"),
                "::lane_count();",
            )
        )
    )

    assert body.render() == "return Self::lane_count();"
    assert body.render(RenderContext(current_owner="<Vec as SimdVector>")) == (
        "return <Vec as SimdVector>::lane_count();"
    )


def test_lowered_body_literal_text_is_not_rewritten_by_context() -> None:
    body = LoweredBody.from_text('return "~::<Self> Self::RegisterType";')

    assert body.render(RenderContext(current_vector="Vec")) == (
        'return "~::<Self> Self::RegisterType";'
    )


def test_backend_syntax_owns_local_and_body_unsafe_framing() -> None:
    class FakeSyntax:
        @staticmethod
        def render_unsafe_block(body: str) -> str:
            return f"guarded[{body}]"

    syntax = FakeSyntax()
    body = LoweredBody.from_render_text(
        render_sequence(("let value = ", unsafe_block("make_value()"), ";")),
        unsafe_block_renderer=syntax.render_unsafe_block,
    )

    assert body.render() == "let value = guarded[make_value()];"
    assert (
        LoweredBody.from_render_text(
            body.content,
            unsafe_block_renderer=syntax.render_unsafe_block,
            requires_unsafe=True,
        ).render()
        == "guarded[let value = make_value();]"
    )


def test_lowered_body_from_text_keeps_source_operator_literal() -> None:
    body = LoweredBody.from_text("return ~mask;")

    assert body.render() == "return ~mask;"


def test_rust_op_bit_negate_lowers_before_body_rendering(
    catalog: Catalog, machine_profiles
) -> None:
    selected = Selector().select_profile(
        catalog, machine_profiles["scalar"], "binary_andnot", ("si32",)
    ).selected
    slot = next(
        slot
        for slot in selected
        if slot.extension.name == "scalar" and slot.type_tag == "si32"
    )

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert rust is not None
    assert rust.body_text == "return (!left) & right;"


def test_raw_text_lowering_does_not_translate_bitwise_not_operator() -> None:
    text = (_REPO_ROOT / "tslc" / "src" / "tslc" / "lower" / "lowerer.py").read_text(
        encoding="utf-8"
    )

    assert "render_bitwise_not_operator" not in text
    assert 'char == "~"' not in text


def test_rust_syntax_dialect_renders_unsafe_wrapper(catalog: Catalog) -> None:
    syntax = create_backend_dialect(catalog, "rust").syntax
    body = LoweredBody.from_text(
        "*ptr = data;",
        unsafe_block_renderer=syntax.render_unsafe_block,
        requires_unsafe=True,
    )

    assert body.render() == "unsafe { *ptr = data; }"


def test_template_application_requires_all_placeholders() -> None:
    template = TemplateApplication("demo", "{value} {missing}", {"value": "ok"})

    with pytest.raises(TemplateRenderError, match="missing"):
        template.render()


def test_template_application_freezes_fields_and_placeholders() -> None:
    fields = {"value": "ok"}
    template = TemplateApplication("demo", "{value}", fields)

    fields["value"] = "{leaked}"

    assert template.placeholders == ("value",)
    assert template.render() == "ok"
    with pytest.raises(TypeError):
        template.fields["value"] = "changed"  # type: ignore[index]


def test_template_application_rejects_unresolved_field_values() -> None:
    template = TemplateApplication("demo", "{value}", {"value": LiteralText("{leaked}")})

    with pytest.raises(TemplateRenderError, match="unresolved"):
        template.render()


def test_template_application_preserves_literal_rust_const_braces() -> None:
    template = TemplateApplication(
        "aligned",
        "Aligned::<{ {align} }, [{type}; {size}]>",
        {"align": "32", "type": "i32", "size": "4"},
    )

    assert template.render() == "Aligned::<{ 32 }, [i32; 4]>"


def test_catalog_template_rendering_validates_fields(catalog: Catalog) -> None:
    rendered = translation_common.render_template(
        catalog,
        "rust",
        "array_type_aligned",
        type="i32",
        size="4",
        align="32",
    )
    assert rendered == "crate::tsl::Aligned::<{ 32 }, [i32; 4]>"

    with pytest.raises(TemplateRenderError, match="missing"):
        translation_common.render_template(catalog, "rust", "array_type_aligned", type="i32")


def test_backend_renderers_do_not_rewrite_body_text_semantics() -> None:
    checked = [
        _REPO_ROOT / "tslc" / "src" / "tslc" / "backend" / "cpp.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "backend" / "rust.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "backend" / "cpp_translation.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "backend" / "rust_translation.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "cpp_project.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "rust_project.py",
    ]

    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert "_concretize_simd_assoc" not in text
        assert _body_text_replace_calls(path, text) == []


def test_backend_dialects_do_not_classify_rendered_expression_text() -> None:
    # Semantics such as address-of-ness arrive as typed lowered facts
    # (PointerCastOperand); a dialect must not re-derive them by sniffing
    # rendered target text.
    for name in ("cpp_translation.py", "rust_translation.py"):
        path = _REPO_ROOT / "tslc" / "src" / "tslc" / "backend" / name
        text = path.read_text(encoding="utf-8")
        assert 'startswith("&' not in text, name


def test_fully_typed_lowering_boundaries_do_not_use_getattr() -> None:
    checked = (
        _REPO_ROOT / "tslc" / "src" / "tslc" / "lower" / "_query_leaf.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "pivot" / "planner.py",
    )
    offenders: list[str] = []
    for path in checked:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def _body_text_replace_calls(path: Path, text: str) -> list[str]:
    tree = ast.parse(text, filename=str(path))
    calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "replace":
            continue
        receiver_names = _expr_names(node.func.value)
        if receiver_names & _BODY_TEXT_NAMES:
            rel = path.relative_to(_REPO_ROOT)
            calls.append(f"{rel}:{node.lineno}: {ast.unparse(node).strip()}")
    return calls


def _expr_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def test_lowered_body_model_does_not_scan_for_semantic_spellings() -> None:
    text = (_REPO_ROOT / "tslc" / "src" / "tslc" / "target_text.py").read_text(
        encoding="utf-8"
    )

    assert "_rust_body_text" not in text
    assert "_rust_vector_placeholders" not in text
    assert "::<Self>" not in text
    assert "Self::RegisterType" not in text


def test_cpp_profile_render_model_decides_smoke_and_guard_facts(
    data_root: Path, machine_profiles_path: Path
) -> None:
    """Smoke instantiations and compile-guard grouping are backend-decided data."""

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "store"],
        profiles=["avx2", "sve", "sve512"],
    )
    model = cpp_project_render_model(result.emitted_profiles)
    by_name = {profile.profile_name: profile for profile in model.profiles}

    base = by_name["avx2"].base_header
    assert base.header_group is None
    assert base.includes is not None
    assert base.registrations

    templated = [entry for entry in base.smoke if entry.template_arguments]
    assert templated
    for entry in templated:
        assert entry.symbol.startswith("tsl::")
        assert entry.lane_count is not None
        assert entry.lane_count > 0
        assert all(argument for argument in entry.template_arguments)
    # Overload dispatch arguments arrive as concrete spellings, not kind tokens.
    assert any(
        argument.endswith("::register_type") or argument.endswith("::base_type")
        for entry in templated
        for argument in entry.template_arguments
    )
    # A LANES-parametric sized slot is exercised at the decided 16-lane count.
    sized = [
        entry
        for entry in by_name["sve"].base_header.smoke
        if entry.template_arguments and "<16>" in entry.template_arguments[0]
    ]
    assert sized
    assert all(entry.lane_count == 16 for entry in sized)

    # Definitions arrive pre-grouped under their availability condition.
    assert base.definition_groups
    for group in base.definition_groups:
        assert group.specializations
        assert group.condition is None or isinstance(group.condition, str)

    guard = by_name["sve512"].base_header.guard
    assert guard is not None
    assert "__ARM_FEATURE_SVE_BITS" in guard.condition
    assert guard.diagnostic


def test_cpp_project_renderer_formats_without_deciding_smoke_semantics() -> None:
    """render/cpp_project.py must not consult the support policy or type ladders."""

    source = (
        _REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "cpp_project.py"
    ).read_text(encoding="utf-8")

    assert "windowed_lane_count" not in source
    assert "DEFAULT_SUPPORT_POLICY" not in source
    assert "support_policy" not in source
    assert "_concrete_arg_type" not in source


def test_generated_artifacts_have_no_unresolved_template_placeholders(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "store"],
        profiles=["scalar", "avx2"],
    )

    unresolved = re.compile(r"\{(?:type|value|name|args|base|size|align|cond)\}")
    for artifact in result.artifacts.artifacts:
        assert unresolved.search(artifact.content) is None, artifact.logical_path
