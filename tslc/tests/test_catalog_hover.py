"""Exact Markdown contracts for compiler-owned editor hover facts."""

from __future__ import annotations

from pathlib import Path
import subprocess

from lsprotocol import types
import pytest

from tslc.catalog.model import Catalog, Extension, ExtensionActivation, Primitive
from tslc.catalog_index import CatalogIndex, IndexedOccurrence, SymbolKind, _hover_text
from tslc.diagnostics import SourceSpan
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.lower.lowerer import Lowerer
from tslc.lsp.features import hover
from tslc.lsp.workspace import AuthoringWorkspace
from tslc.render import project as render_project_module
from tslc.select.selector import Selector


_REGION_FACTS = (
    (
        "intrin",
        "Invoke a target intrinsic.",
        (
            "intrin<name>(args)",
            "intrin<base, build>(args)",
            "intrin<base, build[modifier=value, ...]>(args)",
        ),
    ),
    (
        "helper",
        "Invoke a compiler-owned helper.",
        ("helper<name>(args)", "helper<name, template_arg, ...>(args)"),
    ),
    ("op", "Render a backend-specific operator.", ("op<name>(arg0, arg1, ...)",)),
    (
        "var",
        "Declare local storage.",
        (
            "var<infer>(name, value)",
            "var<const_infer>(name, value)",
            "var<typed>(type, name, value)",
            "var<const_typed>(type, name, value)",
            "var<runtime_array>(element_type, name, count)",
            "var<init_register>(name)",
            "var<const_init_register>(name)",
        ),
    ),
    ("let", "Bind a lowering-time type alias.", ("let<type>(Name, type_expression)",)),
    (
        "mask",
        "Construct or update a mask.",
        (
            "mask<lane_true>()",
            "mask<lane_false>()",
            "mask<none>()",
            "mask<all>()",
            "mask<test>(mask, index)",
            "mask<test, imask>(imask, index)",
            "mask<set>(mask, index)",
            "mask<clear>(mask, index)",
            "mask<set_to>(mask, index, value)",
        ),
    ),
    (
        "mem",
        "Perform raw byte-memory operations.",
        (
            "mem<copy>(dst, src, count)",
            "mem<set>(ptr, value, count)",
            "mem<alloc>(count)",
            "mem<alloc_aligned>(count, align)",
            "mem<free>(ptr)",
        ),
    ),
    (
        "lanes",
        "Read a generation-known lane-list element.",
        ("lanes<at>(lane_list_param, index)",),
    ),
    (
        "array",
        "Update backend-owned array storage.",
        ("array<set>(array, index, value)",),
    ),
    ("io", "Format vector output.", ("io<format>(out, array, modifier)",)),
    (
        "cast",
        "Render a backend-specific cast.",
        (
            "cast<variant>(type_expression, expr)",
            "cast<reinterpret, type=ptr>(type_expression, expr)",
            "cast<reinterpret, type=const_ptr>(type_expression, expr)",
        ),
    ),
    (
        "call",
        "Invoke a generated primitive wrapper.",
        (
            "call<primitive=name>(args)",
            "call<primitive=name[VecOrTypeArgs], attrs[key=value, ...]>(args)",
            "call<primitive=@self[...], attrs[key=value, ...]>(args)",
        ),
    ),
    (
        "if",
        "Select or emit a branch.",
        (
            "if(condition) { then_body } else { else_body }",
            "if<generation>(condition) { then_body } else<generation> { else_body }",
            "if<compile>(condition) { then_body } else<compile> { else_body }",
        ),
    ),
    (
        "select_expr",
        "Render an expression conditional.",
        ("select_expr(condition, if_true, if_false)",),
    ),
    (
        "assume_aligned",
        "Apply an alignment hint.",
        ("assume_aligned<alignment_expression>(ptr)",),
    ),
    (
        "loop",
        "Emit or expand a loop.",
        (
            "loop<backend>(var, start, end, step) { body }",
            "loop<backend, unroll>(var, start, end, step) { body }",
            "loop<generation>(var, start, end, step) { body }",
            "loop<generation, scoped>(var, start, end, step) { body }",
        ),
    ),
    (
        "switch",
        "Emit compile-time selection.",
        ("switch<compile>(selector) { label => { body } _ => { fallback_body } }",),
    ),
    ("type", "Splice a resolved type.", ("type(query)",)),
    ("value", "Splice a resolved value.", ("value(query)",)),
    ("complete", "Return the primitive result.", ("complete(expr)",)),
)


def _span(path: Path, line: int, column: int = 1) -> SourceSpan:
    return SourceSpan(path, line, column, line, column + 5)


def _uri(span: SourceSpan) -> str:
    return f"{span.path.resolve().as_uri()}#L{span.line},{span.column}"


