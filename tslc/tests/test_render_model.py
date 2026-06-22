"""Typed render values for lowered backend body text."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend import translation_common
from tslc.backend.translation import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.lower.lowerer import Lowerer
from tslc.render.model import (
    LiteralText,
    LoweredBody,
    RenderPlaceholder,
    RenderContext,
    TemplateApplication,
    TemplateRenderError,
    render_sequence,
)
from tslc.select.selector import Selector

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_lowered_body_default_render_preserves_rust_vector_owner() -> None:
    body = LoweredBody.from_text(
        "return to_array::<Self>(data);",
        backend_id="rust",
    )

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
        backend_id="rust",
    )

    rendered = body.render(
        RenderContext(
            backend_id="rust",
            current_vector="Simd<i32, Avx2>",
            current_register="core::arch::x86_64::__m256i",
            current_base="i32",
        )
    )

    assert rendered == (
        "return reinterpret::<Simd<i32, Avx2>, ToVec>"
        "(data as core::arch::x86_64::__m256i);"
    )


def test_lowered_body_literal_text_is_not_rewritten_by_context() -> None:
    body = LoweredBody.from_text(
        'return "~::<Self> Self::RegisterType";',
        backend_id="rust",
    )

    assert body.render(RenderContext(backend_id="rust", current_vector="Vec")) == (
        'return "~::<Self> Self::RegisterType";'
    )


def test_lowered_body_from_text_keeps_source_operator_literal() -> None:
    body = LoweredBody.from_text("return ~mask;", backend_id="rust")

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


def test_lowered_body_renders_unsafe_wrapper() -> None:
    body = LoweredBody.from_text("*ptr = data;", backend_id="rust", requires_unsafe=True)

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
        _REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "cpp_project.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "rust_project.py",
    ]

    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert "_concretize_simd_assoc" not in text
        assert ".replace(" not in text


def test_lowered_body_model_does_not_scan_for_semantic_spellings() -> None:
    text = (_REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "model.py").read_text(
        encoding="utf-8"
    )

    assert "_rust_body_text" not in text
    assert "_rust_vector_placeholders" not in text
    assert "::<Self>" not in text
    assert "Self::RegisterType" not in text


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