def _catalog_and_definitions(
    tmp_path: Path,
) -> tuple[Catalog, dict[SymbolKind, dict[str, tuple[SourceSpan, ...]]]]:
    primitive_path = tmp_path / "primitives.tsl"
    extension_path = tmp_path / "extensions.tsl"
    types_path = tmp_path / "types.tsl"
    unary_source = _span(primitive_path, 2)
    binary_source = _span(primitive_path, 8)
    extension_source = _span(extension_path, 3)
    type_group_source = _span(types_path, 4, 3)
    catalog = Catalog(
        primitives=(
            Primitive(
                name="probe",
                signature="s:=v",
                parameters=("value",),
                attribute_keys=(),
                implementations=(),
                header_source=unary_source,
            ),
            Primitive(
                name="probe",
                signature="v:=(v,v)",
                parameters=("left", "right"),
                attribute_keys=(),
                implementations=(),
                brief_description="Combines corresponding lanes.",
                header_source=binary_source,
            ),
        ),
        type_groups={"numbers": ("si32", "ui32", "f32")},
        extensions={
            "wide": Extension(
                name="wide",
                isa_name="wide",
                family="test",
                compose_prefix={},
                compose_suffix_by_type={},
                backend_supported={"rust": False, "cpp": True},
                inherits="base",
                active_when=ExtensionActivation(
                    target_features=frozenset(("wide", "wide_vl")),
                    compile_modes=frozenset(("wide_mode",)),
                ),
                vector_bits=256,
                vector_bits_kind="fixed",
                source=extension_source,
            ),
            "minimal": Extension(
                name="minimal",
                isa_name="minimal",
                family="",
                compose_prefix={},
                compose_suffix_by_type={},
            ),
        },
        type_spellings={},
        translations={},
    )
    definitions = {
        "primitive": {"probe": (unary_source, binary_source)},
        "extension": {"wide": (extension_source,)},
        "type-group": {"numbers": (type_group_source,)},
        "region": {},
    }
    return catalog, definitions


def test_catalog_hover_markdown_contains_typed_facts_and_clean_omissions(
    tmp_path: Path,
) -> None:
    catalog, definitions = _catalog_and_definitions(tmp_path)
    values = _hover_text(catalog, definitions)
    primitive_path = tmp_path / "primitives.tsl"
    unary_source = _span(primitive_path, 2)
    binary_source = _span(primitive_path, 8)
    assert values[("primitive", "probe")] == "\n".join(
        (
            "**Primitive** `probe`",
            "",
            "**Declarations**",
            "",
            f"- `prim<s:=v> probe(value)` ([primitives.tsl:2]({_uri(unary_source)}))",
            "- `prim<v:=(v,v)> probe(left, right)` — Combines corresponding lanes. "
            f"([primitives.tsl:8]({_uri(binary_source)}))",
        )
    )

    extension_source = _span(tmp_path / "extensions.tsl", 3)
    assert values[("extension", "wide")] == "\n\n".join(
        (
            "**Extension** `wide`",
            "**Family:** `test`",
            "**Inherits:** `base`",
            "**Width:** 256 bits (`fixed`)",
            "**Supported backends:** `cpp`",
            "**Required target features:** `wide`, `wide_vl`",
            "**Required compile modes:** `wide_mode`",
            f"[Declaration: extensions.tsl:3]({_uri(extension_source)})",
        )
    )
    assert values[("extension", "minimal")] == "**Extension** `minimal`"

    type_group_source = _span(tmp_path / "types.tsl", 4, 3)
    assert values[("type-group", "numbers")] == "\n\n".join(
        (
            "**Type group** `numbers`",
            "`si32`, `ui32`, `f32`",
            f"**Declared at:** [types.tsl:4]({_uri(type_group_source)})",
        )
    )
    assert "None" not in "\n".join(values.values())


@pytest.mark.parametrize(("keyword", "purpose", "forms"), _REGION_FACTS)
def test_every_registered_region_has_exact_author_facing_hover(
    tmp_path: Path,
    keyword: str,
    purpose: str,
    forms: tuple[str, ...],
) -> None:
    catalog, definitions = _catalog_and_definitions(tmp_path)
    values = _hover_text(catalog, definitions)
    rendered_forms = "\n".join(f"- `{form}`" for form in forms)
    expected = "\n\n".join(
        (
            f"**TSIL region** `{keyword}`",
            purpose,
            f"**Accepted forms**\n\n{rendered_forms}",
            "[TSIL region guide](https://github.com/JPietrzykTUD/tslgen-v2/"
            f"blob/main/docs/tsil-keywords.md#{keyword})",
        )
    )

    assert tuple(item.keyword for item in DEFAULT_TSIL_REGION_DESCRIPTORS) == tuple(
        item[0] for item in _REGION_FACTS
    )
    assert values[("region", keyword)] == expected
    descriptor = next(
        item for item in DEFAULT_TSIL_REGION_DESCRIPTORS if item.keyword == keyword
    )
    if descriptor.shell_validator is not None and descriptor.shell_validator != keyword:
        assert descriptor.shell_validator not in expected


def test_hover_is_a_pure_projection_of_the_supplied_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_work(*args: object, **kwargs: object) -> None:
        raise AssertionError("hover started compiler or process work")

    monkeypatch.setattr(AuthoringWorkspace, "check", unexpected_work)
    monkeypatch.setattr(Selector, "select_profile", unexpected_work)
    monkeypatch.setattr(Lowerer, "lower", unexpected_work)
    monkeypatch.setattr(render_project_module, "render_project", unexpected_work)
    monkeypatch.setattr(subprocess, "run", unexpected_work)
    monkeypatch.setattr(subprocess, "Popen", unexpected_work)

    path = (tmp_path / "probe.tsl").resolve()
    occurrence = IndexedOccurrence(
        kind="primitive",
        name="probe",
        span=SourceSpan(path, 1, 1, 1, 6),
        definition=True,
    )
    index = CatalogIndex(
        occurrences_by_path={path: (occurrence,)},
        hover_text={("primitive", "probe"): "**Primitive** `probe`"},
    )

    result = hover(index, path, "probe", types.Position(line=0, character=1))

    assert result is not None
    assert isinstance(result.contents, types.MarkupContent)
    assert result.contents.value == "**Primitive** `probe`"
